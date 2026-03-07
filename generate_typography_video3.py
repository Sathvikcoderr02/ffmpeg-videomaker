#!/usr/bin/env python3
"""
Vertical video (1080x1920): black bg + red texture (1080x800 at Y=560) + scene image + text.
Per-scene segments -> concat demuxer -> final_video3.mp4.
No audio. 30fps. libx264. Overlay chain FIRST, then drawtext. Persistent "Wait for end 😂" on every scene.
"""

import os
import subprocess
import sys

# -----------------------------------------------------------------------------
# PATHS & SPECS
# -----------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_BOLD_PATH = os.path.join(SCRIPT_DIR, "font_bold.ttf")
RED_TEXTURE_PATH = os.path.join(SCRIPT_DIR, "red_texture.jpg")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "final_video3.mp4")
SCENES_DIR = os.path.join(SCRIPT_DIR, "scene_segments_3")
CONCAT_LIST_PATH = os.path.join(SCRIPT_DIR, "scenes3.txt")

WIDTH = 1080
HEIGHT = 1920
FPS = 30
BG_HEX = "0x000000"
RED_TEXTURE_W = 1080
RED_TEXTURE_H = 800
RED_TEXTURE_Y = 560  # vertical center: (1920-800)/2

# Persistent header on every scene
HEADER_TEXT = "Wait for end 😂"
HEADER_SIZE = 60
HEADER_COLOR = "0xFFFFFF"
HEADER_Y = 250


def escape_drawtext(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "\\'")


def overlay_xy_expr(val) -> str:
    """For overlay filter: int -> literal; str -> W/w/H/h -> main_w/overlay_w/main_h/overlay_h."""
    if isinstance(val, int):
        return str(val)
    s = str(val).strip()
    s = s.replace("w", "overlay_w").replace("W", "main_w").replace("h", "overlay_h").replace("H", "main_h")
    return s


# -----------------------------------------------------------------------------
# SCENE DATA: (duration, image_spec, scene_texts)
# image_spec: (filename, scale_w, x, y)  x,y can be int or "(W-w)/2"
# scene_texts: [(t_start, text, size, x, y), ...]  x can be int or "(w-tw)/2"
# -----------------------------------------------------------------------------
SCENES = [
    # SCENE 1 (3.0s)
    (
        3.0,
        ("stone.png", 400, 550, 700),
        [
            (0.0, "Stone", 80, 150, 720),
            (0.5, "One", 160, 150, 800),
            (1.0, "Enough", 120, 150, 960),
        ],
    ),
    # SCENE 2 (2.0s)
    (
        2.0,
        ("glass.png", 450, 500, 700),
        [
            (0.0, "to break a", 80, 150, 750),
            (0.5, "Glass", 160, 150, 850),
        ],
    ),
    # SCENE 3 (3.0s)
    (
        3.0,
        ("mouth.png", 400, 550, 700),
        [
            (0.0, "Word is", 80, 150, 720),
            (0.5, "One", 160, 150, 800),
            (1.0, "Enough", 120, 150, 960),
        ],
    ),
    # SCENE 4 (2.0s)
    (
        2.0,
        ("heart.png", 450, 450, 700),
        [(0.0, "TO", 220, 150, 750)],
    ),
    # SCENE 5 (3.0s)
    (
        3.0,
        ("clock.png", 350, 600, 700),
        [
            (0.0, "Second is", 80, 150, 720),
            (0.5, "One", 160, 150, 800),
            (1.0, "Enough", 120, 150, 960),
        ],
    ),
    # SCENE 6 (2.0s)
    (
        2.0,
        ("cats.png", 400, "(W-w)/2", 600),
        [(0.5, "To fall in love with a stranger", 60, "(w-tw)/2", 1050)],
    ),
    # SCENE 7 (3.0s)
    (
        3.0,
        ("books.png", 450, "(W-w)/2", 600),
        [
            (0.0, "Kani exams lo pass avadaniki", 60, "(w-tw)/2", 1100),
            (1.0, "Enduku ra oka chapter saripodhu", 60, "(w-tw)/2", 1200),
        ],
    ),
    # SCENE 8 (3.0s)
    (
        3.0,
        ("cool_cat.png", 450, "(W-w)/2", 600),
        [
            (0.0, "Idhi ekkadi dikkumalina", 60, "(w-tw)/2", 1100),
            (1.0, "Logic ra naayana", 60, "(w-tw)/2", 1200),
        ],
    ),
]


