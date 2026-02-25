"""Shared path resolution for build tools."""
import configparser
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DISTRIBUTION = PROJECT_ROOT / "distribution"
BUILD_DIR = PROJECT_ROOT / "build"
TOOLS_DIR = PROJECT_ROOT / "tools"
LASERDISC_DIR = PROJECT_ROOT / "data" / "laserdisc"
DAPHNE_FRAMEFILE = LASERDISC_DIR / "framefile" / "dlcdrom.TXT"
DAPHNE_CONTENT = LASERDISC_DIR / "DLCDROM"


def _load_config():
    cfg = configparser.ConfigParser()
    cfg.read(PROJECT_ROOT / "project.conf")
    return cfg

_cfg = _load_config()


def get(key, default=None):
    """Get config value: env var (uppercased) > project.conf [paths] > default."""
    return os.environ.get(key.upper()) or _cfg.get("paths", key, fallback=None) or default

FFMPEG = get("ffmpeg", "ffmpeg")


# Path conversion helpers
def wsl_to_windows(p):
    """Convert /mnt/x/... to X:\\..."""
    p = str(p)
    if p.startswith("/mnt/") and len(p) > 5:
        return p[5].upper() + ":" + p[6:].replace("/", "\\")
    return p


def windows_to_wsl(p):
    """Convert X:\\... to /mnt/x/..."""
    p = str(p)
    if len(p) >= 3 and p[1] == ':':
        return "/mnt/" + p[0].lower() + p[2:].replace("\\", "/")
    return p
