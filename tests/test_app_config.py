from pathlib import Path

from app_config import AppConfig, is_legacy_input_path, resolve_runtime_output_path, save_config


def test_resolve_runtime_output_path_uses_project_path_when_writable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("app_config.PROJECT_ROOT", tmp_path)
    monkeypatch.chdir(tmp_path)

    resolved_path, used_fallback = resolve_runtime_output_path("Output")

    assert resolved_path == tmp_path / "Output"
    assert used_fallback is False


def test_resolve_runtime_output_path_falls_back_when_project_path_is_unwritable(tmp_path: Path, monkeypatch) -> None:
    fallback_root = tmp_path / "localappdata"
    fallback_root.mkdir()
    monkeypatch.setattr("app_config.PROJECT_ROOT", Path("Z:/definitely-missing-root"))
    monkeypatch.setenv("LOCALAPPDATA", str(fallback_root))
    monkeypatch.chdir(tmp_path)

    resolved_path, used_fallback = resolve_runtime_output_path("Output")

    assert resolved_path == fallback_root / "BRIDGR" / "Output"
    assert used_fallback is True


def test_is_legacy_input_path_handles_windows_and_posix_spellings() -> None:
    assert is_legacy_input_path("data/input") is True
    assert is_legacy_input_path(".\\data\\input") is True
    assert is_legacy_input_path("Input") is False


def test_save_config_persists_debug_mode(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"

    save_config(AppConfig(debug_mode=True), config_path)

    assert '"debug_mode": true' in config_path.read_text(encoding="utf-8")
