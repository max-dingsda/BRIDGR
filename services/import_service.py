from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import shutil

from core.app_config import AppConfig, resolve_project_path
from processing.run_artifacts import atomic_write_json, compute_file_hash, load_latest_run, save_last_import_selection, write_latest_run
from services.runtime_service import get_session_neo4j_client

PENDING_ARCHIVE = "pending_import_archive.json"


def build_import_archive_dir() -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    archive_root = resolve_project_path("data/input_archive")
    archive_dir = archive_root / timestamp
    suffix = 1
    while archive_dir.exists():
        suffix += 1
        archive_dir = archive_root / f"{timestamp}_{suffix}"
    archive_dir.mkdir(parents=True, exist_ok=True)
    return archive_dir




def finalize_import_artifacts(
    config: AppConfig,
    runtime_output_path: Path,
    input_root: Path,
    run_mode: str,
    processed_source_paths: list[str],
    expected_run_id: str = "",
) -> tuple[str, list[str]]:
    client = get_session_neo4j_client(config)
    with client.serialized_writes():
        pending_path = runtime_output_path / PENDING_ARCHIVE
        if pending_path.exists():
            pending = _load_archive_journal(pending_path)
            if {str(Path(value).resolve()) for value in processed_source_paths} != {item["source_path"] for item in pending["files"]}:
                raise ValueError("Eine frühere Archivierung ist ausstehend; zuerst im Import-Tab wiederholen.")
            return _replay_archive(runtime_output_path, client)
        archive_dir = build_import_archive_dir()
        moved_files = []
        destinations = set()
        latest_run = load_latest_run(runtime_output_path, client) or {}
        if expected_run_id and latest_run.get("run_id") != expected_run_id:
            raise ValueError("Ein neuerer Import liegt vor; Archivierung wegen Konflikt abgebrochen. Quelldateien bleiben erhalten.")
        hashes = {document["source_path"]: document.get("file_hash") for document in latest_run.get("documents", [])}
        for value in processed_source_paths:
            source = Path(value).resolve()
            if not source.is_file():
                raise OSError(f"Graph wurde gespeichert; Archivierung ausstehend: Quelldatei fehlt: {source}")
            try:
                relative = source.relative_to(input_root.resolve())
            except ValueError:
                relative = Path(source.name)
            target = archive_dir / relative
            if target in destinations:
                raise ValueError("Archivierung enthält doppelte Zielpfade; Dateien wurden nicht verschoben.")
            destinations.add(target)
            digest = compute_file_hash(source)
            if hashes.get(value) and digest != hashes[value]:
                raise ValueError(f"Datei wurde seit dem Import verändert und wird nicht archiviert: {source}")
            moved_files.append({"source_path": str(source), "archived_path": str(target),
                                "display_path": relative.as_posix(), "file_hash": digest})
        atomic_write_json(pending_path, {"archive_path": str(archive_dir), "files": moved_files,
                                         "run_mode": run_mode, "run_id": expected_run_id})
        return _replay_archive(runtime_output_path, client)


def recover_import_artifacts(config: AppConfig, output_path: Path) -> tuple[str, list[str]]:
    """Retry only post-commit file work; never rerun graph operations or audit writes."""
    client = get_session_neo4j_client(config)
    with client.serialized_writes():
        return _replay_archive(output_path, client)


def stop_import_archiving(config: AppConfig, output_path: Path) -> None:
    """Keep the journal and all source/archive files, but unblock future imports."""
    with get_session_neo4j_client(config).serialized_writes():
        journal = output_path / PENDING_ARCHIVE
        if not journal.exists():
            return
        history = output_path / "archive_journals"
        history.mkdir(parents=True, exist_ok=True)
        target = history / ("stopped_" + datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f") + ".json")
        journal.replace(target)


def _load_archive_journal(path: Path) -> dict:
    try:
        pending = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(pending, dict) or not isinstance(pending["files"], list):
            raise ValueError
        if any(not isinstance(pending[key], str) or not pending[key] for key in ("archive_path", "run_mode")):
            raise ValueError
        for item in pending["files"]:
            if any(not isinstance(item[key], str) or not item[key] for key in ("source_path", "archived_path", "display_path", "file_hash")):
                raise ValueError
        return pending
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Archivierungsprotokoll ist ungültig. Archivierung beenden oder das Protokoll klären; Dateien bleiben erhalten.") from exc


def _replay_archive(runtime_output_path: Path, client) -> tuple[str, list[str]]:
    pending_path = runtime_output_path / PENDING_ARCHIVE
    pending = _load_archive_journal(pending_path)
    moved_files = pending["files"]
    archive_path, run_mode = pending["archive_path"], pending["run_mode"]
    try:
        if pending.get("run_id") and (load_latest_run(runtime_output_path, client) or {}).get("run_id") != pending["run_id"]:
            raise ValueError("Ein neuerer Import liegt vor; Archivierung erfordert Konfliktklärung.")
        for item in moved_files:
            source, target = Path(item["source_path"]), Path(item["archived_path"])
            if target.exists():
                if compute_file_hash(target) != item["file_hash"]:
                    raise ValueError(f"Archivziel wurde verändert: {target}")
                if source.exists():
                    if compute_file_hash(source) != item["file_hash"]:
                        raise ValueError(f"Quelldatei wurde verändert: {source}")
                    source.unlink()
            else:
                if not source.is_file() or compute_file_hash(source) != item["file_hash"]:
                    raise ValueError(f"Quelldatei fehlt oder wurde verändert: {source}")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(target))
        with client.transaction():
            result = _publish_archive_metadata(runtime_output_path, archive_path, run_mode, moved_files, client)
        pending_path.unlink()
        return result
    except (OSError, ValueError) as exc:
        raise OSError(f"Graph wurde gespeichert; Archivierung ausstehend. Wiederholung im Import-Tab möglich. {exc}") from exc


def _publish_archive_metadata(runtime_output_path, archive_path, run_mode, moved_files, client):
    archived_display_paths = [item["display_path"] for item in moved_files]
    archived_source_paths = [item["source_path"] for item in moved_files]

    save_last_import_selection(
        archived_source_paths,
        runtime_output_path,
        display_paths=archived_display_paths,
        archive_path=archive_path,
        run_mode=run_mode,
        neo4j_client=client,
    )

    latest_run = load_latest_run(runtime_output_path, client)
    if latest_run is not None:
        latest_run["import_archive_path"] = archive_path
        latest_run["import_archived_files"] = moved_files
        latest_run["run_mode"] = run_mode
        write_latest_run(latest_run, runtime_output_path, client)

    return archive_path, archived_display_paths


def build_import_completion_message(duration: str, run_mode: str, archive_path: str, archived_display_paths: list[str]) -> str:
    file_count = len(archived_display_paths)
    mode_label = "Vollimport" if run_mode == "full" else "Teilimport"
    if file_count:
        return (
            f"{mode_label} abgeschlossen in {duration}. "
            f"{file_count} Processdatei(en) wurden verarbeitet und nach `{archive_path}` verschoben."
        )
    return f"{mode_label} abgeschlossen in {duration}. Es wurden keine Processdateien verschoben."
