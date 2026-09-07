from __future__ import annotations

import json
import os
import tempfile
import warnings
from dataclasses import asdict, dataclass, field
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = Path("config.json")
DEFAULT_LLM_BASE_URL = "http://localhost:11434/v1"
DEFAULT_NEO4J_URL = "bolt://localhost:7687"
DEFAULT_NEO4J_USER = "neo4j"
LEGACY_INPUT_PATH = Path("data/input")


@dataclass(slots=True)
class AppConfig:
    llm_base_url: str = DEFAULT_LLM_BASE_URL
    llm_model: str = ""
    llm_api_key_env: str = ""
    llm_context_window: int = 131072
    llm_timeout_seconds: int = 900
    neo4j_url: str = DEFAULT_NEO4J_URL
    neo4j_user: str = DEFAULT_NEO4J_USER
    neo4j_password: str = field(default="", repr=False)
    neo4j_database: str = ""
    neo4j_chat_user: str = ""
    neo4j_chat_password: str = field(default="", repr=False)
    fuzzy_threshold: float = 0.85
    cmdb_uuid_column: str = "id"
    cmdb_name_column: str = "name"
    cmdb_server_type_column: str = "server_type"
    cmdb_owner_name_column: str = "owner_name"
    cmdb_multivalue_separator: str = "|"
    cmdb_type_files: dict[str, str] = field(default_factory=dict)
    cmdb_runs_on_column: str = "runs_on"
    cmdb_uses_interfaces_column: str = "uses_interfaces"
    input_path: str = "Input"
    output_path: str = "Output"
    last_run_mode: str = "partial"
    chat_mode: str = "prompt-only"
    debug_mode: bool = False
    snapshot_retention_count: int = 10
    ui_locale: str = "de"


def load_config(path: Path | None = None) -> AppConfig:
    config_path = resolve_project_path(path if path is not None else DEFAULT_CONFIG_PATH)
    if not config_path.exists():
        return AppConfig()

    with config_path.open("r", encoding="utf-8") as handle:
        raw_config = json.load(handle)

    if "input_path" not in raw_config:
        raw_config["input_path"] = raw_config.pop("process_input_path", "Input")
    else:
        raw_config.pop("process_input_path", None)

    if not raw_config.get("cmdb_type_files") and any(raw_config.get(key) for key in ("cmdb_filename", "cmdb_relations_filename", "cmdb_path")):
        warnings.warn("Legacy CMDB format is no longer supported. Configure cmdb_type_files; no legacy files will be imported.", UserWarning)
    for legacy_key in ("cmdb_filename", "cmdb_relations_filename", "cmdb_entity_type_column",
                        "cmdb_relation_source_column", "cmdb_relation_type_column",
                        "cmdb_relation_target_column", "cmdb_path"):
        raw_config.pop(legacy_key, None)

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
    raw_config["neo4j_chat_user"] = resolve_env_backed_value(raw_config.get("neo4j_chat_user"), "NEO4J_CHAT_USERNAME", "")
    raw_config["neo4j_chat_password"] = resolve_env_backed_value(raw_config.get("neo4j_chat_password"), "NEO4J_CHAT_PASSWORD", "")
    raw_config["last_run_mode"] = normalize_run_mode(raw_config.get("last_run_mode", "partial"))
    raw_config["ui_locale"] = raw_config.get("ui_locale", "de") if raw_config.get("ui_locale", "de") in {"de", "en"} else "de"

    return AppConfig(**raw_config)


def normalize_run_mode(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if normalized == "delta":
        return "partial"
    if normalized == "initial":
        return "full"
    if normalized in {"full", "partial"}:
        return normalized
    return "partial"


def resolve_env_backed_value(config_value: str | None, env_name: str, default: str) -> str:
    env_value = os.getenv(env_name, "").strip()
    normalized_config = (config_value or "").strip()
    if env_value and not normalized_config:
        return env_value
    return normalized_config or default


def save_config(config: AppConfig, path: Path | None = None) -> None:
    config_path = resolve_project_path(path if path is not None else DEFAULT_CONFIG_PATH)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as handle:
        json.dump(asdict(config), handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def resolve_project_path(path_value: str | Path) -> Path:
    """Return an absolute project path.

    Relative data and configuration paths always use the repository root,
    independently of the working directory and whether the target exists.
    """

    candidate_path = Path(path_value)
    if candidate_path.is_absolute():
        return candidate_path
    return PROJECT_ROOT / candidate_path


def resolve_archimate_mapping_path() -> Path:
    """Return the path to archimate_mapping.json."""
    return resolve_project_path("data/archimate_mapping.json")


def resolve_cmdb_type_file_paths(config: AppConfig) -> dict[str, Path]:
    """Return {entity_type: absolute_path} for each configured CMDB type file."""
    if not config.cmdb_type_files:
        return {}
    input_dir = resolve_project_path(config.input_path)
    return {
        entity_type: input_dir / filename
        for entity_type, filename in config.cmdb_type_files.items()
        if filename.strip()
    }


def resolve_runtime_output_path(path_value: str | Path) -> tuple[Path, bool]:
    """Return a writable output directory and whether a fallback was used.

    Unlike `resolve_project_path`, this helper guarantees that the returned
    directory is writable or raises `OSError`.
    """

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


def normalize_path_value(path_value: str | Path) -> str:
    """Normalize a path value for stable comparisons across slash styles."""

    return Path(path_value).as_posix().rstrip("/").lower()


def is_legacy_input_path(path_value: str | Path) -> bool:
    """Return whether the given path still points to the pre-Input legacy folder."""

    return normalize_path_value(path_value) == normalize_path_value(LEGACY_INPUT_PATH)
