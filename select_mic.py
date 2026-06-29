"""
Test each input device and measure its noise floor.
The correct mic should have the LOWEST noise floor when silent.
Run: python select_mic.py
"""
import time, numpy as np, sounddevice as sd

SAMPLE_RATE = 16_000
TEST_SECS   = 1.5

devices = sd.query_devices()
input_devs = [(i, d) for i, d in enumerate(devices) if d["max_input_channels"] > 0]

print(f"Testing {len(input_devs)} input devices — stay SILENT\n")
results = []

for idx, dev in input_devs:
    try:
        audio = sd.rec(
            int(TEST_SECS * SAMPLE_RATE),
            samplerate=SAMPLE_RATE, channels=1,
            dtype="float32", device=idx,
        )
        sd.wait()
        rms  = float(np.sqrt(np.mean(audio**2)))
        peak = float(np.max(np.abs(audio)))
        results.append((rms, idx, dev["name"]))
        bar = "█" * min(40, int(rms * 200))
        print(f"  [{idx:2d}] {dev['name'][:40]:<40}  RMS={rms:.4f}  {bar}")
    except Exception as e:
        print(f"  [{idx:2d}] {dev['name'][:40]:<40}  ERROR: {e}")

print()
results.sort()
best_rms, best_idx, best_name = results[0]
print(f"✅ Lowest noise floor: [{best_idx}] {best_name}  (RMS={best_rms:.4f})")
print(f"\nAdd this to your .env:")
print(f"  MICROPHONE_DEVICE={best_idx}")
