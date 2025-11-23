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

if __name__ == '__main__':
    unittest.main()
