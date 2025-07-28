# py2esp-ai-voice-assistant

A simple AI voice assistant system using Python server + ESP32 client.  
The ESP32 receives voice commands processed on a PC (python server) and plays back AI responses via audio over I2S.

## 🧠 Features

- 🎙️ Keyword detection (wakeword) using [Picovoice Porcupine](https://github.com/Picovoice/porcupine)
- 🗣️ Voice-to-text (STT) using speech_recognition
- 🤖 AI response from Gemini
- 🔊 Text-to-speech (TTS) with gTTS
- 📶 Audio streaming via UDP from PC → ESP32S3 n16r8
- 🔈 Playback on MAX98357A speaker module using I2S

# Updating...