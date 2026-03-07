#!/usr/bin/env python3
"""
Vertical typography video (1080x1920) via per-scene segments + concat demuxer.
Supports optional transparent image overlays (stickers); overlays are chained
BEFORE drawtext. Optional voice: put voice.mp3 (or .m4a/.aac/.wav) in script dir.
30fps. libx264, yuv420p. Audio: aac.
"""

import os
import subprocess
import sys

# -----------------------------------------------------------------------------
# PATHS & SPECS
# -----------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(SCRIPT_DIR, "font.ttf")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "final_video.mp4")
SCENES_DIR = os.path.join(SCRIPT_DIR, "scene_segments")
CONCAT_LIST_PATH = os.path.join(SCRIPT_DIR, "scenes.txt")

# Voice: place voice.mp3 (or voice.m4a / voice.aac / voice.wav) in script dir to add narration
VOICE_FILENAMES = ("voice.mp3", "voice.m4a", "voice.aac", "voice.wav")

WIDTH = 1080
HEIGHT = 1920
FPS = 30

# Image assets (transparent PNGs in script directory)
IMAGE_ASSETS = [
    "megaphone.png",
    "cat.png",
    "smiley.png",
    "tigers.png",
    "duck.png",
    "kitten.png",
    "boy.png",
]


def escape_drawtext(s: str) -> str:
    """Escape single quotes and backslashes for FFmpeg drawtext."""
    return s.replace("\\", "\\\\").replace("'", "\\'")


def overlay_xy_expr(val) -> str:
    """Convert x/y to FFmpeg overlay expression. int -> literal; str -> W/w/H/h -> main_w/overlay_w/main_h/overlay_h."""
    if isinstance(val, int):
        return str(val)
    s = str(val).strip()
    # Replace w/h first so that main_w/main_h are not corrupted when we add main_ prefix to W/H
    s = s.replace("w", "overlay_w").replace("W", "main_w").replace("h", "overlay_h").replace("H", "main_h")
    return s


