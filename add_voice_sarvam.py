#!/usr/bin/env python3
"""
Add scene-synced voice to final_video.mp4, final_video2.mp4, final_video3.mp4
using Sarvam AI Bulbul v3. Each scene's on-screen text is spoken in that scene's
time window. Loads SARVAM_API_KEY from .env.
"""

import base64
import json
import os
import subprocess
import sys
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TTS_URL = "https://api.sarvam.ai/text-to-speech"
MAX_CHARS = 2500


def load_dotenv():
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


load_dotenv()
API_KEY = os.environ.get("SARVAM_API_KEY")

# -----------------------------------------------------------------------------
# Language per video: 1 & 2 = Hindi + English (hi-IN), 3 = English + Telugu (te-IN)
# -----------------------------------------------------------------------------
VIDEO_LANGUAGE = {
    "final_video.mp4": "hi-IN",   # Hindi + English
    "final_video2.mp4": "hi-IN",  # Hindi + English
    "final_video3.mp4": "te-IN",  # English + Telugu
}

# -----------------------------------------------------------------------------
# Scene-by-scene text (duration_sec, list of text bits in order) per video.
# Spoken as one sentence per scene so audio matches the scene.
# -----------------------------------------------------------------------------
VIDEO_SCENES = {
    "final_video.mp4": [
        (3, ["Kya", "App", "ko", "ata"]),
        (3, ["APPKE", "Dost", "JAB AAP KO"]),
        (3, ["KYU", "Nahi", "AATA", "??"]),
        (3, ["JAB", "KOI", "DUSRA", "GALI"]),
        (3, ["AAP", "us ki"]),
        (3, ["ASAL", "me", "DOST"]),
        (4, ["dete", "AAP KE", "Father WALA", "HORMONES", "ACTIVE"]),
        (2, ["IS", "LIYE"]),
        (3, ["TO", "YAAD", "RAKHIYE", "DOST"]),
        (4, ["SIRF", "AAPKA DOST", "NAHI", "WO AAPKA", "HAI"]),
    ],
    "final_video2.mp4": [
        (2.0, ["PYAAR FREE", "ME MILTA HAI"]),
        (2.0, ["LEKIN", "sirf", "TEEN"]),
        (1.0, ["AURATO KO"]),
        (1.0, ["BACHHO KO"]),
        (1.0, ["OR KUTTO KO"]),
        (3.0, ["AADMI KO", "pyaar", "FREE", "ME NAHI MILTA"]),
        (2.5, ["USE KUCH", "BAN NA", "padta", "HAI"]),
        (2.5, ["KUCHH", "haasil", "KARNA PADTA HAI"]),
        (2.5, ["APNI EK", "BANANI", "aukaat"]),
        (3.0, ["JAB USKE PAAS", "DENE KE LIYE", "bohot", "KUCHH HOTA"]),
        (3.0, ["TAB JAAKAR", "USE", "pyaar", "MILTA HAI"]),
        (2.0, ["NOTHING IS FREE FOR MEN"]),
        (4.0, ["IS DUNIYA ME", "aadmi", "KO KUCH BHI", "FREE", "ME NAHI MILTA"]),
    ],
    "final_video3.mp4": [
        (3.0, ["Stone", "One", "Enough"]),
        (2.0, ["to break a", "Glass"]),
        (3.0, ["Word is", "One", "Enough"]),
        (2.0, ["TO"]),
        (3.0, ["Second is", "One", "Enough"]),
        (2.0, ["To fall in love with a stranger"]),
        (3.0, ["Kani exams lo pass avadaniki", "Enduku ra oka chapter saripodhu"]),
        (3.0, ["Idhi ekkadi dikkumalina", "Logic ra naayana"]),
    ],
}


def get_video_duration_sec(path: str) -> float:
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


def get_audio_duration_sec(wav_path: str) -> float:
    r = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", wav_path,
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


