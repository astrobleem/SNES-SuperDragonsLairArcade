#!/usr/bin/env python3
"""Generate manifest.xml for bsnes/higan MSU-1 emulation.

Scans the distribution folder for actual PCM files and generates
a manifest listing only tracks that exist.
"""
import os
import re
import sys

from paths import DISTRIBUTION

DIST_DIR = str(DISTRIBUTION)

ROM_NAME = "SuperDragonsLairArcade.sfc"
BASE_NAME = "SuperDragonsLairArcade"


def generate_manifest(dist_dir=None):
    if dist_dir is None:
        dist_dir = DIST_DIR

    # Scan for PCM files matching SuperDragonsLairArcade-{N}.pcm
    pcm_pattern = re.compile(rf'^{re.escape(BASE_NAME)}-(\d+)\.pcm$')
    track_ids = []
    for f in os.listdir(dist_dir):
        m = pcm_pattern.match(f)
        if m:
            track_ids.append(int(m.group(1)))
    track_ids.sort()

    if not track_ids:
        print("WARNING: No PCM files found in", dist_dir)
        return

    manifest_path = os.path.join(dist_dir, 'manifest.xml')
    with open(manifest_path, 'w') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<cartridge region="NTSC">\n')
        f.write(f'  <rom name="{ROM_NAME}" size="0x100000">\n')
        f.write('    <map mode="linear" address="40-7f:0000-ffff"/>\n')
        f.write('    <map mode="linear" address="c0-ff:0000-ffff"/>\n')
        f.write('    <map mode="shadow" address="00-3f:8000-ffff"/>\n')
        f.write('    <map mode="shadow" address="80-bf:8000-ffff"/>\n')
        f.write('  </rom>\n')
        f.write('  <msu1>\n')
        for tid in track_ids:
            f.write(f'    <track number="{tid}">'
                    f'<name>{BASE_NAME}-{tid}.pcm</name></track>\n')
        f.write('  </msu1>\n')
        f.write('</cartridge>\n')

    print(f"Generated {manifest_path}")
    print(f"  {len(track_ids)} audio tracks (IDs {track_ids[0]}-{track_ids[-1]})")


if __name__ == '__main__':
    d = sys.argv[1] if len(sys.argv) > 1 else None
    generate_manifest(d)
