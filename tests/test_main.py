from __future__ import annotations

from types import SimpleNamespace

from core.app_config import AppConfig
import main as cli


def test_cli_without_file_forces_full_inbox_import(monkeypatch, capsys) -> None:
    captured_config = None
    monkeypatch.setattr(cli, "load_env_files", lambda: None)
    monkeypatch.setattr(cli, "load_config", lambda _path: AppConfig(last_run_mode="partial"))
    monkeypatch.setattr(cli.argparse.ArgumentParser, "parse_args", lambda _self: SimpleNamespace(file=None, config="config.json"))

    def fake_run_pipeline(config, input_paths=None):
        nonlocal captured_config
        captured_config = config
        assert input_paths is None
        return SimpleNamespace(documents=[])

    monkeypatch.setattr(cli, "run_pipeline", fake_run_pipeline)

    assert cli.main() == 0
    assert captured_config.last_run_mode == "full"
    assert '"documents": []' in capsys.readouterr().out


def test_cli_file_keeps_explicit_single_file_mode(monkeypatch, tmp_path, capsys) -> None:
    source = tmp_path / "process.txt"
    captured = {}
    monkeypatch.setattr(cli, "load_env_files", lambda: None)
    monkeypatch.setattr(cli, "load_config", lambda _path: AppConfig(last_run_mode="partial"))
    monkeypatch.setattr(cli.argparse.ArgumentParser, "parse_args", lambda _self: SimpleNamespace(file=source, config="config.json"))
    monkeypatch.setattr(cli, "run_pipeline", lambda config, paths: captured.update(config=config, paths=paths) or SimpleNamespace(documents=[]))

    assert cli.main() == 0
    assert captured["config"].last_run_mode == "partial"
    assert captured["paths"] == [source]
    assert '"documents": []' in capsys.readouterr().out
