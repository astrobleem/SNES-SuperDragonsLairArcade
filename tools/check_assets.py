#!/usr/bin/env python3
"""Check asset dimensions and transparency against specifications."""

from PIL import Image
import os
import glob

# Expected specifications
SPRITE_SPECS = {
    'left_arrow': {'size': (32, 32), 'transparent': True},
    'right_arrow': {'size': (32, 32), 'transparent': True},
    'up_arrow': {'size': (32, 32), 'transparent': True},
    'down_arrow': {'size': (32, 32), 'transparent': True},
    'life_car': {'size': (24, 16), 'transparent': True},
    'life_counter': {'size': (16, 16), 'transparent': True},
    'points.normal': {'size': (32, 8), 'transparent': True},
    'points.extra': {'size': (32, 8), 'transparent': True},
    'bang': {'size': (46, 40), 'transparent': True},
    'super': {'size': None, 'transparent': True},  # Variable size, skip size check
}

BACKGROUND_SPECS = {
    'titlescreen.gfx_bg': {'size': (256, 224), 'transparent': False},
    'logo.gfx_bg': {'size': (256, 224), 'transparent': False},
    'hiscore.gfx_bg': {'size': (256, 224), 'transparent': False},
    'scoreentry.gfx_bg': {'size': (256, 224), 'transparent': False},
    'msu1.gfx_bg': {'size': (256, 224), 'transparent': False},
    'hud.gfx_directcolor': {'size': (256, 224), 'transparent': True},
}

def check_sprites():
    """Check all sprite assets."""
    print("=" * 80)
    print("SPRITE ASSET ANALYSIS")
    print("=" * 80)
    
    issues = []
    missing = []
    
    for sprite_name, spec in SPRITE_SPECS.items():
        sprite_dir = f"data/sprites/{sprite_name}.gfx_sprite"
        
        if not os.path.exists(sprite_dir):
            missing.append(f"❌ MISSING: {sprite_dir}/ (entire directory)")
            continue
        
        png_files = sorted(glob.glob(f"{sprite_dir}/*.png"))
        
        if not png_files:
            missing.append(f"❌ MISSING: {sprite_dir}/*.png (no PNG files)")
            continue
        
        print(f"\n{sprite_name}:")
        print(f"  Expected: {spec['size']}, Transparent: {spec['transparent']}")
        
        for png_file in png_files:
            try:
                img = Image.open(png_file)
                size = img.size
                mode = img.mode
                has_alpha = mode in ('RGBA', 'LA', 'PA')
                
                status = "✅"
                notes = []
                
                if spec['size'] is not None and size != spec['size']:
                    status = "❌"
                    notes.append(f"WRONG SIZE: {size} (expected {spec['size']})")
                    issues.append(f"{png_file}: Wrong size {size}, expected {spec['size']}")
                
                if spec['transparent'] and not has_alpha:
                    status = "⚠️"
                    notes.append(f"NO ALPHA: mode={mode} (needs RGBA)")
                    issues.append(f"{png_file}: No alpha channel (mode={mode})")
                
                if not spec['transparent'] and has_alpha:
                    status = "⚠️"
                    notes.append(f"HAS ALPHA: mode={mode} (should be RGB)")
                
                note_str = " - " + ", ".join(notes) if notes else ""
                print(f"  {status} {os.path.basename(png_file)}: {size} {mode}{note_str}")
                
            except Exception as e:
                print(f"  ❌ {os.path.basename(png_file)}: ERROR - {e}")
                issues.append(f"{png_file}: Error reading file - {e}")
    
    return issues, missing

def check_backgrounds():
    """Check all background assets."""
    print("\n" + "=" * 80)
    print("BACKGROUND ASSET ANALYSIS")
    print("=" * 80)
    
    issues = []
    missing = []
    
    for bg_name, spec in BACKGROUND_SPECS.items():
        bg_dir = f"data/backgrounds/{bg_name}"
        
        if not os.path.exists(bg_dir):
            missing.append(f"❌ MISSING: {bg_dir}/ (entire directory)")
            continue
        
        # Look for the expected output filename
        expected_file = f"{bg_dir}/{bg_name}.png"
        png_files = glob.glob(f"{bg_dir}/*.png")
        
        if not png_files:
            missing.append(f"❌ MISSING: {bg_dir}/*.png (no PNG files)")
            continue
        
        print(f"\n{bg_name}:")
        print(f"  Expected: {spec['size']}, Transparent: {spec['transparent']}")
        
        for png_file in png_files:
            try:
                img = Image.open(png_file)
                size = img.size
                mode = img.mode
                has_alpha = mode in ('RGBA', 'LA', 'PA')
                
                status = "✅"
                notes = []
                
                if size != spec['size']:
                    status = "❌"
                    notes.append(f"WRONG SIZE: {size} (expected {spec['size']})")
                    issues.append(f"{png_file}: Wrong size {size}, expected {spec['size']}")
                
                if spec['transparent'] and not has_alpha:
                    status = "⚠️"
                    notes.append(f"NO ALPHA: mode={mode} (needs RGBA)")
                    issues.append(f"{png_file}: No alpha channel (mode={mode})")
                
                if not spec['transparent'] and has_alpha:
                    status = "⚠️"
                    notes.append(f"HAS ALPHA: mode={mode} (should be RGB)")
                
                note_str = " - " + ", ".join(notes) if notes else ""
                print(f"  {status} {os.path.basename(png_file)}: {size} {mode}{note_str}")
                
            except Exception as e:
                print(f"  ❌ {os.path.basename(png_file)}: ERROR - {e}")
                issues.append(f"{png_file}: Error reading file - {e}")
    
    return issues, missing

def main():
    sprite_issues, sprite_missing = check_sprites()
    bg_issues, bg_missing = check_backgrounds()
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    all_issues = sprite_issues + bg_issues
    all_missing = sprite_missing + bg_missing
    
    if all_missing:
        print(f"\n🔴 MISSING ASSETS ({len(all_missing)}):")
        for item in all_missing:
            print(f"  {item}")
    
    if all_issues:
        print(f"\n⚠️  OUT OF SPEC ({len(all_issues)}):")
        for item in all_issues:
            print(f"  {item}")
    
    if not all_missing and not all_issues:
        print("\n✅ All assets are present and meet specifications!")
    
    print(f"\nTotal Issues: {len(all_issues)}")
    print(f"Total Missing: {len(all_missing)}")

if __name__ == "__main__":
    main()
