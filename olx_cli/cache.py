from __future__ import annotations

import os
from pathlib import Path


def _cache_dir() -> Path:
    base = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache'))
    return base / 'olx-cli'
