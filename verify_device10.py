"""
Verify device 10 (Headset) — record 4s, print RMS per 200ms window.
First 2s stay silent, last 2s say HEY LIA.
"""
import time, numpy as np, sounddevice as sd

SR, CHUNK = 16_000, int(16_000 * 0.2)  # 200ms chunks
DEVICE = 10

print(f"Device 10: {sd.query_devices(DEVICE)['name']}")
print("SILENT for 2s then say HEY LIA...")

chunks = []
def cb(indata, frames, t, status):
    chunks.append(indata[:,0].copy())

with sd.InputStream(samplerate=SR, channels=1, dtype="float32",
                    blocksize=CHUNK, device=DEVICE, callback=cb):
    time.sleep(4)

for i, c in enumerate(chunks):
    rms = float(np.sqrt(np.mean(c**2)))
    bar = "█" * int(rms * 300)
    phase = "silent" if i < 10 else "speech"
    print(f"  {phase} RMS={rms:.4f}  {bar}")

silence_rms = [float(np.sqrt(np.mean(c**2))) for c in chunks[:10]]
speech_rms  = [float(np.sqrt(np.mean(c**2))) for c in chunks[10:]]
avg_sil = np.mean(silence_rms)
avg_spk = np.mean(speech_rms) if speech_rms else 0
print(f"\nAvg silence RMS: {avg_sil:.4f}")
print(f"Avg speech  RMS: {avg_spk:.4f}")
if avg_spk > avg_sil * 2:
    ratio = avg_spk / max(avg_sil, 0.0001)
    print(f"✅ Good separation (ratio {ratio:.1f}x) — VAD will work!")
    print(f"   Recommended VAD_SPEECH_RATIO=2.5 in .env")
else:
    print("⚠️  Low separation — try speaking louder or closer to mic")
