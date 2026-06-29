"""
Test the adaptive EnergyVAD with real microphone input.
Run: python diagnose_vad.py
Speak after 1s, then stay quiet, then speak again.
Should show SPEECH_START and SPEECH_END events.
"""
import asyncio
import sys
sys.path.insert(0, '.')

import numpy as np
import sounddevice as sd

SAMPLE_RATE  = 16_000
CHUNK_MS     = 30
CHUNK_FRAMES = int(SAMPLE_RATE * CHUNK_MS / 1000)
TEST_SECS    = 10

async def main():
    from assistant.audio.vad import EnergyVAD, Utterance
    from assistant.config import settings

    vad = EnergyVAD(speech_ratio=3.5)

    utterances_heard = []

    async def on_speech_end(event):
        utt: Utterance = event.data
        dur = len(utt.audio) / utt.sample_rate
        utterances_heard.append(dur)
        print(f"\n  ✅ UTTERANCE READY: {dur:.2f}s of audio → sending to STT\n")

    async def on_speech_start(event):
        print("  🎤 Speech started…", flush=True)

    from assistant.core.events import bus, EventType
    bus.subscribe(EventType.SPEECH_START, on_speech_start)
    bus.subscribe(EventType.SPEECH_END, on_speech_end)

    from assistant.audio.microphone import AudioFrame

    print(f"Adaptive VAD test — {TEST_SECS}s")
    print("1-2s: be QUIET (noise floor calibration)")
    print("3-6s: say 'HEY LIA WHAT TIME IS IT'")
    print("7-8s: be QUIET")
    print("9-10s: say 'HEY LIA'")
    print("-" * 50)

    loop = asyncio.get_running_loop()
    q: asyncio.Queue = asyncio.Queue()

    def sd_callback(indata, frames, time_info, status):
        loop.call_soon_threadsafe(q.put_nowait, indata[:, 0].copy())

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE, channels=1, dtype="float32",
        blocksize=CHUNK_FRAMES, callback=sd_callback,
    )
    stream.start()

    t = 0
    while t < TEST_SECS * 1000 / CHUNK_MS:
        chunk = await q.get()
        frame = AudioFrame(data=chunk, sample_rate=SAMPLE_RATE)
        await vad.process_frame(frame)
        t += 1

    stream.stop()
    stream.close()

    print("-" * 50)
    print(f"Utterances detected: {len(utterances_heard)}")
    if utterances_heard:
        print(f"  Durations: {[f'{d:.2f}s' for d in utterances_heard]}")
        print("✅ VAD is working correctly!")
    else:
        print("❌ No utterances detected. Check noise_floor vs speech level.")
        print(f"   Current noise_floor estimate: {vad._noise_floor:.4f}")
        print(f"   Speech threshold: {max(0.015, vad._noise_floor * 3.5):.4f}")

asyncio.run(main())
