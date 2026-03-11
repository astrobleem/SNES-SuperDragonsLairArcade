#!/usr/bin/env python3
"""
Tile-aware palette optimizer for SNES graphics.

Jointly assigns tiles to sub-palettes and optimizes palette colors using
iterative k-means, minimizing per-tile quantization error with perceptual
color weighting. Based on tiledpalettequant by Rilden
(https://github.com/rilden/tiledpalettequant).

Can be used as a standalone CLI tool or imported as a library by other
tools (e.g. snes_room_converter.py).

Usage:
    # Basic usage
    python tools/tiledpalettequant.py input.png -o output.pal

    # Custom palette configuration
    python tools/tiledpalettequant.py input.png -o output.pal \\
        --palettes 8 --colors 16 --transparent 000000

    # JSON output with tile assignments
    python tools/tiledpalettequant.py input.png --json output.json

    # Verification PNG
    python tools/tiledpalettequant.py input.png -o output.pal --verify
"""

import argparse
import json
import logging
import struct
import sys
from pathlib import Path

import numpy as np

log = logging.getLogger('tiledpalettequant')

# Default SNES Mode 1 BG1 parameters
DEFAULT_NUM_PALETTES = 8
DEFAULT_COLORS_PER_PALETTE = 16
DEFAULT_TILE_SIZE = 8


# ---------------------------------------------------------------------------
# Color-space helpers
# ---------------------------------------------------------------------------

def rgb_to_bgr555(r, g, b):
    """Convert 8-bit RGB to SNES BGR555 (15-bit word)."""
    return int(((r >> 3) & 0x1F) |
               (((g >> 3) & 0x1F) << 5) |
               (((b >> 3) & 0x1F) << 10))


def bgr555_to_rgb(word):
    """Convert SNES BGR555 to 8-bit RGB tuple."""
    return (
        (word & 0x1F) << 3,
        ((word >> 5) & 0x1F) << 3,
        ((word >> 10) & 0x1F) << 3,
    )


def _bgr555_to_components(colors):
    """Decompose BGR555 array into float R, G, B component arrays (0-31)."""
    arr = np.asarray(colors, dtype=np.int32)
    return (arr & 0x1F).astype(np.float64), \
           ((arr >> 5) & 0x1F).astype(np.float64), \
           ((arr >> 10) & 0x1F).astype(np.float64)


def _components_to_bgr555(r, g, b):
    """Convert float R, G, B (0-31) back to BGR555 uint16."""
    ri = np.clip(np.round(r), 0, 31).astype(np.int32)
    gi = np.clip(np.round(g), 0, 31).astype(np.int32)
    bi = np.clip(np.round(b), 0, 31).astype(np.int32)
    return (ri | (gi << 5) | (bi << 10)).astype(np.uint16)


def _weighted_dist_sq(r1, g1, b1, r2, g2, b2):
    """Perceptual weighted squared distance: 2*dR^2 + 4*dG^2 + 1*dB^2."""
    dr = r1 - r2
    dg = g1 - g2
    db = b1 - b2
    return 2.0 * dr * dr + 4.0 * dg * dg + db * db


# ---------------------------------------------------------------------------
# Core algorithm
# ---------------------------------------------------------------------------

def _tile_color_histograms(snes_tiles, pixels_per_tile):
    """Build per-tile unique color lists and pixel counts.

    Returns list of (colors_bgr555, counts) tuples, one per tile.
    colors_bgr555 is a 1D uint16 array, counts is a matching int array.
    """
    n_tiles = snes_tiles.shape[0]
    flat = snes_tiles.reshape(n_tiles, pixels_per_tile)
    histograms = []
    for i in range(n_tiles):
        colors, counts = np.unique(flat[i], return_counts=True)
        histograms.append((colors.astype(np.uint16), counts.astype(np.int32)))
    return histograms


