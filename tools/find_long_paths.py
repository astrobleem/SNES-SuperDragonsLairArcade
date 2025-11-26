
file_path = 'data/chapters/chapter.include'
max_len = 60

import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Find paths longer than 60 characters in chapter.include.")
    parser.parse_args()

    with open(file_path, 'r') as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        line = line.strip()
        # .include "path"
        # The string inside quotes is what matters.
        if line.startswith('.include "'):
            path = line.split('"')[1]
            if len(path) > max_len:
                print(f"Line {i+1}: Length {len(path)}: {path}")
