from pathlib import Path

from core.app_config import AppConfig, is_legacy_input_path, load_config, normalize_run_mode, resolve_runtime_output_path, save_config


def test_resolve_runtime_output_path_uses_project_path_when_writable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("core.app_config.PROJECT_ROOT", tmp_path)
    monkeypatch.chdir(tmp_path)

    resolved_path, used_fallback = resolve_runtime_output_path("Output")

    assert resolved_path == tmp_path / "Output"
    assert used_fallback is False


def test_resolve_runtime_output_path_falls_back_when_project_path_is_unwritable(tmp_path: Path, monkeypatch) -> None:
    fallback_root = tmp_path / "localappdata"
    fallback_root.mkdir()
    monkeypatch.setattr("core.app_config.PROJECT_ROOT", Path("Z:/definitely-missing-root"))
    monkeypatch.setenv("LOCALAPPDATA", str(fallback_root))
    monkeypatch.chdir(tmp_path)

    resolved_path, used_fallback = resolve_runtime_output_path("Output")

    assert resolved_path == fallback_root / "BRIDGR" / "Output"
    assert used_fallback is True


def test_is_legacy_input_path_handles_windows_and_posix_spellings() -> None:
    assert is_legacy_input_path("data/input") is True
    assert is_legacy_input_path(".\\data\\input") is True
    assert is_legacy_input_path("Input") is False


def test_save_config_persists_debug_mode_and_snapshot_retention(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"

    save_config(AppConfig(debug_mode=True, snapshot_retention_count=7), config_path)

    assert '"debug_mode": true' in config_path.read_text(encoding="utf-8")
    assert '"snapshot_retention_count": 7' in config_path.read_text(encoding="utf-8")


def test_save_config_persists_dedicated_chat_credentials(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"

    save_config(AppConfig(neo4j_chat_user="reader", neo4j_chat_password="secret"), config_path)

    saved = config_path.read_text(encoding="utf-8")
    assert '"neo4j_chat_user": "reader"' in saved
    assert '"neo4j_chat_password": "secret"' in saved


def test_environment_secrets_remain_effective_but_are_not_persisted(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text('{"ui_locale": "de"}', encoding="utf-8")
    monkeypatch.setenv("NEO4J_PASSWORD", "environment-writer-secret")
    monkeypatch.setenv("NEO4J_CHAT_PASSWORD", "environment-reader-secret")

    config = load_config(config_path)
    assert config.neo4j_password == "environment-writer-secret"
    assert config.neo4j_password_source == "environment"
    assert config.neo4j_chat_password == "environment-reader-secret"
    assert config.neo4j_chat_password_source == "environment"

    config.ui_locale = "en"
    save_config(config, config_path)

    saved = config_path.read_text(encoding="utf-8")
    assert "environment-writer-secret" not in saved
    assert "environment-reader-secret" not in saved
    assert '"neo4j_password": ""' in saved
    assert '"neo4j_chat_password": ""' in saved
    assert "_source" not in saved


def test_normalize_run_mode_maps_legacy_values() -> None:
    assert normalize_run_mode("delta") == "partial"
    assert normalize_run_mode("initial") == "full"
    assert normalize_run_mode("full") == "full"


def test_relative_paths_and_default_config_ignore_cwd_and_existence(tmp_path, monkeypatch):
    from core.app_config import resolve_project_path, load_config
    root, elsewhere = tmp_path / "project", tmp_path / "elsewhere"
    root.mkdir()
    elsewhere.mkdir()
    monkeypatch.setattr("core.app_config.PROJECT_ROOT", root)
    monkeypatch.chdir(elsewhere)
    (elsewhere / "Output").mkdir()
    assert resolve_project_path("Output") == root / "Output"
    (root / "Output").mkdir()
    assert resolve_project_path("Output") == root / "Output"
    assert resolve_project_path(elsewhere) == elsewhere
    save_config(AppConfig(ui_locale="en"))
    assert (root / "config.json").exists()
    assert load_config().ui_locale == "en"