def build_scene_filter(duration: float, image_spec: tuple, scene_texts: list, font_path: str) -> str:
    """
    Input 0 = black color, Input 1 = red_texture.jpg, Input 2 = scene image.
    Chain: [0][1] red overlay -> [bg]; [bg][2] scene image overlay -> [v0];
    [v0] drawtext header -> [v1]; [v1] drawtext ... -> [v2]; ...
    """
    font = font_path.replace("\\", "/")
    parts = []

    # Red texture: scale 1080x800, overlay at 0:560
    parts.append(f"[1:v]scale={RED_TEXTURE_W}:{RED_TEXTURE_H}[red];")
    parts.append(f"[0:v][red]overlay=0:{RED_TEXTURE_Y}[bg];")

    # Scene image: scale, overlay with enable
    img_filename, scale_w, img_x, img_y = image_spec
    parts.append(f"[2:v]scale={scale_w}:-2[img];")
    x_expr = overlay_xy_expr(img_x)
    y_expr = overlay_xy_expr(img_y)
    x_str = f"'{x_expr}'" if not isinstance(img_x, int) else str(img_x)
    y_str = f"'{y_expr}'" if not isinstance(img_y, int) else str(img_y)
    parts.append(f"[bg][img]overlay=x={x_str}:y={y_str}:enable='between(t,0,{duration})'[v0];")

    # Persistent header "Wait for end 😂"
    header_safe = escape_drawtext(HEADER_TEXT)
    parts.append(
        f"[v0]drawtext=fontfile='{font}':text='{header_safe}':"
        f"fontcolor={HEADER_COLOR}:fontsize={HEADER_SIZE}:x='(w-tw)/2':y={HEADER_Y}:"
        f"enable='between(t,0,{duration})'[v1];"
    )

    # Scene texts
    prev = "v1"
    for i, (t_start, text, size, x, y) in enumerate(scene_texts):
        next_label = f"v{i + 2}"
        safe_text = escape_drawtext(text)
        x_str = f"'(w-tw)/2'" if (isinstance(x, str) and "tw" in str(x)) else str(x)
        segment = (
            f"[{prev}]drawtext=fontfile='{font}':text='{safe_text}':"
            f"fontcolor={HEADER_COLOR}:fontsize={size}:x={x_str}:y={y}:"
            f"enable='between(t,{t_start},{duration})'[{next_label}]"
        )
        if i < len(scene_texts) - 1:
            segment += ";"
        parts.append(segment)
        prev = next_label

    return "".join(parts)


def create_scene(
    scene_index: int,
    duration: float,
    image_spec: tuple,
    scene_texts: list,
    out_path: str,
) -> bool:
    """
    Generate one segment. Input 0 = black, Input 1 = red_texture.jpg, Input 2 = scene image.
    """
    if not os.path.isfile(FONT_BOLD_PATH):
        print(f"Missing font: {FONT_BOLD_PATH}", file=sys.stderr)
        return False
    if not os.path.isfile(RED_TEXTURE_PATH):
        print(f"Missing texture: {RED_TEXTURE_PATH}", file=sys.stderr)
        return False

    img_filename = image_spec[0]
    scene_img_path = os.path.join(SCRIPT_DIR, img_filename)
    if not os.path.isfile(scene_img_path):
        print(f"Missing image: {scene_img_path}", file=sys.stderr)
        return False

    filter_complex = build_scene_filter(duration, image_spec, scene_texts, FONT_BOLD_PATH)
    last_label = f"v{len(scene_texts) + 1}"

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c={BG_HEX}:s={WIDTH}x{HEIGHT}:d={duration}:r={FPS}",
        "-loop", "1", "-i", RED_TEXTURE_PATH,
        "-loop", "1", "-i", scene_img_path,
        "-filter_complex", filter_complex,
        "-map", f"[{last_label}]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-t", str(duration),
        out_path,
    ]

    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        print(f"Scene {scene_index + 1} failed:", r.stderr, file=sys.stderr)
        return False
    return True


