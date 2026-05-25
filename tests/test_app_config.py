from pathlib import Path

from app_config import resolve_runtime_output_path


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