# -----------------------------------------------------------------------------
# SCENE DATA: (duration_sec, bg_hex, images_list, texts_list)
# images_list: [(filename, scale_w, x, y, t_start), ...]  x,y can be int or expr like "(W-w)/2", "H-h-100"
# texts_list: [(t_start, text, color_hex, size, x, y), ...]
# -----------------------------------------------------------------------------
SCENES = [
    # SCENE 1 (3s) - Vintage Green | megaphone + cat
    (
        3,
        "0x62785d",
        [
            ("megaphone.png", 400, 20, 600, 0.0),
            ("cat.png", 250, "(W-w)/2", "H-h-100", 0.0),
        ],
        [
            (0.0, "Kya", "0xeeb62e", 220, 80, 380),    # shifted down to use more of frame
            (0.5, "App", "0xffffff", 180, 520, 580),
            (1.0, "ko", "0xcf4646", 150, 530, 760),
            (1.5, "ata", "0xb3b3b3", 140, 530, 960),   # closer to bottom, less empty space
        ],
    ),
    # SCENE 2 (3s) - Vintage Green | smiley + cat
    (
        3,
        "0x62785d",
        [
            ("smiley.png", 300, 100, 750, 0.0),
            ("cat.png", 250, "W-w-50", "H-h-100", 0.0),
        ],
        [
            (0.0, "APPKE", "0xd63384", 180, 80, 320),
            (0.5, "Dost", "0xfd7e14", 160, 80, 520),
            (1.0, "JAB AAP KO", "0x20c997", 150, 200, 1100),  # center-bottom, clear of smiley & cat
        ],
    ),
    # SCENE 3 (3s) - Vintage Brown | crisscross: KYU left, Nahi right, AATA left, ?? right
    (
        3,
        "0x6b4e3d",
        [],
        [
            (0.0, "KYU", "0x6fcf97", 220, 80, 320),    # top left
            (0.5, "Nahi", "0xffffff", 180, 520, 460),  # right, middle (crisscross)
            (1.0, "AATA", "0xeb5757", 180, 80, 640),  # left, lower (crisscross)
            (1.5, "??", "0xe0e0e0", 260, 380, 880),   # right side bottom
        ],
    ),
    # SCENE 4 (3s) - Vintage Brown | no images
    (
        3,
        "0x6b4e3d",
        [],
        [
            (0.0, "JAB", "0xeb5757", 200, 150, 200),
            (0.5, "KOI", "0xffffff", 180, 350, 400),
            (1.0, "DUSRA", "0x6fcf97", 180, 150, 600),
            (1.5, "GALI", "0xeeb62e", 220, 300, 800),
        ],
    ),
    # SCENE 5 (3s) - Vintage Brown | tigers
    (
        3,
        "0x6b4e3d",
        [
            ("tigers.png", 500, 400, 400, 0.0),
        ],
        [
            (0.0, "AAP", "0xffffff", 250, 80, 280),
            (0.5, "us ki", "0xb3b3b3", 150, 80, 720),
        ],
    ),
    # SCENE 6 (3s) - Vintage Brown | duck right so text on left doesn't overlap
    (
        3,
        "0x6b4e3d",
        [
            ("duck.png", 500, "W-w-80", 80, 0.0),
        ],
        [
            (0.0, "ASAL", "0xeb5757", 220, 80, 380),
            (0.5, "me", "0xffffff", 150, 80, 620),     # gap below ASAL
            (1.0, "DOST", "0x111111", 250, 80, 860),   # gap below me
        ],
    ),
    # SCENE 7 (4s) - Olive Green | kitten
    (
        4,
        "0x4a5d23",
        [
            ("kitten.png", 450, "W-w-50", "H-h-300", 0.0),
        ],
        [
            (0.0, "dete", "0xfd7e14", 150, 80, 200),
            (0.5, "AAP KE", "0xffffff", 180, 80, 400),
            (1.0, "Father WALA", "0xeeb62e", 180, 80, 600),
            (1.5, "HORMONES", "0xd63384", 160, 80, 800),
            (2.0, "ACTIVE", "0x6fcf97", 180, 80, 1000),
        ],
    ),
    # SCENE 8 (2s) - Olive Green | no images
    (
        2,
        "0x4a5d23",
        [],
        [
            (0.0, "IS", "0x6fcf97", 200, 200, 400),
            (0.5, "LIYE", "0x6fcf97", 200, 400, 600),
        ],
    ),
    # SCENE 9 (3s) - Olive Green | boy + smiley (spaced so words don't overlap)
    (
        3,
        "0x4a5d23",
        [
            ("boy.png", 400, "W-w-50", 300, 0.0),
            ("smiley.png", 200, 50, 700, 0.0),
        ],
        [
            (0.0, "TO", "0xeb5757", 150, 80, 200),
            (0.5, "YAAD", "0xffffff", 220, 80, 480),   # gap after TO
            (1.0, "RAKHIYE", "0x6fcf97", 180, 80, 720), # gap after YAAD, clear of smiley
            (1.5, "DOST", "0xeeb62e", 200, 320, 960),   # right of smiley, gap after RAKHIYE
        ],
    ),
    # SCENE 10 (4s) - Olive Green | smiley
    (
        4,
        "0x4a5d23",
        [
            ("smiley.png", 250, 50, "H-h-200", 0.0),
        ],
        [
            (0.0, "SIRF", "0x6fcf97", 180, 80, 200),
            (0.5, "AAPKA DOST", "0xeeb62e", 180, 80, 400),
            (1.0, "NAHI", "0xffffff", 180, 450, 600),
            (1.5, "WO AAPKA", "0xeeb62e", 180, 80, 800),
            (2.0, "HAI", "0xeb5757", 250, 80, 1050),
        ],
    ),
]


