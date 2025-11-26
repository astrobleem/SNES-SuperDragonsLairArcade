import os

import os
import pathlib

script_dir = pathlib.Path(__file__).parent.resolve()
project_root = script_dir.parent
file_path = project_root / 'src/config/macros.inc'

import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fix macros.inc by removing lines before .ifndef MACROS_INC.")
    parser.parse_args()

    with open(file_path, 'r') as f:
        lines = f.readlines()

    # Find the start of the guarded section
    start_index = -1
    for i, line in enumerate(lines):
        if '.ifndef MACROS_INC' in line:
            start_index = i
            break

    if start_index != -1:
        new_content = lines[start_index:]
        with open(file_path, 'w') as f:
            f.writelines(new_content)
        print(f"Fixed {file_path}. Removed {start_index} lines.")
    else:
        print(f"Could not find .ifndef MACROS_INC in {file_path}")