def _assign_tiles_to_palettes(palettes_rgb, histograms):
    """Assign each tile to its lowest-error palette.

    palettes_rgb: (num_pals, pal_size, 3) float64 -- R,G,B components
    histograms: list of (colors_bgr555, counts) per tile

    Returns (assignments, total_errors):
        assignments: (n_tiles,) int -- palette index
        total_errors: (n_tiles,) float -- weighted error per tile
    """
    n_pals = palettes_rgb.shape[0]
    n_tiles = len(histograms)
    assignments = np.zeros(n_tiles, dtype=np.int32)
    total_errors = np.zeros(n_tiles, dtype=np.float64)

    for i, (colors, counts) in enumerate(histograms):
        cr, cg, cb = _bgr555_to_components(colors)
        best_err = np.inf
        best_pal = 0
        for p in range(n_pals):
            pr, pg, pb = palettes_rgb[p, :, 0], palettes_rgb[p, :, 1], palettes_rgb[p, :, 2]
            dist = _weighted_dist_sq(
                cr[:, None], cg[:, None], cb[:, None],
                pr[None, :], pg[None, :], pb[None, :]
            )
            min_dist = dist.min(axis=1)
            err = (min_dist * counts).sum()
            if err < best_err:
                best_err = err
                best_pal = p
        assignments[i] = best_pal
        total_errors[i] = best_err

    return assignments, total_errors


def _recompute_palette_centroids(palettes_rgb, histograms, assignments):
    """Recompute each palette color as the weighted centroid of assigned pixels."""
    n_pals = palettes_rgb.shape[0]
    pal_size = palettes_rgb.shape[1]
    new_pals = palettes_rgb.copy()

    for p in range(n_pals):
        tile_mask = (assignments == p)
        if not tile_mask.any():
            continue

        all_colors_r = []
        all_colors_g = []
        all_colors_b = []
        all_weights = []
        indices = np.where(tile_mask)[0]
        for i in indices:
            colors, counts = histograms[i]
            cr, cg, cb = _bgr555_to_components(colors)
            all_colors_r.append(cr)
            all_colors_g.append(cg)
            all_colors_b.append(cb)
            all_weights.append(counts.astype(np.float64))

        if not all_colors_r:
            continue

        ar = np.concatenate(all_colors_r)
        ag = np.concatenate(all_colors_g)
        ab = np.concatenate(all_colors_b)
        aw = np.concatenate(all_weights)

        pr = new_pals[p, :, 0]
        pg = new_pals[p, :, 1]
        pb = new_pals[p, :, 2]

        dist = _weighted_dist_sq(
            ar[:, None], ag[:, None], ab[:, None],
            pr[None, :], pg[None, :], pb[None, :]
        )
        nearest = dist.argmin(axis=1)

        for c in range(pal_size):
            mask = (nearest == c)
            w = aw[mask]
            if w.sum() > 0:
                wsum = w.sum()
                new_pals[p, c, 0] = (ar[mask] * w).sum() / wsum
                new_pals[p, c, 1] = (ag[mask] * w).sum() / wsum
                new_pals[p, c, 2] = (ab[mask] * w).sum() / wsum

    return new_pals


