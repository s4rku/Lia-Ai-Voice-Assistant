"""
Quick mic test – records 3 seconds, saves to test_recording.wav, plays back RMS level.
Run: python check_mic.py
"""
import sounddevice as sd
import numpy as np
import wave, struct

DURATION = 3
SAMPLE_RATE = 16000
print(f"Recording {DURATION}s from default microphone… speak now!")

audio = sd.rec(int(DURATION * SAMPLE_RATE), samplerate=SAMPLE_RATE,
               channels=1, dtype="float32")
sd.wait()

rms = float(np.sqrt(np.mean(audio**2)))
peak = float(np.max(np.abs(audio)))
print(f"Done.  RMS={rms:.5f}  Peak={peak:.5f}")

if rms < 0.001:
    print("⚠️  Very low level – mic may be muted or wrong device selected.")
else:
    print("✅ Audio captured successfully!")

# Save wav
path = "test_recording.wav"
with wave.open(path, "w") as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(SAMPLE_RATE)
    pcm = (audio * 32767).astype(np.int16)
    wf.writeframes(pcm.tobytes())
print(f"Saved: {path}")
