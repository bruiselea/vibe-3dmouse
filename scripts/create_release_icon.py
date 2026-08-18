"""Draw the original, brand-neutral 6DoF controller art used by the app."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


WORKSPACE = Path(__file__).resolve().parents[1]
ASSETS = WORKSPACE / "spacemouse_input" / "assets"
PNG_PATH = ASSETS / "vibe-6dof.png"
ICO_PATH = ASSETS / "vibe-6dof.ico"
CYAN = (43, 214, 255, 255)
CYAN_SOFT = (43, 214, 255, 105)
INK = (13, 18, 28, 255)
EDGE = (119, 137, 161, 255)


def arrow(draw: ImageDraw.ImageDraw, start, end, *, width=12, color=CYAN):
    draw.line((start, end), fill=color, width=width)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    spread, length = 0.62, 34
    left = (end[0] - length * math.cos(angle - spread), end[1] - length * math.sin(angle - spread))
    right = (end[0] - length * math.cos(angle + spread), end[1] - length * math.sin(angle + spread))
    draw.polygon((end, left, right), fill=color)


def draw_controller() -> Image.Image:
    size = (1600, 1000)
    glow = Image.new("RGBA", size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse((380, 710, 1220, 970), fill=(11, 206, 255, 85))
    glow = glow.filter(ImageFilter.GaussianBlur(80))

    image = Image.new("RGBA", size, (0, 0, 0, 0))
    image.alpha_composite(glow)
    draw = ImageDraw.Draw(image)

    # A deliberately generic control puck built only from geometric primitives.
    base = [(365, 690), (455, 590), (1145, 590), (1235, 690), (1155, 875), (445, 875)]
    draw.polygon(base, fill=(33, 43, 59, 255), outline=EDGE, width=7)
    draw.ellipse((455, 720, 1145, 900), fill=(18, 25, 38, 255), outline=(69, 88, 112, 255), width=5)
    draw.ellipse((520, 650, 1080, 825), fill=(22, 31, 46, 255), outline=CYAN, width=9)
    draw.ellipse((535, 620, 1065, 790), fill=(12, 18, 29, 255), outline=(91, 111, 137, 255), width=5)

    draw.rounded_rectangle((590, 265, 1010, 680), radius=145, fill=INK, outline=EDGE, width=7)
    draw.ellipse((590, 210, 1010, 480), fill=(26, 36, 51, 255), outline=(144, 162, 184, 255), width=7)
    draw.ellipse((635, 245, 965, 445), fill=(10, 16, 26, 255), outline=(52, 67, 86, 255), width=5)
    draw.line((800, 495, 800, 620), fill=(73, 91, 114, 255), width=7)

    # Translation axes.
    arrow(draw, (800, 170), (800, 65))
    arrow(draw, (800, 170), (800, 275))
    arrow(draw, (535, 470), (365, 470))
    arrow(draw, (1065, 470), (1235, 470))
    arrow(draw, (625, 600), (500, 700))
    arrow(draw, (975, 600), (1100, 700))

    # Rotation arcs; these are visual cues, not copied product geometry.
    draw.arc((435, 180, 1165, 755), 195, 325, fill=CYAN, width=13)
    arrow(draw, (1042, 232), (1115, 278), width=13)
    draw.arc((515, 95, 1085, 650), 25, 150, fill=CYAN_SOFT, width=10)
    arrow(draw, (568, 231), (525, 290), width=10, color=CYAN_SOFT)

    draw.ellipse((395, 650, 485, 740), fill=(12, 18, 29, 255), outline=CYAN, width=6)
    draw.ellipse((1115, 650, 1205, 740), fill=(12, 18, 29, 255), outline=CYAN, width=6)
    return image


ASSETS.mkdir(parents=True, exist_ok=True)
art = draw_controller()
art.save(PNG_PATH)

icon_canvas = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
icon_art = art.copy()
icon_art.thumbnail((980, 820), Image.Resampling.LANCZOS)
icon_canvas.alpha_composite(icon_art, ((1024 - icon_art.width) // 2, (1024 - icon_art.height) // 2))
icon_canvas.save(
    ICO_PATH,
    sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
)
print(PNG_PATH)
print(ICO_PATH)
