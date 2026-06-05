from __future__ import annotations

import os
from pathlib import Path


def load_env_files(paths: list[Path] | None = None) -> None:
    env_paths = paths or [Path(".env"), Path("Specs/.env")]
    for env_path in env_paths:
        if env_path.exists():
            _load_env_file(env_path)


def _load_env_file(path: Path) -> None:
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        normalized_key = key.strip()
        normalized_value = value.strip().strip('"').strip("'")
        os.environ.setdefault(normalized_key, normalized_value)

