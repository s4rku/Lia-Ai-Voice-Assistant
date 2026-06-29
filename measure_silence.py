"""
Measure background noise floor — stay SILENT for 3 seconds.
Run: python measure_silence.py
"""
import time, numpy as np, sounddevice as sd

SAMPLE_RATE = 16_000
CHUNK_MS = 100
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_MS / 1000)

print("Stay COMPLETELY SILENT for 3 seconds...")
time.sleep(1)
print("Measuring now...")

rms_values = []

def cb(indata, frames, t, status):
    rms_values.append(float(np.sqrt(np.mean(indata[:,0]**2))))

with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                    dtype="float32", blocksize=CHUNK_SIZE, callback=cb):
    time.sleep(3)

avg = float(np.mean(rms_values))
p95 = float(np.percentile(rms_values, 95))
mx  = float(np.max(rms_values))

print(f"\nSilence noise floor:")
print(f"  Average RMS : {avg:.5f}")
print(f"  95th pct RMS: {p95:.5f}")
print(f"  Max RMS     : {mx:.5f}")
print(f"\nRecommended settings:")
print(f"  speech_ratio = 3.0  →  speech threshold ≈ {p95*3.0:.4f}")
print(f"  speech_ratio = 4.0  →  speech threshold ≈ {p95*4.0:.4f}")
print(f"\nAdd to .env:")
print(f"  VAD_ENERGY_THRESHOLD={avg:.4f}")
print(f"  VAD_SPEECH_RATIO=3.0")
