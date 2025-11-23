#!/usr/bin/env python3
"""Analyze the difference between gracon and superfamiconv tilemap outputs."""

def main():
    # Read both tilemap files
    with open('test_gracon_new.tilemap', 'rb') as f:
        gracon = f.read()
    
    with open('test_sfc_new.tilemap', 'rb') as f:
        sfc = f.read()
    
    print("=" * 70)
    print("TILEMAP FORMAT COMPARISON")
    print("=" * 70)
    
    print(f"\nFile sizes:")
    print(f"  gracon.py:      {len(gracon):4d} bytes")
    print(f"  superfamiconv:  {len(sfc):4d} bytes")
    print(f"  Difference:      {len(gracon) - len(sfc):4d} bytes")
    
    # SNES tilemap entries are 2 bytes each
    gracon_entries = len(gracon) // 2
    sfc_entries = len(sfc) // 2
    
    print(f"\nTilemap entries (2 bytes each):")
    print(f"  gracon.py:      {gracon_entries:4d} entries")
    print(f"  superfamiconv:  {sfc_entries:4d} entries")
    print(f"  Difference:      {gracon_entries - sfc_entries:4d} entries")
    
    # For 256x224 screen with 8x8 tiles
    width_tiles = 256 // 8  # 32 tiles
    height_tiles = 224 // 8  # 28 tiles
    expected_entries = width_tiles * height_tiles
    
    print(f"\nExpected for 256x224 screen:")
    print(f"  Width in tiles:  {width_tiles} (256 / 8)")
    print(f"  Height in tiles: {height_tiles} (224 / 8)")
    print(f"  Total entries:   {expected_entries}")
    
    print(f"\nFormat analysis:")
    print(f"  gracon.py:      {gracon_entries} = 32 x 32 (padded to square)")
    print(f"  superfamiconv:  {sfc_entries} = 32 x 28 (exact screen size)")
    
    # Check padding pattern
    extra_rows = (gracon_entries - sfc_entries) // width_tiles
    print(f"\nPadding:")
    print(f"  gracon has {extra_rows} extra rows of {width_tiles} tiles each")
    print(f"  This is vertical padding at the bottom")
    
    # Show first few entries from each
    print(f"\nFirst 8 tilemap entries (hex words):")
    print(f"  gracon:  ", end="")
    for i in range(8):
        word = int.from_bytes(gracon[i*2:(i+1)*2], byteorder='little')
        print(f"{word:04X} ", end="")
    print()
    
    print(f"  sfc:     ", end="")
    for i in range(8):
        word = int.from_bytes(sfc[i*2:(i+1)*2], byteorder='little')
        print(f"{word:04X} ", end="")
    print()
    
    # Check if the bottom padding is empty
    print(f"\nPadding content analysis:")
    padding_start = sfc_entries * 2
    padding_data = gracon[padding_start:]
    
    # Check what values are in the padding
    unique_words = set()
    for i in range(0, len(padding_data), 2):
        word = int.from_bytes(padding_data[i:i+2], byteorder='little')
        unique_words.add(word)
    
    print(f"  Unique word values in padding: {sorted(unique_words)}")
    if unique_words == {0}:
        print(f"  Padding is all zeros (empty tiles)")
    elif 0xC000 in unique_words or 0x00C0 in unique_words:
        print(f"  Padding contains 0xC000 (tile with h-flip, v-flip, priority)")
    
    print("\n" + "=" * 70)
    print("CONCLUSION:")
    print("=" * 70)
    print("gracon.py pads the tilemap to 32x32 (1024 entries, 2048 bytes)")
    print("superfamiconv uses exact size 32x28 (896 entries, 1792 bytes)")
    print("\nThe extra 256 bytes are 4 rows of bottom padding (32 tiles x 4 rows)")
    print("\nFor SNES compatibility, the exact format depends on your game engine:")
    print("  - If engine expects 32x32 maps: use gracon format (or add padding)")
    print("  - If engine handles variable sizes: use superfamiconv format")

if __name__ == '__main__':
    main()
