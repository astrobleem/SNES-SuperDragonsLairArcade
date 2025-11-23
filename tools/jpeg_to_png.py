"""Convert JPEG images to PNG with optional colorspace normalization.

This script provides a small CLI wrapper around Pillow to convert JPEG
files to PNG, optionally forcing a specific Pillow mode (e.g., RGBA).
It includes overwrite protection to avoid clobbering existing files.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from PIL import Image


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a JPEG image to PNG with optional colorspace normalization.",
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to the input JPEG image.",
    )
    parser.add_argument(
        "--output",
        help="Path to the output PNG image. Defaults to input basename with .png extension.",
    )
    parser.add_argument(
        "--colorspace",
        help="Optional Pillow mode to normalize the image to (e.g., RGBA).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting the output file if it already exists.",
    )
    return parser.parse_args(argv)


def derive_output_path(input_path: Path) -> Path:
    return input_path.with_suffix(".png")


def convert_jpeg_to_png(input_path: Path, output_path: Path, colorspace: Optional[str] = None, overwrite: bool = False) -> None:
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if output_path.exists() and not overwrite:
        raise FileExistsError(f"Output file already exists: {output_path}. Use --overwrite to replace it.")

    with Image.open(input_path) as img:
        if colorspace:
            img = img.convert(colorspace)
        img.save(output_path, format="PNG")


def main(argv: Optional[list[str]] = None) -> None:
    args = parse_args(argv)
    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else derive_output_path(input_path)

    convert_jpeg_to_png(
        input_path=input_path,
        output_path=output_path,
        colorspace=args.colorspace,
        overwrite=args.overwrite,
    )


if __name__ == "__main__":
    main()
