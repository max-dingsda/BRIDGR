from pathlib import Path
import tomllib


def test_declared_minimum_python_supports_datetime_utc() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    metadata = tomllib.loads(pyproject.read_text(encoding="utf-8"))

    assert metadata["project"]["requires-python"] == ">=3.11"
