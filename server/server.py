import socket
from gtts import gTTS
import asyncio
from edge_tts import Communicate
from pydub import AudioSegment
import time
import speech_recognition as sr
import pvporcupine
import pyaudio
import struct
import google.generativeai as gen_ai
import os
from dotenv import load_dotenv
import sys
sys.stdout.reconfigure(encoding='utf-8')

# Cấu hình UDP
ESP32_IP   = '192.168.39.78'   # IP ESP32
ESP32_PORT = 5005
MAX_PACKET_SIZE = 1024
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

load_dotenv()  
API_KEY = os.getenv("GOOGLE_API_KEY")
gen_ai.configure(api_key=API_KEY)
model = gen_ai.GenerativeModel("gemini-2.5-flash-lite")

access_key = "FpoCjJic8WNWbTsJssh63tI5cG3yfe84hDGoN7vFS850koUZKfDRQA=="
porcupine = pvporcupine.create(
    access_key=access_key,
    keyword_paths=["C:\\Users\\Admin\\Downloads\\hey-green_en_windows_v3_0_0.ppn"],
    sensitivities=[0.9]
)

# ---------- Text-to-Speech (TTS) ----------
def covert_wav(input_path = "temp.wav", output_path = "output.wav"):
    sound = AudioSegment.from_file(input_path)
    sound = sound.set_channels(1).set_frame_rate(16000)  # phù hợp cho ESP32 I2S mono, 16kHz
    louder = sound.high_pass_filter(150).normalize(headroom=0.5)
    louder.export(output_path, format="wav")
    return output_path

async def text_to_wav_bytes(text):
    esp_output = "esp32_ready.wav"
    communicate = Communicate(text, voice = "vi-VN-NamMinhNeural", volume= "+30%")
    await communicate.save("temp.wav")
    covert_wav(input_path="temp.wav", output_path=esp_output)

    with open(esp_output, "rb") as f:
        return f.read()
    
'''def text_to_wav_bytes(text):
    tts = gTTS(text=text, lang='vi')
    tts.save("temp.mp3")

    sound = AudioSegment.from_mp3("temp.mp3")
    sound = sound.set_channels(1).set_frame_rate(16000)  # phù hợp cho ESP32 I2S mono, 16kHz
    louder = sound.high_pass_filter(150).normalize(headroom=0.5)
    louder.export("temp.wav", format="wav")

    with open("temp.wav", "rb") as f:
        return f.read()'''

def is_control_command(prompt: str) -> bool:
    prompt = prompt.lower()
    keywords = ["bật", "tắt", "mở", "đóng"]
    return any(k in prompt for k in keywords)


pa = pyaudio.PyAudio()
stream = pa.open(format=pyaudio.paInt16,
                 channels=1,
                 rate=porcupine.sample_rate,
                 input=True,
                 frames_per_buffer=porcupine.frame_length)

print("Đang chờ lệnh đánh thức...")

while True:
    pcm = stream.read(porcupine.frame_length, exception_on_overflow=False)
    pcm = struct.unpack_from("h" * porcupine.frame_length, pcm)

    result = porcupine.process(pcm)
    if result >= 0:
        print("Đã đánh thức!")

        recognizer = sr.Recognizer()
        mic = sr.Microphone()  

        print("Đang nghe...")

        while True:
            with mic as source:
                recognizer.adjust_for_ambient_noise(source, duration=1)
                audio = recognizer.listen(source, phrase_time_limit=10)
                try:
                    prompt = recognizer.recognize_google(audio, language='vi-VN')
                    if is_control_command(prompt):
                        print("Bạn đã nói lệnh:", prompt)
                        audio_bytes = asyncio.run(text_to_wav_bytes(prompt))
                        total_len = len(audio_bytes)
                        sock.sendto(b'\x02' + prompt.encode('utf-8'), (ESP32_IP, ESP32_PORT))
                        # Gửi từng gói nhỏ
                        for i in range(0, total_len, MAX_PACKET_SIZE):
                            chunk = audio_bytes[i:i + MAX_PACKET_SIZE]
                            sock.sendto(b'\x03' + chunk, (ESP32_IP, ESP32_PORT))
                            time.sleep(0.03)

                        lower_text = prompt.lower()
                        if "bật" in lower_text:
                            order = "Đã bật"
                            audio_bytes = asyncio.run(text_to_wav_bytes(order))
                            total_len = len(audio_bytes)
                            sock.sendto(b'\x02' + b"1", (ESP32_IP, ESP32_PORT))
                            # Gửi từng gói nhỏ
                            for i in range(0, total_len, MAX_PACKET_SIZE):
                                chunk = audio_bytes[i:i + MAX_PACKET_SIZE]
                                sock.sendto(b'\x03' + chunk, (ESP32_IP, ESP32_PORT))
                                time.sleep(0.03)
                            print("Đã gửi lệnh bật đến ESP32")

                        elif "tắt" in lower_text:
                            order = "Đã tắt"
                            audio_bytes = asyncio.run(text_to_wav_bytes(order))
                            total_len = len(audio_bytes)
                            sock.sendto(b'\x02' + b"0", (ESP32_IP, ESP32_PORT))
                            # Gửi từng gói nhỏ
                            for i in range(0, total_len, MAX_PACKET_SIZE):
                                chunk = audio_bytes[i:i + MAX_PACKET_SIZE]
                                sock.sendto(b'\x03' + chunk, (ESP32_IP, ESP32_PORT))
                                time.sleep(0.03)
                            print("Đã gửi lệnh tắt đến ESP32")

                        else:
                            print("Lệnh không hợp lệ")
                    else:
                        response = model.generate_content([
                            {"role": "user", "parts": [f"{prompt}\nPhản hồi ngắn gọn, dưới 1000 byte, chỉ ở dạng văn bản thường (plain text). Không sử dụng Markdown in đậm (**) hoặc in nghiêng (_), không tiêu đề (#)."]}
                        ])

                        reply = response.text

                        print("Bạn đã nói:", prompt)
                        audio_bytes = asyncio.run(text_to_wav_bytes(prompt))
                        total_len = len(audio_bytes)
                        sock.sendto(b'\x02' + prompt.encode('utf-8'), (ESP32_IP, ESP32_PORT))
                        # Gửi từng gói nhỏ
                        for i in range(0, total_len, MAX_PACKET_SIZE):
                            chunk = audio_bytes[i:i + MAX_PACKET_SIZE]
                            sock.sendto(b'\x03' + chunk, (ESP32_IP, ESP32_PORT))
                            time.sleep(0.03)

                        print(reply)
                        audio_bytes = asyncio.run(text_to_wav_bytes(reply))
                        total_len = len(audio_bytes)
                        sock.sendto(b'\x02' + reply.encode('utf-8'), (ESP32_IP, ESP32_PORT))
                        # Gửi từng gói nhỏ
                        for i in range(0, total_len, MAX_PACKET_SIZE):
                            chunk = audio_bytes[i:i + MAX_PACKET_SIZE]
                            sock.sendto(b'\x03' + chunk, (ESP32_IP, ESP32_PORT))
                            time.sleep(0.03)

                except sr.UnknownValueError:
                    print("Không nhận diện được giọng nói")
                except sr.RequestError as e:
                    print("Lỗi kết nối đến dịch vụ nhận diện giọng nói:", e)
                except KeyboardInterrupt:
                    print("Dừng chương trình")
                
                '''finally:
                    if stream is not None:
                        stream.close()
                    if porcupine is not None:
                        porcupine.delete()'''