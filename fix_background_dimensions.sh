#!/bin/bash
# Automated script to resize all problematic background images to 256x224

echo "Resizing problematic background images to 256x224..."
echo "========================================================"

# 1. hall_of_fame.png (1024x559 -> 256x224)
echo "Resizing hall_of_fame.png..."
python3 tools/img_processor.py \
  --input data/backgrounds/hiscore.gfx_bg/hall_of_fame.png \
  --output data/backgrounds/hiscore.gfx_bg/hall_of_fame.png \
  --width 256 --height 224 --mode cover --colors 16

# 2. msu1.png (1024x890 -> 256x224, rename to msu1.gfx_bg.png)
echo "Resizing msu1.png..."
python3 tools/img_processor.py \
  --input data/backgrounds/msu1.gfx_bg/msu1.png \
  --output data/backgrounds/msu1.gfx_bg/msu1.gfx_bg.png \
  --width 256 --height 224 --mode cover --colors 16

# 3. Fix msu1.gfx_bg.png (256x192 -> 256x224)
echo "Fixing msu1.gfx_bg.png height..."
python3 tools/img_processor.py \
  --input data/backgrounds/msu1.gfx_bg/msu1.gfx_bg.png \
  --output data/backgrounds/msu1.gfx_bg/msu1.gfx_bg.png \
  --width 256 --height 224 --mode cover --colors 16

# 4. nameentry.png (1024x890 -> 256x224, rename to scoreentry.gfx_bg.png)
echo "Resizing nameentry.png..."
python3 tools/img_processor.py \
  --input data/backgrounds/scoreentry.gfx_bg/nameentry.png \
  --output data/backgrounds/scoreentry.gfx_bg/scoreentry.gfx_bg.png \
  --width 256 --height 224 --mode cover --colors 16

# 5. titlescreen.png (1024x559 -> 256x224, rename to titlescreen.gfx_bg.png)
echo "Resizing titlescreen.png..."
python3 tools/img_processor.py \
  --input data/backgrounds/titlescreen.gfx_bg/titlescreen.png \
  --output data/backgrounds/titlescreen.gfx_bg/titlescreen.gfx_bg.png \
  --width 256 --height 224 --mode cover --colors 16

echo "========================================================"
echo "Done! Verifying dimensions..."
python3 tests/check_image_dimensions.py
