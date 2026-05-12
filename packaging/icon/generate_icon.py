"""
Generate the LLM Knowledge Base app icon.

Design: A neural-knowledge graph — a central glowing node surrounded by six
satellite nodes, all connected, on a deep indigo rounded-square background.
This represents LLM (neural network) + Knowledge Base (graph of linked articles).

Output:
  icon.png  — 256 × 256 RGBA master
  icon.ico  — multi-size Windows ICO (16, 24, 32, 48, 64, 128, 256)
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

OUT_DIR = Path(__file__).parent


# ── Colour palette ────────────────────────────────────────────────────────────
BG_TOP    = (20, 16, 60)    # deep indigo
BG_BOTTOM = (38, 28, 100)   # slightly lighter indigo
EDGE_COL  = (139, 92, 246, 120)   # violet-500, semi-transparent
GLOW_COL  = (167, 139, 250)       # violet-400
NODE_COL  = (255, 255, 255)       # white fill
RING_COL  = (196, 181, 253)       # violet-300 for outer nodes
SPARK_COL = (224, 214, 255, 180)  # very light violet, sparks


def _lerp_color(a: tuple, b: tuple, t: float) -> tuple:
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def render(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # ── Gradient background ───────────────────────────────────────────────────
    for y in range(size):
        t = y / max(size - 1, 1)
        col = _lerp_color(BG_TOP, BG_BOTTOM, t) + (255,)
        draw.line([(0, y), (size - 1, y)], fill=col)

    # ── Apply rounded-square mask ─────────────────────────────────────────────
    mask = Image.new("L", (size, size), 0)
    m = ImageDraw.Draw(mask)
    corner_r = int(size * 0.22)
    m.rounded_rectangle([0, 0, size - 1, size - 1], radius=corner_r, fill=255)
    img.putalpha(mask)

    # ── Node layout ───────────────────────────────────────────────────────────
    # One centre + six outer nodes arranged in a hexagon
    cx, cy = size * 0.5, size * 0.5
    outer_r = size * 0.31

    def hex_pt(i: int) -> tuple[float, float]:
        angle = math.radians(i * 60 - 30)
        return cx + outer_r * math.cos(angle), cy + outer_r * math.sin(angle)

    outer_nodes = [hex_pt(i) for i in range(6)]
    centre = (cx, cy)
    all_nodes = [centre] + outer_nodes

    # ── Draw edges ────────────────────────────────────────────────────────────
    lw = max(1, round(size * 0.025))

    # Centre → each outer
    for pt in outer_nodes:
        draw.line([centre, pt], fill=EDGE_COL, width=lw)

    # Outer ring connections (every other one to avoid clutter)
    for i in range(6):
        a = outer_nodes[i]
        b = outer_nodes[(i + 1) % 6]
        draw.line([a, b], fill=EDGE_COL, width=max(1, lw - 1))

    # ── Draw glow halos (blurred layer) ──────────────────────────────────────
    glow_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow_layer)

    centre_r = size * 0.115
    outer_node_r = size * 0.065

    def draw_glow(d, px, py, node_r, col, alpha_scale=1.0):
        for factor, alpha in [(2.2, 40), (1.6, 70), (1.2, 100)]:
            gr = node_r * factor
            a = int(alpha * alpha_scale)
            d.ellipse(
                [px - gr, py - gr, px + gr, py + gr],
                fill=col + (a,),
            )

    draw_glow(gd, cx, cy, centre_r, GLOW_COL, 1.0)
    for pt in outer_nodes:
        draw_glow(gd, pt[0], pt[1], outer_node_r, GLOW_COL, 0.75)

    glow_blurred = glow_layer.filter(ImageFilter.GaussianBlur(radius=size * 0.025))
    img = Image.alpha_composite(img, glow_blurred)

    # ── Draw solid nodes ──────────────────────────────────────────────────────
    draw = ImageDraw.Draw(img)

    def solid_node(px, py, r, fill, border=None):
        if border:
            bw = max(1, round(r * 0.18))
            draw.ellipse(
                [px - r, py - r, px + r, py + r],
                fill=border,
            )
            ir = r - bw
        else:
            ir = r
        draw.ellipse(
            [px - ir, py - ir, px + ir, py + ir],
            fill=fill,
        )

    # Centre node: white with violet border
    solid_node(cx, cy, centre_r, NODE_COL, GLOW_COL)

    # Add a tiny inner highlight
    hi = centre_r * 0.35
    ho = centre_r * 0.28
    draw.ellipse(
        [cx - hi + ho, cy - hi, cx + hi + ho, cy + hi - ho],
        fill=(255, 255, 255, 160),
    )

    # Outer nodes
    for pt in outer_nodes:
        solid_node(pt[0], pt[1], outer_node_r, RING_COL)

    # ── Tiny sparkle dots between some edges ─────────────────────────────────
    spark_r = max(1, round(size * 0.018))
    for i in (0, 2, 4):
        mx = (centre[0] + outer_nodes[i][0]) * 0.5
        my = (centre[1] + outer_nodes[i][1]) * 0.5
        draw.ellipse(
            [mx - spark_r, my - spark_r, mx + spark_r, my + spark_r],
            fill=SPARK_COL,
        )

    return img


def build_all() -> None:
    sizes = [256, 128, 64, 48, 32, 24, 16]

    master = render(256)
    master.save(OUT_DIR / "icon.png")
    print("Saved icon.png")

    frames = []
    for s in sizes:
        if s == 256:
            frames.append(master)
        else:
            frames.append(master.resize((s, s), Image.LANCZOS))

    frames[0].save(
        OUT_DIR / "icon.ico",
        format="ICO",
        append_images=frames[1:],
        sizes=[(s, s) for s in sizes],
    )
    print("Saved icon.ico  (sizes:", sizes, ")")


if __name__ == "__main__":
    build_all()
