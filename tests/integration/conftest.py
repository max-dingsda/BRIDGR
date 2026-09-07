"""Opt-in integration tests using a newly created, disposable Neo4j database."""
from dataclasses import replace
import os
import re
from uuid import uuid4

import pytest

from core.app_config import load_config
from core.env_loader import load_env_files
from core.neo4j_utils import Neo4jClient, Neo4jConfig


@pytest.fixture(scope="session")
def isolated_neo4j_config():
    if os.getenv("BRIDGR_RUN_NEO4J_TESTS") != "1":
        pytest.skip("Set BRIDGR_RUN_NEO4J_TESTS=1 to create a disposable Neo4j test database")
    from neo4j import GraphDatabase

    load_env_files()
    config = load_config()
    database = "bridgr-test-" + uuid4().hex
    assert re.fullmatch(r"bridgr-test-[0-9a-f]{32}", database)
    assert database != config.neo4j_database
    with GraphDatabase.driver(config.neo4j_url, auth=(config.neo4j_user, config.neo4j_password)) as driver:
        created = False
        try:
            with driver.session(database="system") as session:
                session.run(f"CREATE DATABASE `{database}` WAIT 30 SECONDS").consume()
                created = True
            yield replace(config, neo4j_database=database)
        finally:
            if created:
                with driver.session(database="system") as session:
                    session.run(f"DROP DATABASE `{database}` DESTROY DATA WAIT 30 SECONDS").consume()


@pytest.fixture
def graph_client(isolated_neo4j_config):
    config = isolated_neo4j_config
    client = Neo4jClient(Neo4jConfig(config.neo4j_url, config.neo4j_user,
                                   config.neo4j_password, config.neo4j_database))
    try:
        client.execute_write("MATCH (n) WHERE NOT n:__BridgrWriteLock DETACH DELETE n")
        client.ensure_constraints()
        yield client
    finally:
        client.close()


@pytest.fixture
def chat_client(isolated_neo4j_config, graph_client):
    from secrets import token_urlsafe
    from neo4j import GraphDatabase
    from core.chat_neo4j import ChatNeo4jClient

    config = isolated_neo4j_config
    username = "bridgr_test_" + uuid4().hex
    password = token_urlsafe(32)
    with GraphDatabase.driver(config.neo4j_url, auth=(config.neo4j_user, config.neo4j_password)) as admin:
        with admin.session(database="system") as session:
            session.run(f"CREATE USER {username} SET PASSWORD $password CHANGE NOT REQUIRED", password=password).consume()
        client = None
        try:
            with admin.session(database="system") as session:
                session.run(f"GRANT ROLE reader TO {username}").consume()
            client = ChatNeo4jClient(Neo4jConfig(config.neo4j_url, username, password, config.neo4j_database))
            yield client
        finally:
            if client:
                client.close()
            with admin.session(database="system") as session:
                session.run(f"DROP USER {username}").consume()
