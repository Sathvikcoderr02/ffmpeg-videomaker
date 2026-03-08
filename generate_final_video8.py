#!/usr/bin/env python3
"""
Vertical typography video pipeline (1080x1920) → final_video8.mp4.
6 scenes. Letterbox drawbox y=600 h=720. Stencil font + shadow. TTS Sarvam from .env.
Images downloaded from web and overlaid on scenes 1 and 6. Fallback silent WAV if API key missing/fails.
"""

import base64
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
import urllib.error

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WIDTH = 1080
HEIGHT = 1920
FPS = 30
TTS_URL = "https://api.sarvam.ai/text-to-speech"
SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY", "your_sarvam_api_key_here")

STENCIL_FONT = os.path.join(SCRIPT_DIR, "stencil_font.ttf")
OUTPUT_MP4 = os.path.join(SCRIPT_DIR, "final_video8.mp4")
SEGMENTS_DIR = os.path.join(SCRIPT_DIR, "video8_segments")
CONCAT_LIST = os.path.join(SCRIPT_DIR, "scenes_v8.txt")

ASSETS = {
    "stencil_font.ttf": [
        "https://raw.githubusercontent.com/google/fonts/main/ofl/blackopsone/BlackOpsOne-Regular.ttf",
        "https://github.com/google/fonts/raw/main/ofl/blackopsone/BlackOpsOne-Regular.ttf",
    ],
    "scene1_img.png": [
        "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/2b50.png",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e7/Sparkles_Emoji.png/512px-Sparkles_Emoji.png",
    ],
    "scene6_img.png": [
        "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/2728.png",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e7/Sparkles_Emoji.png/512px-Sparkles_Emoji.png",
    ],
}


def _load_dotenv():
    env_path = os.path.join(SCRIPT_DIR, ".env")
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
SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY", "your_sarvam_api_key_here")


def download_assets():
    try:
        import requests
        def get(url):
            r = requests.get(
                url,
                timeout=30,
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) VideoPipeline/1.0"},
            )
            r.raise_for_status()
            return r.content
    except ImportError:
        def get(url):
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) VideoPipeline/1.0"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read()

    for fname, urls in ASSETS.items():
        path = os.path.join(SCRIPT_DIR, fname)
        if not os.path.isfile(path):
            urls_list = [urls] if isinstance(urls, str) else urls
            for j, url in enumerate(urls_list):
                try:
                    if j > 0:
                        import time
                        time.sleep(1.5)
                    print(f"Downloading {fname} ...")
                    data = get(url)
                    if data and len(data) > 100:
                        with open(path, "wb") as f:
                            f.write(data)
                        print(f"  Saved {path}")
                        break
                except Exception as e:
                    print(f"  Try failed {fname}: {e}", file=sys.stderr)
            if not os.path.isfile(path):
                print(f"  ERROR: Could not download {fname}. Asset must be downloaded from web.", file=sys.stderr)
                sys.exit(1)


def generate_audio(text: str, filename: str) -> bool:
    if not text or not text.strip():
        _silent_wav(filename, 0.5)
        return True
    key = os.environ.get("SARVAM_API_KEY", SARVAM_API_KEY)
    if not key or key == "your_sarvam_api_key_here":
        dur = max(0.5, min(20.0, len(text) * 0.08))
        _silent_wav(filename, dur)
        print(f"  No API key: dummy audio {dur:.2f}s -> {filename}")
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
        headers={"Content-Type": "application/json", "api-subscription-key": key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            body = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err = e.read().decode() if e.fp else ""
        print(f"  TTS API error {e.code}: {err[:150]}", file=sys.stderr)
        _silent_wav(filename, max(0.5, min(20.0, len(text) * 0.08)))
        return True
    except Exception as e:
        print(f"  TTS failed: {e}", file=sys.stderr)
        _silent_wav(filename, max(0.5, min(20.0, len(text) * 0.08)))
        return True
    audios = body.get("audios") or []
    if not audios:
        _silent_wav(filename, max(0.5, min(20.0, len(text) * 0.08)))
        return True
    with open(filename, "wb") as f:
        f.write(base64.b64decode(audios[0]))
    return True


def _silent_wav(path: str, duration_sec: float):
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", str(duration_sec), "-acodec", "pcm_s16le", path],
        capture_output=True,
        timeout=10,
    )


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
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if r.returncode == 0 and r.stdout.strip():
        return float(r.stdout.strip())
    return 2.0