def build_palettes_tileaware(snes_tiles, num_palettes=DEFAULT_NUM_PALETTES,
                             colors_per_palette=DEFAULT_COLORS_PER_PALETTE,
                             trans_color=None):
    """Build sub-palettes using tile-aware iterative optimization.

    Jointly assigns tiles to palettes and recomputes palette colors to minimize
    per-tile quantization error. Based on tiledpalettequant by Rilden.

    Args:
        snes_tiles: (n_tiles, tile_h, tile_w) uint16 BGR555 pixels
        num_palettes: number of sub-palettes to generate (default: 8)
        colors_per_palette: colors per sub-palette including transparent (default: 16)
        trans_color: BGR555 transparent color value (default: rgb_to_bgr555(0,0,0))

    Returns (palettes, indexed_tiles, tile_pal_ids):
        palettes:      list of num_palettes lists of colors_per_palette BGR555 values
        indexed_tiles: (n_tiles, tile_h, tile_w) uint8 palette-relative indices
        tile_pal_ids:  (n_tiles,) uint8 sub-palette assignments
    """
    if trans_color is None:
        trans_color = rgb_to_bgr555(0, 0, 0)

    n_tiles = snes_tiles.shape[0]
    tile_h = snes_tiles.shape[1]
    tile_w = snes_tiles.shape[2]
    pixels_per_tile = tile_h * tile_w
    pal_size = colors_per_palette - 1  # usable colors (index 0 = transparent)
    rng = np.random.RandomState(42)

    # Build per-tile color histograms
    histograms = _tile_color_histograms(snes_tiles, pixels_per_tile)

    # Gather all pixel colors with weights for global stats
    all_r, all_g, all_b, all_w = [], [], [], []
    for colors, counts in histograms:
        cr, cg, cb = _bgr555_to_components(colors)
        all_r.append(cr)
        all_g.append(cg)
        all_b.append(cb)
        all_w.append(counts.astype(np.float64))
    glob_r = np.concatenate(all_r)
    glob_g = np.concatenate(all_g)
    glob_b = np.concatenate(all_b)
    glob_w = np.concatenate(all_w)

    # Global weighted average color
    ws = glob_w.sum()
    avg_r = (glob_r * glob_w).sum() / ws
    avg_g = (glob_g * glob_w).sum() / ws
    avg_b = (glob_b * glob_w).sum() / ws

    # --- Initialize palettes via splitting ---
    palettes_rgb = np.zeros((1, pal_size, 3), dtype=np.float64)
    palettes_rgb[0, 0] = [avg_r, avg_g, avg_b]

    while palettes_rgb.shape[0] < num_palettes:
        n_pals = palettes_rgb.shape[0]
        assignments, _ = _assign_tiles_to_palettes(palettes_rgb, histograms)

        _, tile_errors = _assign_tiles_to_palettes(palettes_rgb, histograms)
        pal_errors = np.zeros(n_pals)
        for i in range(n_tiles):
            pal_errors[assignments[i]] += tile_errors[i]

        worst = int(np.argmax(pal_errors))

        new_pal = palettes_rgb[worst].copy()
        perturbed = new_pal + rng.uniform(-1.5, 1.5, new_pal.shape)
        perturbed = np.clip(perturbed, 0, 31)

        palettes_rgb = np.concatenate([palettes_rgb, perturbed[None]], axis=0)

        for _ in range(3):
            assignments, _ = _assign_tiles_to_palettes(palettes_rgb, histograms)
            palettes_rgb = _recompute_palette_centroids(palettes_rgb, histograms, assignments)

    # --- Expand palettes from initial colors to full pal_size ---
    for expand_round in range(3):
        assignments, _ = _assign_tiles_to_palettes(palettes_rgb, histograms)

        for p in range(num_palettes):
            tile_mask = (assignments == p)
            if not tile_mask.any():
                continue

            p_colors_r, p_colors_g, p_colors_b, p_weights = [], [], [], []
            for i in np.where(tile_mask)[0]:
                colors, counts = histograms[i]
                cr, cg, cb = _bgr555_to_components(colors)
                p_colors_r.append(cr)
                p_colors_g.append(cg)
                p_colors_b.append(cb)
                p_weights.append(counts.astype(np.float64))

            pr = np.concatenate(p_colors_r)
            pg = np.concatenate(p_colors_g)
            pb = np.concatenate(p_colors_b)
            pw = np.concatenate(p_weights)

            n_unique = len(pr)
            n_centers = min(pal_size, n_unique)

            if n_centers < 1:
                continue

            # k-means++ initialization
            centers_r = np.zeros(n_centers)
            centers_g = np.zeros(n_centers)
            centers_b = np.zeros(n_centers)

            probs = pw / pw.sum()
            idx = rng.choice(n_unique, p=probs)
            centers_r[0], centers_g[0], centers_b[0] = pr[idx], pg[idx], pb[idx]

            for c in range(1, n_centers):
                dist = np.full(n_unique, np.inf)
                for cc in range(c):
                    d = _weighted_dist_sq(pr, pg, pb, centers_r[cc], centers_g[cc], centers_b[cc])
                    dist = np.minimum(dist, d)
                probs = (dist * pw)
                s = probs.sum()
                if s > 0:
                    probs /= s
                else:
                    probs = pw / pw.sum()
                idx = rng.choice(n_unique, p=probs)
                centers_r[c], centers_g[c], centers_b[c] = pr[idx], pg[idx], pb[idx]

            # Run k-means iterations
            for _ in range(8):
                dist = _weighted_dist_sq(
                    pr[:, None], pg[:, None], pb[:, None],
                    centers_r[None, :], centers_g[None, :], centers_b[None, :]
                )
                nearest = dist.argmin(axis=1)
                for c in range(n_centers):
                    mask = (nearest == c)
                    w = pw[mask]
                    if w.sum() > 0:
                        wsum = w.sum()
                        centers_r[c] = (pr[mask] * w).sum() / wsum
                        centers_g[c] = (pg[mask] * w).sum() / wsum
                        centers_b[c] = (pb[mask] * w).sum() / wsum

            palettes_rgb[p, :n_centers, 0] = centers_r
            palettes_rgb[p, :n_centers, 1] = centers_g
            palettes_rgb[p, :n_centers, 2] = centers_b
            for c in range(n_centers, pal_size):
                palettes_rgb[p, c] = palettes_rgb[p, 0]

    # --- Main refinement: alternating assignment + centroid recomputation ---
    best_palettes = palettes_rgb.copy()
    best_error = np.inf

    for iteration in range(10):
        assignments, tile_errors = _assign_tiles_to_palettes(palettes_rgb, histograms)
        total_err = tile_errors.sum()

        if total_err < best_error:
            best_error = total_err
            best_palettes = palettes_rgb.copy()

        palettes_rgb = _recompute_palette_centroids(palettes_rgb, histograms, assignments)

    # Final assignment with best palettes
    palettes_rgb = best_palettes
    assignments, _ = _assign_tiles_to_palettes(palettes_rgb, histograms)
    palettes_rgb = _recompute_palette_centroids(palettes_rgb, histograms, assignments)
    assignments, _ = _assign_tiles_to_palettes(palettes_rgb, histograms)

    # --- Quantize to BGR555 and build output ---
    palettes_out = []
    for p in range(num_palettes):
        pal = [trans_color]
        bgr_arr = _components_to_bgr555(
            palettes_rgb[p, :, 0], palettes_rgb[p, :, 1], palettes_rgb[p, :, 2]
        )
        for c in range(pal_size):
            pal.append(int(bgr_arr[c]))
        palettes_out.append(pal)

    # --- Palettize tiles: assign pixels to nearest color in assigned palette ---
    flat_tiles = snes_tiles.reshape(n_tiles, pixels_per_tile).astype(np.int32)
    tr = (flat_tiles & 0x1F).astype(np.float64)
    tg = ((flat_tiles >> 5) & 0x1F).astype(np.float64)
    tb = ((flat_tiles >> 10) & 0x1F).astype(np.float64)

    indexed_tiles = np.zeros((n_tiles, pixels_per_tile), dtype=np.uint8)
    tile_pal_ids = assignments.astype(np.uint8)

    pal_decomp = []
    for pal in palettes_out:
        arr = np.array(pal, dtype=np.int32)
        pal_decomp.append((
            (arr & 0x1F).astype(np.float64),
            ((arr >> 5) & 0x1F).astype(np.float64),
            ((arr >> 10) & 0x1F).astype(np.float64),
        ))

    for p in range(num_palettes):
        mask = (assignments == p)
        if not mask.any():
            continue
        idxs = np.where(mask)[0]
        pr, pg, pb = pal_decomp[p]

        t_r = tr[idxs]
        t_g = tg[idxs]
        t_b = tb[idxs]

        dist = _weighted_dist_sq(
            t_r[:, :, None], t_g[:, :, None], t_b[:, :, None],
            pr[None, None, :], pg[None, None, :], pb[None, None, :]
        )
        dist[:, :, 0] = np.inf  # never map pixels to transparent slot
        indexed_tiles[idxs] = dist.argmin(axis=2).astype(np.uint8)

    indexed_tiles = indexed_tiles.reshape(n_tiles, tile_h, tile_w)
    return palettes_out, indexed_tiles, tile_pal_ids


