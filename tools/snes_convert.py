#!/usr/bin/env python3
"""
SNES Background Converter
-------------------------
Takes an input PNG and converts it to:
- 256x224 resolution (letterboxed)
- Indexed palette with user-defined color count
- SNES‑friendly nearest-neighbor scaling

Usage:
    python snes_convert.py input.png output.png --colors 48

Place this file in tools/ inside the SNES-SuperDragonsLairArcade repo.
"""

import argparse
from PIL import Image


def letterbox_resize(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Resize while preserving aspect ratio, centered in a 256x224 canvas."""
    img_w, img_h = img.size
    scale = min(target_w / img_w, target_h / img_h)
    new_w = int(img_w * scale)
    new_h = int(img_h * scale)

    resized = img.resize((new_w, new_h), Image.Resampling.NEAREST)
    canvas = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    offset = ((target_w - new_w) // 2, (target_h - new_h) // 2)
    canvas.paste(resized, offset)
    return canvas


def convert_to_indexed(img: Image.Image, colors: int) -> Image.Image:
    """Convert the image to an indexed palette with N colors."""
    return img.convert("P", palette=Image.Palette.ADAPTIVE, colors=colors)


def process(input_path: str, output_path: str, colors: int):
    print(f"Loading {input_path}…")
    img = Image.open(input_path).convert("RGBA")

    print("Resizing to 256x224 with letterboxing…")
    img = letterbox_resize(img, 256, 224)

    print(f"Quantizing to {colors} colors…")
    indexed = convert_to_indexed(img, colors)

    print(f"Saving {output_path}…")
    indexed.save(output_path)
    print("Done!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert images to SNES‑ready 4bpp background format.")
    parser.add_argument("input", help="Input PNG file")
    parser.add_argument("output", help="Output PNG file")
    parser.add_argument("--colors", type=int, default=48, help="Number of colors (max 128, SNES limit 8 palettes × 16 colors)")

    args = parser.parse_args()
    process(args.input, args.output, args.colors)