def escape_drawtext(s: str) -> str:
    # For filter_complex_script: backslash and double single-quote for apostrophe
    return s.replace("\\", "\\\\").replace("'", "''")


# 6 scenes. Spec layout; ONCE/THEN/GOD at 140 so "GOD" does not cut off at x=100. Images from web for scenes 1 & 6.
SCENES = [
    {"transcript": "Once someone asked God", "band_color": "0x354256", "image": {"path": "scene1_img.png", "scale_w": 180, "x": "main_w-overlay_w-60", "y": 680, "t": 0.0}, "texts": [
        {"text": "ONCE", "color": "0xffffff", "size": 140, "x": 100, "y": 750, "t": 0.0},
        {"text": "SOMEONE ASKED GOD", "color": "0xb0b8c4", "size": 76, "x": 100, "y": 950, "t": 0.5},
    ]},
    {"transcript": "If everything is already written in destiny,", "band_color": "0xf4f4f4", "image": None, "texts": [
        {"text": "IF EVERYTHING", "color": "0x354256", "size": 92, "x": 100, "y": 680, "t": 0.0},
        {"text": "IS ALREADY WRITTEN", "color": "0x354256", "size": 84, "x": 100, "y": 800, "t": 0.8},
        {"text": "IN DESTINY,", "color": "0x354256", "size": 92, "x": 100, "y": 920, "t": 1.6},
    ]},
    {"transcript": "Then why should I make a wish?", "band_color": "0x6d849b", "image": None, "texts": [
        {"text": "THEN", "color": "0xffffff", "size": 140, "x": 100, "y": 700, "t": 0.0},
        {"text": "WHY SHOULD", "color": "0xffffff", "size": 100, "x": 100, "y": 880, "t": 0.5},
        {"text": "I MAKE A WISH?\"", "color": "0xffffff", "size": 88, "x": 100, "y": 1010, "t": 1.0},
    ]},
    {"transcript": "God smiled and replied,", "band_color": "0x354256", "image": None, "texts": [
        {"text": "GOD", "color": "0xffffff", "size": 140, "x": 100, "y": 750, "t": 0.0},
        {"text": "SMILED AND REPLIED,", "color": "0xb0b8c4", "size": 84, "x": 100, "y": 950, "t": 0.5},
    ]},
    {"transcript": "Maybe on some pages I have written", "band_color": "0xf4f4f4", "image": None, "texts": [
        {"text": "MAYBE ON SOME", "color": "0x354256", "size": 92, "x": 100, "y": 680, "t": 0.0},
        {"text": "PAGES", "color": "0x354256", "size": 140, "x": 100, "y": 800, "t": 0.6},
        {"text": "I HAVE WRITTEN", "color": "0x354256", "size": 92, "x": 100, "y": 980, "t": 1.2},
    ]},
    {"transcript": "AS YOU WISH", "band_color": "0x354256", "image": {"path": "scene6_img.png", "scale_w": 160, "x": 50, "y": 720, "t": 0.0}, "texts": [
        {"text": "AS YOU WISH", "color": "0xffffff", "size": 140, "x": "(w-tw)/2", "y": 850, "t": 0.0},
    ]},
]


