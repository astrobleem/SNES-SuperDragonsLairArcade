# Daphne Laserdisc Source Files

This directory holds the Daphne CDROM content needed to generate MSU-1 video
and audio data for Super Dragon's Lair Arcade.

## Required Files

1. **`dlcdrom.TXT`** — Daphne framefile mapping laserdisc frame numbers to
   segment files. This small text file can be committed to the repository.

2. **`segments/`** — Directory containing the actual .m2v (video) and .ogg
   (audio) segment files from the Daphne CDROM (~947 MB total). These are
   too large to commit and are gitignored.

## Setup

1. Obtain the Daphne Dragon's Lair CDROM content.
2. Copy the framefile to `data/laserdisc/dlcdrom.TXT`.
3. Copy all `.m2v` and `.ogg` segment files into `data/laserdisc/segments/`.
4. Run the MSU-1 pipeline:
   ```bash
   wsl -e bash -c "cd /mnt/<drive>/path/to/project && python3 tools/generate_msu_data.py --workers 8"
   ```
