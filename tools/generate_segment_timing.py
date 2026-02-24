#!/usr/bin/env python3
"""Generate segment_timing.json from the Daphne framefile.

Parses the Daphne framefile (dlcdrom.TXT), probes each .m2v segment
with ffprobe to get duration, and builds a cumulative timing table.
Only segments with matching .ogg audio are included (matching
convert_daphne.py's behavior of skipping audio-less segments).

Output: data/segment_timing.json

Usage:
    python3 tools/generate_segment_timing.py
    python3 tools/generate_segment_timing.py --framefile /path/to/dlcdrom.TXT --content-root /path/to/DLCDROM
"""

import argparse
import json
import os
import subprocess
import sys
from paths import DAPHNE_FRAMEFILE, DAPHNE_CONTENT


def main():
    parser = argparse.ArgumentParser(description='Generate segment timing JSON from Daphne framefile')
    parser.add_argument('--framefile', default=str(DAPHNE_FRAMEFILE),
                        help='Path to Daphne framefile')
    parser.add_argument('--content-root', default=str(DAPHNE_CONTENT),
                        help='Path to Daphne content root (where .m2v files are)')
    parser.add_argument('--output', default=None,
                        help='Output JSON path (default: data/segment_timing.json relative to project root)')
    args = parser.parse_args()

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        output_path = os.path.join(project_root, 'data', 'segment_timing.json')

    # Parse framefile
    with open(args.framefile) as f:
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
            m2v_path = os.path.join(args.content_root, filename)
            ogg_path = os.path.splitext(m2v_path)[0] + '.ogg'
            has_audio = os.path.exists(ogg_path)
            segments.append((frame_num, filename, m2v_path, has_audio))

    print(f'Parsed {len(segments)} segments from framefile')

    # Probe each segment for duration
    frame_cache = {}
    audio_segments = []
    cumulative_ms = 0.0

    for i, (frame_num, filename, m2v_path, has_audio) in enumerate(segments):
        if not has_audio:
            continue

        # Get frame count and rate (cached per unique file)
        if m2v_path not in frame_cache:
            result = subprocess.run(
                ['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                 '-show_entries', 'stream=nb_read_frames,r_frame_rate', '-of', 'csv=p=0', m2v_path],
                capture_output=True, text=True
            )
            parts = result.stdout.strip().split(',')
            if len(parts) != 2:
                print(f'  ERROR probing {filename}: {result.stdout.strip()}', file=sys.stderr)
                continue
            rate_str, fc = parts
            num, den = map(int, rate_str.split('/'))
            duration_s = int(fc) * den / num
            frame_cache[m2v_path] = duration_s

        duration_s = frame_cache[m2v_path]
        duration_ms = duration_s * 1000.0

        audio_segments.append({
            'frame': frame_num,
            'filename': filename,
            'cumulative_ms': round(cumulative_ms, 3),
            'duration_ms': round(duration_ms, 3),
        })

        cumulative_ms += duration_ms

    print(f'Probed {len(audio_segments)} audio segments, total duration: {cumulative_ms/1000:.3f}s')

    # Write JSON
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump({'segments': audio_segments}, f, indent=2)

    print(f'Written to {output_path}')

    # Verify a few key frames
    print('\nVerification:')
    for target_frame, name in [(1424, 'castle_exterior'), (1821, 'exit_room'),
                                (2044, 'start_dead'), (3505, 'flaming_ropes')]:
        ms = frame_to_ms(audio_segments, target_frame)
        old_ms = target_frame / 23.976 * 1000 - 6297.0
        diff = ms - old_ms
        print(f'  {name} (frame {target_frame}): new={ms:.1f}ms  old={old_ms:.1f}ms  diff={diff:+.1f}ms ({diff/1000*23.976:+.1f} frames)')


def frame_to_ms(segments, frame):
    """Convert a laserdisc frame number to MP4 milliseconds using segment timing."""
    # Find containing segment (last segment where seg.frame <= frame)
    seg = None
    for s in segments:
        if s['frame'] <= frame:
            seg = s
        else:
            break
    if seg is None:
        return frame / 23.976 * 1000.0  # fallback
    offset_ms = (frame - seg['frame']) / 23.976 * 1000.0
    return seg['cumulative_ms'] + offset_ms


if __name__ == '__main__':
    main()
