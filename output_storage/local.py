from __future__ import annotations

import os
import uuid
from pathlib import Path


class OutputStorage:
    def __init__(self, base_dir: str | Path | None = None) -> None:
        root = base_dir or os.environ.get("OUTPUT_DIR", "./outputs")
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def root(self) -> Path:
        return self._root

    def new_file_id(self, suffix: str) -> tuple[str, Path]:
        fid = str(uuid.uuid4())
        path = self._root / f"{fid}{suffix}"
        return fid, path

    def path_for(self, file_id: str, suffix: str) -> Path:
        return self._root / f"{file_id}{suffix}"
