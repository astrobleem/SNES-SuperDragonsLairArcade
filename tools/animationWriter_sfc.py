#!/usr/bin/env python3

import argparse
import sys
import os
import subprocess
import struct
import tempfile
import shutil
import logging
from PIL import Image

# Constants
HEADER_MAGIC = b'SP'
HEADER_SIZE = 9
FRAME_HEADER_SIZE = 6
ALLOWED_FRAME_FILETYPES = ('.png', '.gif', '.bmp')

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')

def run_command(cmd):
    print(f"Running: {' '.join(cmd)}")
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        print(output.decode('utf-8', errors='replace'))
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {' '.join(cmd)}")
        print(f"Output: {e.output.decode('utf-8', errors='replace')}")
        sys.exit(1)

def get_sfc_path():
    # Assuming superfamiconv is in the same directory as this script, under 'superfamiconv' folder
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sfc_path = os.path.join(script_dir, "superfamiconv", "superfamiconv.exe")
    if not os.path.exists(sfc_path):
        # Fallback to just 'superfamiconv' if in path
        sfc_path = "superfamiconv"
    return sfc_path

def parse_arguments():
    parser = argparse.ArgumentParser(description="SNES Animation Writer using superfamiconv")
    
    # Required arguments
    parser.add_argument("-infolder", required=True, help="Input folder containing animation frames")
    parser.add_argument("-outfile", required=True, help="Output animation file")
    
    # Optional arguments with defaults matching animationWriter.py
    parser.add_argument("-palettes", type=int, default=1, help="Number of palettes (default: 1)")
    parser.add_argument("-transcol", help="Transparent color hex (default: 7c1f)", default="7c1f")
    parser.add_argument("-tilesizex", type=int, default=8, help="Tile width (default: 8)")
    parser.add_argument("-tilesizey", type=int, default=8, help="Tile height (default: 8)")
    parser.add_argument("-bpp", type=int, default=4, help="Bits per pixel (default: 4)")
    parser.add_argument("-mode", choices=['bg', 'sprite'], default='bg', help="Mode: bg or sprite (default: bg)")
    parser.add_argument("-verbose", action="store_true", help="Enable verbose logging")
    
    # Ignored/Legacy arguments for compatibility
    parser.add_argument("-refpalette", help="Reference palette image (ignored)")
    parser.add_argument("-optimize", type=bool, default=True, help="Optimize tiles (ignored, always on)")
    parser.add_argument("-directcolor", type=bool, default=False, help="Direct color (ignored)")
    parser.add_argument("-tilethreshold", type=int, default=0, help="Tile threshold (triggers fallback to legacy tool if > 0)")
    parser.add_argument("-maxtiles", type=int, default=1023, help="Max tiles (ignored)")
    parser.add_argument("-resolutionx", type=int, default=256, help="Resolution X (ignored)")
    parser.add_argument("-resolutiony", type=int, default=224, help="Resolution Y (ignored)")
    parser.add_argument("-verify", help="Verify mode (ignored)", default="off")

    return parser.parse_args()

def get_frames(infolder):
    if not os.path.exists(infolder):
        logging.error(f"Error, input folder \"{infolder}\" is nonexistant.")
        sys.exit(1)
        
    files = [f for f in os.listdir(infolder) if os.path.splitext(f)[1].lower() in ALLOWED_FRAME_FILETYPES]
    files.sort()
    
    if not files:
        logging.error(f"Error, input folder \"{infolder}\" does not contain any parseable frame image files.")
        sys.exit(1)
        
    return [os.path.join(infolder, f) for f in files]

def to_windows_path(path):
    # Check if we are on Windows
    if os.name == 'nt':
        return os.path.abspath(path)

    # Check if we are in WSL
    if hasattr(os, 'uname'):
        release = os.uname().release
        # print(f"DEBUG: Release: {release}, Path: {path}")
        if 'microsoft' in release.lower() or 'wsl' in release.lower():
            try:
                # If file exists, convert directly
                if os.path.exists(path):
                    return subprocess.check_output(['wslpath', '-w', path], text=True).strip()
                
                # If file doesn't exist, convert directory and append filename
                dirname, basename = os.path.split(path)
                if dirname:
                    win_dir = subprocess.check_output(['wslpath', '-w', dirname], text=True).strip()
                    # Join with backslash for Windows
                    return f"{win_dir}\\\\{basename}"
                else:
                    # Just a filename? wslpath might fail on just filename if not in current dir?
                    # Assume current dir
                    cwd = os.getcwd()
                    win_cwd = subprocess.check_output(['wslpath', '-w', cwd], text=True).strip()
                    return f"{win_cwd}\\\\{path}"
                    
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                print(f"DEBUG: wslpath failed: {e}")
                return path
    return path

