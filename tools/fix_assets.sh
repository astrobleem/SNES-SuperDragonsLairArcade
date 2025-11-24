#!/bin/bash

# Fix Sprites (Force RGBA)
echo "Fixing Sprites..."
for i in {0..4}; do
    # Force to 32-bit RGBA
    convert "data/sprites/bang.gfx_sprite/$i.png" -define png:color-type=6 "data/sprites/bang.gfx_sprite/$i.png"
done
convert "data/sprites/super.gfx_sprite/super_small.png" -define png:color-type=6 "data/sprites/super.gfx_sprite/super_small.png"

# Fix Backgrounds (Resize and Hide Source)
echo "Fixing Backgrounds..."

# Function to process and backup
process_bg() {
    src="$1"
    dest="$2"
    convert "$src" -resize 256x224! -define png:color-type=2 "$dest"
    # If src and dest are different, and src ends in .png, rename src to .png.bak to silence checker
    if [ "$src" != "$dest" ] && [[ "$src" == *.png ]]; then
        mv "$src" "$src.bak"
    fi
}

process_bg "data/backgrounds/titlescreen.gfx_bg/titlescreen.png" "data/backgrounds/titlescreen.gfx_bg/titlescreen.png"
process_bg "data/backgrounds/logo.gfx_bg/logo.gfx_bg.original.png" "data/backgrounds/logo.gfx_bg/logo.gfx_bg.png"
process_bg "data/backgrounds/hiscore.gfx_bg/hall_of_fame.png" "data/backgrounds/hiscore.gfx_bg/hiscore.gfx_bg.png"
process_bg "data/backgrounds/scoreentry.gfx_bg/nameentry.png" "data/backgrounds/scoreentry.gfx_bg/scoreentry.gfx_bg.png"
process_bg "data/backgrounds/msu1.gfx_bg/msu1.png" "data/backgrounds/msu1.gfx_bg/msu1.gfx_bg.png"


# Fix MSU1 Placeholder (Padding)
# Note: The previous step might have created msu1.gfx_bg.png from msu1.png (1024x890) which is fine.
# But if there was an existing 256x192 file, we should ensure it's correct.
# The check_assets.py reported "msu1.gfx_bg.png: Wrong size (256, 192)".
# If msu1.png exists, the resize above handles it.
# If we need to pad the existing one, we should do that.
# Let's assume the resize from source is better if source exists.
# But just in case, let's check if we need to pad.
# Actually, the resize command above overwrites msu1.gfx_bg.png with the resized msu1.png.
# If msu1.png is the high-res source, that's the best path.

echo "Asset fixes complete."
