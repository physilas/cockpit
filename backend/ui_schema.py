"""Read-only UI metadata shared by every frontend.

The JSON file is deliberately independent of gameplay code.  `build.py`
exports the same data for the browser, so labels, field layout and error
messages cannot silently diverge between Pass & Play and multiplayer.
"""
import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def frontend_schema():
    path = Path(__file__).with_name("ui_schema.json")
    return json.loads(path.read_text(encoding="utf-8"))


def feld_layout():
    """Return a fresh layout so callers cannot mutate the cached schema."""
    return json.loads(json.dumps(frontend_schema()["feld_layout"]))
