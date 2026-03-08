#!/usr/bin/env python3
"""
Vertical typography video pipeline (1080x1920) → final_video6.mp4.
Steps: 1) Download assets  2) TTS per scene (Sarvam Bulbul v3)  3) Measure duration
4) Per-scene MP4: letterbox drawbox → overlay image → watermark (white@0.15) → foreground text
5) Concat  6) Cleanup. API key from .env. 30fps, libx264. Thick condensed block font (Anton).
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

FONT_PATH = os.path.join(SCRIPT_DIR, "anton_font.ttf")
OUTPUT_MP4 = os.path.join(SCRIPT_DIR, "final_video6.mp4")
SEGMENTS_DIR = os.path.join(SCRIPT_DIR, "video6_segments")
CONCAT_LIST = os.path.join(SCRIPT_DIR, "scenes_v6.txt")

ASSETS = {
    "anton_font.ttf": "https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf",
    "tiny_cat.png": [
        "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f431.png",
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


# -----------------------------------------------------------------------------
# STEP 1: ASSET DOWNLOADER (requests / urllib)
# -----------------------------------------------------------------------------
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
                print(f"  ERROR: Could not download {fname} from any URL. Asset must be downloaded from web.", file=sys.stderr)
                sys.exit(1)


# -----------------------------------------------------------------------------
# STEP 2: TTS (Sarvam) + fallback silent WAV len(text)*0.08
# -----------------------------------------------------------------------------
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


# -----------------------------------------------------------------------------
# STEP 3: SCENE CONFIG — watermark (white@0.15) drawn FIRST, then foreground
# -----------------------------------------------------------------------------
def escape_drawtext(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "'\\''")


SCENES = [
    {
        "transcript": "How do I explain it to someone",
        "band_color": "0x62785d",
        "image": {"path": "tiny_cat.png", "scale_w": 120, "x": 200, "y": 1050, "t": 0.0},
        "watermark": {"text": "HOW", "size": 400, "x": "(w-tw)/2", "y": 750, "t": 0.0},
        "texts": [
            {"text": "HOW DO I", "color": "0xFFFFFF", "size": 130, "x": 200, "y": 700, "t": 0.0},
            {"text": "EXPLAIN", "color": "0xd2ccb9", "size": 130, "x": "(w-tw)/2", "y": 840, "t": 0.5},
            {"text": "IT TO SOMEONE", "color": "0xFFFFFF", "size": 100, "x": 200, "y": 980, "t": 1.0},
        ],
    },
    {
        "transcript": "That my parents are strict",
        "band_color": "0xa3b19b",
        "image": {"path": "tiny_cat.png", "scale_w": 120, "x": 300, "y": 1100, "t": 0.0},
        "watermark": {"text": "STRICT!!", "size": 350, "x": "(w-tw)/2", "y": 800, "t": 0.0},
        "texts": [
            {"text": "THAT MY", "color": "0xFFFFFF", "size": 120, "x": "(w-tw)/2", "y": 750, "t": 0.0},
            {"text": "PARENTS ARE", "color": "0xFFFFFF", "size": 120, "x": "(w-tw)/2", "y": 880, "t": 0.5},
            {"text": "STRICT!!", "color": "0x62785d", "size": 150, "x": "(w-tw)/2", "y": 1020, "t": 1.0},
        ],
    },
    {
        "transcript": "But not that strict",
        "band_color": "0xd2ccb9",
        "image": {"path": "tiny_cat.png", "scale_w": 120, "x": "(main_w-overlay_w)/2", "y": 1100, "t": 0.0},
        "watermark": {"text": "HUH..", "size": 350, "x": "(w-tw)/2", "y": 800, "t": 0.0},
        "texts": [
            {"text": "BUT!", "color": "0x62785d", "size": 150, "x": "(w-tw)/2", "y": 750, "t": 0.0},
            {"text": "NOT THAT", "color": "0x62785d", "size": 120, "x": "(w-tw)/2", "y": 910, "t": 0.5},
            {"text": "STRICT", "color": "0x62785d", "size": 120, "x": "(w-tw)/2", "y": 1050, "t": 0.9},
        ],
    },
    {
        "transcript": "Like they let me go out",
        "band_color": "0xd2ccb9",
        "image": {"path": "tiny_cat.png", "scale_w": 120, "x": 600, "y": 1050, "t": 0.0},
        "watermark": None,
        "texts": [
            {"text": "LIKE THEY", "color": "0x62785d", "size": 130, "x": 150, "y": 750, "t": 0.0},
            {"text": "LET ME GO", "color": "0xa3b19b", "size": 160, "x": 150, "y": 890, "t": 0.5},
            {"text": "OUT", "color": "0xa3b19b", "size": 140, "x": "(w-tw)/2", "y": 1020, "t": 1.0},
        ],
    },
    {
        "transcript": "But they also won't",
        "band_color": "0x62785d",
        "image": {"path": "tiny_cat.png", "scale_w": 120, "x": 650, "y": 1050, "t": 0.0},
        "watermark": None,
        "texts": [
            {"text": "BUT THEY", "color": "0xa3b19b", "size": 120, "x": "(w-tw)/2", "y": 720, "t": 0.0},
            {"text": "ALSO", "color": "0xa3b19b", "size": 160, "x": "(w-tw)/2", "y": 850, "t": 0.35},
            {"text": "WON'T", "color": "0xa3b19b", "size": 160, "x": "(w-tw)/2", "y": 1000, "t": 0.7},
        ],
    },
    {
        "transcript": "I have freedom but I also don't",
        "band_color": "0x62785d",
        "image": {"path": "tiny_cat.png", "scale_w": 120, "x": 700, "y": 1100, "t": 0.0},
        "watermark": None,
        "texts": [
            {"text": "I", "color": "0xa3b19b", "size": 120, "x": 150, "y": 700, "t": 0.0},
            {"text": "HAVE FREEDOM", "color": "0xa3b19b", "size": 120, "x": 150, "y": 780, "t": 0.25},
            {"text": "BUT I ALSO", "color": "0xFFFFFF", "size": 110, "x": 150, "y": 900, "t": 0.9},
            {"text": "DON'T", "color": "0xFFFFFF", "size": 120, "x": 150, "y": 1020, "t": 1.25},
        ],
    },
    {
        "transcript": "I can do what I want, but I also can't",
        "band_color": "0xd2ccb9",
        "image": {"path": "tiny_cat.png", "scale_w": 120, "x": 800, "y": 1050, "t": 0.0},
        "watermark": None,
        "texts": [
            {"text": "I CAN DO WHAT I WANT,", "color": "0x62785d", "size": 80, "x": "(w-tw)/2", "y": 800, "t": 0.0},
            {"text": "BUT I ALSO CAN'T", "color": "0xFFFFFF", "size": 80, "x": "(w-tw)/2", "y": 920, "t": 1.5},
        ],
    },
    {
        "transcript": "I need a word for this concept",
        "band_color": "0x62785d",
        "image": {"path": "tiny_cat.png", "scale_w": 120, "x": 800, "y": 1000, "t": 0.0},
        "watermark": {"text": "CONCEPT", "size": 300, "x": "(w-tw)/2", "y": 800, "t": 0.0},
        "texts": [
            {"text": "I NEED A WORD FOR", "color": "0xa3b19b", "size": 90, "x": "(w-tw)/2", "y": 750, "t": 0.0},
            {"text": "THIS CONCEPT", "color": "0xd2ccb9", "size": 130, "x": "(w-tw)/2", "y": 880, "t": 1.0},
        ],
    },
]


# -----------------------------------------------------------------------------
# STEP 4: create_scene_video — drawbox → overlay → watermark (white@0.15) → foreground
# -----------------------------------------------------------------------------
def create_scene_video(scene_data: dict, audio_path: str, output_path: str, duration: float) -> bool:
    fontfile = FONT_PATH
    if not os.path.isfile(fontfile):
        print(f"  Missing font: {fontfile}", file=sys.stderr)
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
            w, x, y, t0 = im.get("scale_w", 120), im["x"], im["y"], im.get("t", 0.0)
            t0_esc = str(t0).replace(",", "\\,")
            parts.append(f"[1:v]scale={w}:-1[img]")
            parts.append(f"[{vid}][img]overlay={x}:{y}:enable='gte(t\\,{t0_esc})'[v1]")
            vid = "v1"

    wm = scene_data.get("watermark")
    if wm:
        text = escape_drawtext(wm["text"])
        size = wm["size"]
        x, y, t = wm["x"], wm["y"], wm["t"]
        t_esc = str(t).replace(",", "\\,")
        parts.append(
            f"[{vid}]drawtext=fontfile='{fontfile}':text='{text}':fontsize={size}:fontcolor=white@0.15:"
            f"x={x}:y={y}:enable='gte(t\\,{t_esc})'[v2]"
        )
        vid = "v2"

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
        parts.append(
            f"[{vid}]drawtext=fontfile='{fontfile}':text='{text}':fontsize={size}:fontcolor={color}:"
            f"x={x_str}:y={y}:enable='gte(t\\,{t_esc})'[tx{next_idx}]"
        )
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


# -----------------------------------------------------------------------------
# STEP 5: CONCAT + CLEANUP
# -----------------------------------------------------------------------------
def concat_segments(segment_paths: list, out_mp4: str) -> bool:
    with open(CONCAT_LIST, "w") as f:
        for p in segment_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")
    r = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", CONCAT_LIST, "-c", "copy", out_mp4],
        capture_output=True,
        text=True,
        timeout=120,
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


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------
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

    print("Step 5: Concatenate to final_video6.mp4")
    if not concat_segments(segments, OUTPUT_MP4):
        sys.exit(1)
    print(f"  Written {OUTPUT_MP4}")

    print("Step 6: Cleanup")
    cleanup(segments, wavs)
    print("Done.")


if __name__ == "__main__":
    main()
