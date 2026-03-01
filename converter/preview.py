#!/usr/bin/env python3
"""
preview.py - SNES tile/tilemap/palette reconstruction for visual preview

Reconstructs RGB images from SNES 4BPP tile data for previewing conversion
results. Ported from SNES-VideoPlayer for Super Dragon's Lair Arcade.
"""

import os
import sys

# Ensure BLAS is single-threaded
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('MKL_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')

import struct
import numpy as np
from PIL import Image

BPP = 4
BYTES_PER_TILE = 8 * BPP  # 32


def decode_tiles_4bpp_rgb(tiles_raw, palette_rgb, tile_pal_offsets=None):
    """Decode SNES 4BPP tiles to RGB values using the frame's actual palette.

    tiles_raw: (N, 32) uint8 array of raw SNES 4BPP tile data
    palette_rgb: (C, 3) float32 array of RGB values
    tile_pal_offsets: optional (N,) uint16, per-tile palette base offset
    Returns: (N, 192) float32 array (64 pixels x 3 RGB channels)

    SNES 4BPP tile format (32 bytes per 8x8 tile):
      Bytes  0-15: bitplanes 0,1 interleaved by row (2 bytes/row x 8 rows)
      Bytes 16-31: bitplanes 2,3 interleaved by row (2 bytes/row x 8 rows)
    """
    N = tiles_raw.shape[0]
    pixel_indices = np.zeros((N, 8, 8), dtype=np.uint8)
    for row in range(8):
        bp0 = tiles_raw[:, 2 * row].astype(np.uint16)
        bp1 = tiles_raw[:, 2 * row + 1].astype(np.uint16)
        bp2 = tiles_raw[:, 16 + 2 * row].astype(np.uint16)
        bp3 = tiles_raw[:, 16 + 2 * row + 1].astype(np.uint16)
        for px in range(8):
            bit = 7 - px
            pixel_indices[:, row, px] = (
                ((bp0 >> bit) & 1) |
                (((bp1 >> bit) & 1) << 1) |
                (((bp2 >> bit) & 1) << 2) |
                (((bp3 >> bit) & 1) << 3)
            ).astype(np.uint8)
    flat_indices = pixel_indices.reshape(N, 64)

    if tile_pal_offsets is not None:
        flat_indices = flat_indices.astype(np.uint16) + tile_pal_offsets[:, None]

    rgb = palette_rgb[flat_indices]  # (N, 64, 3)
    return rgb.reshape(N, 192)


def parse_palette(pal_bytes):
    """Parse SNES BGR555 palette bytes to (N, 3) float32 RGB array in 0-255 range."""
    num_colors = len(pal_bytes) // 2
    # SDLA uses up to 8 sub-palettes x 16 colors = 128 colors max
    pal_rgb = np.zeros((max(128, num_colors), 3), dtype=np.float32)
    for i in range(num_colors):
        bgr555 = struct.unpack_from('<H', pal_bytes, i * 2)[0]
        pal_rgb[i, 0] = (bgr555 & 0x1F) * (255.0 / 31.0)
        pal_rgb[i, 1] = ((bgr555 >> 5) & 0x1F) * (255.0 / 31.0)
        pal_rgb[i, 2] = ((bgr555 >> 10) & 0x1F) * (255.0 / 31.0)
    return pal_rgb


def reconstruct_image(tile_bytes, map_bytes, pal_bytes, width=256, height=160):
    """Reconstruct RGB image from SNES tile/tilemap/palette data.

    Args:
        tile_bytes: Raw SNES 4BPP tile data
        map_bytes: Raw tilemap data (2 bytes per entry, LE)
        pal_bytes: Raw BGR555 palette data
        width: Image width in pixels (default 256)
        height: Image height in pixels (default 160)

    Returns:
        (height, width, 3) float32 array with values in 0-255 range
    """
    num_tiles = len(tile_bytes) // BYTES_PER_TILE
    tiles_w = width // 8
    tiles_h = height // 8

    # Parse palette
    pal_rgb = parse_palette(pal_bytes)

    # Decode tiles to RGB
    tiles_raw = np.frombuffer(tile_bytes, dtype=np.uint8).reshape(num_tiles, BYTES_PER_TILE)

    # Get per-tile palette offsets from tilemap
    tilemap = np.frombuffer(map_bytes[:tiles_w * tiles_h * 2], dtype=np.uint16)
    tile_indices = tilemap & 0x3FF
    pal_nums = (tilemap >> 10) & 0x7
    h_flip = (tilemap >> 14) & 1
    v_flip = (tilemap >> 15) & 1

    # Reconstruct image tile by tile with per-tilemap-entry palette offsets
    img = np.zeros((height, width, 3), dtype=np.float32)
    for ty in range(tiles_h):
        for tx in range(tiles_w):
            map_idx = ty * tiles_w + tx
            if map_idx >= len(tilemap):
                continue
            tidx = int(tile_indices[map_idx])
            if tidx >= num_tiles:
                continue

            # Get palette offset for this tilemap entry
            pal_offset = int(pal_nums[map_idx]) * 16

            # Re-decode this specific tile with its palette
            tile_raw = tiles_raw[tidx:tidx+1]  # (1, 32)
            tile_pal = np.array([pal_offset], dtype=np.uint16)
            tile_rgb_data = decode_tiles_4bpp_rgb(tile_raw, pal_rgb, tile_pal)
            tile_rgb = tile_rgb_data[0].reshape(8, 8, 3)

            if h_flip[map_idx]:
                tile_rgb = tile_rgb[:, ::-1, :]
            if v_flip[map_idx]:
                tile_rgb = tile_rgb[::-1, :, :]

            y0, x0 = ty * 8, tx * 8
            img[y0:y0+8, x0:x0+8, :] = tile_rgb

    return img


def reconstruct_to_pil(tile_bytes, map_bytes, pal_bytes, width=256, height=160):
    """Reconstruct and return a PIL Image from SNES data.

    Args:
        tile_bytes: Raw SNES 4BPP tile data
        map_bytes: Raw tilemap data
        pal_bytes: Raw BGR555 palette data
        width: Image width in pixels
        height: Image height in pixels

    Returns:
        PIL.Image.Image in RGB mode
    """
    img_arr = reconstruct_image(tile_bytes, map_bytes, pal_bytes, width, height)
    img_uint8 = np.clip(img_arr, 0, 255).astype(np.uint8)
    return Image.fromarray(img_uint8, 'RGB')


def preview_frame_files(tile_file, map_file, pal_file, width=256, height=160):
    """Load SNES data files and return a PIL Image preview.

    Args:
        tile_file: Path to .tiles file
        map_file: Path to .tilemap file
        pal_file: Path to .palette file
        width: Frame width
        height: Frame height

    Returns:
        PIL.Image.Image
    """
    with open(tile_file, 'rb') as f:
        tile_bytes = f.read()
    with open(map_file, 'rb') as f:
        map_bytes = f.read()
    with open(pal_file, 'rb') as f:
        pal_bytes = f.read()

    return reconstruct_to_pil(tile_bytes, map_bytes, pal_bytes, width, height)
