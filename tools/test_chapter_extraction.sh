#!/bin/bash
# Test extraction of a single Dragon's Lair chapter to verify timing alignment
# This extracts video frames and audio for one chapter to verify the conversion worked

set -e

CHAPTER_XML="data/events/introduction_castle_exterior.xml"
CHAPTER_NAME="introduction_castle_exterior"
VIDEO_FILE="data/videos/dl_arcade.mp4"
OUTPUT_DIR="data/chapters/${CHAPTER_NAME}_test"

echo "========================================="
echo "Single Chapter Extraction Test"
echo "========================================="
echo ""
echo "Chapter: $CHAPTER_NAME"
echo "Video: $VIDEO_FILE"
echo "Output: $OUTPUT_DIR"
echo ""

# Check if video file exists
if [ ! -f "$VIDEO_FILE" ]; then
    echo "ERROR: Video file not found: $VIDEO_FILE"
    echo "Make sure the FPS conversion completed successfully."
    exit 1
fi

# Check if XML exists
if [ ! -f "$CHAPTER_XML" ]; then
    echo "ERROR: Chapter XML not found: $CHAPTER_XML"
    exit 1
fi

# Check video frame rate
echo "Checking video frame rate..."
FPS=$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of default=noprint_wrappers=1:nokey=1 "$VIDEO_FILE")
echo "Video FPS: $FPS"

if [ "$FPS" != "24000/1001" ]; then
    echo "WARNING: Video is not 23.976 fps! Expected 24000/1001, got $FPS"
    echo "The timing may not align correctly."
    read -p "Continue anyway? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 0
    fi
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"

echo ""
echo "Extracting chapter with xmlsceneparser.py..."
echo "This will take about 30-60 seconds..."
echo ""

# Run the XML scene parser with video extraction
python3 tools/xmlsceneparser.py \
    -infile "$CHAPTER_XML" \
    -outfolder "$OUTPUT_DIR" \
    -videofile "$VIDEO_FILE"

if [ $? -ne 0 ]; then
    echo "ERROR: Extraction failed!"
    exit 1
fi

echo ""
echo "========================================="
echo "Extraction Complete!"
echo "========================================="
echo ""

# Count extracted files
VIDEO_FRAMES=$(find "$OUTPUT_DIR" -name "video_*.png" 2>/dev/null | wc -l)
AUDIO_FILES=$(find "$OUTPUT_DIR" -name "audio.*.wav" 2>/dev/null | wc -l)

echo "Results:"
echo "  Video frames: $VIDEO_FRAMES PNG files"
echo "  Audio files: $AUDIO_FILES WAV files"
echo "  Location: $OUTPUT_DIR"
echo ""

if [ $VIDEO_FRAMES -eq 0 ]; then
    echo "WARNING: No video frames extracted!"
    echo "Check the chapter XML timestamps and video content."
else
    echo "SUCCESS: Video frames extracted successfully!"
    echo ""
    echo "To verify timing alignment:"
    echo "1. Check the first frame: $OUTPUT_DIR/video_000001.gfx_video.png"
    echo "2. Play the audio: $OUTPUT_DIR/audio.sfx_video.wav"
    echo "3. Compare with video at timestamp 0:53 (start of chapter)"
fi

echo ""
echo "If timing looks correct, you can:"
echo "1. Uncomment line 413 in makefile"
echo "2. Run 'make' to extract all 516 chapters"
