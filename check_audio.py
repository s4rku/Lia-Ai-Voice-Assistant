import sounddevice as sd
print("=== Audio Devices ===")
devices = sd.query_devices()
for i, d in enumerate(devices):
    tag = ""
    if d["max_input_channels"] > 0:
        tag += " [INPUT]"
    if d["max_output_channels"] > 0:
        tag += " [OUTPUT]"
    print(f"  {i:2d}: {d['name']}{tag}")

print()
default_in = sd.query_devices(kind="input")
print(f"Default input : {default_in['name']}")
default_out = sd.query_devices(kind="output")
print(f"Default output: {default_out['name']}")
