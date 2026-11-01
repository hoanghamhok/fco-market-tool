"""Separate durable user data from the one-file bundle's temporary resources."""

from pathlib import Path
import sys

RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
APP_ROOT = (
    Path(sys.executable).resolve().parent / "FCO-Market-3-data"
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent.parent / "data-v3"
)
