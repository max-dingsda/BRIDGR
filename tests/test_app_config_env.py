import json
from pathlib import Path

from app_config import load_config


def test_load_config_uses_neo4j_env_fallbacks(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({}), encoding="utf-8")
    monkeypatch.setenv("NEO4J_URI", "neo4j+s://example.databases.neo4j.io")
    monkeypatch.setenv("NEO4J_USERNAME", "tester")
    monkeypatch.setenv("NEO4J_PASSWORD", "secret")
    monkeypatch.setenv("NEO4J_DATABASE", "neo4j")

    config = load_config(config_path)

    assert config.neo4j_url == "neo4j+s://example.databases.neo4j.io"
    assert config.neo4j_user == "tester"
    assert config.neo4j_password == "secret"
    assert config.neo4j_database == "neo4j"


def test_load_config_keeps_explicit_local_neo4j_values_even_if_they_match_defaults(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "neo4j_url": "bolt://localhost:7687",
                "neo4j_user": "neo4j",
                "neo4j_password": "",
                "neo4j_database": "",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("NEO4J_URI", "neo4j+s://example.databases.neo4j.io")
    monkeypatch.setenv("NEO4J_USERNAME", "tester")
    monkeypatch.setenv("NEO4J_PASSWORD", "secret")
    monkeypatch.setenv("NEO4J_DATABASE", "aura-db")

    config = load_config(config_path)

    assert config.neo4j_url == "bolt://localhost:7687"
    assert config.neo4j_user == "neo4j"
    assert config.neo4j_password == "secret"
    assert config.neo4j_database == "aura-db"


def test_load_config_keeps_explicit_neo4j_config_values(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "neo4j_url": "neo4j+s://custom.databases.neo4j.io",
                "neo4j_user": "custom-user",
                "neo4j_password": "custom-secret",
                "neo4j_database": "custom-db",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("NEO4J_URI", "neo4j+s://example.databases.neo4j.io")
    monkeypatch.setenv("NEO4J_USERNAME", "tester")
    monkeypatch.setenv("NEO4J_PASSWORD", "secret")
    monkeypatch.setenv("NEO4J_DATABASE", "aura-db")

    config = load_config(config_path)

    assert config.neo4j_url == "neo4j+s://custom.databases.neo4j.io"
    assert config.neo4j_user == "custom-user"
    assert config.neo4j_password == "custom-secret"
    assert config.neo4j_database == "custom-db"
