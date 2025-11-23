import subprocess
import sys
from pathlib import Path

from PIL import Image


def create_sample_jpeg(path: Path) -> None:
    image = Image.new("RGB", (4, 4), color=(255, 0, 0))
    image.save(path, format="JPEG")


def test_jpeg_to_png_conversion(tmp_path: Path) -> None:
    input_path = tmp_path / "sample.jpg"
    output_path = tmp_path / "sample.png"
    create_sample_jpeg(input_path)

    script_path = Path(__file__).resolve().parents[1] / "tools" / "jpeg_to_png.py"

    subprocess.run(
        [sys.executable, str(script_path), "--input", str(input_path), "--output", str(output_path), "--colorspace", "RGBA"],
        check=True,
    )

    assert output_path.exists(), "PNG output file was not created"

    with Image.open(output_path) as png_image:
        assert png_image.mode == "RGBA"
        assert png_image.format == "PNG"
