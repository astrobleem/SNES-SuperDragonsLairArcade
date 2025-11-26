#!/usr/bin/env python3
"""
Rotate arrow sprite PNG files.

This script rotates the left arrow sprite to create up and down arrow sprites.
- Rotate 90° clockwise (right) to create an up arrow
- Rotate 90° counter-clockwise (left) to create a down arrow
"""

import sys
from pathlib import Path
from PIL import Image


def rotate_sprite(input_path, output_path, rotation_degrees):
    """
    Rotate a PNG sprite image.
    
    Args:
        input_path: Path to the input PNG file
        output_path: Path to save the rotated PNG file
        rotation_degrees: Degrees to rotate (positive = counter-clockwise, negative = clockwise)
    """
    try:
        # Open the image
        img = Image.open(input_path)
        
        # Rotate the image
        # PIL's rotate() uses counter-clockwise as positive
        # So we negate for clockwise rotation
        rotated_img = img.rotate(rotation_degrees, expand=True)
        
        # Save the rotated image
        rotated_img.save(output_path)
        
        print(f"✓ Rotated {input_path.name} by {rotation_degrees}° → {output_path.name}")
        
    except Exception as e:
        print(f"✗ Error rotating {input_path}: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    # Define paths
    project_root = Path(__file__).parent.parent
    sprites_dir = project_root / "data" / "sprites"
    
    # Input: left arrow (mislabeled as up_arrow)
    left_arrow_path = sprites_dir / "up_arrow.gfx_sprite" / "0.png"
    
    # Output paths
    up_arrow_dir = sprites_dir / "up_arrow.gfx_sprite"
    down_arrow_dir = sprites_dir / "down_arrow.gfx_sprite"
    
    # Create output directory for down arrow if it doesn't exist
    down_arrow_dir.mkdir(parents=True, exist_ok=True)
    
    # Verify input file exists
    if not left_arrow_path.exists():
        print(f"✗ Error: Input file not found: {left_arrow_path}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Input: {left_arrow_path}")
    print()
    
    # Rotate right 90° (clockwise) to create up arrow
    # In PIL, negative rotation = clockwise
    up_arrow_path = up_arrow_dir / "0.png"
    print("Creating up arrow (rotate 90° clockwise)...")
    rotate_sprite(left_arrow_path, up_arrow_path, -90)
    
    # Rotate left 90° (counter-clockwise) to create down arrow
    # In PIL, positive rotation = counter-clockwise
    down_arrow_path = down_arrow_dir / "0.png"
    print("Creating down arrow (rotate 90° counter-clockwise)...")
    rotate_sprite(left_arrow_path, down_arrow_path, 90)
    
    print()
    print("✓ All arrow sprites generated successfully!")
    print(f"  Up arrow:   {up_arrow_path}")
    print(f"  Down arrow: {down_arrow_path}")


import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rotate arrow sprite PNG files.")
    parser.parse_args()
    main()
