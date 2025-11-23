import os
import sys
import subprocess
import shutil
import unittest

# Add tools directory to path to import gracon if needed, 
# but we will run it as a subprocess to test the CLI interface as intended.

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
TOOLS_DIR = os.path.join(PROJECT_ROOT, 'tools')
GRACON_SCRIPT = os.path.join(TOOLS_DIR, 'gracon.py')
TEST_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'output')

# Path to the local fixture
TEST_IMAGE_PATH = os.path.join(os.path.dirname(__file__), 'fixtures', 'dirk_standin.png')

class TestGracon(unittest.TestCase):
    def setUp(self):
        if not os.path.exists(TEST_OUTPUT_DIR):
            os.makedirs(TEST_OUTPUT_DIR)
            
    def tearDown(self):
        # Comment out to inspect output
        # if os.path.exists(TEST_OUTPUT_DIR):
        #     shutil.rmtree(TEST_OUTPUT_DIR)
        pass

    def test_conversion_defaults(self):
        """Test basic conversion with default settings and verify flag."""
        output_base = os.path.join(TEST_OUTPUT_DIR, 'test_output')
        
        cmd = [
            sys.executable, 
            GRACON_SCRIPT,
            '-infile', TEST_IMAGE_PATH,
            '-outfilebase', output_base,
            '-verify', 'on',
            '-optimize', 'off',
            '-mode', 'bg' # Defaulting to bg mode for testing
        ]
        
        print(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            
        self.assertEqual(result.returncode, 0, "gracon.py failed to run")
        
        # Check if output files exist
        expected_extensions = ['.tiles', '.palette', '.tilemap', '.sample.png']
        for ext in expected_extensions:
            file_path = output_base + ext
            self.assertTrue(os.path.exists(file_path), f"Expected output file {file_path} not found")
            
            if ext == '.tiles':
                file_size = os.path.getsize(file_path)
                self.assertGreater(file_size, 0, f"Tiles file {file_path} is empty")
                print(f"Verified {file_path} exists and has size {file_size} bytes.")
            else:
                print(f"Verified {file_path} exists.")

if __name__ == '__main__':
    unittest.main()
