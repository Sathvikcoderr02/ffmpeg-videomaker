#!/usr/bin/env python3
"""
Vertical typography video (1080x1920), white background, pure text.
Per-scene segments + FFmpeg concat demuxer -> final_video2.mp4.
No audio. 30fps. libx264. Two fonts: font_bold.ttf, font_cursive.ttf.
Centered text: x=(w-tw)/2. Staggered pop-in via enable='between(t,start,end)'.
"""

import os
import subprocess
import sys

# -----------------------------------------------------------------------------
# PATHS & SPECS
# -----------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_BOLD_PATH = os.path.join(SCRIPT_DIR, "font_bold.ttf")
FONT_CURSIVE_PATH = os.path.join(SCRIPT_DIR, "font_cursive.ttf")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "final_video2.mp4")
SCENES_DIR = os.path.join(SCRIPT_DIR, "scene_segments_2")
CONCAT_LIST_PATH = os.path.join(SCRIPT_DIR, "scenes2.txt")

WIDTH = 1080
HEIGHT = 1920
FPS = 30
BG_HEX = "0xFFFFFF"


def escape_drawtext(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "\\'")


# -----------------------------------------------------------------------------
# SCENE DATA: (duration_sec, [(t_start, text, font_key, color_hex, size, x_expr, y), ...])
# font_key: "bold" | "cursive"
# x_expr: "(w-tw)/2" or "(w/2)-250" or "(w/2)+20" (FFmpeg drawtext uses w, tw)
# -----------------------------------------------------------------------------
SCENES = [
    # SCENE 1 (2.0s)
    (
        2.0,
        [
            (0.0, "PYAAR FREE", "bold", "0x000000", 130, "(w-tw)/2", 850),
            (0.5, "ME MILTA HAI", "bold", "0x000000", 130, "(w-tw)/2", 980),
        ],
    ),
    # SCENE 2 (2.0s)
    (
        2.0,
        [
            (0.0, "LEKIN", "bold", "0x000000", 130, "(w/2)-250", 850),
            (0.4, "sirf", "cursive", "0xe6005c", 180, "(w/2)+20", 830),
            (0.8, "TEEN", "bold", "0x4b0082", 150, "(w-tw)/2", 980),
        ],
    ),
    # SCENE 3 (1.0s)
    (1.0, [(0.0, "AURATO KO", "bold", "0xe6005c", 150, "(w-tw)/2", 900)]),
    # SCENE 4 (1.0s)
    (1.0, [(0.0, "BACHHO KO", "bold", "0xe6005c", 150, "(w-tw)/2", 900)]),
    # SCENE 5 (1.0s)
    (1.0, [(0.0, "OR KUTTO KO", "bold", "0xe6005c", 150, "(w-tw)/2", 900)]),
    # SCENE 6 (3.0s)
    (
        3.0,
        [
            (0.0, "AADMI KO", "bold", "0x000000", 130, "(w-tw)/2", 720),
            (0.5, "pyaar", "cursive", "0xe6005c", 200, "(w-tw)/2", 820),
            (1.0, "FREE", "bold", "0x000000", 150, "(w-tw)/2", 960),
            (1.5, "ME NAHI MILTA", "bold", "0x000000", 130, "(w-tw)/2", 1090),
        ],
    ),
    # SCENE 7 (2.5s)
    (
        2.5,
        [
            (0.0, "USE KUCH", "bold", "0x000000", 130, "(w-tw)/2", 720),
            (0.5, "BAN NA", "bold", "0x000000", 130, "(w-tw)/2", 850),
            (1.0, "padta", "cursive", "0xe6005c", 180, "(w-tw)/2", 950),
            (1.5, "HAI", "bold", "0x000000", 130, "(w-tw)/2", 1100),
        ],
    ),
    # SCENE 8 (2.5s)
    (
        2.5,
        [
            (0.0, "KUCHH", "bold", "0x000000", 160, "(w-tw)/2", 750),
            (0.5, "haasil", "cursive", "0xe6005c", 200, "(w-tw)/2", 870),
            (1.0, "KARNA PADTA HAI", "bold", "0x000000", 120, "(w-tw)/2", 1030),
        ],
    ),
    # SCENE 9 (2.5s)
    (
        2.5,
        [
            (0.0, "APNI EK", "bold", "0x000000", 130, "(w-tw)/2", 750),
            (0.5, "BANANI", "bold", "0x000000", 140, "(w-tw)/2", 880),
            (1.0, "aukaat", "cursive", "0xe6005c", 180, "(w-tw)/2", 990),
        ],
    ),
    # SCENE 10 (3.0s)
    (
        3.0,
        [
            (0.0, "JAB USKE PAAS", "bold", "0x000000", 120, "(w-tw)/2", 700),
            (0.5, "DENE KE LIYE", "bold", "0x000000", 120, "(w-tw)/2", 820),
            (1.0, "bohot", "cursive", "0xe6005c", 180, "(w-tw)/2", 920),
            (1.5, "KUCHH HOTA", "bold", "0x000000", 130, "(w-tw)/2", 1060),
        ],
    ),
    # SCENE 11 (3.0s)
    (
        3.0,
        [
            (0.0, "TAB JAAKAR", "bold", "0x000000", 130, "(w-tw)/2", 750),
            (0.5, "USE", "bold", "0x000000", 130, "(w-tw)/2", 870),
            (1.0, "pyaar", "cursive", "0xe6005c", 180, "(w-tw)/2", 960),
            (1.5, "MILTA HAI", "bold", "0x000000", 130, "(w-tw)/2", 1100),
        ],
    ),
    # SCENE 12 (2.0s)
    (
        2.0,
        [(0.0, "NOTHING IS FREE FOR MEN", "bold", "0x4b0082", 100, "(w-tw)/2", 900)],
    ),
    # SCENE 13 (4.0s)
    (
        4.0,
        [
            (0.0, "IS DUNIYA ME", "bold", "0x000000", 120, "(w-tw)/2", 600),
            (0.5, "aadmi", "cursive", "0xe6005c", 180, "(w-tw)/2", 700),
            (1.0, "KO KUCH BHI", "bold", "0x000000", 130, "(w-tw)/2", 850),
            (1.5, "FREE", "bold", "0x000000", 180, "(w-tw)/2", 970),
            (2.0, "ME NAHI MILTA", "bold", "0x000000", 130, "(w-tw)/2", 1150),
        ],
    ),
]


