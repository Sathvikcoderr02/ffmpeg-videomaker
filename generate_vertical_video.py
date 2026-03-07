#!/usr/bin/env python3
"""
Vertical Video Generator (1080x1920) using FFmpeg filter_complex.
No audio. 10 seconds. Scene 1 (0-5s): green bg + megaphone + cat + text.
Scene 2 (5-10s): brown bg + text only.
"""

import os
import subprocess
import sys

# -----------------------------------------------------------------------------
# PATHS (assets in same directory as script)
# -----------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(SCRIPT_DIR, "font.ttf")
MEGAPHONE_PATH = os.path.join(SCRIPT_DIR, "megaphone.png")
CAT_PATH = os.path.join(SCRIPT_DIR, "cat.png")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "final_video.mp4")

# -----------------------------------------------------------------------------
# VIDEO SPECS
# -----------------------------------------------------------------------------
WIDTH = 1080
HEIGHT = 1920
DURATION_SCENE = 5.0
FPS = 30

# -----------------------------------------------------------------------------
# SCENE 1 (0s - 5s): Background + overlays
# -----------------------------------------------------------------------------
BG1_HEX = "0x62785d"  # Vintage Green

# Megaphone: scale width (px), position
MEGAPHONE_W = 450
MEGAPHONE_X = 50
MEGAPHONE_Y = 700

# Cat: scale width (px), Y offset from bottom
CAT_W = 350
CAT_Y_FROM_BOTTOM = 100  # Y = H - cat_h - this

# Scene 1 text (appear time, text, color hex, size, x, y)
# Avoid megaphone zone (X 50–500, Y 700–1030) and cat zone (center, bottom ~400px)
SCENE1_TEXTS = [
    (0.5, "kya", "0xeeb62e", 220, 80, 280),   # top-left with margin (was cutting off)
    (1.0, "App", "0x111111", 180, 80, 540),   # left, above megaphone
    (1.5, "ko", "0xcf4646", 150, 530, 560),   # right of megaphone
    (2.0, "ata", "0xb3b3b3", 140, 530, 820),  # right of megaphone, below it (was overlapping)
]

# -----------------------------------------------------------------------------
# SCENE 2 (5s - 10s): Background + text only
# -----------------------------------------------------------------------------
BG2_HEX = "0x735642"  # Vintage Brown

# Scene 2 text (appear time, text, color hex, size, x, y)
# "??" moved to lower-right so it doesn't overlap Nahi (540) / AATA (800)
SCENE2_TEXTS = [
    (5.5, "KYU", "0x5cb85c", 220, 80, 280),
    (6.0, "Nahi", "0x111111", 180, 80, 540),
    (6.5, "AATA", "0xeb5757", 180, 80, 800),
    (7.0, "??", "0xe0e0e0", 300, 620, 1100),  # lower-right, clear of other lines
]


def escape_drawtext(s: str) -> str:
    """Escape single quotes and backslashes for FFmpeg drawtext."""
    return s.replace("\\", "\\\\").replace("'", "\\'")


def build_filter_complex() -> str:
    """Build the full filter_complex string with proper tag chaining."""
    font = FONT_PATH.replace("\\", "/")
    t_end_s1 = DURATION_SCENE
    t_end_s2 = 10.0

    # ---- 1. Two solid backgrounds, then concat to 10s ----
    # Input 0 = green 5s, Input 1 = brown 5s
    parts = [
        f"[0:v][1:v]concat=n=2:v=1:a=0[bg];",
        f"[2:v]scale={MEGAPHONE_W}:-2[megaphone];",
        f"[3:v]scale={CAT_W}:-2[cat];",
        f"[bg][megaphone]overlay={MEGAPHONE_X}:{MEGAPHONE_Y}:enable='between(t,0,{t_end_s1})'[v1];",
        f"[v1][cat]overlay=(main_w-overlay_w)/2:main_h-overlay_h-{CAT_Y_FROM_BOTTOM}:enable='between(t,0,{t_end_s1})'[v2];",
    ]

    # ---- 2. Scene 1 drawtexts (chain v2 -> v3 -> v4 -> v5 -> v6) ----
    prev = "v2"
    for i, (t_start, text, color, size, x, y) in enumerate(SCENE1_TEXTS):
        next_label = f"v{3 + i}"
        safe_text = escape_drawtext(text)
        parts.append(
            f"[{prev}]drawtext=fontfile='{font}':text='{safe_text}':"
            f"fontcolor={color}:fontsize={size}:x={x}:y={y}:"
            f"enable='between(t,{t_start},{t_end_s1})'[{next_label}];"
        )
        prev = next_label

    # ---- 3. Scene 2 drawtexts (chain v6 -> v7 -> v8 -> v9 -> v10) ----
    for i, (t_start, text, color, size, x, y) in enumerate(SCENE2_TEXTS):
        next_label = f"v{7 + i}"
        safe_text = escape_drawtext(text)
        parts.append(
            f"[{prev}]drawtext=fontfile='{font}':text='{safe_text}':"
            f"fontcolor={color}:fontsize={size}:x={x}:y={y}:"
            f"enable='between(t,{t_start},{t_end_s2})'[{next_label}];"
        )
        prev = next_label

    # Last segment ends with [v10]; remove trailing semicolon for last filter output
    # FFmpeg expects the last filter to have no semicolon after the output label
    full = "".join(parts)
    return full.rstrip(";")


def main():
    for p in (FONT_PATH, MEGAPHONE_PATH, CAT_PATH):
        if not os.path.isfile(p):
            print(f"Missing asset: {p}", file=sys.stderr)
            sys.exit(1)

    filter_complex = build_filter_complex()

    # Inputs: 0 = green 5s, 1 = brown 5s, 2 = megaphone, 3 = cat
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "lavfi",
        "-i", f"color=c={BG1_HEX}:s={WIDTH}x{HEIGHT}:d={DURATION_SCENE}:r={FPS}",
        "-f", "lavfi",
        "-i", f"color=c={BG2_HEX}:s={WIDTH}x{HEIGHT}:d={DURATION_SCENE}:r={FPS}",
        "-loop", "1",
        "-i", MEGAPHONE_PATH,
        "-loop", "1",
        "-i", CAT_PATH,
        "-filter_complex", filter_complex,
        "-map", "[v10]",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-t", "10",
        OUTPUT_PATH,
    ]

    print("Running FFmpeg (filter_complex excerpt):")
    print(filter_complex[:200] + "..." if len(filter_complex) > 200 else filter_complex)
    print()

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("STDERR:", result.stderr, file=sys.stderr)
        sys.exit(result.returncode)
    print("Done:", OUTPUT_PATH)


if __name__ == "__main__":
    main()