def create_scene_video(scene_data: dict, audio_path: str, output_path: str, duration: float) -> bool:
    if not os.path.isfile(STENCIL_FONT):
        print("  Missing stencil_font.ttf", file=sys.stderr)
        return False

    parts = []
    vid = "0:v"
    band = scene_data.get("band_color")
    if band:
        parts.append(f"[{vid}]drawbox=y=600:w=1080:h=720:color={band}:t=fill[bg]")
        vid = "bg"

    im = scene_data.get("image")
    img_path = None
    if im:
        path = os.path.join(SCRIPT_DIR, im["path"])
        if os.path.isfile(path):
            img_path = path
            w, x, y, t0 = im.get("scale_w", 200), im["x"], im["y"], im.get("t", 0.0)
            t0_esc = str(t0).replace(",", "\\,")
            parts.append(f"[1:v]scale={w}:-1[img]")
            parts.append(f"[{vid}][img]overlay={x}:{y}:enable='gte(t\\,{t0_esc})'[v1]")
            vid = "v1"

    shadow_opts = "shadowcolor=black@0.6:shadowx=4:shadowy=4"
    next_idx = 0
    for line in scene_data.get("texts") or []:
        t = line["t"]
        text = escape_drawtext(line["text"])
        color = line.get("color", "0xffffff")
        size = line["size"]
        x = line["x"]
        y = line["y"]
        x_str = str(x)
        t_esc = str(t).replace(",", "\\,")
        draw = f"[{vid}]drawtext=fontfile='{STENCIL_FONT}':text='{text}':fontsize={size}:fontcolor={color}:x={x_str}:y={y}:{shadow_opts}:enable='gte(t\\,{t_esc})'"
        parts.append(draw + f"[tx{next_idx}]")
        vid = f"tx{next_idx}"
        next_idx += 1

    parts.append(f"[{vid}]copy[outv]")
    filter_body = ";".join(parts)

    fd, filter_script = tempfile.mkstemp(suffix=".txt")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(filter_body)
    except Exception:
        os.close(fd)
        try:
            os.remove(filter_script)
        except OSError:
            pass
        raise

    try:
        cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=black:s={WIDTH}x{HEIGHT}:d={duration}:r={FPS}"]
        audio_idx = 1
        if im and img_path:
            cmd.extend(["-loop", "1", "-i", img_path])
            audio_idx = 2
        cmd.extend(["-i", audio_path])
        cmd.extend(["-filter_complex_script", filter_script, "-map", "[outv]", "-map", f"{audio_idx}:a"])
        cmd.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-shortest", output_path])
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    finally:
        try:
            os.remove(filter_script)
        except OSError:
            pass
    if r.returncode != 0:
        print(f"  FFmpeg error: {r.stderr[-600:]}", file=sys.stderr)
        return False
    return True


def concat_segments(segment_paths: list, out_mp4: str) -> bool:
    with open(CONCAT_LIST, "w") as f:
        for p in segment_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")
    r = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", CONCAT_LIST, "-c", "copy", out_mp4],
        capture_output=True,
        text=True,
        timeout=180,
        cwd=SCRIPT_DIR,
    )
    if r.returncode != 0:
        print(f"  Concat error: {r.stderr[-500:]}", file=sys.stderr)
        return False
    return True


def cleanup(segment_mp4s: list, wavs: list):
    for p in segment_mp4s + wavs:
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


def main():
    os.makedirs(SEGMENTS_DIR, exist_ok=True)
    print("Step 1: Download assets")
    download_assets()
    print("Step 2: Generate TTS audio per scene")
    wavs = []
    for i, scene in enumerate(SCENES):
        wav = os.path.join(SEGMENTS_DIR, f"scene_{i:02d}.wav")
        generate_audio(scene["transcript"], wav)
        wavs.append(wav)
    print("Step 3: Measure audio durations")
    durations = [get_audio_duration_sec(w) for w in wavs]
    for i, (w, d) in enumerate(zip(wavs, durations)):
        print(f"  {os.path.basename(w)}: {d:.2f}s")
    print("Step 4: Generate scene videos")
    segments = []
    for i, (scene, dur) in enumerate(zip(SCENES, durations)):
        out_mp4 = os.path.join(SEGMENTS_DIR, f"scene_{i:02d}.mp4")
        if create_scene_video(scene, wavs[i], out_mp4, dur):
            segments.append(out_mp4)
        else:
            print(f"  Failed scene {i}", file=sys.stderr)
            sys.exit(1)
    print("Step 5: Concatenate to final_video8.mp4")
    if not concat_segments(segments, OUTPUT_MP4):
        sys.exit(1)
    print(f"  Written {OUTPUT_MP4}")
    print("Step 6: Cleanup")
    cleanup(segments, wavs)
    print("Done.")


if __name__ == "__main__":
    main()
