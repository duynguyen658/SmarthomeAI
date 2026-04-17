import asyncio
import struct
import pyaudio
import pvporcupine
import speech_recognition as sr
# from gtts import gTTS
import edge_tts
import uuid
import pygame
import os
import sys
import requests  
from dotenv import load_dotenv

load_dotenv()  
# import aiohttp
# import concurrent.futures

# Lấy API key từ environment variable
PICOVOICE_ACCESS_KEY = os.getenv("PICOVOICE_ACCESS_KEY", "")

VOICE_NAME = "vi-VN-HoaiMyNeural"
API_URL = "http://localhost:8000/api/chat"

async def speak(text):
    """
    Chuyển văn bản thành giọng nói dùng Edge-TTS và phát ngay lập tức.
    """
    if not text: 
        return
    
    print(f"[BOT nói]: {text}")
    filename = f"voice_{uuid.uuid4().hex}.mp3"
    try:
        communicate = edge_tts.Communicate(text, VOICE_NAME)
        await communicate.save(filename)
        pygame.mixer.init()
        pygame.mixer.music.load(filename)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            await asyncio.sleep(0.1)
        pygame.mixer.quit()
    except Exception as e:
        print(f"Lỗi Edge-TTS: {e}")
    finally:
        if os.path.exists(filename):
            try:
                os.remove(filename)
            except PermissionError:
                print(f"Không thể xóa file {filename} (đang được sử dụng)")
            except Exception:
                pass
async def listen_command():
    """Lắng nghe câu lệnh sau khi đã đánh thức"""
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("\n>>> ĐANG NGHE LỆNH... (Mời bạn nói)")
        # Lọc tiếng ồn môi trường
        recognizer.adjust_for_ambient_noise(source, duration=0.4)
        try:
            audio = recognizer.listen(source, timeout=10, phrase_time_limit=15)
            print(">>> ĐANG DỊCH GIỌNG NÓI...")
            
            text = recognizer.recognize_google(audio, language="vi-VN")
            print(f"[BẠN NÓI]: {text}")
            return text   
        except sr.WaitTimeoutError:
            print("--- Hết giờ, không nghe thấy gì ---")
            return None
        except sr.UnknownValueError:
            print("--- Không nghe rõ ---")
            return None
        except Exception as e:
            print(f"Lỗi Mic: {e}")
            return None
#Tiếng beep 
def play_beep():
    try:
        pygame.mixer.init()
        pygame.mixer.music.load("./sounds/google_home_beep.wav")
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
        pygame.mixer.quit()
    except Exception as e:
        print(f"Lỗi phát beep: {e}")
# --- VÒNG LẶP CHÍNH (MAIN LOOP) ---
async def main():
    try:
        porcupine = pvporcupine.create(access_key=PICOVOICE_ACCESS_KEY, keyword_paths=[r"./keywword/hey-home_en_windows_v3_0_0.ppn"])
        print("Wake word 'hey-home' loaded")
    except Exception as e:
        print(f"\nLỖI KHI KHỞI TẠO PICOVOICE: {e}")
        return
    pa = pyaudio.PyAudio()
    audio_stream = pa.open(
        rate=porcupine.sample_rate,
        channels=1,
        format=pyaudio.paInt16,
        input=True,
        frames_per_buffer=porcupine.frame_length
    )

    print("-" * 50)
    print("HỆ THỐNG SẴN SÀNG! Hãy nói 'hey home' để ra lệnh.")
    print("-" * 50)
    try:
        while True:
    
            pcm = audio_stream.read(porcupine.frame_length, exception_on_overflow=False)
            pcm = struct.unpack_from("h" * porcupine.frame_length, pcm)
            keyword_index = porcupine.process(pcm)

            if keyword_index >= 0:
                print("\n[WAKE WORD] Đã phát hiện 'HEY HOME'!")
                play_beep()
                while True: 
                    user_text = await listen_command()
                    if not user_text:
                        print(">>> (Kết thúc hội thoại do im lặng)")
                        break 
                    try:
                        print(f">>> Gửi lệnh: {user_text}")
                        payload = {
                        "query": user_text,
                        "user_id": "client_voice",
                        "session_id": "session_voice_0101"
                        }

                        response = requests.post(API_URL, json=payload)
                        
                        if response.status_code == 200:
                            data = response.json()
                            bot_reply = data.get("response", "Xin lỗi, tôi không hiểu.")
                            await speak(bot_reply)
                            print(">>> Đang lắng nghe câu tiếp theo...")
                        else:
                            await speak("Lỗi kết nối Server.")
                            break 

                    except Exception as e:
                        print(f"Lỗi: {e}")
                        break
    except KeyboardInterrupt:
        print("\nĐang dừng hệ thống...")
    finally:
        if porcupine: porcupine.delete()
        if audio_stream: audio_stream.close()
        if pa: pa.terminate()

if __name__ == "__main__":
    asyncio.run(main())
