#!/usr/bin/env python3
"""
Vertical typography video pipeline (1080x1920) → final_video4.mp4.
Steps: 1) Download assets  2) Scene config  3) TTS per scene (Sarvam Bulbul v3)
4) Measure audio duration  5) Generate per-scene MP4  6) Concat  7) Cleanup.
30fps, libx264. Letterbox layout (drawbox middle band). Grunge/stencil font.
"""

import base64
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error


def _load_dotenv():
    """Load .env so SARVAM_API_KEY is set when present in project dir."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.isfile(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip()
                if key and value and value.startswith(('"', "'")):
                    value = value[1:-1].replace("\\n", "\n")
                os.environ.setdefault(key, value)


_load_dotenv()
# Placeholder: replace with your key or set SARVAM_API_KEY in .env
SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY", "your_sarvam_api_key_here")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WIDTH = 1080
HEIGHT = 1920
FPS = 30
TTS_URL = "https://api.sarvam.ai/text-to-speech"

# Font + scene images. Each image can have multiple URLs (tried in order until one works).
# Using jsDelivr CDN (Twemoji) for reliability; no rate limits.
FONT_URL = "https://github.com/google/fonts/raw/main/ofl/blackopsone/BlackOpsOne-Regular.ttf"
FONT_PATH = os.path.join(SCRIPT_DIR, "stencil_font.ttf")
# Format: filename -> list of URLs (first success wins)
IMAGE_URLS = {
    "cat.png": [
        "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f431.png",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a9/Cat_silhouette.svg/512px-Cat_silhouette.svg.png",
    ],
    "instagram_icon.png": [
        "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f4f7.png",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a5/Instagram_icon.png/240px-Instagram_icon.png",
    ],
    "sad_icon.png": [
        "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f625.png",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9f/Emoji_u1f625.svg/240px-Emoji_u1f625.svg.png",
    ],
    "food_icon.png": [
        "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f355.png",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3e/Cute_ball_icon.svg/240px-Cute_ball_icon.svg.png",
    ],
}

OUTPUT_MP4 = os.path.join(SCRIPT_DIR, "final_video4.mp4")
SEGMENTS_DIR = os.path.join(SCRIPT_DIR, "video4_segments")
CONCAT_LIST = os.path.join(SCRIPT_DIR, "scenes_v4.txt")


# -----------------------------------------------------------------------------
# STEP 1: ASSET DOWNLOADER
# -----------------------------------------------------------------------------
def download_assets():
    """Download font and cat image if they don't exist. Uses requests if available else urllib."""
    try:
        import requests
        def get(url):
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            return r.content
    except ImportError:
        def get(url):
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read()

    if not os.path.isfile(FONT_PATH):
        print("Downloading stencil font ...")
        try:
            data = get(FONT_URL)
            with open(FONT_PATH, "wb") as f:
                f.write(data)
            print(f"  Saved {FONT_PATH}")
        except Exception as e:
            print(f"  Font download failed: {e}", file=sys.stderr)
            sys.exit(1)

    for fname, urls in IMAGE_URLS.items():
        path = os.path.join(SCRIPT_DIR, fname)
        if not os.path.isfile(path):
            urls_list = urls if isinstance(urls, (list, tuple)) else [urls]
            saved = False
            for url in urls_list:
                try:
                    print(f"Downloading {fname} ...")
                    data = get(url)
                    if data and len(data) > 100:
                        with open(path, "wb") as f:
                            f.write(data)
                        print(f"  Saved {path}")
                        saved = True
                        break
                except Exception as e:
                    print(f"  Try failed {fname}: {e}", file=sys.stderr)
            if not saved:
                print(f"  All URLs failed for {fname}", file=sys.stderr)


# -----------------------------------------------------------------------------
# STEP 2: SCRIPT & SCENE CONFIGURATIONS
# Letterbox: top/bottom black, middle band drawbox y=600 h=720. x=(w-tw)/2 for text.
# -----------------------------------------------------------------------------
def escape_drawtext(s: str) -> str:
    """Escape for FFmpeg drawtext inside single-quoted value: \ and '."""
    return s.replace("\\", "\\\\").replace("'", "'\\''")  # FFmpeg: '\'' = literal quote


