"""
Record 4 seconds and send to Google STT — say HEY LIA after 1s.
"""
import time, io, wave, numpy as np, sounddevice as sd, speech_recognition as sr

SR = 16_000
DEVICE = 10
print("Recording 4s on device 10 (Headset) — say HEY LIA WHAT TIME IS IT")
time.sleep(0.5)
audio = sd.rec(4*SR, samplerate=SR, channels=1, dtype="float32", device=DEVICE)
sd.wait()
print(f"Recorded. RMS={float(np.sqrt(np.mean(audio**2))):.4f}")

# WAV
buf = io.BytesIO()
with wave.open(buf, "wb") as wf:
    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR)
    wf.writeframes((audio[:,0]*32767).astype(np.int16).tobytes())
wav_bytes = buf.getvalue()

r = sr.Recognizer()
audio_data = sr.AudioData(wav_bytes, SR, 2)
print("Sending to Google STT...")
try:
    result = r.recognize_google(audio_data, language="en-IN")
    print(f"✅ Result: '{result}'")
except sr.UnknownValueError:
    print("❌ Google could not understand audio")
    print("   Try: speaking louder, closer to mic, or adjusting VAD")
except Exception as e:
    print(f"❌ Error: {e}")
