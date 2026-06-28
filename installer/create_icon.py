"""
Creates a simple lia.ico using Pillow.
Run once: python installer/create_icon.py
"""
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Outer circle
    draw.ellipse([8, 8, 248, 248], fill=(20, 20, 60, 255))
    # Accent ring
    draw.ellipse([20, 20, 236, 236], outline=(233, 69, 96, 255), width=8)
    # Letter S
    try:
        font = ImageFont.truetype("arial.ttf", 140)
    except Exception:
        font = ImageFont.load_default()
    draw.text((128, 128), "S", font=font, fill=(233, 69, 96, 255), anchor="mm")

    out = Path(__file__).parent / "lia.ico"
    img.save(str(out), format="ICO", sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
    print(f"Icon saved: {out}")
except ImportError:
    print("Pillow not installed – icon not created. Using PyInstaller default.")