# Image positions chosen so they do NOT overlap centered text (text ~Y 750–950).
# Scene 1: text 750, 900 → cat bottom-right below text at Y=1100.
# Scenes 2–6: text at 850 → icons in corners (above Y≤620 or below Y≥1100).
SCENES = [
    {
        "tts_text": "Who understand you the most",
        "middle_band": True,
        "band_color": "0x6b1326",
        "text_color": "0xFFFFFF",
        "lines": [
            {"text": "WHO UNDERSTAND", "t": 0.0, "size": 110, "y": 750},
            {"text": "YOU THE MOST", "t": 0.5, "size": 110, "y": 880},
        ],
        "image": {"path": "cat.png", "scale_w": 280, "x": 750, "y": 1100},
    },
    {
        "tts_text": "Instagram",
        "middle_band": True,
        "band_color": "0xFFFFFF",
        "text_color": "0x6b1326",
        "lines": [{"text": "INSTAGRAM", "t": 0.0, "size": 150, "y": 850}],
        "image": {"path": "instagram_icon.png", "scale_w": 90, "x": 980, "y": 615},
    },
    {
        "tts_text": "Sad mood",
        "middle_band": True,
        "band_color": "0xFFFFFF",
        "text_color": "0x6b1326",
        "lines": [{"text": "SAD MOOD", "t": 0.0, "size": 150, "y": 850}],
        "image": {"path": "sad_icon.png", "scale_w": 100, "x": 30, "y": 1100},
    },
    {
        "tts_text": "Sad reels",
        "middle_band": True,
        "band_color": "0xFFFFFF",
        "text_color": "0x6b1326",
        "lines": [{"text": "SAD REELS", "t": 0.0, "size": 150, "y": 850}],
        "image": {"path": "sad_icon.png", "scale_w": 80, "x": 30, "y": 620},
    },
    {
        "tts_text": "Hungry",
        "middle_band": True,
        "band_color": "0xFFFFFF",
        "text_color": "0x6b1326",
        "lines": [{"text": "HUNGRY", "t": 0.0, "size": 150, "y": 850}],
        "image": {"path": "food_icon.png", "scale_w": 90, "x": 980, "y": 1100},
    },
    {
        "tts_text": "Food reels",
        "middle_band": True,
        "band_color": "0xFFFFFF",
        "text_color": "0x6b1326",
        "lines": [{"text": "FOOD REELS", "t": 0.0, "size": 150, "y": 850}],
        "image": {"path": "food_icon.png", "scale_w": 90, "x": 30, "y": 1100},
    },
    {
        "tts_text": "It's now me better than my family",
        "middle_band": False,
        "band_color": None,
        "text_color": "0xFFFFFF",
        "lines": [
            {"text": "IT'S NOW ME", "t": 0.0, "size": 120, "y": 780},
            {"text": "BETTER THAN", "t": 0.5, "size": 88, "y": 920},
            {"text": "MY FAMILY", "t": 0.5, "size": 88, "y": 1020},
        ],
        "image": None,
    },
]


