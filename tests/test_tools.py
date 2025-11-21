import os
import struct
import subprocess
import sys
import wave

from pathlib import Path
from PIL import Image


ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"


def run_script(args):
    result = subprocess.run([sys.executable] + args, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result


def create_wav(path: Path):
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(2)
        wav_file.setsampwidth(2)
        wav_file.setframerate(44100)
        wav_file.writeframes(struct.pack("<hhhh", 0, 0, 1000, -1000) * 10)


def test_msu1pcmwriter(tmp_path):
    wav_path = tmp_path / "input.wav"
    out_path = tmp_path / "output.pcm"
    create_wav(wav_path)
    run_script([str(TOOLS / "msu1pcmwriter.py"), "-infile", str(wav_path), "-outfile", str(out_path), "-loopstart", "0"])
    assert out_path.exists()
    assert out_path.read_bytes()[:4] == b"MSU1"


def test_animation_writer(tmp_path):
    frame_dir = tmp_path / "frames"
    frame_dir.mkdir()
    for idx, color in enumerate([(255, 0, 0, 255), (0, 255, 0, 255)]):
        img = Image.new("RGBA", (8, 8), color)
        img.save(frame_dir / f"frame{idx}.png")

    out_path = tmp_path / "output.anim"
    run_script(
        [
            str(TOOLS / "animationWriter.py"),
            "-infolder",
            str(frame_dir),
            "-outfile",
            str(out_path),
        ]
    )
    assert out_path.exists()
    assert out_path.stat().st_size > 0


def test_msu1blockwriter(tmp_path):
    base_dir = tmp_path / "chapters"
    chapter_dir = base_dir / "chapter01"
    chapter_dir.mkdir(parents=True)

    (chapter_dir / "chapter.id1").write_text("chapter 1")

    (chapter_dir / "gfx_video.tiles").write_bytes(b"\x01\x02")
    (chapter_dir / "gfx_video.tilemap").write_bytes(b"\x03\x04")
    (chapter_dir / "gfx_video.palette").write_bytes(b"\x05\x06")
    (chapter_dir / "sfx_video.pcm").write_bytes(b"\x07\x08")

    out_path = tmp_path / "movie.msu"
    run_script(
        [
            str(TOOLS / "msu1blockwriter.py"),
            "-infilebase",
            str(base_dir),
            "-outfile",
            str(out_path),
            "-title",
            "Demo",
        ]
    )

    assert out_path.exists()
    with open(out_path, "rb") as handle:
        assert handle.read(6) == b"S-MSU1"