def quantize_image(input_image, output_image, num_colors):
    with Image.open(input_image) as img:
        img = img.convert('RGB')
        # Quantize to num_colors
        # method=1 (MaxCoverage) usually gives good results for pixel art/limited palettes
        # dither=Image.NONE avoids noise
        out = img.quantize(colors=num_colors, method=1, dither=Image.NONE)
        out.save(output_image)

def generate_palette(sfc_path, input_image, output_palette, colors_per_palette):
    # superfamiconv palette -i input.png -d output.palette -C colors
    cmd = [
        sfc_path, "palette",
        "-i", to_windows_path(input_image),
        "-d", to_windows_path(output_palette),
        "-C", str(colors_per_palette)
    ]
    run_command(cmd)

def generate_tiles_and_map(sfc_path, input_image, palette_file, output_tiles, output_map, bpp, tile_w, tile_h, mode):
    # superfamiconv tiles -i input.png -p palette.palette -d output.tiles -B bpp -W w -H h
    cmd_tiles = [
        sfc_path, "tiles",
        "-i", to_windows_path(input_image),
        "-p", to_windows_path(palette_file),
        "-d", to_windows_path(output_tiles),
        "-B", str(bpp),
        "-W", str(tile_w),
        "-H", str(tile_h)
    ]
    
    cmd_map = [
        sfc_path, "map",
        "-i", to_windows_path(input_image),
        "-p", to_windows_path(palette_file),
        "-t", to_windows_path(output_tiles),
        "-d", to_windows_path(output_map),
        "-B", str(bpp),
        "-W", str(tile_w),
        "-H", str(tile_h)
    ]
    
    run_command(cmd_tiles)
    run_command(cmd_map)

def read_file(filepath):
    with open(filepath, 'rb') as f:
        return f.read()

def convert_map_to_sparse_sprite(map_data, tile_w, tile_h, image_w, image_h):
    # map_data is a sequence of 2-byte entries (standard SNES map)
    sparse_data = bytearray()
    
    num_tiles = len(map_data) // 2
    tiles_per_row = image_w // tile_w
    
    for i in range(num_tiles):
        entry = struct.unpack('<H', map_data[i*2:i*2+2])[0]
        
        tile_idx = entry & 0x3FF
        palette = (entry >> 10) & 0x7
        priority = (entry >> 13) & 0x1
        h_flip = (entry >> 14) & 0x1
        v_flip = (entry >> 15) & 0x1
        
        # Calculate X, Y
        col = i % tiles_per_row
        row = i // tiles_per_row
        x = col * tile_w
        y = row * tile_h
        
        # Gracon: priority = 0x3. Let's stick to that for now to match legacy.
        prio = 3
        
        concat_config = (v_flip << 15) | (h_flip << 14) | (prio << 12) | (palette << 9) | (0 << 8) | tile_idx
        
        sparse_data.append(x & 0xFF)
        sparse_data.append(y & 0xFF)
        sparse_data.append(concat_config & 0xFF)
        sparse_data.append((concat_config >> 8) & 0xFF)
        
    return sparse_data

def find_empty_tile_id(tiles_data, bpp):
    tile_size = 8 * bpp 
    num_tiles = len(tiles_data) // tile_size
    for i in range(num_tiles):
        chunk = tiles_data[i*tile_size : (i+1)*tile_size]
        # Check if tile is all zeros
        if all(b == 0 for b in chunk):
            return i
    return -1

