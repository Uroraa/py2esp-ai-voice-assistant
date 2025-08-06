import socket
import re
from typing import List
from rapidfuzz import fuzz
#from gtts import gTTS
import asyncio
from edge_tts import Communicate
from pydub import AudioSegment
import time
from datetime import datetime 
import pytz
import speech_recognition as sr
import pvporcupine
import pyaudio
import struct
import google.generativeai as gen_ai
import os
from dotenv import load_dotenv
import contextlib
import sys
sys.stdout.reconfigure(encoding='utf-8')

ACTIONS = {
    "bật": 1,
    "mở": 1,
    "khởi động": 1,
    "kích hoạt": 1,
    "bắt đầu": 1,
    "tắt": 0,
    "đóng": 0,
    "dừng": 0,
    "ngưng": 0,
    "ngừng": 0
}
NEGATIONS = ["đừng", "không", "thôi", "chữa", "chưa"]
FUZZY_THRESHOLD = 80

# Detect command
def contain_action_word(text: str, candidates: List[str]) -> bool:
    for c in candidates:
        if re.search(rf"\b{re.escape(c)}\b", text):
            return True
    for c in candidates:
        if fuzz.partial_ratio(text, c) >= FUZZY_THRESHOLD:
            return True
    return False
def is_control_command(input_prompt: str) -> bool:
    p = input_prompt.lower()
    for neg in NEGATIONS:
        if re.search(rf"\b{re.escape(neg)}\b\s+\b({'|'.join(map(re.escape, ACTIONS))})\b", p):
            return False
    cmd = contain_action_word(p, ACTIONS)
    return cmd

# Configure UDP
UDP_IP   = '0.0.0.0'
ESP32_IP = ''
ESP32_PORT = 5005
MAX_PACKET_SIZE = 1024
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, ESP32_PORT))
sock.settimeout(15) 
try:
    data, addr = sock.recvfrom(MAX_PACKET_SIZE)
    print(f"Thiết bị {addr} đã sẵn sàng")
    ESP32_IP = addr[0]  # Cập nhật lại IP của ESP32 từ gói tin nhận được
except socket.timeout:
    print("Thiết bị chưa sẵn sàng, chuẩn bị gửi lệnh đầu tiên...")
    data, addr = None, None

# Configure API_KEY
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
    sound = sound.set_channels(1).set_frame_rate(16000)  
    louder = sound.high_pass_filter(200).normalize(headroom=0.5)
    louder.export(output_path, format="wav")
    return output_path
async def text_to_wav_bytes(text):
    esp_output = "esp32_ready.wav"
    communicate = Communicate(text, voice = "vi-VN-NamMinhNeural", volume= "+50%")
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

# Wake word detection
pa = pyaudio.PyAudio()
stream = pa.open(format=pyaudio.paInt16,
                 channels=1,
                 rate=porcupine.sample_rate,
                 input=True,
                 frames_per_buffer=porcupine.frame_length)

print("Đang chờ lệnh đánh thức...")

try:
    while True:
        pcm = stream.read(porcupine.frame_length, exception_on_overflow=False)
        pcm = struct.unpack_from("h" * porcupine.frame_length, pcm)

        result = porcupine.process(pcm)
        if result >= 0:
            print("Đã đánh thức!")

            recognizer = sr.Recognizer()
            mic = sr.Microphone()  

            print("Đang nghe...")
            welcome = "Chào bạn, tôi có thể giúp gì?"
            #if data == "READY":
            while True:
                try:               
                    with mic as source:
                        recognizer.adjust_for_ambient_noise(source, duration=1)
                        audio = recognizer.listen(source, phrase_time_limit=10)
                        prompt = recognizer.recognize_google(audio, language='vi-VN')
                        lower_text = prompt.lower()
                    if is_control_command(prompt):
                        print("Bạn đã nói lệnh:", prompt)
                        
                        for cmd, code in ACTIONS.items():
                            if re.search(rf"\b{re.escape(cmd)}\b", lower_text):
                                order = f"Đã {cmd}"
                                audio_bytes = asyncio.run(text_to_wav_bytes(order))
                                total_len = len(audio_bytes)
                                sock.sendto(b'\x02' + str(code).encode(), (ESP32_IP, ESP32_PORT))

                                # Gửi từng gói nhỏ
                                for i in range(0, total_len, MAX_PACKET_SIZE):
                                    chunk = audio_bytes[i:i + MAX_PACKET_SIZE]
                                    sock.sendto(b'\x03' + chunk, (ESP32_IP, ESP32_PORT))
                                    time.sleep(0.03)
                                print(f"Đã gửi lệnh {cmd} đến ESP32")
                                break
                            
                    else:
                        now = datetime.now(pytz.timezone("Asia/Ho_Chi_Minh")).strftime("%A, %d-%m-%Y %H:%M")
                        response = model.generate_content([
                            {"role": "user", "parts": [f"{prompt}\nPhản hồi ngắn gọn, dưới 1000 byte, chỉ ở dạng văn bản thường (plain text). Không sử dụng Markdown in đậm (**) hoặc in nghiêng (_), không tiêu đề (#). Chú ý thời gian hiện tại là {now}."]},
                        ])
                        reply = response.text

                        print("Bạn đã nói:", prompt)
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
                    print("Không nhận diện được")

                    errorReply = "Không nhận diện được giọng nói, vui lòng thử lại."
                    audio_bytes = asyncio.run(text_to_wav_bytes(errorReply))
                    total_len = len(audio_bytes)
                    sock.sendto(b'\x02' + errorReply.encode('utf-8'), (ESP32_IP, ESP32_PORT))
                    
                    # Gửi từng gói nhỏ
                    for i in range(0, total_len, MAX_PACKET_SIZE):
                        chunk = audio_bytes[i:i + MAX_PACKET_SIZE]
                        sock.sendto(b'\x03' + chunk, (ESP32_IP, ESP32_PORT))
                        time.sleep(0.03)
                except sr.RequestError as e:
                    print("Lỗi kết nối đến dịch vụ nhận diện giọng nói:", e)
                except KeyboardInterrupt:
                    print("Dừng chương trình")
                    break
            break

except KeyboardInterrupt:
    print("Dừng chương trình")
finally:
    with contextlib.suppress(Exception):
        sock.close()
    if stream is not None:
        with contextlib.suppress(Exception):
            stream.close()
    if porcupine is not None:
        with contextlib.suppress(Exception):
            porcupine.delete()