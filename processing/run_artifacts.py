from __future__ import annotations

import hashlib
import json
import os
import tempfile
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


def load_latest_run(output_path: Path, neo4j_client=None) -> dict[str, Any] | None:
    run_path = output_path / LATEST_RUN_FILENAME
    if neo4j_client is not None:
        staged = neo4j_client.read_staged_artifact(run_path)
        if staged is not None:
            return staged
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


def save_import_state(state: ImportState, output_path: Path, neo4j_client=None) -> None:
    write_artifact(output_path / STATE_FILENAME, asdict(state), neo4j_client)


def write_latest_run(payload: dict[str, Any], output_path: Path, neo4j_client=None) -> None:
    write_artifact(output_path / LATEST_RUN_FILENAME, payload, neo4j_client)


def write_artifact(path: Path, payload: dict, neo4j_client=None) -> None:
    if neo4j_client is not None:
        neo4j_client.stage_artifact(path, payload)
    else:
        atomic_write_json(path, payload)


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def save_last_import_selection(
    source_paths: list[str],
    output_path: Path,
    *,
    display_paths: list[str] | None = None,
    archive_path: str = "",
    run_mode: str = "",
    neo4j_client=None,
) -> None:
    write_artifact(output_path / LAST_IMPORT_SELECTION_FILENAME, {
        "source_paths": source_paths,
        "display_paths": display_paths or source_paths,
        "archive_path": archive_path,
        "run_mode": run_mode,
    }, neo4j_client)


def load_last_import_selection(output_path: Path) -> list[str]:
    return list(load_last_import_context(output_path).get("source_paths", []))


def load_last_import_context(output_path: Path) -> dict[str, Any]:
    selection_path = output_path / LAST_IMPORT_SELECTION_FILENAME
    if not selection_path.exists():
        return {"source_paths": [], "display_paths": [], "archive_path": "", "run_mode": ""}
    with selection_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return {
        "source_paths": list(payload.get("source_paths", [])),
        "display_paths": list(payload.get("display_paths", payload.get("source_paths", []))),
        "archive_path": str(payload.get("archive_path", "")),
        "run_mode": str(payload.get("run_mode", "")),
    }
