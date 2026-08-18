"""Create the multi-resolution Windows icon used by the beta package."""

from pathlib import Path

from PIL import Image


workspace = Path(__file__).resolve().parents[1]
source = workspace / "spacemouse_input" / "assets" / "spacemouse-controller.png"
destination = workspace / "spacemouse_input" / "assets" / "spacemouse-controller.ico"

image = Image.open(source).convert("RGBA")
canvas = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
image.thumbnail((940, 760), Image.Resampling.LANCZOS)
canvas.alpha_composite(image, ((1024 - image.width) // 2, (1024 - image.height) // 2))
canvas.save(destination, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print(destination)

