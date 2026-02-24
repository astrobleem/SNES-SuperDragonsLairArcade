#!/usr/bin/env python3
"""Analyze the mapping between Daphne framefile laserdisc frame numbers
and actual cumulative MP4 positions from concatenated .m2v segments."""

import subprocess
import os
import sys
from paths import DAPHNE_FRAMEFILE, DAPHNE_CONTENT

framefile = str(DAPHNE_FRAMEFILE)
content_root = str(DAPHNE_CONTENT)

with open(framefile) as f:
    lines = f.readlines()

segments = []
for line in lines[2:]:  # skip first 2 lines (root path + blank)
    line = line.strip()
    if not line:
        continue
    parts = line.split(None, 1)
    if len(parts) >= 2:
        frame_num = int(parts[0])
        filename = parts[1]
        m2v_path = os.path.join(content_root, filename)
        ogg_path = os.path.splitext(m2v_path)[0] + ".ogg"
        segments.append((frame_num, filename, m2v_path, os.path.exists(ogg_path)))

# Calculate cumulative MP4 time
cumulative_time = 0.0

# Cache frame counts to avoid re-probing the same file
frame_cache = {}

print(f"{'#':>3} {'Frame':>8} {'Segment':<25} {'A':>1} {'Frames':>7} {'Dur(s)':>10} {'CumTime':>10} {'Formula':>10} {'Err(s)':>10} {'ErrFr':>6}")
print("-" * 110)

for i, (frame_num, filename, m2v_path, has_audio) in enumerate(segments):
    if m2v_path not in frame_cache:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
             "-show_entries", "stream=nb_read_frames,r_frame_rate", "-of", "csv=p=0", m2v_path],
            capture_output=True, text=True
        )
        parts = result.stdout.strip().split(",")
        if len(parts) != 2:
            print(f"  ERROR probing {filename}: {result.stdout.strip()}", file=sys.stderr)
            continue
        rate_str, fc = parts
        num, den = map(int, rate_str.split("/"))
        frame_cache[m2v_path] = (int(fc), num / den, den, num)

    frame_count, fps, den, num = frame_cache[m2v_path]
    duration = frame_count * den / num  # in seconds

    formula_time = frame_num / 23.976 - 6.297  # seconds

    if has_audio:
        error = cumulative_time - formula_time
        err_frames = error * 23.976
        print(f"{i:>3} {frame_num:>8} {filename:<25} Y {frame_count:>7} {duration:>10.3f} {cumulative_time:>10.3f} {formula_time:>10.3f} {error:>+10.3f} {err_frames:>+6.1f}")
        cumulative_time += duration
    else:
        print(f"{i:>3} {frame_num:>8} {filename:<25} N {frame_count:>7} {duration:>10.3f} {'SKIP':>10} {formula_time:>10.3f} {'N/A':>10} {'N/A':>6}")

print(f"\nTotal cumulative time: {cumulative_time:.3f}s")

print(f"\nKey frame positions:")
for target_frame, name in [(1424, "castle_exterior"), (1821, "exit_room"), (2044, "start_dead"), (2297, "snake_room")]:
    formula = target_frame / 23.976 - 6.297
    # Find which segment contains this frame
    seg_frame = 0
    seg_name = ""
    seg_idx = -1
    for j in range(len(segments) - 1, -1, -1):
        if segments[j][0] <= target_frame and segments[j][3]:  # has audio
            seg_frame = segments[j][0]
            seg_name = segments[j][1]
            seg_idx = j
            break
    offset_in_seg = target_frame - seg_frame
    print(f"  {name} (frame {target_frame}): formula={formula:.3f}s, in '{seg_name}' +{offset_in_seg} frames")
