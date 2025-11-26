
file_path = 'data/chapters/chapter.include'

import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Remove duplicate .include lines from chapter.include file.")
    parser.parse_args()

    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()

        seen = set()
        unique_lines = []
        duplicates_count = 0

        for line in lines:
            stripped = line.strip()
            # Keep empty lines or comments, or check for duplicates of includes
            if stripped.startswith('.include'):
                if stripped not in seen:
                    seen.add(stripped)
                    unique_lines.append(line)
                else:
                    duplicates_count += 1
            else:
                unique_lines.append(line)

        with open(file_path, 'w') as f:
            f.writelines(unique_lines)

        print(f"Removed {duplicates_count} duplicate lines from {file_path}")

    except FileNotFoundError:
        print(f"File not found: {file_path}")
