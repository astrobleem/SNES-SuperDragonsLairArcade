#!/usr/bin/env python3
import argparse
import subprocess
import os
import shutil
import sys

def run_command(cmd):
    print(f"Running: {' '.join(cmd)}")
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e}")
        sys.exit(1)

def pad_tilemap_to_32x32(tilemap_file):
    """
    Pad a tilemap file to 32x32 tiles (2048 bytes) if it's smaller.
    
    superfamiconv generates 32x28 tilemaps (1792 bytes) for 256x224 screens.
    gracon.py generates 32x32 tilemaps (2048 bytes) with bottom padding.
    This function adds the padding for compatibility with code expecting 32x32.
    
    Args:
        tilemap_file: Path to the tilemap file to pad
    """
    TARGET_SIZE = 2048  # 32 * 32 * 2 bytes per entry
    
    with open(tilemap_file, 'rb') as f:
        data = f.read()
    
    current_size = len(data)
    
    if current_size >= TARGET_SIZE:
        print(f"Tilemap already {current_size} bytes, no padding needed")
        return
    
    padding_needed = TARGET_SIZE - current_size
    padding = b'\x00' * padding_needed
    
    with open(tilemap_file, 'wb') as f:
        f.write(data)
        f.write(padding)
    
    print(f"Padded tilemap from {current_size} to {TARGET_SIZE} bytes (+{padding_needed} bytes)")

    print(f"Padded tilemap from {current_size} to {TARGET_SIZE} bytes (+{padding_needed} bytes)")

def to_windows_path(path):
    """
    Convert a path to Windows format if running in WSL.
    """
    if not path:
        return path
        
    # Check if running in WSL
    if 'microsoft' in os.uname().release.lower():
        try:
            # If path exists, convert directly
            if os.path.exists(path):
                result = subprocess.check_output(['wslpath', '-w', path], text=True).strip()
                return result
            else:
                # If path doesn't exist, convert directory and append filename
                dirname = os.path.dirname(path)
                basename = os.path.basename(path)
                if os.path.exists(dirname):
                    dir_win = subprocess.check_output(['wslpath', '-w', dirname], text=True).strip()
                    return f"{dir_win}\\{basename}"
                else:
                    # Fallback if directory doesn't exist either
                    return path
        except (subprocess.CalledProcessError, FileNotFoundError):
            return path
    return path

def convert_superfamiconv(input_file, output_base, bpp, palettes, tools_dir, pad_to_32x32=False):
    exe_path = os.path.join(tools_dir, "superfamiconv", "superfamiconv.exe")
    
    print(f"DEBUG: palettes={palettes}, bpp={bpp}")
    
    # Convert paths for Windows executable if needed
    win_input = to_windows_path(os.path.abspath(input_file))
    win_output_base = to_windows_path(os.path.abspath(output_base))
    
    # We need to construct output filenames manually because superfamiconv appends extensions
    # But we passed the base to superfamiconv, so it will append extensions to the Windows path.
    # We don't need to convert the output filenames for our python script's logging, 
    # but we do need to pass the windows base to the tool.
    
    pal_file = f"{output_base}.palette"
    chr_file = f"{output_base}.tiles"
    map_file = f"{output_base}.tilemap"

    # 1. Palette
    # Use provided palettes count if available, otherwise guess based on bpp
    colors_per_palette = 16 if bpp == 4 else 4
    if palettes:
        colors = palettes * colors_per_palette
    else:
        colors = colors_per_palette

    # Note: exe_path is likely /mnt/e/..., which works if we call it directly in WSL?
    # No, we need to call it as a command.
    # If it's a Windows exe, we might need to invoke it differently?
    # subprocess.check_call(['/mnt/e/.../superfamiconv.exe']) works in WSL.
    # But arguments must be Windows paths.
    
    run_command([exe_path, "palette", "-i", win_input, "-d", f"{win_output_base}.palette", "-C", str(colors)])

    # 2. Tiles
    run_command([exe_path, "tiles", "-i", win_input, "-p", f"{win_output_base}.palette", "-d", f"{win_output_base}.tiles", "-B", str(bpp)])

    # 3. Map
    run_command([exe_path, "map", "-i", win_input, "-p", f"{win_output_base}.palette", "-t", f"{win_output_base}.tiles", "-d", f"{win_output_base}.tilemap", "-B", str(bpp)])

    # 4. Pad tilemap if requested
    if pad_to_32x32:
        pad_tilemap_to_32x32(map_file)

    print(f"Successfully converted using superfamiconv: {pal_file}, {chr_file}, {map_file}")

def convert_gracon(input_file, output_base, bpp, tools_dir, unknown_args):
    script_path = os.path.join(tools_dir, "gracon.py")
    
    # Construct command with all arguments
    cmd = [sys.executable, script_path, "-infile", input_file, "-outfilebase", output_base, "-bpp", str(bpp)]
    
    # Pass through any other arguments (like -verify, -mode, etc.)
    cmd.extend(unknown_args)
    
    run_command(cmd)

    # No renaming needed as gracon produces the desired extensions
    dst_pal = f"{output_base}.palette"
    dst_chr = f"{output_base}.tiles"
    dst_map = f"{output_base}.tilemap"

    print(f"Successfully converted using gracon: {dst_pal}, {dst_chr}, {dst_map}")

def main():
    parser = argparse.ArgumentParser(description="SNES Graphics Converter Abstraction")
    parser.add_argument("--tool", choices=["superfamiconv", "gracon"], required=True, help="Converter tool to use")
    
    # Support both --input and -infile (legacy)
    parser.add_argument("--input", help="Input image file")
    parser.add_argument("-infile", dest="input_legacy", help="Input image file (legacy)")
    
    # Support both --output-base and -outfilebase (legacy)
    parser.add_argument("--output-base", help="Output filename base (without extension)")
    parser.add_argument("-outfilebase", dest="output_base_legacy", help="Output filename base (legacy)")
    
    parser.add_argument("--bpp", "-bpp", type=int, default=4, help="Bits per pixel (default: 4)")
    parser.add_argument("--pad-to-32x32", action="store_true", 
                        help="Pad tilemap to 32x32 (2048 bytes) for gracon compatibility (superfamiconv only)")
    
    # Capture other arguments to pass through or ignore
    parser.add_argument("-palettes", type=int, help="Number of palettes (legacy)")
    
    # Use parse_known_args to handle unknown flags like -verify, -optimize, -mode
    args, unknown = parser.parse_known_args()

    # Resolve input/output from legacy args if needed
    input_file = args.input or args.input_legacy
    output_base = args.output_base or args.output_base_legacy
    
    if not input_file or not output_base:
        parser.error("Must provide input file and output base")

    # Determine tools directory relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    if args.tool == "superfamiconv":
        convert_superfamiconv(input_file, output_base, args.bpp, args.palettes, script_dir, args.pad_to_32x32)
    elif args.tool == "gracon":
        if args.pad_to_32x32:
            print("Note: --pad-to-32x32 is ignored for gracon (already outputs 32x32)")
        
        # Reconstruct unknown args for gracon
        # We need to pass -palettes if it was captured
        pass_through_args = unknown
        if args.palettes:
            pass_through_args.extend(["-palettes", str(args.palettes)])
            
        convert_gracon(input_file, output_base, args.bpp, script_dir, pass_through_args)

if __name__ == "__main__":
    main()

