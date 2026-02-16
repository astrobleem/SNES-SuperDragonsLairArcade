#!/usr/bin/env python3
"""Convert the dragon roar WAV to MSU-1 PCM format at track 900."""
import subprocess, os, sys

FFMPEG = "/mnt/c/Users/chad/AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-6.0-full_build/bin/ffmpeg.exe"
INPUT_WAV = "/mnt/e/gh/SNES-SuperDragonsLairArcade/roar.sfx_normal.wav"
STEREO_WAV = "/mnt/e/gh/SNES-SuperDragonsLairArcade/data/sounds/dragon_roar_msu1.wav"
TRACK_NUM = 900
BUILD_DIR = "/mnt/e/gh/SNES-SuperDragonsLairArcade/build"
SFC_DIR = "/mnt/e/gh/SuperDragonsLairArcade.sfc"
BASE_NAME = "SuperDragonsLairArcade"

def to_win_path(path):
    path = os.path.abspath(path)
    if path.startswith("/mnt/"):
        parts = path[5:]
        drive = parts[0].upper()
        rest = parts[1:]
        return drive + ":" + rest.replace("/", "\\")
    return path

# Step 1: Convert to 44100Hz stereo 16-bit WAV
print(f"Converting {INPUT_WAV} to 44100Hz stereo...")
r = subprocess.run([
    FFMPEG, "-y", "-i", to_win_path(INPUT_WAV),
    "-ar", "44100", "-ac", "2", "-sample_fmt", "s16",
    "-f", "wav", to_win_path(STEREO_WAV)
], capture_output=True, text=True, timeout=30)

if r.returncode != 0:
    print(f"ffmpeg error: {r.stderr[-300:]}")
    sys.exit(1)

wav_size = os.path.getsize(STEREO_WAV)
print(f"Stereo WAV: {wav_size} bytes")

# Step 2: Wrap with MSU1 header (find "data" chunk in WAV, add MSU1 + loop point)
MSU1_MAGIC = b"MSU1"
LOOP_START = 0  # no loop

# Find the "data" chunk offset (not always at 44 if ffmpeg adds LIST/INFO chunks)
with open(STEREO_WAV, "rb") as f:
    wav_data = f.read()
data_offset = wav_data.find(b"data")
if data_offset < 0:
    print("ERROR: no 'data' chunk found in WAV")
    sys.exit(1)
audio_offset = data_offset + 8  # skip "data" + 4-byte size
print(f"WAV 'data' chunk at offset {data_offset}, audio starts at {audio_offset}")

pcm_filename = f"{BASE_NAME}-{TRACK_NUM}.pcm"
for out_dir in [BUILD_DIR, SFC_DIR]:
    pcm_path = os.path.join(out_dir, pcm_filename)
    os.makedirs(out_dir, exist_ok=True)
    with open(pcm_path, "wb") as outf:
        outf.write(MSU1_MAGIC)
        outf.write(LOOP_START.to_bytes(4, "little"))
        outf.write(wav_data[audio_offset:])
    pcm_size = os.path.getsize(pcm_path)
    print(f"Wrote {pcm_path} ({pcm_size} bytes)")

print("Done! Dragon roar PCM at track 900.")
