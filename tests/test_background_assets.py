#!/usr/bin/env python3
"""
Pre-build validation test for background assets.
Tests that all background images:
1. Can be converted without errors (recursion, timeout, etc.)
2. Have correct dimensions (256x224 for SNES backgrounds)
3. Don't have mixed sizes in the same folder

This catches issues before the full build.
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path
from PIL import Image

# Add tools directory to path
TOOLS_DIR = Path(__file__).parent.parent / 'tools'
sys.path.insert(0, str(TOOLS_DIR))

import gracon

# Expected dimensions for SNES backgrounds
EXPECTED_WIDTH = 256
EXPECTED_HEIGHT = 224

def check_image_dimensions(png_file):
    """Check if image has correct SNES dimensions"""
    try:
        with Image.open(png_file) as img:
            width, height = img.size
            return width, height, (width == EXPECTED_WIDTH and height == EXPECTED_HEIGHT)
    except Exception as e:
        return None, None, False

def test_background_conversion():
    """Test that all background images can be converted with gracon.py"""
    
    project_root = Path(__file__).parent.parent
    backgrounds_dir = project_root / 'data' / 'backgrounds'
    
    if not backgrounds_dir.exists():
        print(f"ERROR: Backgrounds directory not found: {backgrounds_dir}")
        return False
    
    # Find all background folders
    bg_folders = [d for d in backgrounds_dir.iterdir() 
                  if d.is_dir() and (d.name.endswith('.gfx_bg') or d.name.endswith('.gfx_directcolor'))]
    
    print(f"Found {len(bg_folders)} background folders to test")
    print("=" * 60)
    
    failed_backgrounds = []
    dimension_issues = []
    
    for bg_folder in sorted(bg_folders):
        # Find PNG files in the folder
        png_files = list(bg_folder.glob('*.png'))
        
        # Skip folders with no PNG files or only .original.png files
        png_files = [f for f in png_files if not f.name.endswith('.original.png')]
        
        if not png_files:
            print(f"⚠️  SKIP: {bg_folder.name} (no PNG files)")
            continue
        
        # Check for mixed dimensions in the same folder
        dimensions_in_folder = set()
        
        for png_file in png_files:
            width, height, is_correct = check_image_dimensions(png_file)
            
            if width is None:
                print(f"❌ ERROR: {bg_folder.name}/{png_file.name} - Cannot read image")
                failed_backgrounds.append((bg_folder.name, png_file.name, "Cannot read image file"))
                continue
            
            dimensions_in_folder.add((width, height))
            
            # Check dimensions
            if not is_correct:
                msg = f"Wrong dimensions: {width}×{height} (expected {EXPECTED_WIDTH}×{EXPECTED_HEIGHT})"
                dimension_issues.append((bg_folder.name, png_file.name, width, height))
                print(f"⚠️  DIM: {bg_folder.name}/{png_file.name} - {width}×{height}")
            
            # Test conversion
            print(f"Testing: {bg_folder.name}/{png_file.name} ({width}×{height})...", end=' ')
            
            # Determine conversion flags based on folder type
            if bg_folder.name.endswith('.gfx_directcolor'):
                flags = ['-verify', 'on', '-optimize', 'on', '-directcolor', 'on', 
                        '-tilethreshold', '10', '-palettes', '1', '-bpp', '8', '-mode', 'bg']
            else:
                flags = ['-verify', 'on', '-optimize', 'on', '-tilethreshold', '15', 
                        '-palettes', '8', '-bpp', '4', '-mode', 'bg']
            
            # Create temporary output directory
            with tempfile.TemporaryDirectory() as tmpdir:
                outbase = os.path.join(tmpdir, 'test_output')
                
                cmd = [
                    sys.executable,
                    str(TOOLS_DIR / 'gracon.py'),
                    *flags,
                    '-infile', str(png_file),
                    '-outfilebase', outbase
                ]
                
                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=30  # 30 second timeout per image
                    )
                    
                    if result.returncode == 0:
                        print("✅ PASS")
                    else:
                        print(f"❌ FAIL")
                        print(f"   Error: {result.stderr[:200]}")
                        failed_backgrounds.append((bg_folder.name, png_file.name, result.stderr))
                        
                except subprocess.TimeoutExpired:
                    print("❌ TIMEOUT")
                    failed_backgrounds.append((bg_folder.name, png_file.name, "Conversion timed out after 30 seconds"))
                    
                except RecursionError as e:
                    print("❌ RECURSION ERROR")
                    failed_backgrounds.append((bg_folder.name, png_file.name, f"RecursionError: {str(e)}"))
                    
                except Exception as e:
                    print(f"❌ ERROR: {type(e).__name__}")
                    failed_backgrounds.append((bg_folder.name, png_file.name, str(e)))
        
        # Warn about mixed dimensions in same folder
        if len(dimensions_in_folder) > 1:
            print(f"⚠️  WARNING: {bg_folder.name} has mixed dimensions: {dimensions_in_folder}")
    
    print("=" * 60)
    
    # Report dimension issues
    if dimension_issues:
        print(f"\n⚠️  DIMENSION ISSUES: {len(dimension_issues)} image(s) with incorrect size:")
        for folder, file, width, height in dimension_issues:
            print(f"  {folder}/{file}: {width}×{height} (expected {EXPECTED_WIDTH}×{EXPECTED_HEIGHT})")
        print()
    
    # Report conversion failures
    if failed_backgrounds:
        print(f"❌ CONVERSION FAILED: {len(failed_backgrounds)} background(s) failed:")
        for folder, file, error in failed_backgrounds:
            print(f"\n  {folder}/{file}")
            print(f"    {error[:200]}")
        return False
    
    if dimension_issues:
        print("⚠️  Build may have issues due to incorrect image dimensions.")
        print("   Use tools/img_processor.py to resize images to 256×224")
        return False
    
    print(f"✅ SUCCESS: All backgrounds passed validation!")
    return True

if __name__ == '__main__':
    success = test_background_conversion()
    sys.exit(0 if success else 1)
