file_path = 'src/config/macros.inc'

import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Find duplicate CLASS_NOEXPORT macros.")
    parser.parse_args()

    with open(file_path, 'r') as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        if 'CLASS_NOEXPORT' in line:
            print(f"Found CLASS_NOEXPORT at line {i+1}")
