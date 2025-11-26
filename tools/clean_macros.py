import re

import os
import pathlib

# Resolve path relative to this script
script_dir = pathlib.Path(__file__).parent.resolve()
project_root = script_dir.parent
file_path = project_root / 'src/config/macros.inc'

import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean macros.inc by removing duplicate macros.")
    parser.parse_args()

    with open(file_path, 'r') as f:
        lines = f.readlines()

    defined_macros = set()
    new_lines = []
    skip = False
    skip_until_endm = False

    macro_pattern = re.compile(r'^\s*\.macro\s+(\w+)')

    i = 0
    while i < len(lines):
        line = lines[i]
        match = macro_pattern.match(line)
        
        if match:
            macro_name = match.group(1)
            if macro_name in defined_macros:
                print(f"Removing duplicate macro: {macro_name} at line {i+1}")
                skip_until_endm = True
            else:
                defined_macros.add(macro_name)
                new_lines.append(line)
        elif skip_until_endm:
            if line.strip() == '.endm':
                skip_until_endm = False
                # Don't append .endm for the skipped macro
            else:
                # Skipping content
                pass
        else:
            new_lines.append(line)
        
        i += 1

    with open(file_path, 'w') as f:
        f.writelines(new_lines)

    print("Finished cleaning macros.inc")
