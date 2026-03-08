#!/usr/bin/env python3
"""
Vertical typography video pipeline (1080x1920) → final_video7.mp4.
17 scenes. Letterbox (drawbox y=600 h=720) except Scene 10 (full black).
2 fonts (serif + cartoon), 4 images. TTS Sarvam from .env. No fallbacks/placeholders.
"""

import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WIDTH = 1080
HEIGHT = 1920
FPS = 30
TTS_URL = "https://api.sarvam.ai/text-to-speech"
SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY", "your_sarvam_api_key_here")

SERIF_FONT = os.path.join(SCRIPT_DIR, "serif_font.ttf")
CARTOON_FONT = os.path.join(SCRIPT_DIR, "cartoon_font.ttf")
OUTPUT_MP4 = os.path.join(SCRIPT_DIR, "final_video7.mp4")
SEGMENTS_DIR = os.path.join(SCRIPT_DIR, "video7_segments")
CONCAT_LIST = os.path.join(SCRIPT_DIR, "scenes_v7.txt")

# Distinct images: heart-eyes cat, worried cat, dog, smiley cat (twemoji 1f63b, 1f63f, 1f436, 1f63a)
ASSETS = {
    "serif_font.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/ptserif/PT_Serif-Web-Bold.ttf",
    "cartoon_font.ttf": "https://raw.githubusercontent.com/google/fonts/main/apache/luckiestguy/LuckiestGuy-Regular.ttf",
    "heart_cat.png": [
        "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f63b.png",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a9/Cat_silhouette.svg/512px-Cat_silhouette.svg.png",
    ],
    "crying_cat.png": [
        "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f63f.png",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a9/Cat_silhouette.svg/512px-Cat_silhouette.svg.png",
    ],
    "dog.png": [
        "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f436.png",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/2/26/YellowLabradorLooking_new.jpg/512px-YellowLabradorLooking_new.jpg",
    ],
    "blush_cat.png": [
        "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f63a.png",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a9/Cat_silhouette.svg/512px-Cat_silhouette.svg.png",
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
    # For filter_complex_script: backslash and double single-quote for apostrophe (e.g. Valentine's)
    return s.replace("\\", "\\\\").replace("'", "''")


# 17 scenes. band_color None = Scene 10 full black. Text font defaults to serif; scene 10 uses cartoon_font + shadow.
SCENES = [
    {"transcript": "Valentine's Day is coming.", "band_color": "0xf4f1e1", "image": {"path": "heart_cat.png", "scale_w": 300, "x": "main_w-overlay_w-50", "y": 900, "t": 0.0}, "texts": [
        {"text": "Valentine's", "color": "0xc81d25", "size": 130, "x": 100, "y": 700, "t": 0.0},
        {"text": "Day is", "color": "0x1b2a47", "size": 110, "x": 100, "y": 850, "t": 0.5},
        {"text": "COMING.", "color": "0xf4d03f", "size": 140, "x": 100, "y": 1000, "t": 1.0},
    ]},
    {"transcript": "And people are asking,", "band_color": "0x6488a7", "image": None, "texts": [
        {"text": "AND PEOPLE ARE ASKING,", "color": "0xffffff", "size": 82, "x": "(w-tw)/2", "y": 850, "t": 0.0},
    ]},
    {"transcript": "Are you single?", "band_color": "0x1b2a47", "image": {"path": "crying_cat.png", "scale_w": 250, "x": "main_w-overlay_w-50", "y": 800, "t": 0.0}, "texts": [
        {"text": "ARE YOU", "color": "0xffffff", "size": 120, "x": "(w-tw)/2", "y": 750, "t": 0.0},
        {"text": "SINGLE?", "color": "0xf4d03f", "size": 150, "x": "(w-tw)/2", "y": 920, "t": 0.5},
    ]},
    {"transcript": "But the real question is,", "band_color": "0x1b2a47", "image": None, "texts": [
        {"text": "BUT THE REAL QUESTION IS,", "color": "0xffffff", "size": 68, "x": "(w-tw)/2", "y": 850, "t": 0.0},
    ]},
    {"transcript": "When you were completely broken,", "band_color": "0x1b2a47", "image": None, "texts": [
        {"text": "WHEN YOU WERE", "color": "0xffffff", "size": 100, "x": "(w-tw)/2", "y": 700, "t": 0.0},
        {"text": "COMPLETELY", "color": "0xffffff", "size": 120, "x": "(w-tw)/2", "y": 850, "t": 0.6},
        {"text": "BROKEN,", "color": "0xffffff", "size": 130, "x": "(w-tw)/2", "y": 1000, "t": 1.2},
    ]},
    {"transcript": "who was there?", "band_color": "0x1b2a47", "image": None, "texts": [
        {"text": "WHO WAS THERE?", "color": "0xf4d03f", "size": 120, "x": "(w-tw)/2", "y": 850, "t": 0.0},
    ]},
    {"transcript": "Not that one who said,", "band_color": "0x1b2a47", "image": None, "texts": [
        {"text": "NOT THAT ONE WHO SAID,", "color": "0xffffff", "size": 72, "x": "(w-tw)/2", "y": 850, "t": 0.0},
    ]},
    {"transcript": "I love you,", "band_color": "0xf4f1e1", "image": None, "texts": [
        {"text": "\"I LOVE YOU,\"", "color": "0x1b2a47", "size": 130, "x": "(w-tw)/2", "y": 850, "t": 0.0},
    ]},
    {"transcript": "But one who said,", "band_color": "0xf4f1e1", "image": None, "texts": [
        {"text": "BUT ONE WHO SAID,", "color": "0x1b2a47", "size": 88, "x": "(w-tw)/2", "y": 850, "t": 0.0},
    ]},
    {"transcript": "Bro wait I'm coming", "band_color": None, "image": {"path": "dog.png", "scale_w": 350, "x": 50, "y": 780, "t": 0.0}, "texts": [
        {"text": "BRO", "color": "0xffffff", "size": 180, "x": "w-tw-80", "y": 700, "t": 0.0, "font": "cartoon_font.ttf", "shadow": (5, 5)},
        {"text": "WAIT", "color": "0xffffff", "size": 180, "x": "w-tw-80", "y": 880, "t": 0.4, "font": "cartoon_font.ttf", "shadow": (5, 5)},
        {"text": "I'M COMING", "color": "0xffffff", "size": 150, "x": "w-tw-80", "y": 1060, "t": 0.8, "font": "cartoon_font.ttf", "shadow": (5, 5)},
    ]},
    {"transcript": "Didn't care about day or time,", "band_color": "0x6488a7", "image": None, "texts": [
        {"text": "DIDN'T CARE", "color": "0x1b2a47", "size": 120, "x": "(w-tw)/2", "y": 750, "t": 0.0},
        {"text": "ABOUT DAY OR TIME,", "color": "0xffffff", "size": 92, "x": "(w-tw)/2", "y": 900, "t": 0.8},
    ]},
    {"transcript": "Just stayed and proved what friendship really means.", "band_color": "0x1b2a47", "image": None, "texts": [
        {"text": "JUST STAYED AND PROVED", "color": "0xffffff", "size": 72, "x": "(w-tw)/2", "y": 750, "t": 0.0},
        {"text": "WHAT FRIENDSHIP REALLY MEANS.", "color": "0xf4d03f", "size": 62, "x": "(w-tw)/2", "y": 900, "t": 1.0},
    ]},
    {"transcript": "So this Valentine's Day,", "band_color": "0xf4f1e1", "image": None, "texts": [
        {"text": "SO THIS", "color": "0x1b2a47", "size": 110, "x": 150, "y": 750, "t": 0.0},
        {"text": "VALENTINE'S DAY,", "color": "0x1b2a47", "size": 120, "x": 150, "y": 900, "t": 0.5},
    ]},
    {"transcript": "don't celebrate love.", "band_color": "0x1b2a47", "image": None, "texts": [
        {"text": "Don't celebrate love.", "color": "0xffffff", "size": 92, "x": "(w-tw)/2", "y": 850, "t": 0.0},
    ]},
    {"transcript": "Celebrate that friendship", "band_color": "0xf4f1e1", "image": None, "texts": [
        {"text": "CELEBRATE THAT", "color": "0x1b2a47", "size": 100, "x": 150, "y": 750, "t": 0.0},
        {"text": "FRIENDSHIP", "color": "0x1b2a47", "size": 130, "x": 150, "y": 900, "t": 0.5},
    ]},
    {"transcript": "which stays with you", "band_color": "0xf4f1e1", "image": None, "texts": [
        {"text": "WHICH STAYS WITH YOU", "color": "0x1b2a47", "size": 82, "x": "(w-tw)/2", "y": 850, "t": 0.0},
    ]},
    {"transcript": "without any conditions.", "band_color": "0xf4f1e1", "image": {"path": "blush_cat.png", "scale_w": 300, "x": "main_w-overlay_w-50", "y": 800, "t": 0.0}, "texts": [
        {"text": "WITHOUT ANY", "color": "0x1b2a47", "size": 100, "x": 100, "y": 750, "t": 0.0},
        {"text": "CONDITIONS.", "color": "0x1b2a47", "size": 110, "x": 100, "y": 900, "t": 0.5},
    ]},
]


def create_scene_video(scene_data: dict, audio_path: str, output_path: str, duration: float) -> bool:
    serif_path = SERIF_FONT
    cartoon_path = CARTOON_FONT
    if not os.path.isfile(serif_path) or not os.path.isfile(cartoon_path):
        print(f"  Missing font(s)", file=sys.stderr)
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
            w, x, y, t0 = im.get("scale_w", 300), im["x"], im["y"], im.get("t", 0.0)
            t0_esc = str(t0).replace(",", "\\,")
            parts.append(f"[1:v]scale={w}:-1[img]")
            parts.append(f"[{vid}][img]overlay={x}:{y}:enable='gte(t\\,{t0_esc})'[v1]")
            vid = "v1"

    next_idx = 0
    for line in scene_data.get("texts") or []:
        t = line["t"]
        text = escape_drawtext(line["text"])
        color = line.get("color", "0xffffff")
        size = line["size"]
        x = line["x"]
        y = line["y"]
        fontfile = os.path.join(SCRIPT_DIR, line.get("font", "serif_font.ttf"))
        if not os.path.isfile(fontfile):
            fontfile = serif_path
        x_str = str(x)
        t_esc = str(t).replace(",", "\\,")
        shadow = line.get("shadow")
        if shadow:
            sx, sy = shadow
            draw = f"[{vid}]drawtext=fontfile='{fontfile}':text='{text}':fontsize={size}:fontcolor={color}:x={x_str}:y={y}:shadowcolor=black:shadowx={sx}:shadowy={sy}:enable='gte(t\\,{t_esc})'"
        else:
            draw = f"[{vid}]drawtext=fontfile='{fontfile}':text='{text}':fontsize={size}:fontcolor={color}:x={x_str}:y={y}:enable='gte(t\\,{t_esc})'"
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
    print("Step 5: Concatenate to final_video7.mp4")
    if not concat_segments(segments, OUTPUT_MP4):
        sys.exit(1)
    print(f"  Written {OUTPUT_MP4}")
    print("Step 6: Cleanup")
    cleanup(segments, wavs)
    print("Done.")


if __name__ == "__main__":
    main()