def build_scene_filter(
    duration: float,
    images: list,
    texts: list,
    font_path: str,
) -> str:
    """
    Build filter_complex: overlay chain FIRST (on [0:v]), then drawtext chain.
    Input 0 = background. Inputs 1..N = image files. Output = last drawtext label.
    """
    font = font_path.replace("\\", "/")
    parts = []

    if not images:
        # No images: start drawtext from [0:v]
        prev = "0:v"
    else:
        # Scale each image: [1:v]scale=400:-2[img0]; [2:v]scale=250:-2[img1]; ...
        for i, (_, scale_w, _, _, t_start) in enumerate(images):
            in_label = f"{i + 1}:v"
            out_label = f"img{i}"
            parts.append(f"[{in_label}]scale={scale_w}:-2[{out_label}];")

        # Overlay chain: [0:v][img0]overlay[bg0]; [bg0][img1]overlay[bg1]; ...
        prev = "0:v"
        for i, (_, _, x, y, t_start) in enumerate(images):
            x_expr = overlay_xy_expr(x)
            y_expr = overlay_xy_expr(y)
            # Quote only expressions (contain letters); literals stay unquoted
            x_str = f"'{x_expr}'" if not isinstance(x, int) else x_expr
            y_str = f"'{y_expr}'" if not isinstance(y, int) else y_expr
            next_label = f"bg{i}"
            parts.append(
                f"[{prev}][img{i}]overlay=x={x_str}:y={y_str}:enable='between(t,{t_start},{duration})'[{next_label}];"
            )
            prev = next_label
        prev = f"bg{len(images) - 1}"

    # Drawtext chain
    for i, (t_start, text, color, size, x, y) in enumerate(texts):
        next_label = f"v{i + 1}"
        safe_text = escape_drawtext(text)
        segment = (
            f"[{prev}]drawtext=fontfile='{font}':text='{safe_text}':"
            f"fontcolor={color}:fontsize={size}:x={x}:y={y}:"
            f"enable='between(t,{t_start},{duration})'[{next_label}]"
        )
        if i < len(texts) - 1:
            segment += ";"
        parts.append(segment)
        prev = next_label

    return "".join(parts)


def create_scene(
    scene_index: int,
    duration: float,
    bg_hex: str,
    images: list,
    texts: list,
    out_path: str,
) -> bool:
    """
    Generate one scene segment as MP4 (no audio).
    images: [(filename, scale_w, x, y, t_start), ...]
    texts: [(t_start, text, color_hex, size, x, y), ...]
    Overlays are applied first, then drawtext. Returns True on success.
    """
    if not os.path.isfile(FONT_PATH):
        print(f"Missing font: {FONT_PATH}", file=sys.stderr)
        return False

    # Resolve image paths (all in script dir)
    image_paths = []
    for (filename, *rest) in images:
        path = os.path.join(SCRIPT_DIR, filename)
        if not os.path.isfile(path):
            print(f"Missing image: {path}", file=sys.stderr)
            return False
        image_paths.append(path)

    filter_complex = build_scene_filter(duration, images, texts, FONT_PATH)

    # Build command: -i color, then -loop 1 -i for each image
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c={bg_hex}:s={WIDTH}x{HEIGHT}:d={duration}:r={FPS}",
    ]
    for p in image_paths:
        cmd.extend(["-loop", "1", "-i", p])

    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", f"[v{len(texts)}]",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-t", str(duration),
        out_path,
    ])

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Scene {scene_index + 1} failed:", result.stderr, file=sys.stderr)
        return False
    return True


