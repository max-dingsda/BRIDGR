from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = Path("config.json")


@dataclass(slots=True)
class AppConfig:
    llm_base_url: str = "http://localhost:11434/v1"
    llm_model: str = ""
    llm_api_key_env: str = ""
    llm_context_window: int = 131072
    neo4j_url: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    fuzzy_threshold: float = 0.85
    cmdb_uuid_column: str = "app_id"
    cmdb_name_column: str = "application_name"
    process_input_path: str = "Input"
    cmdb_path: str = "data/cmdb.csv"
    output_path: str = "Output"
    last_run_mode: str = "delta"


def load_config(path: Path | None = None) -> AppConfig:
    config_path = path or DEFAULT_CONFIG_PATH
    if not config_path.exists():
        return AppConfig()

    with config_path.open("r", encoding="utf-8") as handle:
        raw_config = json.load(handle)

    return AppConfig(**raw_config)


def save_config(config: AppConfig, path: Path | None = None) -> None:
    config_path = path or DEFAULT_CONFIG_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as handle:
        json.dump(asdict(config), handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def resolve_project_path(path_value: str | Path) -> Path:
    candidate_path = Path(path_value)
    if candidate_path.is_absolute():
        return candidate_path
    current_workdir_path = Path.cwd() / candidate_path
    if current_workdir_path.exists():
        return current_workdir_path
    return PROJECT_ROOT / candidate_path


def resolve_runtime_output_path(path_value: str | Path) -> tuple[Path, bool]:
    preferred_path = resolve_project_path(path_value)
    if is_directory_writable(preferred_path):
        return preferred_path, False

    local_appdata = Path(os.getenv("LOCALAPPDATA") or tempfile.gettempdir())
    fallback_path = local_appdata / "BRIDGR" / "Output"
    if is_directory_writable(fallback_path):
        return fallback_path, True

    raise OSError(f"No writable output directory available for '{path_value}'.")


def is_directory_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe_path = path / ".bridgr-write-probe"
        with probe_path.open("w", encoding="utf-8") as handle:
            handle.write("ok")
        probe_path.unlink(missing_ok=True)
        return True
    except OSError:
        return False