# ---------------------------------------------------------------------------
# CLI support
# ---------------------------------------------------------------------------

def _load_png_as_tiles(png_path, tile_size=DEFAULT_TILE_SIZE):
    """Load a PNG image and split into BGR555 tiles.

    Returns (snes_tiles, width_px, height_px, width_tiles, height_tiles).
    snes_tiles: (n_tiles, tile_size, tile_size) uint16 BGR555
    """
    from PIL import Image

    img = Image.open(png_path).convert('RGB')
    width_px, height_px = img.size

    if width_px % tile_size or height_px % tile_size:
        raise ValueError(
            f"Image {width_px}x{height_px} not evenly divisible by tile size {tile_size}")

    width_tiles = width_px // tile_size
    height_tiles = height_px // tile_size

    rgb = np.array(img, dtype=np.int32)
    snes_pixels = (
        ((rgb[:, :, 0] >> 3) & 0x1F) |
        (((rgb[:, :, 1] >> 3) & 0x1F) << 5) |
        (((rgb[:, :, 2] >> 3) & 0x1F) << 10)
    ).astype(np.uint16)

    snes_tiles = snes_pixels.reshape(
        height_tiles, tile_size, width_tiles, tile_size
    ).transpose(0, 2, 1, 3).reshape(-1, tile_size, tile_size)

    return snes_tiles, width_px, height_px, width_tiles, height_tiles


