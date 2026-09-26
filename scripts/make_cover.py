#!/usr/bin/env python
"""Render the 1280x720 submission cover: docs/submission/cover.png

    "C:/Users/csdee/AppData/Local/Programs/Python/Python313/python.exe" scripts/make_cover.py

Dev-only tooling: needs Pillow, which is NOT a project requirement (the repo venv does not carry it).
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
OUT = Path(__file__).resolve().parents[1] / "docs" / "submission" / "cover.png"
FONTS = Path("C:/Windows/Fonts")


def font(name: str, size: int):
    for candidate in (FONTS / name, Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")):
        try:
            return ImageFont.truetype(str(candidate), size)
        except OSError:
            continue
    return ImageFont.load_default()


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def main() -> int:
    img = Image.new("RGB", (W, H))
    px = img.load()
    top, bottom = (11, 15, 24), (30, 22, 74)
    for y in range(H):
        row = lerp(top, bottom, y / H)
        for x in range(W):
            glow = max(0.0, 1 - math.hypot(x - 980, y - 360) / 520)  # soft light behind the loop
            px[x, y] = lerp(row, (52, 60, 150), glow * 0.55)
    d = ImageDraw.Draw(img, "RGBA")

    white, muted, accent = (240, 244, 250), (150, 162, 182), (110, 160, 255)
    amber, green, red, violet = (240, 176, 74), (76, 195, 138), (255, 138, 146), (179, 148, 255)

    # ── left: title block ──
    d.rounded_rectangle((70, 78, 118, 126), radius=12, fill=(110, 160, 255, 255))
    d.rounded_rectangle((76, 84, 112, 120), radius=9, fill=(138, 63, 252, 255))
    d.text((134, 86), "IBM Bob 2.0 Hackathon", font=font("segoeuib.ttf", 26), fill=muted)
    d.text((66, 168), "Bob Reliability", font=font("segoeuib.ttf", 92), fill=white)
    d.text((66, 268), "Engineer", font=font("segoeuib.ttf", 92), fill=accent)
    d.text((70, 398), "Don't just generate a fix.", font=font("segoeui.ttf", 40), fill=white)
    d.text((70, 448), "Verify it — and learn who was right.", font=font("segoeui.ttf", 40), fill=white)

    chips = [("evidence first", accent), ("human-gated writes", amber), ("branch + rollback", violet),
             ("real test verification", green)]
    x = 70
    for label, color in chips:
        f = font("segoeuib.ttf", 18)
        w = d.textlength(label, font=f) + 26
        d.rounded_rectangle((x, 552, x + w, 590), radius=19, fill=color + (36,), outline=color + (180,), width=2)
        d.text((x + 13, 559), label, font=f, fill=color)
        x += w + 10
    d.text((70, 640), "BRE orchestrates IBM Bob  ·  it never reimplements it", font=font("segoeui.ttf", 24), fill=muted)

    # ── right: the loop ──
    cx, cy, R = 1000, 340, 200
    nodes = [("Detect", muted), ("Investigate", accent), ("Diagnose", accent), ("Risk", accent), ("Approve", amber),
             ("Remediate", violet), ("Verify", green), ("Learn", green)]
    pts = []
    for i, (label, color) in enumerate(nodes):
        a = -math.pi / 2 + i * 2 * math.pi / len(nodes)
        pts.append((cx + R * math.cos(a), cy + R * math.sin(a), label, color))
    for (x1, y1, *_), (x2, y2, *_) in zip(pts, pts[1:] + pts[:1]):
        d.line((x1, y1, x2, y2), fill=(150, 162, 182, 90), width=3)
    # the retry edge: verify -> investigate (refuted, capped)
    vx, vy = pts[6][0], pts[6][1]
    ix, iy = pts[1][0], pts[1][1]
    d.line((vx, vy, cx, cy, ix, iy), fill=red + (150,), width=3)
    d.text((cx - 70, cy - 16), "refuted?", font=font("segoeuib.ttf", 22), fill=red)
    d.text((cx - 78, cy + 10), "roll back · retry", font=font("segoeui.ttf", 18), fill=red)
    for x, y, label, color in pts:
        d.ellipse((x - 54, y - 54, x + 54, y + 54), fill=(16, 22, 36, 255), outline=color + (255,), width=4)
        f = font("segoeuib.ttf", 17)
        d.text((x, y), label, font=f, fill=color, anchor="mm")
    d.text((cx, cy + 285), "capped at 3 attempts — then ABANDONED", font=font("segoeui.ttf", 18), fill=muted, anchor="mm")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, "PNG", optimize=True)
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