def get_video_duration_sec(path: str) -> float:
    """Return duration of video file in seconds via ffprobe."""
    r = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", path,
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if r.returncode != 0 or not r.stdout.strip():
        return 0.0
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def merge_voice_into_video(video_path: str, voice_path: str) -> bool:
    """Mux voice audio into video. Pads short audio with silence, trims long audio to video length."""
    duration = get_video_duration_sec(video_path)
    if duration <= 0:
        return False
    temp_path = video_path + ".with_voice.mp4"
    # Trim to video duration then pad to same (so we get exactly duration seconds of audio)
    filter_complex = f"[1:a]atrim=end={duration},apad=whole_dur={duration}[a]"
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", voice_path,
        "-filter_complex", filter_complex,
        "-map", "0:v", "-map", "[a]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-t", str(duration), temp_path,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        print("Voice merge failed:", r.stderr, file=sys.stderr)
        return False
    os.replace(temp_path, video_path)
    return True


def download_missing_assets():
    """Download missing transparent PNGs into SCRIPT_DIR."""
    # (filename, direct_url) - use transparent/cartoon-style assets where possible
    urls = [
        ("smiley.png", "https://raw.githubusercontent.com/twitter/twemoji/v14.0.1/assets/72x72/1f600.png"),
        ("tigers.png", "https://pngimg.com/d/tiger_PNG548.png"),
        ("duck.png", "https://pngimg.com/d/duck_PNG5014.png"),
        ("kitten.png", "https://pngimg.com/d/cat_PNG50497.png"),
        ("boy.png", "https://cdn-icons-png.flaticon.com/512/4140/4140047.png"),
    ]
    for filename, url in urls:
        path = os.path.join(SCRIPT_DIR, filename)
        if os.path.isfile(path):
            continue
        print(f"Downloading {filename} ...")
        try:
            r = subprocess.run(
                ["curl", "-sL", "-o", path, url],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=SCRIPT_DIR,
            )
            if r.returncode != 0 or not os.path.isfile(path):
                print(f"  Failed: {filename}", file=sys.stderr)
        except Exception as e:
            print(f"  Error: {e}", file=sys.stderr)


def main():
    download_missing_assets()

    if not os.path.isfile(FONT_PATH):
        print(f"Missing font: {FONT_PATH}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(SCENES_DIR, exist_ok=True)
    segment_paths = []

    for i, scene in enumerate(SCENES):
        duration, bg_hex, images, texts = scene
        out_name = f"scene_{i + 1:03d}.mp4"
        out_path = os.path.join(SCENES_DIR, out_name)
        segment_paths.append(out_path)
        print(f"Creating scene {i + 1}/{len(SCENES)}: {out_name} ({duration}s, {len(images)} images)")
        if not create_scene(i, duration, bg_hex, images, texts, out_path):
            sys.exit(1)

    with open(CONCAT_LIST_PATH, "w") as f:
        for p in segment_paths:
            path_escaped = p.replace("'", "'\\''")
            f.write(f"file '{path_escaped}'\n")

    print("Concatenating segments -> final_video.mp4")
    result = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", CONCAT_LIST_PATH, "-c", "copy", OUTPUT_PATH],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("Concat failed:", result.stderr, file=sys.stderr)
        sys.exit(1)

    for p in segment_paths:
        try:
            os.remove(p)
        except OSError as e:
            print(f"Warning: could not remove {p}: {e}", file=sys.stderr)
    try:
        os.remove(CONCAT_LIST_PATH)
    except OSError:
        pass
    try:
        os.rmdir(SCENES_DIR)
    except OSError:
        pass

    # Add voice if present
    voice_path = None
    for name in VOICE_FILENAMES:
        p = os.path.join(SCRIPT_DIR, name)
        if os.path.isfile(p):
            voice_path = p
            break
    if voice_path:
        print("Adding voice to video...")
        if merge_voice_into_video(OUTPUT_PATH, voice_path):
            print("Voice added.")
        else:
            print("Voice merge failed; output is video-only.", file=sys.stderr)
    else:
        print("No voice file found (voice.mp3 / voice.m4a / voice.aac / voice.wav). Output is video-only.")

    print("Done:", OUTPUT_PATH)


if __name__ == "__main__":
    main()
