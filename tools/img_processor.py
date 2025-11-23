import argparse
from PIL import Image, ImageOps
import sys
import os

def process_image(input_path, output_path, width, height, mode, background_color, colors=None):
    try:
        img = Image.open(input_path).convert("RGB")
        target_size = (width, height)

        if mode == 'stretch':
            new_img = img.resize(target_size, Image.Resampling.LANCZOS)
        
        elif mode == 'cover':
            # Resize maintaining aspect ratio to cover the target area, then crop
            img_ratio = img.width / img.height
            target_ratio = width / height

            if img_ratio > target_ratio:
                # Image is wider than target
                new_height = height
                new_width = int(new_height * img_ratio)
            else:
                # Image is taller than target
                new_width = width
                new_height = int(new_width / img_ratio)

            resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Center crop
            left = (new_width - width) / 2
            top = (new_height - height) / 2
            right = (new_width + width) / 2
            bottom = (new_height + height) / 2
            
            new_img = resized_img.crop((left, top, right, bottom))

        elif mode == 'contain':
            # Resize maintaining aspect ratio to fit within target area, pad with background
            new_img = Image.new("RGB", target_size, background_color)
            
            img.thumbnail(target_size, Image.Resampling.LANCZOS)
            
            # Center paste
            paste_x = (width - img.width) // 2
            paste_y = (height - img.height) // 2
            
            new_img.paste(img, (paste_x, paste_y))
        
        else:
            print(f"Error: Unknown mode '{mode}'")
            sys.exit(1)

        # Quantize if requested
        if colors:
            print(f"Quantizing to {colors} colors...")
            # quantize requires an image in P mode or RGB, returns P mode
            new_img = new_img.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)

        # Ensure output directory exists
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        
        new_img.save(output_path)
        print(f"Successfully processed image to {width}x{height} using '{mode}' mode: {output_path}")

    except Exception as e:
        print(f"Error processing image: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Image Processor for SNES Tools")
    parser.add_argument("--input", required=True, help="Input image path")
    parser.add_argument("--output", required=True, help="Output image path")
    parser.add_argument("--width", type=int, default=256, help="Target width (default: 256)")
    parser.add_argument("--height", type=int, default=224, help="Target height (default: 224)")
    parser.add_argument("--mode", choices=['cover', 'contain', 'stretch'], default='cover', 
                        help="Resize mode: cover (crop), contain (pad), stretch (distort)")
    parser.add_argument("--bg-color", default="#000000", help="Background color for contain mode (hex or name)")
    parser.add_argument("--colors", type=int, help="Number of colors to quantize to (optional)")

    args = parser.parse_args()

    process_image(args.input, args.output, args.width, args.height, args.mode, args.bg_color, args.colors)

if __name__ == "__main__":
    main()
