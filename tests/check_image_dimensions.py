#!/usr/bin/env python3
"""
Quick dimension check for all background images.
Identifies images that aren't 256×224 without attempting conversion.
"""

from pathlib import Path
from PIL import Image

EXPECTED_WIDTH = 256
EXPECTED_HEIGHT = 224

def main():
    project_root = Path(__file__).parent.parent
    backgrounds_dir = project_root / 'data' / 'backgrounds'
    
    bg_folders = [d for d in backgrounds_dir.iterdir() 
                  if d.is_dir() and (d.name.endswith('.gfx_bg') or d.name.endswith('.gfx_directcolor'))]
    
    print(f"Checking dimensions of background images...")
    print("=" * 70)
    
    issues = []
    correct = []
    
    for bg_folder in sorted(bg_folders):
        png_files = [f for f in bg_folder.glob('*.png') 
                     if not f.name.endswith('.original.png')]
        
        if not png_files:
            continue
        
        for png_file in png_files:
            try:
                with Image.open(png_file) as img:
                    width, height = img.size
                    size_mb = png_file.stat().st_size / (1024 * 1024)
                    
                    status = "✅" if (width == EXPECTED_WIDTH and height == EXPECTED_HEIGHT) else "❌"
                    
                    print(f"{status} {bg_folder.name}/{png_file.name}")
                    print(f"   Dimensions: {width}×{height}, Size: {size_mb:.2f}MB")
                    
                    if width != EXPECTED_WIDTH or height != EXPECTED_HEIGHT:
                        issues.append((bg_folder.name, png_file.name, width, height, size_mb))
                    else:
                        correct.append((bg_folder.name, png_file.name, size_mb))
                        
            except Exception as e:
                print(f"❌ {bg_folder.name}/{png_file.name}")
                print(f"   ERROR: {e}")
                issues.append((bg_folder.name, png_file.name, None, None, 0))
    
    print("=" * 70)
    print(f"\n✅ Correct dimensions: {len(correct)}")
    print(f"❌ Incorrect dimensions: {len(issues)}")
    
    if issues:
        print(f"\n⚠️  Images needing resize to {EXPECTED_WIDTH}×{EXPECTED_HEIGHT}:")
        for folder, file, width, height, size_mb in issues:
            if width and height:
                print(f"  {folder}/{file}: {width}×{height} ({size_mb:.2f}MB)")
            else:
                print(f"  {folder}/{file}: ERROR reading file")
        
        print(f"\nTo fix, use:")
        print(f"  python tools/img_processor.py --input INPUT.png --output OUTPUT.png \\")
        print(f"    --width {EXPECTED_WIDTH} --height {EXPECTED_HEIGHT} --mode cover --colors 16")
        
        return False
    
    return True

if __name__ == '__main__':
    import sys
    success = main()
    sys.exit(0 if success else 1)
