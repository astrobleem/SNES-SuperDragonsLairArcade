
import os

def generate_manifest():
    header = """<?xml version="1.0" encoding="UTF-8"?>
<cartridge region="NTSC">
  <rom name="SuperDragonsLairArcade.sfc" size="0x100000">
    <map mode="linear" address="40-7f:0000-ffff"/>
    <map mode="linear" address="c0-ff:0000-ffff"/>
    <map mode="shadow" address="00-3f:8000-ffff"/>
    <map mode="shadow" address="80-bf:8000-ffff"/>
  </rom>
  <map address="00-3f:8000-ffff" id="rom" mode="shadow"/>
  <map address="80-bf:8000-ffff" id="rom" mode="shadow"/>
  <msu1>
    <!-- Audio tracks for Super Dragon's Lair Arcade -->
"""
    footer = """  </msu1>
</cartridge>
"""
    
    with open("/mnt/e/gh/SuperDragonsLairArcade.sfc/manifest.xml", "w") as f:
        f.write(header)
        for i in range(1, 206):
            f.write(f'    <track number="{i}"><name>SuperDragonsLairArcade-{i}.pcm</name></track>\n')
        f.write(footer)

if __name__ == "__main__":
    generate_manifest()
