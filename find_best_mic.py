"""
Record from each input device, check RMS, send loudest to Google STT.
SAY: 'hello testing one two three' during each 2s recording.
"""
import time, io, wave, numpy as np, sounddevice as sd

SR = 16_000
DURATION = 2
INPUT_DEVICES = [1, 2, 9, 10, 19, 27]  # known input devices from earlier scan

results = []
for dev_id in INPUT_DEVICES:
    try:
        devname = sd.query_devices(dev_id)["name"]
        print(f"\n[{dev_id}] {devname[:40]} — SAY 'HELLO LIA' NOW...")
        time.sleep(0.3)
        audio = sd.rec(DURATION*SR, samplerate=SR, channels=1, dtype="float32", device=dev_id)
        sd.wait()
        rms = float(np.sqrt(np.mean(audio**2)))
        peak = float(np.max(np.abs(audio)))
        bar = "█" * int(rms * 200)
        print(f"    RMS={rms:.4f}  Peak={peak:.4f}  {bar}")
        results.append((rms, dev_id, devname, audio[:,0].copy()))
    except Exception as e:
        print(f"[{dev_id}] ERROR: {e}")

results.sort(reverse=True)
print("\n=== Results (highest RMS first) ===")
for rms, dev_id, name, _ in results:
    print(f"  [{dev_id:2d}] {name[:40]:<40} RMS={rms:.4f}")

if results:
    best_rms, best_id, best_name, best_audio = results[0]
    print(f"\n✅ Best mic: [{best_id}] {best_name} (RMS={best_rms:.4f})")
    print(f"Add to .env: MICROPHONE_DEVICE={best_id}")

    # Try Google STT with best mic
    import speech_recognition as sr
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR)
        wf.writeframes((best_audio*32767).astype(np.int16).tobytes())
    audio_data = sr.AudioData(buf.getvalue(), SR, 2)
    r = sr.Recognizer()
    try:
        text = r.recognize_google(audio_data, language="en-IN")
        print(f"Google STT result: '{text}'")
    except sr.UnknownValueError:
        print("Google STT: could not understand (speak louder next time)")
    except Exception as e:
        print(f"Google STT error: {e}")
