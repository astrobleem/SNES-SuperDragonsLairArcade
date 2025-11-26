from PIL import Image
import sys

def quantize_image(input_image, output_image, num_colors):
    print(f"Processing {input_image} -> {output_image} with {num_colors} colors")
    try:
        with Image.open(input_image) as img:
            print(f"Original mode: {img.mode}")
            print(f"Original info: {img.info}")
            
            img = img.convert('RGB')
            print(f"Converted mode: {img.mode}")
            
            # method=1 (MaxCoverage) usually gives good results for pixel art/limited palettes
            # dither=Image.NONE avoids noise
            out = img.quantize(colors=num_colors, method=1, dither=Image.NONE)
            print(f"Quantized mode: {out.mode}")
            print(f"Quantized info: {out.info}")
            
            out.save(output_image)
            print("Saved successfully")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

import os
import pathlib

if __name__ == "__main__":
    script_dir = pathlib.Path(__file__).parent.resolve()
    project_root = script_dir.parent
    input_path = project_root / "data/sprites/brake.gfx_sprite/0.png"
    output_path = script_dir / "test_out.png"
    quantize_image(str(input_path), str(output_path), 16)