# -----------------------------------------------------------------------------
# STEP 3: AUDIO GENERATION (SARVAM AI BULBUL V3)
# -----------------------------------------------------------------------------
def generate_audio(text: str, filename: str, api_key: str) -> bool:
    """Generate TTS WAV via Sarvam. On failure, write dummy silent WAV (len(text)*0.1 sec)."""
    if not text or not text.strip():
        _write_silent_wav(filename, 0.5)
        return True
    if not api_key or api_key == "your_sarvam_api_key_here":
        dur = max(1.0, min(15.0, len(text) * 0.1))
        _write_silent_wav(filename, dur)
        print(f"  No API key: dummy audio {dur:.1f}s -> {filename}")
        return True
    payload = {
        "text": text.strip()[:2500],
        "target_language_code": "en-IN",
        "model": "bulbul:v3",
        "speaker": "shubh",
        "speech_sample_rate": "24000",
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        TTS_URL,
        data=data,
        headers={"Content-Type": "application/json", "api-subscription-key": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            body = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err = e.read().decode() if e.fp else ""
        print(f"  TTS API error {e.code}: {err[:200]}", file=sys.stderr)
        dur = max(1.0, min(15.0, len(text) * 0.1))
        _write_silent_wav(filename, dur)
        return True
    except Exception as e:
        print(f"  TTS failed: {e}", file=sys.stderr)
        dur = max(1.0, min(15.0, len(text) * 0.1))
        _write_silent_wav(filename, dur)
        return True
    audios = body.get("audios") or []
    if not audios:
        dur = max(1.0, min(15.0, len(text) * 0.1))
        _write_silent_wav(filename, dur)
        return True
    with open(filename, "wb") as f:
        f.write(base64.b64decode(audios[0]))
    return True


def _write_silent_wav(path: str, duration_sec: float):
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            f"anullsrc=r=24000:cl=mono", "-t", str(duration_sec),
            "-acodec", "pcm_s16le", path,
        ],
        capture_output=True,
        timeout=10,
    )


# -----------------------------------------------------------------------------
# STEP 4: MEASURE AUDIO DURATION (pydub / mutagen / wave fallback)
# -----------------------------------------------------------------------------
def get_audio_duration_sec(path: str) -> float:
    try:
        from pydub import AudioSegment
        return len(AudioSegment.from_file(path)) / 1000.0
    except Exception:
        pass
    try:
        from mutagen.wave import WAVE
        return WAVE(path).info.length
    except Exception:
        pass
    try:
        import wave
        with wave.open(path, "rb") as w:
            return w.getnframes() / float(w.getframerate())
    except Exception:
        pass
    r = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", path,
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if r.returncode == 0 and r.stdout.strip():
        return float(r.stdout.strip())
    return 2.0


# -----------------------------------------------------------------------------
# STEP 5: FFMPEG FILTERGRAPH — create_scene_video
# -----------------------------------------------------------------------------
def create_scene_video(scene_dict: dict, audio_file: str, output_file: str, duration: float) -> bool:
    """
    Base: color=c=black:s=1080x1920:d=duration.
    Optional drawbox y=600:w=1080:h=720. drawtext with stencil_font, x=(w-tw)/2.
    Optional image overlay (scene 1). Map video + audio to output MP4.
    """
    fontfile = FONT_PATH
    if not os.path.isfile(fontfile):
        print(f"  Missing font: {fontfile}", file=sys.stderr)
        return False

    # Build filter: [0:v] base -> optional drawbox -> drawtext chain -> optional overlay
    parts = []
    vid_label = "0:v"
    if scene_dict.get("middle_band"):
        band_color = scene_dict.get("band_color", "0xFFFFFF")
        parts.append(f"[{vid_label}]drawbox=y=600:w=1080:h=720:color={band_color}:t=fill[bg]")
        vid_label = "bg"

    next_idx = 0
    for line in scene_dict["lines"]:
        t = line["t"]
        text = escape_drawtext(line["text"])
        size = line["size"]
        y = line["y"]
        color = scene_dict.get("text_color", "0xFFFFFF")
        # Quoted enable so comma in gte(t,0.5) doesn't split (text uses '\'' for apostrophe)
        parts.append(
            f"[{vid_label}]drawtext=fontfile='{fontfile}':text='{text}':fontsize={size}:fontcolor={color}:"
            f"x=(w-tw)/2:y={y}:enable='gte(t,{t})'[v{next_idx}]"
        )
        vid_label = f"v{next_idx}"
        next_idx += 1

    img = scene_dict.get("image")
    if img:
        img_path = os.path.join(SCRIPT_DIR, img["path"])
        if os.path.isfile(img_path):
            w, x, y = img.get("scale_w", 300), img.get("x", 730), img.get("y", 1000)
            parts.append(f"[1:v]scale={w}:-1[img]")
            parts.append(f"[{vid_label}][img]overlay={x}:{y}[outv]")
            vid_label = "outv"

    if vid_label != "outv":
        parts.append(f"[{vid_label}]copy[outv]")
    filter_complex = ";".join(parts)

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=black:s={WIDTH}x{HEIGHT}:d={duration}:r={FPS}",
    ]
    audio_idx = 1
    if img and os.path.isfile(os.path.join(SCRIPT_DIR, img["path"])):
        cmd.extend(["-loop", "1", "-i", img_path])
        audio_idx = 2
    cmd.extend(["-i", audio_file])
    cmd.extend(["-filter_complex", filter_complex, "-map", "[outv]", "-map", f"{audio_idx}:a"])
    cmd.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-shortest", output_file])
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        print(f"  FFmpeg error: {r.stderr[-800:]}", file=sys.stderr)
        return False
    return True


