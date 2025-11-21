import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "lua_scene_exporter"


def run_exporter(lua_file: Path, output_path: Path):
    result = subprocess.run(
        [
            sys.executable,
            str(TOOLS / "lua_scene_exporter.py"),
            "--input",
            str(lua_file),
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_lua_scene_exporter(tmp_path):
    lua_file = FIXTURE_DIR / "game.lua"
    expected_script = (FIXTURE_DIR / "expected_chapter.script").read_text()

    output_path = tmp_path / "chapter.script"
    run_exporter(lua_file, output_path)

    assert output_path.exists()
    assert output_path.read_text() == expected_script
