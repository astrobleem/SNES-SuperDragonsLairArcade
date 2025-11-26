#!/usr/bin/env python3
"""
Batch convert Dragon's Lair .ogg audio files to MSU-1 PCM format.
This script:
1. Finds all .ogg files in DaphneCDROM/DLCDROM
2. Converts each to WAV using ffmpeg
3. Converts WAV to MSU-1 PCM format
4. Names tracks sequentially based on scene order
"""

import os
import subprocess
import sys
from pathlib import Path

# Paths
DAPHNE_DIR = Path("/mnt/e/gh/DaphneCDROM/DLCDROM")
OUTPUT_DIR = Path("/mnt/e/gh/SuperDragonsLairArcade.sfc")
MSU_CONVERTER = Path("/mnt/e/gh/SNES-SuperDragonsLairArcade/tools/msu1pcmwriter.py")
TEMP_WAV = Path("temp_audio.wav")

# MSU-1 Audio Requirements
SAMPLE_RATE = 44100
CHANNELS = 2
BIT_DEPTH = 16

def convert_ogg_to_wav(ogg_file, wav_file):
    """Convert .ogg to WAV with MSU-1 specs using ffmpeg"""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(ogg_file),
        "-ar", str(SAMPLE_RATE),
        "-ac", str(CHANNELS),
        "-sample_fmt", "s16",
        str(wav_file)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0

def convert_wav_to_pcm(wav_file, pcm_file, loop_start=0):
    """Convert WAV to MSU-1 PCM format"""
    cmd = [
        "python3", str(MSU_CONVERTER),
        "-infile", str(wav_file),
        "-outfile", str(pcm_file),
        "-loopstart", str(loop_start)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0

def get_track_mapping():
    """Read framefile and create track mapping"""
    framefile = Path("/mnt/e/gh/DaphneCDROM/framefile/dlcdrom.TXT")
    
    track_map = {}
    track_num = 1
    
    with open(framefile, 'r') as f:
        lines = f.readlines()[2:]  # Skip first 2 lines (path and blank)
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            parts = line.split('\t')
            if len(parts) >= 2:
                video_file = parts[1]
                # Replace .m2v with .ogg for audio file
                audio_file = video_file.replace('.m2v', '.ogg')
                track_map[track_num] = audio_file
                track_num += 1
    
    return track_map

def main():
    print("Dragon's Lair MSU-1 Audio Converter")
    print("=" * 50)
    
    # Create output directory if needed
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Get track mapping from framefile
    print("Reading framefile...")
    track_map = get_track_mapping()
    print(f"Found {len(track_map)} audio tracks to convert")
    
    # Get all .ogg files in order
    total_tracks = len(track_map)
    converted = 0
    failed = 0
    
    for track_num, audio_file in sorted(track_map.items()):
        ogg_path = DAPHNE_DIR / audio_file
        
        if not ogg_path.exists():
            print(f"⚠ Track {track_num}: {audio_file} not found, skipping")
            failed += 1
            continue
        
        pcm_filename = f"SuperDragonsLairArcade-{track_num}.pcm"
        pcm_path = OUTPUT_DIR / pcm_filename
        
        print(f"[{track_num}/{total_tracks}] Converting {audio_file}...")
        
        # Step 1: OGG → WAV
        if not convert_ogg_to_wav(ogg_path, TEMP_WAV):
            print(f"  ✗ Failed to convert to WAV")
            failed += 1
            continue
        
        # Step 2: WAV → MSU-1 PCM
        if not convert_wav_to_pcm(TEMP_WAV, pcm_path):
            print(f"  ✗ Failed to convert to PCM")
            failed += 1
            continue
        
        print(f"  ✓ Created {pcm_filename}")
        converted += 1
        
        # Clean up temp WAV
        if TEMP_WAV.exists():
            TEMP_WAV.unlink()
    
    print("\n" + "=" * 50)
    print(f"Conversion Complete!")
    print(f"  ✓ Converted: {converted}")
    print(f"  ✗ Failed: {failed}")
    print(f"\nOutput directory: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
