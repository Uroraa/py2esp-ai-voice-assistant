import sounddevice as sd
import numpy as np
import socket
from gtts import gTTS
from pydub import AudioSegment
import time
import wave
import io
import numpy as np
import speech_recognition as sr
import pvporcupine
import pyaudio
import struct
import google.generativeai as gen_ai
import sys
sys.stdout.reconfigure(encoding='utf-8')

# Cấu hình UDP
ESP32_IP   = '192.168.37.108'   # Đổi thành IP ESP32 của bạn
ESP32_PORT = 5005
MAX_PACKET_SIZE = 1024
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

gen_ai.configure(api_key="AIzaSyB4De60bhnM7anDuBmygcpWnbmTe-uSzY8")
model = gen_ai.GenerativeModel("gemini-2.5-flash-lite")

access_key = "FpoCjJic8WNWbTsJssh63tI5cG3yfe84hDGoN7vFS850koUZKfDRQA=="
porcupine = pvporcupine.create(
    access_key=access_key,
    keyword_paths=["C:\\Users\\Admin\\Downloads\\hey-green_en_windows_v3_0_0.ppn"],
    sensitivities=[0.9]
)

# ---------- Text-to-Speech (TTS) ----------
def text_to_wav_bytes(text):
    tts = gTTS(text=text, lang='vi')
    tts.save("temp.mp3")

    sound = AudioSegment.from_mp3("temp.mp3")
    sound = sound.set_channels(1).set_frame_rate(16000)  # phù hợp cho ESP32 I2S mono, 16kHz
    louder = sound.high_pass_filter(200).normalize(headroom=0.2)
    louder.export("temp.wav", format="wav")

    with open("temp.wav", "rb") as f:
        return f.read()

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
                audio = recognizer.listen(source, phrase_time_limit=4)
                try:
                    prompt = recognizer.recognize_google(audio, language='vi-VN')
                    if is_control_command(prompt):
                        print("Bạn đã nói lệnh:", prompt)
                        audio_bytes = text_to_wav_bytes(prompt)
                        sock.sendto(b'\x02' + prompt.encode('utf-8'), (ESP32_IP, ESP32_PORT))

                        total_len = len(audio_bytes)
                        # Gửi từng gói nhỏ
                        for i in range(0, total_len, MAX_PACKET_SIZE):
                            chunk = audio_bytes[i:i + MAX_PACKET_SIZE]
                            sock.sendto(b'\x03' + chunk, (ESP32_IP, ESP32_PORT))
                            time.sleep(0.01)

                        lower_text = prompt.lower()
                        if "bật" in lower_text:
                            order = "Bật đèn"
                            audio_bytes = text_to_wav_bytes(order)
                            total_len = len(audio_bytes)
                            sock.sendto(b'\x02' + b"1", (ESP32_IP, ESP32_PORT))
                            # Gửi từng gói nhỏ
                            for i in range(0, total_len, MAX_PACKET_SIZE):
                                chunk = audio_bytes[i:i + MAX_PACKET_SIZE]
                                sock.sendto(b'\x03' + chunk, (ESP32_IP, ESP32_PORT))
                                time.sleep(0.01)
                            print("Đã gửi lệnh bật đến ESP32")

                        elif "tắt" in lower_text:
                            order = "Tắt đèn"
                            audio_bytes = text_to_wav_bytes(order)
                            total_len = len(audio_bytes)
                            sock.sendto(b'\x02' + b"0", (ESP32_IP, ESP32_PORT))
                            # Gửi từng gói nhỏ
                            for i in range(0, total_len, MAX_PACKET_SIZE):
                                chunk = audio_bytes[i:i + MAX_PACKET_SIZE]
                                sock.sendto(b'\x03' + chunk, (ESP32_IP, ESP32_PORT))
                                time.sleep(0.01)
                            print("Đã gửi lệnh tắt đến ESP32")

                        else:
                            print("Lệnh không hợp lệ")
                    else:
                        response = model.generate_content([
                            {"role": "user", "parts": [f"{prompt}\nPhản hồi ngắn gọn, dưới 1000 byte."]}
                        ])

                        reply = response.text

                        print("Bạn đã nói lệnh:", prompt)
                        audio_bytes = text_to_wav_bytes(prompt)
                        total_len = len(audio_bytes)
                        sock.sendto(b'\x02' + prompt.encode('utf-8'), (ESP32_IP, ESP32_PORT))
                        # Gửi từng gói nhỏ
                        for i in range(0, total_len, MAX_PACKET_SIZE):
                            chunk = audio_bytes[i:i + MAX_PACKET_SIZE]
                            sock.sendto(b'\x03' + chunk, (ESP32_IP, ESP32_PORT))
                            time.sleep(0.01)

                        print(reply)
                        audio_bytes = text_to_wav_bytes(reply)
                        total_len = len(audio_bytes)
                        sock.sendto(b'\x02' + reply.encode('utf-8'), (ESP32_IP, ESP32_PORT))
                        # Gửi từng gói nhỏ
                        for i in range(0, total_len, MAX_PACKET_SIZE):
                            chunk = audio_bytes[i:i + MAX_PACKET_SIZE]
                            sock.sendto(b'\x03' + chunk, (ESP32_IP, ESP32_PORT))
                            time.sleep(0.01)

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