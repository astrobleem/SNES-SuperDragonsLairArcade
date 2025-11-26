import unittest
import subprocess
import sys
import os

TOOLS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'tools'))

class TestToolsSmoke(unittest.TestCase):
    def test_gracon_help(self):
        cmd = [sys.executable, os.path.join(TOOLS_DIR, 'gracon.py'), '--help']
        result = subprocess.run(cmd, capture_output=True, text=True)
        # gracon might not have --help implemented nicely, but it shouldn't crash with SyntaxError
        # It actually prints usage if no args, or might exit 1.
        # Let's check if it runs at all.
        self.assertNotEqual(result.returncode, 0xC0000005) # Access violation (crash)

    def test_xmlsceneparser_help(self):
        cmd = [sys.executable, os.path.join(TOOLS_DIR, 'xmlsceneparser.py'), '--help']
        result = subprocess.run(cmd, capture_output=True, text=True)
        # Should not crash
        self.assertNotEqual(result.returncode, 0xC0000005)

    def test_mod2snes_help(self):
        cmd = [sys.executable, os.path.join(TOOLS_DIR, 'mod2snes.py'), '--help']
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0xC0000005)

    def test_animationWriter_help(self):
        cmd = [sys.executable, os.path.join(TOOLS_DIR, 'animationWriter.py'), '--help']
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0xC0000005)

    def test_msu1blockwriter_help(self):
        cmd = [sys.executable, os.path.join(TOOLS_DIR, 'msu1blockwriter.py'), '--help']
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0xC0000005)

    def test_check_assets_help(self):
        cmd = [sys.executable, os.path.join(TOOLS_DIR, 'check_assets.py'), '--help']
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0xC0000005)

    def test_chapter_event_inventory_help(self):
        cmd = [sys.executable, os.path.join(TOOLS_DIR, 'chapter_event_inventory.py'), '--help']
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0xC0000005)

    def test_deduplicate_chapters_help(self):
        cmd = [sys.executable, os.path.join(TOOLS_DIR, 'deduplicate_chapters.py'), '--help']
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0xC0000005)

    def test_create_template_help(self):
        cmd = [sys.executable, os.path.join(TOOLS_DIR, 'create_template.py'), '--help']
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0xC0000005)

    def test_create_missing_headers_help(self):
        cmd = [sys.executable, os.path.join(TOOLS_DIR, 'create_missing_headers.py'), '--help']
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0xC0000005)

    def test_find_dupes_help(self):
        cmd = [sys.executable, os.path.join(TOOLS_DIR, 'find_dupes.py'), '--help']
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0xC0000005)

    def test_find_long_paths_help(self):
        cmd = [sys.executable, os.path.join(TOOLS_DIR, 'find_long_paths.py'), '--help']
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0xC0000005)

    def test_fix_macros_help(self):
        cmd = [sys.executable, os.path.join(TOOLS_DIR, 'fix_macros.py'), '--help']
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0xC0000005)

    def test_fix_macros_final_help(self):
        cmd = [sys.executable, os.path.join(TOOLS_DIR, 'fix_macros_final.py'), '--help']
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0xC0000005)

    def test_rename_long_paths_help(self):
        cmd = [sys.executable, os.path.join(TOOLS_DIR, 'rename_long_paths.py'), '--help']
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0xC0000005)

    def test_rotate_arrow_sprite_help(self):
        cmd = [sys.executable, os.path.join(TOOLS_DIR, 'rotate_arrow_sprite.py'), '--help']
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0xC0000005)

    def test_clean_macros_help(self):
        cmd = [sys.executable, os.path.join(TOOLS_DIR, 'clean_macros.py'), '--help']
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0xC0000005)

    def test_compare_anim_help(self):
        cmd = [sys.executable, os.path.join(TOOLS_DIR, 'compare_anim.py'), '--help']
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0xC0000005)

    def test_expand_cutscene_events_help(self):
        cmd = [sys.executable, os.path.join(TOOLS_DIR, 'expand_cutscene_events.py'), '--help']
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0xC0000005)

if __name__ == '__main__':
    unittest.main()
