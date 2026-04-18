#!/usr/bin/env python3
"""Generate 1200x630 OG images for 8bitconcepts landing pages that aren't
the homepage or /work-with-us (those already have bespoke OGs).
"""
import os
from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630
BG = (13, 13, 14)
SURFACE = (20, 20, 22)
BORDER = (31, 31, 35)
TEXT = (224, 224, 224)
MUTED = (136, 136, 136)
ACCENT = (217, 119, 87)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "..")  # 8bc is a flat GH Pages site — OGs live at repo root


def load_font(size, bold=False):
    candidates = []
    if bold:
        candidates += [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
    candidates += [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def text_w(draw, txt, font):
    bbox = draw.textbbox((0, 0), txt, font=font)
    return bbox[2] - bbox[0]


def wrap(draw, txt, font, max_w):
    words = txt.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if text_w(draw, trial, font) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def render(filename, eyebrow, headline, sub, url_path):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([(0, 0), (W, 6)], fill=ACCENT)
    pad = 48
    d.rectangle([(pad, pad + 20), (W - pad, H - pad)], outline=BORDER, width=2)

    f_brow = load_font(22, bold=True)
    ebw = text_w(d, eyebrow, f_brow)
    d.text(((W - ebw) // 2, 110), eyebrow, font=f_brow, fill=ACCENT)

    f_title = load_font(72, bold=True)
    lines = wrap(d, headline, f_title, W - (pad + 80) * 2)
    y = 170
    for line in lines[:2]:
        lw = text_w(d, line, f_title)
        d.text(((W - lw) // 2, y), line, font=f_title, fill=TEXT)
        y += 82

    f_sub = load_font(28)
    for sub_line in wrap(d, sub, f_sub, W - (pad + 80) * 2)[:2]:
        sw = text_w(d, sub_line, f_sub)
        d.text(((W - sw) // 2, y + 20), sub_line, font=f_sub, fill=MUTED)
        y += 40

    f_url = load_font(26, bold=True)
    url = "8bitconcepts.com" + url_path
    uw = text_w(d, url, f_url)
    d.text(((W - uw) // 2, H - pad - 40), url, font=f_url, fill=ACCENT)

    out = os.path.join(OUT_DIR, filename)
    img.save(out, "PNG", optimize=True)
    return out


LANDINGS = [
    ("og-diagnostic.png",    "DIAGNOSTIC",   "AI Org Structure Diagnostic", "30-min focused check. Find which placement trap you're in + the structural fix.", "/diagnostic"),
    ("og-research.png",       "RESEARCH",    "Enterprise AI Research",       "Practitioner research for engineering teams at Series B-D companies.",           "/research"),
    ("og-case-studies.png",   "CASE STUDIES", "First-Party Builds",          "Three products we run — NHS, ADB, 8bc. Live traffic, real data, shipping daily.", "/case-studies"),
    ("og-faq.png",            "FAQ",         "Embedded AI Consulting FAQ",   "14 skeptical-operator questions about working with us.",                        "/faq"),
    ("og-local.png",          "PNW",         "AI Consulting, Pacific NW",    "Vancouver WA · Camas WA · Portland OR · Tigard OR. Practitioners, local.",      "/local"),
]


def main():
    print(f"rendering {len(LANDINGS)} OG images...")
    for filename, eyebrow, headline, sub, url_path in LANDINGS:
        path = render(filename, eyebrow, headline, sub, url_path)
        print(f"  {filename:30s} -> {os.path.getsize(path)//1024}KB")
    print("done.")


if __name__ == "__main__":
    main()
