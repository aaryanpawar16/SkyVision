from __future__ import annotations
from pathlib import Path

def ensure_dir(p: Path | str) -> None:
    Path(p).mkdir(parents=True, exist_ok=True)