def text_to_speech(text: str, api_key: str, out_wav: str, language_code: str = "hi-IN") -> bool:
    if not text or not text.strip():
        # Generate silence (0.5s minimal WAV) so concat doesn't break
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "0.5", "-acodec", "pcm_s16le", out_wav],
            capture_output=True,
            timeout=10,
        )
        return True
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS]
    payload = {
        "text": text.strip(),
        "target_language_code": language_code,
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
        err_body = e.read().decode() if e.fp else ""
        print(f"  TTS API error {e.code}: {err_body}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"  TTS failed: {e}", file=sys.stderr)
        return False
    audios = body.get("audios") or []
    if not audios:
        print("  TTS response had no audio", file=sys.stderr)
        return False
    with open(out_wav, "wb") as f:
        f.write(base64.b64decode(audios[0]))
    return True


def build_concat_audio(scene_wavs: list, scene_durations: list, out_wav: str) -> bool:
    """Trim/pad each scene WAV to scene_durations[i], then concat. All must be same sample rate (24k)."""
    if not scene_wavs or len(scene_wavs) != len(scene_durations):
        return False
    n = len(scene_wavs)
    # [0:a]atrim=end=D0,apad=whole_dur=D0[a0]; [1:a]atrim=end=D1,apad=whole_dur=D1[a1]; ... [a0][a1]...[a(n-1)]concat=n=N:v=0:a=1[out]
    parts = []
    for i in range(n):
        d = scene_durations[i]
        parts.append(f"[{i}:a]atrim=end={d},apad=whole_dur={d}[a{i}]")
    concat_inputs = "".join(f"[a{i}]" for i in range(n))
    filter_complex = ";".join(parts) + ";" + concat_inputs + f"concat=n={n}:v=0:a=1[out]"
    cmd = ["ffmpeg", "-y"]
    for w in scene_wavs:
        cmd.extend(["-i", w])
    cmd.extend(["-filter_complex", filter_complex, "-map", "[out]", "-acodec", "pcm_s16le", "-ar", "24000", out_wav])
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        print("  Concat audio failed:", r.stderr, file=sys.stderr)
        return False
    return True


def merge_audio_into_video(video_path: str, wav_path: str) -> bool:
    duration = get_video_duration_sec(video_path)
    if duration <= 0:
        return False
    temp_path = video_path + ".temp_voiced.mp4"
    filter_complex = f"[1:a]atrim=end={duration},apad=whole_dur={duration}[a]"
    cmd = [
        "ffmpeg", "-y", "-i", video_path, "-i", wav_path,
        "-filter_complex", filter_complex, "-map", "0:v", "-map", "[a]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", str(duration), temp_path,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        print("  Merge failed:", r.stderr, file=sys.stderr)
        return False
    os.replace(temp_path, video_path)
    return True


def add_voice_to_video(video_name: str, scenes: list, api_key: str, language_code: str = "hi-IN") -> bool:
    video_path = os.path.join(SCRIPT_DIR, video_name)
    if not os.path.isfile(video_path):
        print(f"Skip (not found): {video_name}")
        return False
    base = video_name.replace(".mp4", "")
    temp_dir = os.path.join(SCRIPT_DIR, f"_voice_{base}")
    os.makedirs(temp_dir, exist_ok=True)
    scene_wavs = []
    scene_durations = []
    try:
        for i, (dur, texts) in enumerate(scenes):
            script = " ".join(str(t) for t in texts)
            wav_path = os.path.join(temp_dir, f"scene_{i:02d}.wav")
            if not text_to_speech(script, api_key, wav_path, language_code):
                return False
            scene_wavs.append(wav_path)
            scene_durations.append(float(dur))
        combined_wav = os.path.join(temp_dir, "combined.wav")
        if not build_concat_audio(scene_wavs, scene_durations, combined_wav):
            return False
        if not merge_audio_into_video(video_path, combined_wav):
            return False
        return True
    finally:
        for f in scene_wavs + [os.path.join(temp_dir, "combined.wav")]:
            try:
                if os.path.isfile(f):
                    os.remove(f)
            except OSError:
                pass
        try:
            os.rmdir(temp_dir)
        except OSError:
            pass


def main():
    if not API_KEY:
        print("Add SARVAM_API_KEY=your_key to .env in this directory", file=sys.stderr)
        sys.exit(1)
    for video_name, scenes in VIDEO_SCENES.items():
        lang = VIDEO_LANGUAGE.get(video_name, "hi-IN")
        print(f"Adding scene-synced voice to {video_name} ({len(scenes)} scenes, {lang}) ...")
        if add_voice_to_video(video_name, scenes, API_KEY, lang):
            print(f"  Done: {video_name}")
        else:
            print(f"  Failed: {video_name}")
    print("Finished.")


if __name__ == "__main__":
    main()