def _write_pal_file(palettes, output_path):
    """Write palettes as SNES CGRAM binary (BGR555, little-endian)."""
    data = bytearray()
    for pal in palettes:
        for color in pal:
            data += struct.pack('<H', color & 0x7FFF)
    Path(output_path).write_bytes(bytes(data))
    return len(data)


def _write_json_output(palettes, tile_pal_ids, output_path, width_tiles, height_tiles):
    """Write JSON with palettes and tile assignments."""
    pal_rgb = []
    for pal in palettes:
        pal_rgb.append([
            {'bgr555': int(c), 'rgb': list(bgr555_to_rgb(c))} for c in pal
        ])

    assignments = []
    for i, pid in enumerate(tile_pal_ids):
        row = i // width_tiles
        col = i % width_tiles
        assignments.append({'tile': i, 'row': row, 'col': col, 'palette': int(pid)})

    result = {
        'num_palettes': len(palettes),
        'colors_per_palette': len(palettes[0]) if palettes else 0,
        'width_tiles': width_tiles,
        'height_tiles': height_tiles,
        'total_tiles': len(tile_pal_ids),
        'palettes': pal_rgb,
        'tile_assignments': assignments,
    }

    Path(output_path).write_text(json.dumps(result, indent=2))


def _write_verify_png(palettes, indexed_tiles, tile_pal_ids, output_path,
                      width_tiles, height_tiles, tile_size):
    """Save verification PNG showing palette-reduced output."""
    from PIL import Image

    w = width_tiles * tile_size
    h = height_tiles * tile_size
    img = Image.new('RGB', (w, h), (0, 0, 0))
    px = img.load()

    # Build palette RGB lookup
    pal_rgb = []
    for pal in palettes:
        pal_rgb.append([bgr555_to_rgb(c) for c in pal])

    n_tiles = len(tile_pal_ids)
    for i in range(n_tiles):
        row = i // width_tiles
        col = i % width_tiles
        tile = indexed_tiles[i]
        pal_id = int(tile_pal_ids[i])
        colors = pal_rgb[pal_id]

        for ty in range(tile_size):
            for tx in range(tile_size):
                ci = int(tile[ty, tx])
                rgb = colors[ci] if ci < len(colors) else (255, 0, 255)
                px[col * tile_size + tx, row * tile_size + ty] = rgb

    img.save(output_path)


