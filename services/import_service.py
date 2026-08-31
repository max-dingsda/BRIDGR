from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
import shutil

from core.app_config import AppConfig, resolve_project_path
from processing.run_artifacts import load_latest_run, save_last_import_selection, write_latest_run


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


def archive_processed_input_files(input_root: Path, source_paths: list[str]) -> tuple[Path, list[dict[str, str]]]:
    archive_dir = build_import_archive_dir()
    moved_files: list[dict[str, str]] = []

    for source_path_value in source_paths:
        source_path = Path(source_path_value)
        if not source_path.exists() or not source_path.is_file():
            continue

        try:
            relative_path = source_path.relative_to(input_root)
        except ValueError:
            relative_path = Path(source_path.name)

        target_path = archive_dir / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source_path), str(target_path))
        moved_files.append(
            {
                "source_path": str(source_path),
                "archived_path": str(target_path),
                "display_path": relative_path.as_posix(),
            }
        )

    return archive_dir, moved_files


def finalize_import_artifacts(
    config: AppConfig,
    runtime_output_path: Path,
    input_root: Path,
    run_mode: str,
    processed_source_paths: list[str],
) -> tuple[str, list[str]]:
    archive_dir, moved_files = archive_processed_input_files(input_root, processed_source_paths)
    archived_display_paths = [item["display_path"] for item in moved_files]
    archived_source_paths = [item["source_path"] for item in moved_files]
    archive_path = str(archive_dir)

    save_last_import_selection(
        archived_source_paths,
        runtime_output_path,
        display_paths=archived_display_paths,
        archive_path=archive_path,
        run_mode=run_mode,
    )

    latest_run = load_latest_run(runtime_output_path)
    if latest_run is not None:
        latest_run["import_archive_path"] = archive_path
        latest_run["import_archived_files"] = moved_files
        latest_run["run_mode"] = run_mode
        write_latest_run(latest_run, runtime_output_path)

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
