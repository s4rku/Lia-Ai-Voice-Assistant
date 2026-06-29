"""Quick test of the new MicrophoneStream with device 1."""
import asyncio
import numpy as np

async def main():
    from assistant.audio.microphone import MicrophoneStream
    mic = MicrophoneStream(device=1)
    await mic.start()
    print("Stream opened OK — collecting 30 frames (say something)…")
    frames = []
    async for f in mic.stream():
        frames.append(f)
        if len(frames) >= 30:
            break
    await mic.stop()
    all_audio = np.concatenate([f.data for f in frames])
    rms  = float(np.sqrt(np.mean(all_audio**2)))
    peak = float(np.max(np.abs(all_audio)))
    print(f"Frames : {len(frames)}")
    print(f"SR     : {frames[0].sample_rate} Hz")
    print(f"Length : {len(frames[0].data)} samples per frame")
    print(f"RMS    : {rms:.4f}")
    print(f"Peak   : {peak:.4f}")
    print("✅ Mic stream works!" if rms > 0.001 else "⚠️ Very low signal")

asyncio.run(main())