def main():
    args = parse_arguments()
    
    # Fallback to legacy animationWriter.py if tilethreshold > 0
    # superfamiconv does not support lossy tile compression (merging similar tiles).
    # Complex backgrounds often rely on this to fit in 1024 tiles.
    if args.tilethreshold > 0:
        logging.info(f"Tile threshold {args.tilethreshold} > 0. Falling back to legacy animationWriter.py for lossy compression.")
        script_dir = os.path.dirname(os.path.abspath(__file__))
        legacy_script = os.path.join(script_dir, "animationWriter.py")
        
        # Forward all arguments
        cmd = [sys.executable, legacy_script] + sys.argv[1:]
        
        try:
            subprocess.check_call(cmd)
            sys.exit(0)
        except subprocess.CalledProcessError as e:
            logging.error(f"Legacy animationWriter.py failed with exit code {e.returncode}")
            sys.exit(e.returncode)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        
    sfc_path = get_sfc_path()
    frames = get_frames(args.infolder)
    
    # Use current directory for temp files to ensure Windows executable can access them
    # (WSL /tmp might not be accessible to Windows apps)
    with tempfile.TemporaryDirectory(dir=os.getcwd()) as temp_dir:
        logging.info(f"Processing {len(frames)} frames...")

        # 2. Process all frames
        processed_frames = []
        
        max_tile_len = 0
        # max_pal_len will be determined by first frame
        max_pal_len = 0
        
        first_frame_palette_data = b''
        
        for frame_idx, frame_path in enumerate(frames):
            base_name = os.path.basename(frame_path)
            
            palette_file = os.path.join(temp_dir, f"{frame_idx}.bin")
            quantized_image = os.path.join(temp_dir, f"{frame_idx}.quantized.png")
            
            colors = 16 if args.bpp == 4 else 4
            # if args.palettes > 1:
            #     colors = colors * args.palettes
            
            # 1. Quantize image using PIL
            # This ensures the image has at most 'colors' unique colors.
            # PIL generates an optimal palette for this image.
            quantize_image(frame_path, quantized_image, colors)
            
            # 2. Generate palette from QUANTIZED image
            # superfamiconv will read the quantized image (RGB) and generate a SNES palette.
            # Since the image has <= colors, superfamiconv should be able to fit it,
            # assuming it can arrange them into sub-palettes correctly.
            # If PIL picked colors that violate sub-palette constraints, superfamiconv might still fail or drop colors.
            # But this is the best we can do without implementing the constraint solver in Python.
            generate_palette(sfc_path, quantized_image, palette_file, colors)
            
            tiles_file = os.path.join(temp_dir, f"{frame_idx}.tiles")
            map_file = os.path.join(temp_dir, f"{frame_idx}.map")
            
            # 3. Generate tiles/map from QUANTIZED image and GENERATED palette
            # Since the palette was generated from THIS image, colors should match exactly.
            generate_tiles_and_map(sfc_path, quantized_image, palette_file, tiles_file, map_file, 
                                   args.bpp, args.tilesizex, args.tilesizey, args.mode)
            
            tiles_data = read_file(tiles_file)
            map_data = read_file(map_file)
            palette_data = read_file(palette_file)
            
            if frame_idx == 0:
                first_frame_palette_data = palette_data
                max_pal_len = len(palette_data)
            
            # Post-process map for sprite mode
            final_map_data = bytearray()
            if args.mode == 'sprite':
                # We need image dimensions to calculate X/Y
                # Use quantized image dimensions
                with Image.open(quantized_image) as img:
                    w, h = img.size
                
                # Find empty tile ID to filter out
                empty_id = find_empty_tile_id(tiles_data, args.bpp)
                
                # Convert
                raw_sparse = convert_map_to_sparse_sprite(map_data, args.tilesizex, args.tilesizey, w, h)
                
                # Filter
                # raw_sparse is sequence of 4 bytes: X, Y, ConfigL, ConfigH
                for i in range(0, len(raw_sparse), 4):
                    entry = raw_sparse[i:i+4]
                    config = entry[2] | (entry[3] << 8)
                    tile_id = config & 0x3FF
                    
                    if tile_id != empty_id:
                        final_map_data.extend(entry)
            else:
                # BG mode: just dump the map
                final_map_data = map_data

            processed_frames.append({
                'tiles': tiles_data,
                'map': final_map_data,
                'palette': first_frame_palette_data if frame_idx == 0 else b'' 
            })
            
            if len(tiles_data) > max_tile_len:
                max_tile_len = len(tiles_data)
                
        # 3. Write Output
        with open(args.outfile, 'wb') as out:
            # Header
            out.write(HEADER_MAGIC)
            out.write(struct.pack('<H', max_tile_len))
            out.write(struct.pack('<H', max_pal_len))
            out.write(struct.pack('<H', len(frames)))
            out.write(bytes([int(args.bpp/2)])) 
            
            # Frame Pointers
            current_ptr = 0
            pointers = []
            
            for frame in processed_frames:
                pointers.append(current_ptr)
                frame_size = FRAME_HEADER_SIZE + len(frame['tiles']) + len(frame['map']) + len(frame['palette'])
                current_ptr += frame_size
                
            base_offset = HEADER_SIZE + len(frames) * 2
            for ptr in pointers:
                final_ptr = base_offset + ptr
                out.write(struct.pack('<H', final_ptr))
                
            # Write Frames
            for frame in processed_frames:
                out.write(struct.pack('<H', len(frame['tiles'])))
                out.write(struct.pack('<H', len(frame['map'])))
                out.write(struct.pack('<H', len(frame['palette'])))
                
                out.write(frame['tiles'])
                out.write(frame['map'])
                out.write(frame['palette'])
                
        logging.info(f"Successfully wrote animation file {args.outfile}")

if __name__ == "__main__":
    main()
