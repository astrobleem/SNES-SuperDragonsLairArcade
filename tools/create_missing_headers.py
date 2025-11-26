import os

import os
import pathlib

script_dir = pathlib.Path(__file__).parent.resolve()
project_root = script_dir.parent
directory = project_root / 'src/object/event'
extension_asm = '.65816'
extension_header = '.h'

import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create missing header files for .65816 asm files.")
    parser.parse_args()

    for filename in os.listdir(directory):
        if filename.endswith(extension_asm):
            base_name = filename[:-len(extension_asm)]
            header_name = base_name + extension_header
            header_path = os.path.join(directory, header_name)
            
            if not os.path.exists(header_path):
                print(f"Creating missing header: {header_path}")
                with open(header_path, 'w') as f:
                    f.write(f"; Empty header for {base_name}\n")
