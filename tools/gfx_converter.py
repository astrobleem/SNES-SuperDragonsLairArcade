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

def convert_superfamiconv(input_file, output_base, bpp, tools_dir):
    exe_path = os.path.join(tools_dir, "superfamiconv", "superfamiconv.exe")
    
    pal_file = f"{output_base}.palette"
    chr_file = f"{output_base}.tiles"
    map_file = f"{output_base}.tilemap"

    # 1. Palette
    # Note: Using -C 16 for 4bpp default, might need adjustment based on bpp input
    colors = 16 if bpp == 4 else 4 # Simplified assumption
    run_command([exe_path, "palette", "-i", input_file, "-d", pal_file, "-C", str(colors)])

    # 2. Tiles
    run_command([exe_path, "tiles", "-i", input_file, "-p", pal_file, "-d", chr_file, "-B", str(bpp)])

    # 3. Map
    run_command([exe_path, "map", "-i", input_file, "-p", pal_file, "-t", chr_file, "-d", map_file, "-B", str(bpp)])

    print(f"Successfully converted using superfamiconv: {pal_file}, {chr_file}, {map_file}")

def convert_gracon(input_file, output_base, bpp, tools_dir):
    script_path = os.path.join(tools_dir, "gracon.py")
    
    # gracon uses -outfilebase to determine output names
    # It produces .palette, .tiles, .tilemap by default
    
    run_command([sys.executable, script_path, "-infile", input_file, "-outfilebase", output_base, "-bpp", str(bpp), "-mode", "bg"])

    # No renaming needed as gracon produces the desired extensions
    dst_pal = f"{output_base}.palette"
    dst_chr = f"{output_base}.tiles"
    dst_map = f"{output_base}.tilemap"

    print(f"Successfully converted using gracon: {dst_pal}, {dst_chr}, {dst_map}")

def main():
    parser = argparse.ArgumentParser(description="SNES Graphics Converter Abstraction")
    parser.add_argument("--tool", choices=["superfamiconv", "gracon"], required=True, help="Converter tool to use")
    parser.add_argument("--input", required=True, help="Input image file")
    parser.add_argument("--output-base", required=True, help="Output filename base (without extension)")
    parser.add_argument("--bpp", type=int, default=4, help="Bits per pixel (default: 4)")

    args = parser.parse_args()

    # Determine tools directory relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    if args.tool == "superfamiconv":
        convert_superfamiconv(args.input, args.output_base, args.bpp, script_dir)
    elif args.tool == "gracon":
        convert_gracon(args.input, args.output_base, args.bpp, script_dir)

if __name__ == "__main__":
    main()
