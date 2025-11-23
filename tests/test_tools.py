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
    """Test animationWriter with real sprite frames and validate binary output format."""
    import shutil
    
    # Use real sprite frames from the bang animation
    source_dir = ROOT / "data" / "sprites" / "bang.gfx_sprite"
    frame_dir = tmp_path / "frames"
    frame_dir.mkdir()
    
    # Copy the 5 PNG frames from bang.gfx_sprite
    png_files = sorted(source_dir.glob("*.png"))
    assert len(png_files) == 5, f"Expected 5 PNG files in {source_dir}, found {len(png_files)}"
    
    for png_file in png_files:
        shutil.copy(png_file, frame_dir / png_file.name)
    
    out_path = tmp_path / "output.anim"
    
    # Run animationWriter with timeout to prevent hanging
    result = subprocess.run(
        [
            sys.executable,
            str(TOOLS / "animationWriter.py"),
            "-infolder",
            str(frame_dir),
            "-outfile",
            str(out_path),
        ],
        capture_output=True,
        text=True,
        timeout=30  # Prevent hanging like we saw with gracon.py
    )
    
    assert result.returncode == 0, f"animationWriter failed: {result.stderr}"
    assert out_path.exists(), "Output file was not created"
    
    # Validate the binary output format
    with open(out_path, "rb") as f:
        # Read header (9 bytes)
        header = f.read(9)
        assert len(header) == 9, f"Header should be 9 bytes, got {len(header)}"
        
        # Verify magic bytes "SP"
        magic = header[0:2]
        assert magic == b"SP", f"Expected magic 'SP', got {magic}"
        
        # Parse header fields
        max_tile_size = header[2] | (header[3] << 8)
        max_palette_size = header[4] | (header[5] << 8)
        frame_count = header[6] | (header[7] << 8)
        bpp_field = header[8]
        
        # Validate frame count
        assert frame_count == 5, f"Expected 5 frames, got {frame_count}"
        
        # Validate fields are reasonable (not zero/garbage)
        assert max_tile_size > 0, f"max_tile_size should be > 0, got {max_tile_size}"
        assert max_tile_size < 0x10000, f"max_tile_size seems too large: {max_tile_size}"
        assert max_palette_size >= 0, f"max_palette_size should be >= 0, got {max_palette_size}"
        assert bpp_field in [0, 1, 2, 3, 4], f"bpp field should be 0-4 (bpp/2), got {bpp_field}"
        
        # Verify frame pointer table exists (2 bytes per frame)
        frame_pointers_size = frame_count * 2
        frame_pointers = f.read(frame_pointers_size)
        assert len(frame_pointers) == frame_pointers_size, \
            f"Expected {frame_pointers_size} bytes for frame pointers, got {len(frame_pointers)}"
        
        # Verify file has data beyond header and pointers
        file_size = out_path.stat().st_size
        min_expected_size = 9 + frame_pointers_size
        assert file_size > min_expected_size, \
            f"File should be larger than header+pointers ({min_expected_size}), got {file_size}"


def test_mod2snes(tmp_path):
    """Test mod2snes.py with trans_atlantic.mod fixture and validate SPCMOD output."""
    # Use the real MOD file from fixtures
    fixtures_dir = ROOT / "tests" / "fixtures"
    mod_file = fixtures_dir / "trans_atlantic.mod"
    assert mod_file.exists(), f"Fixture file not found: {mod_file}"
    
    out_base = tmp_path / "output"
    out_file = tmp_path / "output.spcmod"
    
    # Run mod2snes with timeout to prevent hanging
    result = subprocess.run(
        [
            sys.executable,
            str(TOOLS / "mod2snes.py"),
            str(mod_file),
            str(out_base),
        ],
        capture_output=True,
        text=True,
        timeout=60  # MOD conversion can take time
    )
    
    assert result.returncode == 0, f"mod2snes.py failed: {result.stderr}"
    assert out_file.exists(), "Output .spcmod file was not created"
    
    # Validate the SPCMOD binary format
    with open(out_file, "rb") as f:
        # Read instrument data section (248 bytes)
        f.seek(0)
        instrument_data = f.read(248)
        assert len(instrument_data) == 248, f"Expected 248 bytes of instrument data, got {len(instrument_data)}"
        
        # Read song length (1 byte at offset 248)
        f.seek(248)
        song_length = f.read(1)[0]
        assert song_length > 0, f"Song length should be > 0, got {song_length}"
        assert song_length <= 128, f"Song length seems too large: {song_length}"
        
        # Read pattern count (1 byte at offset 249)
        f.seek(249)
        pattern_count = f.read(1)[0]
        assert pattern_count > 0, f"Pattern count should be > 0, got {pattern_count}"
        
        # Read pattern sequence (128 bytes starting at offset 250)
        f.seek(250)
        sequence = f.read(128)
        assert len(sequence) == 128, f"Expected 128 bytes for sequence, got {len(sequence)}"
        
        # Read pattern pointers (130 bytes = 65 pointers * 2 bytes at offset 378)
        f.seek(378)
        pattern_pointers = f.read(130)
        assert len(pattern_pointers) == 130, f"Expected 130 bytes for pattern pointers, got {len(pattern_pointers)}"
        
        # Verify file has pattern data and samples beyond header
        file_size = out_file.stat().st_size
        min_expected_size = 508  # SPCMOD_PATTERN_DATA offset
        assert file_size > min_expected_size, \
            f"File should be larger than {min_expected_size} bytes (header only), got {file_size}"
        
        # Verify BRR sample data exists (should start somewhere after pattern data)
        # Sample data should have BRR blocks with proper headers
        f.seek(508)  # Start of pattern data
        # Just verify we can read some data here
        pattern_data = f.read(100)
        assert len(pattern_data) == 100, "Could not read pattern data"


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
