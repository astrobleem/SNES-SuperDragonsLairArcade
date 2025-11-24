#!/bin/bash
# Convert Dragon's Lair video from 29.97 fps (Daphne) to 23.976 fps (DirkSimple XML)
# This ensures video timing aligns with the XML chapter event timings

set -e  # Exit on error

INPUT="data/videos/dl_arcade.mp4"
OUTPUT="data/videos/dl_arcade_23976.mp4"
BACKUP="data/videos/dl_arcade_29.97fps_backup.mp4"

echo "========================================="
echo "Dragon's Lair Video FPS Conversion"
echo "========================================="
echo ""
echo "Converting from 29.97 fps to 23.976 fps"
echo "This will take approximately 15-30 minutes..."
echo ""

# Check if input file exists
if [ ! -f "$INPUT" ]; then
    echo "ERROR: Input file not found: $INPUT"
    exit 1
fi

# Check if output already exists
if [ -f "$OUTPUT" ]; then
    echo "WARNING: Output file already exists: $OUTPUT"
    read -p "Overwrite? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Conversion cancelled."
        exit 0
    fi
    rm "$OUTPUT"
fi

echo "Step 1/3: Converting video..."
ffmpeg -i "$INPUT" \
    -r 24000/1001 \
    -c:v libx264 \
    -preset slow \
    -crf 18 \
    -c:a copy \
    "$OUTPUT"

if [ $? -ne 0 ]; then
    echo "ERROR: Conversion failed!"
    exit 1
fi

echo ""
echo "Step 2/3: Verifying output..."
NEW_FPS=$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of default=noprint_wrappers=1:nokey=1 "$OUTPUT")
echo "New frame rate: $NEW_FPS"

if [ "$NEW_FPS" != "24000/1001" ]; then
    echo "WARNING: Frame rate verification failed! Expected 24000/1001, got $NEW_FPS"
    echo "The file was created but may not be correct."
    exit 1
fi

echo ""
echo "Step 3/3: Backing up original and replacing..."
read -p "Replace original file with converted version? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    mv "$INPUT" "$BACKUP"
    mv "$OUTPUT" "$INPUT"
    echo ""
    echo "========================================="
    echo "Conversion Complete!"
    echo "========================================="
    echo "Original backed up to: $BACKUP"
    echo "New 23.976 fps video: $INPUT"
    echo ""
    echo "Next steps:"
    echo "1. Uncomment line 413 in makefile to enable video extraction"
    echo "2. Run 'make' to generate chapter video/audio assets"
else
    echo ""
    echo "========================================="
    echo "Conversion Complete!"
    echo "========================================="
    echo "Original file unchanged: $INPUT"
    echo "Converted file saved to: $OUTPUT"
    echo ""
    echo "To use the converted file:"
    echo "  mv $INPUT $BACKUP"
    echo "  mv $OUTPUT $INPUT"
fi
