from __future__ import annotations

from services.alias_service import write_merged_org_unit_alias
from services.decision_service import create_manual_decision
from services.runtime_service import get_session_neo4j_client


def merge_org_units(config, source_name: str, target_name: str) -> tuple[str, str]:
    cleaned_source = " ".join(source_name.strip().split())
    cleaned_target = " ".join(target_name.strip().split())
    if not cleaned_source or not cleaned_target:
        return "error", "Quelle und Ziel dürfen nicht leer sein."
    if cleaned_source.casefold() == cleaned_target.casefold():
        return "error", "Quelle und Ziel dürfen nicht identisch sein."

    neo4j_client = get_session_neo4j_client(config)
    _merge_org_unit_relationships(neo4j_client, cleaned_source, cleaned_target)
    write_merged_org_unit_alias(neo4j_client, cleaned_source, cleaned_target)
    neo4j_client.execute_write(
        """
        MATCH (source:OrgEinheit {name: $source_name})
        DETACH DELETE source
        """,
        {
            "source_name": cleaned_source,
        },
    )
    create_manual_decision(
        neo4j_client,
        "entity_merge",
        {
            "entity_type": "OrgEinheit",
            "source_name": cleaned_source,
            "target_name": cleaned_target,
        },
    )
    return "success", f"Organisationseinheit '{cleaned_source}' wurde in '{cleaned_target}' überführt."


def _merge_org_unit_relationships(neo4j_client, source_name: str, target_name: str) -> None:
    neo4j_client.execute_write(
        """
        MATCH (source:OrgEinheit {name: $source_name})
        MATCH (target:OrgEinheit {name: $target_name})
        MATCH (source)-[:VERANTWORTET]->(p:Prozess)
        WHERE elementId(source) <> elementId(target)
        MERGE (target)-[:VERANTWORTET]->(p)
        """,
        {"source_name": source_name, "target_name": target_name},
    )
    neo4j_client.execute_write(
        """
        MATCH (source:OrgEinheit {name: $source_name})
        MATCH (target:OrgEinheit {name: $target_name})
        MATCH (source)-[:VERANTWORTET]->(a:Anwendung)
        WHERE elementId(source) <> elementId(target)
        MERGE (target)-[:VERANTWORTET]->(a)
        """,
        {"source_name": source_name, "target_name": target_name},
    )
    neo4j_client.execute_write(
        """
        MATCH (source:OrgEinheit {name: $source_name})
        MATCH (target:OrgEinheit {name: $target_name})
        MATCH (source)-[:VERANTWORTET]->(i:Schnittstelle)
        WHERE elementId(source) <> elementId(target)
        MERGE (target)-[:VERANTWORTET]->(i)
        """,
        {"source_name": source_name, "target_name": target_name},
    )
    neo4j_client.execute_write(
        """
        MATCH (source:OrgEinheit {name: $source_name})
        MATCH (target:OrgEinheit {name: $target_name})
        MATCH (source)-[:VERANTWORTET]->(s:Server)
        WHERE elementId(source) <> elementId(target)
        MERGE (target)-[:VERANTWORTET]->(s)
        """,
        {"source_name": source_name, "target_name": target_name},
    )
    neo4j_client.execute_write(
        """
        MATCH (source:OrgEinheit {name: $source_name})
        MATCH (target:OrgEinheit {name: $target_name})
        MATCH (source)-[:VERANTWORTET]->(i:Infrastruktur)
        WHERE elementId(source) <> elementId(target)
        MERGE (target)-[:VERANTWORTET]->(i)
        """,
        {"source_name": source_name, "target_name": target_name},
    )
    neo4j_client.execute_write(
        """
        MATCH (source:OrgEinheit {name: $source_name})
        MATCH (target:OrgEinheit {name: $target_name})
        MATCH (source)-[:KANN_EINNEHMEN]->(r:Rolle)
        WHERE elementId(source) <> elementId(target)
        MERGE (target)-[:KANN_EINNEHMEN]->(r)
        """,
        {"source_name": source_name, "target_name": target_name},
    )
    neo4j_client.execute_write(
        """
        MATCH (source:OrgEinheit {name: $source_name})
        MATCH (target:OrgEinheit {name: $target_name})
        MATCH (source)-[:IST_VERBUNDEN_MIT]->(n)
        WHERE elementId(source) <> elementId(target)
        MERGE (target)-[:IST_VERBUNDEN_MIT]->(n)
        """,
        {"source_name": source_name, "target_name": target_name},
    )
    neo4j_client.execute_write(
        """
        MATCH (source:OrgEinheit {name: $source_name})
        MATCH (target:OrgEinheit {name: $target_name})
        MATCH (alias:Alias)-[:KANN_MEINEN]->(source)
        WHERE elementId(source) <> elementId(target)
        MERGE (alias)-[:KANN_MEINEN]->(target)
        """,
        {"source_name": source_name, "target_name": target_name},
    )
