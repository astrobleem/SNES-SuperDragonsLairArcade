#!/usr/bin/env python3
"""Quick script to extract sample frames from intro death segments."""
import subprocess, os, sys
from paths import FFMPEG, PROJECT_ROOT, DAPHNE_CONTENT, wsl_to_windows as to_win_path

ffmpeg = FFMPEG
outdir = str(PROJECT_ROOT / "mesen" / "Screenshots" / "death")
os.makedirs(outdir, exist_ok=True)

segments = ["dls01d1.vob.m2v", "dls01d2.vob.m2v", "dls01d3.vob.m2v", "dls01b.vob.m2v"]

for seg in segments:
    base = seg.replace(".vob.m2v", "")
    inp = to_win_path(str(DAPHNE_CONTENT / seg))

    # first frame
    out1 = os.path.join(outdir, base + "_first.png")
    r = subprocess.run([ffmpeg, "-y", "-i", inp, "-vf", "yadif,fps=24000/1001,scale=256:192",
                        "-frames:v", "1", "-update", "1", to_win_path(out1)],
                       capture_output=True, text=True, timeout=30)
    ok1 = os.path.exists(out1)

    # mid frame (frame 15)
    out2 = os.path.join(outdir, base + "_mid.png")
    r2 = subprocess.run([ffmpeg, "-y", "-i", inp, "-vf", "yadif,fps=24000/1001,scale=256:192",
                         "-ss", "0.8", "-frames:v", "1", "-update", "1", to_win_path(out2)],
                        capture_output=True, text=True, timeout=30)
    ok2 = os.path.exists(out2)

    # late frame
    out3 = os.path.join(outdir, base + "_late.png")
    r3 = subprocess.run([ffmpeg, "-y", "-i", inp, "-vf", "yadif,fps=24000/1001,scale=256:192",
                         "-ss", "1.5", "-frames:v", "1", "-update", "1", to_win_path(out3)],
                        capture_output=True, text=True, timeout=30)
    ok3 = os.path.exists(out3)

    print(f"{seg}: first={ok1} mid={ok2} late={ok3}")
    if not ok1:
        print(f"  stderr: {r.stderr[-200:]}")
