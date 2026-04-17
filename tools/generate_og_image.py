#!/usr/bin/env python3
"""
Shared OG-image generator for 8bitconcepts research papers.

Produces 1200x630 PNG with:
  - Dark slate #0d0d0e background
  - Terracotta #d97757 accent top bar + headline
  - Inter or IBM Plex Mono if installed, else macOS system fonts (SFNS / Helvetica), else PIL default
  - Eyebrow label, big headline, subtext, footer
  - "8bitconcepts.com / research" footer signature

Usage (as a module):
    from generate_og_image import generate_og_image
    generate_og_image(
        headline_text="8,618 AI/ML roles hiring",
        subtext="Q2 2026 | OpenAI leads $360k avg",
        output_path="/path/to/research/og/q2-2026-ai-hiring-snapshot.png",
    )

Usage (CLI, for manual regeneration of all three):
    python3 tools/generate_og_image.py --all

The generator is intentionally forgiving: any missing font falls back to the
next candidate. If no truetype font is available at all, ImageFont.load_default()
is used with the requested font size where PIL supports it.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as e:
    print(f"ERROR: PIL (Pillow) not available: {e}", file=sys.stderr)
    sys.exit(1)


# --- Palette (8bitconcepts brand) -----------------------------------------
W, H = 1200, 630
BG = (13, 13, 14)           # #0d0d0e   slate
SURFACE = (26, 28, 31)      # #1a1c1f   slate-2
BORDER = (46, 49, 53)       # #2e3135   slate-4
TEXT = (232, 232, 233)      # #e8e8e9
MUTED = (139, 141, 145)     # #8b8d91
DIMMER = (90, 92, 97)       # #5a5c61
ACCENT = (217, 119, 87)     # #d97757   terracotta


# --- Font resolution ------------------------------------------------------
# Preference order: Inter > IBM Plex > SF/Helvetica > Arial > PIL default.
# Values are filesystem paths; the first existing path wins.
_FONT_CANDIDATES_REGULAR = [
    # Inter (if installed via user install)
    "/Library/Fonts/Inter-Regular.ttf",
    os.path.expanduser("~/Library/Fonts/Inter-Regular.ttf"),
    # IBM Plex (user install)
    "/Library/Fonts/IBMPlexSans-Regular.ttf",
    os.path.expanduser("~/Library/Fonts/IBMPlexSans-Regular.ttf"),
    # macOS system
    "/System/Library/Fonts/SFNS.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
]

_FONT_CANDIDATES_BOLD = [
    "/Library/Fonts/Inter-Bold.ttf",
    os.path.expanduser("~/Library/Fonts/Inter-Bold.ttf"),
    "/Library/Fonts/IBMPlexSans-Bold.ttf",
    os.path.expanduser("~/Library/Fonts/IBMPlexSans-Bold.ttf"),
    # macOS — SFNS is a variable font; fall back to Helvetica/Arial Bold
    "/System/Library/Fonts/SFNS.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]

_FONT_CANDIDATES_MONO = [
    "/Library/Fonts/IBMPlexMono-Medium.ttf",
    os.path.expanduser("~/Library/Fonts/IBMPlexMono-Medium.ttf"),
    "/Library/Fonts/IBMPlexMono-Regular.ttf",
    os.path.expanduser("~/Library/Fonts/IBMPlexMono-Regular.ttf"),
    "/System/Library/Fonts/SFNSMono.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/Monaco.ttf",
    "/System/Library/Fonts/Supplemental/Andale Mono.ttf",
]


def _load_font(size: int, style: str = "regular") -> ImageFont.ImageFont:
    """Load a TrueType font at the requested size, falling back gracefully."""
    if style == "bold":
        candidates = _FONT_CANDIDATES_BOLD
    elif style == "mono":
        candidates = _FONT_CANDIDATES_MONO
    else:
        candidates = _FONT_CANDIDATES_REGULAR

    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    # Final fallback — PIL's bitmap default. Ignores size on older PIL versions
    # but on Pillow >= 10 `load_default(size=...)` exists; try both.
    try:
        return ImageFont.load_default(size=size)  # type: ignore[call-arg]
    except TypeError:
        return ImageFont.load_default()


def _text_w(draw: ImageDraw.ImageDraw, txt: str, font: ImageFont.ImageFont) -> int:
    bbox = draw.textbbox((0, 0), txt, font=font)
    return bbox[2] - bbox[0]


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    """Simple greedy word-wrap; fits as many whole words per line as possible."""
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = current + " " + word
        if _text_w(draw, candidate, font) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _fit_headline(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    max_lines: int = 3,
    start_size: int = 78,
    min_size: int = 44,
) -> tuple[ImageFont.ImageFont, list[str]]:
    """Pick the largest font size where `text` wraps into `max_lines` or fewer."""
    size = start_size
    while size >= min_size:
        font = _load_font(size, style="bold")
        lines = _wrap_text(draw, text, font, max_width)
        if len(lines) <= max_lines:
            return font, lines
        size -= 4
    font = _load_font(min_size, style="bold")
    return font, _wrap_text(draw, text, font, max_width)


def generate_og_image(headline_text: str, subtext: str, output_path: str | Path) -> str:
    """Render and save a 1200x630 OG image.

    Args:
        headline_text: the main stat/line ("8,618 AI/ML roles hiring")
        subtext: the secondary line ("Q2 2026 | OpenAI leads $360k avg")
        output_path: absolute path of the PNG to write. Parent dirs are created.

    Returns:
        The absolute output path on success.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # Top accent bar
    d.rectangle([(0, 0), (W, 8)], fill=ACCENT)

    # Frame
    pad_x = 64
    pad_y = 56
    inner_w = W - 2 * pad_x

    # Eyebrow — branded label
    f_eyebrow = _load_font(22, style="mono")
    eyebrow = "8BITCONCEPTS / RESEARCH"
    d.text((pad_x, pad_y + 20), eyebrow, font=f_eyebrow, fill=ACCENT)

    # Headline — big, bold, terracotta
    # Reserve vertical budget: eyebrow block ~50, footer block ~90, subtext ~70
    headline_top = pad_y + 72
    footer_top = H - pad_y - 64
    subtext_budget = 72
    headline_budget = footer_top - subtext_budget - headline_top - 24  # 24 breathing

    font_h, lines_h = _fit_headline(d, headline_text, inner_w, max_lines=3)
    # Vertically center the headline block inside its budget
    line_h = font_h.size + 8
    block_h = line_h * len(lines_h)
    y = headline_top + max((headline_budget - block_h) // 2, 0)
    for line in lines_h:
        d.text((pad_x, y), line, font=font_h, fill=TEXT)
        y += line_h

    # Subtext — muted, single line preferred but wraps to 2 if needed
    sub_top = headline_top + headline_budget + 12
    f_sub = _load_font(28, style="regular")
    sub_lines = _wrap_text(d, subtext, f_sub, inner_w)[:2]
    sy = sub_top
    for line in sub_lines:
        d.text((pad_x, sy), line, font=f_sub, fill=MUTED)
        sy += f_sub.size + 6

    # Divider
    div_y = H - pad_y - 52
    d.rectangle([(pad_x, div_y), (W - pad_x, div_y + 1)], fill=BORDER)

    # Footer — URL (left) + tag (right accent)
    f_footer = _load_font(22, style="mono")
    url_text = "8bitconcepts.com / research"
    d.text((pad_x, div_y + 14), url_text, font=f_footer, fill=MUTED)

    f_tag = _load_font(22, style="mono")
    tag_text = "LIVE DATA"
    tag_w = _text_w(d, tag_text, f_tag)
    d.text((W - pad_x - tag_w, div_y + 14), tag_text, font=f_tag, fill=ACCENT)

    img.save(output_path, "PNG", optimize=True)
    return str(output_path)


# --- CLI for manual regeneration -----------------------------------------
_REPO = Path(__file__).resolve().parent.parent
_OG_DIR = _REPO / "research" / "og"

_MANUAL_TARGETS = [
    {
        "slug": "q2-2026-ai-hiring-snapshot",
        "headline": "8,405 AI/ML engineering roles open",
        "subtext": "Q2 2026 | 489 companies | $205k median salary",
    },
    {
        "slug": "q2-2026-mcp-ecosystem-health",
        "headline": "575 of 5,578 MCP claims verified",
        "subtext": "Q2 2026 | Live JSON-RPC probe across agent-ready index",
    },
    {
        "slug": "q2-2026-ai-compensation-by-skill",
        "headline": "Research pays $42k more than genAI",
        "subtext": "Q2 2026 | Top-paying tags vs in-demand tags across AI Dev Jobs",
    },
]


def _cli() -> int:
    ap = argparse.ArgumentParser(description="Generate 8bc research OG images.")
    ap.add_argument("--all", action="store_true", help="Regenerate all 3 auto-regen paper OG images with fallback static headlines")
    ap.add_argument("--headline", help="Single-shot: headline text")
    ap.add_argument("--subtext", help="Single-shot: subtext")
    ap.add_argument("--out", help="Single-shot: output PNG path")
    args = ap.parse_args()

    if args.all:
        for t in _MANUAL_TARGETS:
            out = _OG_DIR / f"{t['slug']}.png"
            p = generate_og_image(t["headline"], t["subtext"], out)
            print(f"wrote {p}")
        return 0

    if args.headline and args.subtext and args.out:
        p = generate_og_image(args.headline, args.subtext, args.out)
        print(f"wrote {p}")
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(_cli())