def get_font_path(font_key: str) -> str:
    return FONT_BOLD_PATH if font_key == "bold" else FONT_CURSIVE_PATH


def build_scene_filter(duration: float, texts: list) -> str:
    """Chain drawtext filters: [0:v] -> [v1] -> [v2] -> ..."""
    parts = []
    prev = "0:v"
    for i, (t_start, text, font_key, color, size, x_expr, y) in enumerate(texts):
        font_path = get_font_path(font_key).replace("\\", "/")
        next_label = f"v{i + 1}"
        safe_text = escape_drawtext(text)
        # x can be expression; wrap in single quotes for FFmpeg
        x_str = f"'{x_expr}'" if "(" in x_expr else x_expr
        segment = (
            f"[{prev}]drawtext=fontfile='{font_path}':text='{safe_text}':"
            f"fontcolor={color}:fontsize={size}:x={x_str}:y={y}:"
            f"enable='between(t,{t_start},{duration})'[{next_label}]"
        )
        if i < len(texts) - 1:
            segment += ";"
        parts.append(segment)
        prev = next_label
    return "".join(parts)


def create_scene(scene_index: int, duration: float, texts: list, out_path: str) -> bool:
    """Generate one scene segment (white bg + drawtext chain). No images, no audio."""
    for _, _, font_key, _, _, _, _ in texts:
        path = get_font_path(font_key)
        if not os.path.isfile(path):
            print(f"Missing font: {path}", file=sys.stderr)
            return False

    filter_complex = build_scene_filter(duration, texts)

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c={BG_HEX}:s={WIDTH}x{HEIGHT}:d={duration}:r={FPS}",
        "-filter_complex", filter_complex,
        "-map", f"[v{len(texts)}]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-t", str(duration),
        out_path,
    ]

    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        print(f"Scene {scene_index + 1} failed:", r.stderr, file=sys.stderr)
        return False
    return True


def download_fonts():
    """Download font_bold.ttf (Bebas Neue) and font_cursive.ttf (Great Vibes) if missing."""
    # Bebas Neue Bold (parentheses in URL)
    bold_url = "https://raw.githubusercontent.com/dharmatype/Bebas-Neue/master/fonts/BebasNeue(2014)ByFontFabric/BebasNeue-Bold.ttf"
    if not os.path.isfile(FONT_BOLD_PATH):
        print("Downloading font_bold.ttf (Bebas Neue)...")
        subprocess.run(
            ["curl", "-sL", "-o", FONT_BOLD_PATH, bold_url],
            capture_output=True, timeout=30, cwd=SCRIPT_DIR,
        )
    # Great Vibes Regular
    cursive_url = "https://raw.githubusercontent.com/google/fonts/main/ofl/greatvibes/GreatVibes-Regular.ttf"
    if not os.path.isfile(FONT_CURSIVE_PATH):
        print("Downloading font_cursive.ttf (Great Vibes)...")
        subprocess.run(
            ["curl", "-sL", "-o", FONT_CURSIVE_PATH, cursive_url],
            capture_output=True, timeout=30, cwd=SCRIPT_DIR,
        )


def main():
    download_fonts()

    if not os.path.isfile(FONT_BOLD_PATH) or not os.path.isfile(FONT_CURSIVE_PATH):
        print("Missing font(s). Check font_bold.ttf and font_cursive.ttf.", file=sys.stderr)
        sys.exit(1)

    os.makedirs(SCENES_DIR, exist_ok=True)
    segment_paths = []

    for i, (duration, texts) in enumerate(SCENES):
        out_name = f"scene_{i + 1:03d}.mp4"
        out_path = os.path.join(SCENES_DIR, out_name)
        segment_paths.append(out_path)
        print(f"Creating scene {i + 1}/{len(SCENES)}: {out_name} ({duration}s)")
        if not create_scene(i, duration, texts, out_path):
            sys.exit(1)

    with open(CONCAT_LIST_PATH, "w") as f:
        for p in segment_paths:
            path_escaped = p.replace("'", "'\\''")
            f.write(f"file '{path_escaped}'\n")

    print("Concatenating segments -> final_video2.mp4")
    r = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", CONCAT_LIST_PATH, "-c", "copy", OUTPUT_PATH],
        capture_output=True, text=True, timeout=60,
    )
    if r.returncode != 0:
        print("Concat failed:", r.stderr, file=sys.stderr)
        sys.exit(1)

    for p in segment_paths:
        try:
            os.remove(p)
        except OSError:
            pass
    try:
        os.remove(CONCAT_LIST_PATH)
    except OSError:
        pass
    try:
        os.rmdir(SCENES_DIR)
    except OSError:
        pass

    print("Done:", OUTPUT_PATH)


if __name__ == "__main__":
    main()
