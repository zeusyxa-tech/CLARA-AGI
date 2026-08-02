"""
CLARA-AGI Voice mode — nói vào micro, nghe CLARA đáp lại qua loa.
PHỤ THUỘC TÙY CHỌN (không cài thì CLARA vẫn chạy CLI/Web bình thường):
  pip install openai-whisper piper-tts sounddevice soundfile numpy pyaudio

Nếu không cù đủ thư viện, bạn có thể dùng chế độ fallback:
  - STT fallback: dùng SpeechRecognition + Google (online, free, nhẹ)
  - TTS fallback: dùng pyttsx3 (offline, giọng máy mặc định)
"""
import sys, time


def _import_stt():
    try:
        import whisper
        model = whisper.load_model("tiny")  # ~70MB
        return "whisper", model
    except Exception:
        pass
    try:
        import speech_recognition as sr
        return "google", sr.Recognizer()
    except Exception:
        pass
    return None, None


def _import_tts():
    try:
        from piper import PiperVoice
        # cần model tiếng Việt — nếu chưa có, fallback
        import os
        model_path = os.path.expanduser("~/.clara/vi_voice.onnx")
        if not os.path.exists(model_path):
            print("ℹ️ Chưa có model Piper tiếng Việt, dùng pyttsx3.")
            raise ImportError
        voice = PiperVoice.load(model_path)
        return "piper", voice
    except Exception:
        pass
    try:
        import pyttsx3
        eng = pyttsx3.init()
        # cố gắng chọn giọng tiếng Việt
        try:
            for v in eng.getProperty("voices"):
                if "vietnam" in v.name.lower() or "vi" in v.id.lower():
                    eng.setProperty("voice", v.id); break
        except Exception: pass
        eng.setProperty("rate", 160)
        return "pyttsx3", eng
    except Exception:
        pass
    return None, None


class VoiceCLARA:
    def __init__(self, agi):
        self.agi = agi
        self.stt_name, self.stt = _import_stt()
        self.tts_name, self.tts = _import_tts()
        if not self.stt or not self.tts:
            print("❌ Không thể nạp voice module. Cài thêm thư viện:")
            print("   pip install SpeechRecognition pyaudio pyttsx3")
            print("   (hoặc tốt nhất: pip install openai-whisper piper-tts sounddevice soundfile)")
            sys.exit(1)
        print(f"   👂 STT: {self.stt_name}  ·  🗣️ TTS: {self.tts_name}")
        self._init_audio()

    def _init_audio(self):
        self.pa = None
        if self.stt_name == "google":
            import speech_recognition as sr
            self.sr = sr
            self.mic = sr.Microphone()
            with self.mic as source:
                self.stt.adjust_for_ambient_noise(source, duration=1)
        else:
            import sounddevice as sd
            import numpy as np
            self.sd = sd
            self.np = np

    def _listen_whisper(self, duration=6, fs=16000):
        print("🎙️ Đang nghe...")
        audio = self.sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype="float32")
        self.sd.wait()
        audio = audio.flatten()
        result = self.stt.transcribe(audio, language="vi", fp16=False)
        return (result.get("text") or "").strip()

    def _listen_google(self, timeout=8):
        print("🎙️ Đang nghe (Google STT)...")
        with self.mic as source:
            try:
                audio = self.stt.listen(source, timeout=timeout, phrase_time_limit=10)
                return self.stt.recognize_google(audio, language="vi-VN")
            except Exception as e:
                return ""

    def listen(self):
        if self.stt_name == "whisper":
            return self._listen_whisper()
        return self._listen_google()

    def speak(self, text):
        print(f"🗣️  {text}")
        if self.tts_name == "piper":
            # stream ra loa
            import sounddevice as sd
            import numpy as np
            stream = sd.OutputStream(samplerate=22050, channels=1, dtype="int16")
            stream.start()
            for audio_bytes in self.tts.synthesize_stream_raw(text):
                data = np.frombuffer(audio_bytes, dtype=np.int16)
                stream.write(data)
            stream.stop(); stream.close()
        else:
            self.tts.say(text)
            self.tts.runAndWait()

    def loop(self):
        self.speak(f"Xin chào, tôi là {self.agi.traits['name']}. Tôi đã sẵn sàng nói chuyện với bạn.")
        while True:
            input("⏺️  Nhấn Enter để nói (hoặc Ctrl+C để thoát)... ")
            try:
                t = self.listen()
            except KeyboardInterrupt:
                print("\n👋 Tạm biệt!"); break
            if not t:
                self.speak("Xin lỗi, tôi không nghe rõ.")
                continue
            print(f"👂 Bạn: {t}")
            reply = self.agi.chat(t)
            # cắt bỏ phần footer kĩ thuật cho đỡ thừa
            short = reply.split("\n\n⏱️")[0].strip()
            self.speak(short)
