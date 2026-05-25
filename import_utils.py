from __future__ import annotations

from pathlib import Path


SUPPORTED_PROCESS_SUFFIXES = {".bpmn", ".xml", ".txt", ".docx", ".pdf"}
SUPPORTED_CMDB_SUFFIXES = {".csv"}


def list_process_files(root_path: Path) -> list[Path]:
    if not root_path.exists():
        return []
    return sorted(
        path
        for path in root_path.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_PROCESS_SUFFIXES
    )


def save_uploaded_file(target_path: Path, content: bytes) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(content)


def sanitize_uploaded_name(filename: str) -> str:
    return Path(filename).name


def list_cmdb_files(root_path: Path) -> list[Path]:
    if not root_path.exists():
        return []
    return sorted(
        path
        for path in root_path.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_CMDB_SUFFIXES
    )
