from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = Path("config.json")
DEFAULT_LLM_BASE_URL = "http://localhost:11434/v1"
DEFAULT_NEO4J_URL = "bolt://localhost:7687"
DEFAULT_NEO4J_USER = "neo4j"


@dataclass(slots=True)
class AppConfig:
    llm_base_url: str = DEFAULT_LLM_BASE_URL
    llm_model: str = ""
    llm_api_key_env: str = ""
    llm_context_window: int = 131072
    neo4j_url: str = DEFAULT_NEO4J_URL
    neo4j_user: str = DEFAULT_NEO4J_USER
    neo4j_password: str = ""
    neo4j_database: str = ""
    fuzzy_threshold: float = 0.85
    cmdb_uuid_column: str = "app_id"
    cmdb_name_column: str = "application_name"
    input_path: str = "Input"
    cmdb_filename: str = "cmdb.csv"
    output_path: str = "Output"
    last_run_mode: str = "delta"


def load_config(path: Path | None = None) -> AppConfig:
    config_path = path or DEFAULT_CONFIG_PATH
    if not config_path.exists():
        return AppConfig()

    with config_path.open("r", encoding="utf-8") as handle:
        raw_config = json.load(handle)

    if "input_path" not in raw_config:
        raw_config["input_path"] = raw_config.pop("process_input_path", "Input")
    else:
        raw_config.pop("process_input_path", None)

    if "cmdb_filename" not in raw_config:
        legacy_cmdb_path = raw_config.pop("cmdb_path", "cmdb.csv")
        raw_config["cmdb_filename"] = Path(legacy_cmdb_path).name
    else:
        raw_config.pop("cmdb_path", None)

    raw_config["neo4j_url"] = resolve_env_backed_value(
        raw_config.get("neo4j_url"),
        env_name="NEO4J_URI",
        default=DEFAULT_NEO4J_URL,
    )
    raw_config["neo4j_user"] = resolve_env_backed_value(
        raw_config.get("neo4j_user"),
        env_name="NEO4J_USERNAME",
        default=DEFAULT_NEO4J_USER,
    )
    raw_config["neo4j_password"] = resolve_env_backed_value(
        raw_config.get("neo4j_password"),
        env_name="NEO4J_PASSWORD",
        default="",
    )
    raw_config["neo4j_database"] = resolve_env_backed_value(
        raw_config.get("neo4j_database"),
        env_name="NEO4J_DATABASE",
        default="",
    )

    return AppConfig(**raw_config)


def resolve_env_backed_value(config_value: str | None, env_name: str, default: str) -> str:
    env_value = os.getenv(env_name, "").strip()
    normalized_config = (config_value or "").strip()
    if env_value and (not normalized_config or normalized_config == default):
        return env_value
    return normalized_config or default


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


def resolve_input_cmdb_path(config: AppConfig) -> Path:
    return resolve_project_path(config.input_path) / config.cmdb_filename


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
