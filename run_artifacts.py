from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


STATE_FILENAME = "import_state.json"
LATEST_RUN_FILENAME = "latest_run.json"
LAST_IMPORT_SELECTION_FILENAME = "last_import_selection.json"


@dataclass(slots=True)
class DocumentState:
    source_path: str
    file_hash: str
    process_id: str


@dataclass(slots=True)
class ImportState:
    documents: list[DocumentState]


def load_latest_run(output_path: Path) -> dict[str, Any] | None:
    run_path = output_path / LATEST_RUN_FILENAME
    if not run_path.exists():
        return None

    with run_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def compute_file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_import_state(output_path: Path) -> ImportState:
    state_path = output_path / STATE_FILENAME
    if not state_path.exists():
        return ImportState(documents=[])

    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    return ImportState(
        documents=[
            DocumentState(
                source_path=document["source_path"],
                file_hash=document["file_hash"],
                process_id=document.get("process_id", ""),
            )
            for document in payload.get("documents", [])
        ]
    )


def save_import_state(state: ImportState, output_path: Path) -> None:
    output_path.mkdir(parents=True, exist_ok=True)
    state_path = output_path / STATE_FILENAME
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(asdict(state), handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def write_latest_run(payload: dict[str, Any], output_path: Path) -> None:
    output_path.mkdir(parents=True, exist_ok=True)
    run_path = output_path / LATEST_RUN_FILENAME
    with run_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def save_last_import_selection(source_paths: list[str], output_path: Path) -> None:
    output_path.mkdir(parents=True, exist_ok=True)
    selection_path = output_path / LAST_IMPORT_SELECTION_FILENAME
    with selection_path.open("w", encoding="utf-8") as handle:
        json.dump({"source_paths": source_paths}, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def load_last_import_selection(output_path: Path) -> list[str]:
    selection_path = output_path / LAST_IMPORT_SELECTION_FILENAME
    if not selection_path.exists():
        return []
    with selection_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return list(payload.get("source_paths", []))