def main():
    parser = argparse.ArgumentParser(
        description="Tile-aware palette optimizer for SNES graphics")
    parser.add_argument('input', help="Input PNG image")
    parser.add_argument('--output', '-o', help="Output .pal file path")
    parser.add_argument('--json', dest='json_output', help="Output JSON file path")
    parser.add_argument('--palettes', '-p', type=int, default=DEFAULT_NUM_PALETTES,
                        help=f"Number of sub-palettes (default: {DEFAULT_NUM_PALETTES})")
    parser.add_argument('--colors', '-c', type=int, default=DEFAULT_COLORS_PER_PALETTE,
                        help=f"Colors per sub-palette (default: {DEFAULT_COLORS_PER_PALETTE})")
    parser.add_argument('--transparent', default='000000',
                        help="Transparent color in hex (default: 000000)")
    parser.add_argument('--tile-size', type=int, default=DEFAULT_TILE_SIZE,
                        help=f"Tile size in pixels (default: {DEFAULT_TILE_SIZE})")
    parser.add_argument('--verbose', '-v', action='store_true',
                        help="Print per-tile assignment info")
    parser.add_argument('--verify', action='store_true',
                        help="Save verification PNG showing palette-reduced output")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(levelname)s: %(message)s',
    )

    if not args.output and not args.json_output and not args.verify:
        parser.error("At least one output required: --output, --json, or --verify")

    # Parse transparent color
    try:
        tc = args.transparent.lstrip('#')
        r, g, b = int(tc[0:2], 16), int(tc[2:4], 16), int(tc[4:6], 16)
        trans = rgb_to_bgr555(r, g, b)
    except (ValueError, IndexError):
        log.error("Invalid --transparent color: %s (use 6-digit hex, e.g. 000000)", args.transparent)
        sys.exit(1)

    # Load image
    log.info("Loading %s...", args.input)
    snes_tiles, w_px, h_px, w_tiles, h_tiles = _load_png_as_tiles(
        args.input, args.tile_size)
    n_tiles = snes_tiles.shape[0]
    log.info("Image: %dx%d (%dx%d tiles, %d total)", w_px, h_px, w_tiles, h_tiles, n_tiles)

    # Run optimizer
    log.info("Optimizing %d palettes x %d colors...", args.palettes, args.colors)
    palettes, indexed_tiles, tile_pal_ids = build_palettes_tileaware(
        snes_tiles,
        num_palettes=args.palettes,
        colors_per_palette=args.colors,
        trans_color=trans,
    )

    # Summary
    pals_used = sum(1 for p in palettes if any(c != trans for c in p[1:]))
    log.info("Palettes used: %d/%d", pals_used, args.palettes)

    if args.verbose:
        from collections import Counter
        counts = Counter(int(p) for p in tile_pal_ids)
        for pid in sorted(counts):
            log.info("  Palette %d: %d tiles", pid, counts[pid])

    # Write outputs
    if args.output:
        nbytes = _write_pal_file(palettes, args.output)
        log.info("Wrote %s (%d bytes)", args.output, nbytes)

    if args.json_output:
        _write_json_output(palettes, tile_pal_ids, args.json_output, w_tiles, h_tiles)
        log.info("Wrote %s", args.json_output)

    if args.verify:
        verify_path = Path(args.input).with_suffix('.verify.png')
        if args.output:
            verify_path = Path(args.output).with_suffix('.verify.png')
        _write_verify_png(palettes, indexed_tiles, tile_pal_ids, verify_path,
                          w_tiles, h_tiles, args.tile_size)
        log.info("Wrote verification: %s", verify_path)


if __name__ == '__main__':
    main()
