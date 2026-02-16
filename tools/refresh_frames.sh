#!/bin/bash
cd /mnt/e/gh/SNES-SuperDragonsLairArcade

count=0
for d in data/chapters/*/; do
    name=$(basename "$d")
    if ls "$d"video_*.gfx_video.png >/dev/null 2>&1; then
        mkdir -p "data/videos/frames/$name"
        cp "$d"video_*.gfx_video.png "data/videos/frames/$name/"
        count=$((count + 1))
    fi
done
echo "Copied frames for $count chapters"
