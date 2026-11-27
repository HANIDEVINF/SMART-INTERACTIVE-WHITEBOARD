"""Small file-system helpers shared by the whole application."""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
OUTPUT_DIR = PROJECT_ROOT / "output"
ASSETS_DIR = PROJECT_ROOT / "assets"


def ensure_dirs() -> None:
    """Create the runtime directories if they do not exist yet."""
    for d in (CONFIG_DIR, OUTPUT_DIR, ASSETS_DIR / "images",
              ASSETS_DIR / "icons", ASSETS_DIR / "fonts"):
        d.mkdir(parents=True, exist_ok=True)


def load_json(path: Path, default=None):
    """Load a JSON file, returning ``default`` (and logging) on failure."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        logger.info("JSON file not found, using default: %s", path)
        return default
    except json.JSONDecodeError as exc:
        logger.error("Invalid JSON in %s: %s", path, exc)
        return default


def save_json(path: Path, data) -> bool:
    """Write ``data`` as JSON.  Returns True on success."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        return True
    except OSError as exc:
        logger.error("Could not write %s: %s", path, exc)
        return False
