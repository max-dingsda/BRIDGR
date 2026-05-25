import os
from pathlib import Path

from env_loader import load_env_files


def test_load_env_files_reads_specs_env(tmp_path: Path, monkeypatch) -> None:
    specs_dir = tmp_path / "Specs"
    specs_dir.mkdir()
    env_path = specs_dir / ".env"
    env_path.write_text("OPENAI_API_KEY=test-key\n", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    load_env_files([env_path])

    assert os.environ["OPENAI_API_KEY"] == "test-key"
