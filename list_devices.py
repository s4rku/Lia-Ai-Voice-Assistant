import sounddevice as sd
print("Input devices with their native sample rates:")
for i, d in enumerate(sd.query_devices()):
    if d["max_input_channels"] > 0:
        name = d["name"]
        ch = d["max_input_channels"]
        sr = int(d["default_samplerate"])
        print(f"  [{i:2d}] {name[:45]:<45}  ch={ch}  sr={sr}")
