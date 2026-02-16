#!/bin/bash
# Regenerate chapter include files from XML events
cd /mnt/e/gh/SNES-SuperDragonsLairArcade

# Clear stale includes
rm -f data/chapters/chapter.include data/chapters/chapter_data.include

# Re-run xmlsceneparser on all XMLs
for xml in data/events/*.xml; do
    python3 tools/xmlsceneparser.py -infile "$xml" -outfolder data/chapters 2>/dev/null
done

echo "Done. Include file line counts:"
wc -l data/chapters/chapter.include data/chapters/chapter_data.include