# -----------------------------------------------------------------------------
# STEP 6: CONCATENATE segments -> final_video4.mp4
# -----------------------------------------------------------------------------
def concat_segments(segment_paths: list, out_mp4: str) -> bool:
    list_path = CONCAT_LIST
    with open(list_path, "w") as f:
        for p in segment_paths:
            p_abs = os.path.abspath(p)
            f.write(f"file '{p_abs}'\n")
    r = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", out_mp4],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=SCRIPT_DIR,
    )
    if r.returncode != 0:
        print(f"  Concat error: {r.stderr[-800:]}", file=sys.stderr)
        return False
    return True


# -----------------------------------------------------------------------------
# STEP 7: CLEANUP
# -----------------------------------------------------------------------------
def cleanup(segment_paths: list, audio_paths: list):
    for p in segment_paths + audio_paths:
        try:
            if os.path.isfile(p):
                os.remove(p)
        except OSError:
            pass
    try:
        if os.path.isfile(CONCAT_LIST):
            os.remove(CONCAT_LIST)
    except OSError:
        pass
    try:
        if os.path.isdir(SEGMENTS_DIR) and not os.listdir(SEGMENTS_DIR):
            os.rmdir(SEGMENTS_DIR)
    except OSError:
        pass


# -----------------------------------------------------------------------------
# MAIN PIPELINE
# -----------------------------------------------------------------------------
def main():
    os.makedirs(SEGMENTS_DIR, exist_ok=True)

    # 1. Download assets
    print("Step 1: Download assets")
    download_assets()

    # 2 & 3. Generate TTS for each scene
    print("Step 2 & 3: Generate TTS audio per scene")
    audio_files = []
    for i, scene in enumerate(SCENES):
        wav = os.path.join(SEGMENTS_DIR, f"scene_{i:02d}.wav")
        generate_audio(scene["tts_text"], wav, SARVAM_API_KEY)
        audio_files.append(wav)

    # 4. Measure duration of each audio
    print("Step 4: Measure audio durations")
    durations = []
    for wav in audio_files:
        d = get_audio_duration_sec(wav)
        durations.append(d)
        print(f"  {os.path.basename(wav)}: {d:.2f}s")

    # 5. Generate individual MP4 segments
    print("Step 5: Generate scene videos")
    segment_mp4s = []
    for i, (scene, dur) in enumerate(zip(SCENES, durations)):
        out_mp4 = os.path.join(SEGMENTS_DIR, f"scene_{i:02d}.mp4")
        if create_scene_video(scene, audio_files[i], out_mp4, dur):
            segment_mp4s.append(out_mp4)
        else:
            print(f"  Failed scene {i}", file=sys.stderr)
            sys.exit(1)

    # 6. Concatenate
    print("Step 6: Concatenate to final_video4.mp4")
    if not concat_segments(segment_mp4s, OUTPUT_MP4):
        sys.exit(1)
    print(f"  Written {OUTPUT_MP4}")

    # 7. Cleanup
    print("Step 7: Cleanup temporary files")
    cleanup(segment_mp4s, audio_files)
    print("Done.")


if __name__ == "__main__":
    main()