def download_assets():
    """Download font_bold.ttf and scene images from web if missing."""
    # Font: Bebas Neue Bold (parentheses in path)
    if not os.path.isfile(FONT_BOLD_PATH):
        print("Downloading font_bold.ttf (Bebas Neue)...")
        url = "https://raw.githubusercontent.com/dharmatype/Bebas-Neue/master/fonts/BebasNeue(2014)ByFontFabric/BebasNeue-Bold.ttf"
        subprocess.run(
            ["curl", "-sL", "-o", FONT_BOLD_PATH, url],
            capture_output=True, timeout=30, cwd=SCRIPT_DIR,
        )
    # Scene images: (filename, url)
    image_urls = [
        ("stone.png", "https://pngimg.com/d/stone_PNG13623.png"),
        ("glass.png", "https://cdn-icons-png.flaticon.com/512/3050/3050158.png"),
        ("mouth.png", "https://cdn-icons-png.flaticon.com/512/3983/3983466.png"),
        ("heart.png", "https://pngimg.com/d/heart_PNG51352.png"),
        ("clock.png", "https://pngimg.com/d/clock_PNG6657.png"),
        ("cats.png", "https://pngimg.com/d/cat_PNG106.png"),
        ("books.png", "https://cdn-icons-png.flaticon.com/512/2111/2111580.png"),
        ("cool_cat.png", "https://pngimg.com/d/cat_PNG50497.png"),
    ]
    for filename, url in image_urls:
        path = os.path.join(SCRIPT_DIR, filename)
        if os.path.isfile(path):
            continue
        print(f"Downloading {filename} ...")
        subprocess.run(
            ["curl", "-sL", "-o", path, url],
            capture_output=True, timeout=30, cwd=SCRIPT_DIR,
        )


def ensure_red_texture():
    """Create a placeholder red texture (1080x800) if missing."""
    if os.path.isfile(RED_TEXTURE_PATH):
        return
    print("Creating placeholder red_texture.jpg ...")
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"color=c=0x8B0000:s={RED_TEXTURE_W}x{RED_TEXTURE_H}:d=1",
            "-frames:v", "1", RED_TEXTURE_PATH,
        ],
        capture_output=True,
        timeout=10,
        cwd=SCRIPT_DIR,
    )


def main():
    download_assets()
    if not os.path.isfile(FONT_BOLD_PATH):
        print(f"Missing {FONT_BOLD_PATH}", file=sys.stderr)
        sys.exit(1)
    ensure_red_texture()
    if not os.path.isfile(RED_TEXTURE_PATH):
        print(f"Missing {RED_TEXTURE_PATH}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(SCENES_DIR, exist_ok=True)
    segment_paths = []

    for i, (duration, image_spec, scene_texts) in enumerate(SCENES):
        out_name = f"scene_{i + 1:03d}.mp4"
        out_path = os.path.join(SCENES_DIR, out_name)
        segment_paths.append(out_path)
        print(f"Creating scene {i + 1}/{len(SCENES)}: {out_name} ({duration}s)")
        if not create_scene(i, duration, image_spec, scene_texts, out_path):
            sys.exit(1)

    with open(CONCAT_LIST_PATH, "w") as f:
        for p in segment_paths:
            path_escaped = p.replace("'", "'\\''")
            f.write(f"file '{path_escaped}'\n")

    print("Concatenating segments -> final_video3.mp4")
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
