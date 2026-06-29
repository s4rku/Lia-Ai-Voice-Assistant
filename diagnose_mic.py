"""
Diagnose microphone + VAD.
Listens for 8 seconds and prints RMS every 100ms so we can
see the exact level while speaking vs silence.
Run: python diagnose_mic.py
"""
import time
import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16_000
CHUNK_MS    = 100
CHUNK_SIZE  = int(SAMPLE_RATE * CHUNK_MS / 1000)
DURATION_S  = 8

THRESHOLD   = 0.015   # current VAD threshold

print(f"Listening for {DURATION_S}s — SAY 'HEY LIA' after 1 second")
print(f"Current VAD threshold: {THRESHOLD}")
print("-" * 50)

samples_collected = 0
speech_frames = 0

def callback(indata, frames, time_info, status):
    global samples_collected, speech_frames
    chunk = indata[:, 0]
    rms   = float(np.sqrt(np.mean(chunk ** 2)))
    peak  = float(np.max(np.abs(chunk)))
    is_speech = rms >= THRESHOLD
    bar   = "█" * int(rms * 400)
    flag  = "🎤 SPEECH" if is_speech else "       "
    print(f"  RMS={rms:.4f}  Peak={peak:.4f}  {bar:<30} {flag}")
    if is_speech:
        speech_frames += 1
    samples_collected += 1

with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                    dtype="float32", blocksize=CHUNK_SIZE,
                    callback=callback):
    time.sleep(DURATION_S)

print("-" * 50)
print(f"Speech frames detected: {speech_frames}/{samples_collected}")
if speech_frames == 0:
    print("⚠️  No speech detected at threshold 0.015")
    print("   → Try lowering VAD_ENERGY_THRESHOLD in .env (e.g. 0.005)")
elif speech_frames < 5:
    print("⚠️  Very few speech frames — threshold may be too high")
    print("   → Try lowering VAD_ENERGY_THRESHOLD in .env (e.g. 0.008)")
else:
    print("✅ VAD should work — threshold looks correct")
