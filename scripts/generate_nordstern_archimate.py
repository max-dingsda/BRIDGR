from __future__ import annotations

import csv
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import xml.etree.ElementTree as ET


ARCHIMATE_NS = "http://www.opengroup.org/xsd/archimate/3.1/"
DC_NS = "http://purl.org/dc/elements/1.1/"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = PROJECT_ROOT / "Specs" / "testdata_nordstern"
OUTPUT_XML = DATASET_DIR / "nordstern_archimate_3_1.xml"
OUTPUT_ASSUMPTIONS = DATASET_DIR / "nordstern_archimate_assumptions.md"

ET.register_namespace("", ARCHIMATE_NS)
ET.register_namespace("dc", DC_NS)
ET.register_namespace("xsi", XSI_NS)


@dataclass(frozen=True)
class Entity:
    source_id: str
    name: str
    entity_type: str
    owner_name: str
    server_type: str = ""


@dataclass(frozen=True)
class ProcessRecord:
    process_id: str
    process_name: str
    department: str
    role: str
    owner: str
    mentioned_applications: tuple[str, ...]
    txt_file: str
    documentation: str


def _normalize_key(value: str) -> str:
    normalized = value.strip().casefold()
    normalized = normalized.replace("&", " und ")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _identifier(prefix: str, key: str) -> str:
    digest = hashlib.sha1(f"{prefix}:{key}".encode("utf-8")).hexdigest()[:16]
    return f"id-{prefix}-{digest}"


def _split_apps(raw: str) -> tuple[str, ...]:
    if not raw.strip():
        return ()
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def _extract_documentation(text_path: Path) -> str:
    lines = text_path.read_text(encoding="utf-8").splitlines()
    relevant: list[str] = []
    capture = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(("Beschreibung:", "Ziel:", "Ablauf:")):
            capture = True
            remainder = stripped.split(":", 1)[1].strip()
            if remainder:
                relevant.append(remainder)
            continue
        if stripped.startswith(("Genutzte Anwendungen:", "Hinweis", "Prozess-ID:", "Prozessname:", "Abteilung:", "Rolle:", "Owner:")):
            if capture and relevant:
                break
            continue
        if capture and stripped:
            relevant.append(stripped)
    return " ".join(relevant).strip()


def _resolve_process_text_path(dataset_dir: Path, process_id: str, declared_filename: str) -> Path:
    declared_path = dataset_dir / "processes_txt" / declared_filename
    if declared_path.exists():
        return declared_path

    process_dir = dataset_dir / "processes_txt"
    prefix = f"{process_id.lower()}_"
    matches = sorted(path for path in process_dir.glob("*.txt") if path.name.lower().startswith(prefix))
    if matches:
        return matches[0]
    raise FileNotFoundError(f"Could not resolve text file for {process_id}: {declared_filename}")


def load_processes(dataset_dir: Path = DATASET_DIR) -> list[ProcessRecord]:
    inventory_path = dataset_dir / "process_inventory.csv"
    processes: list[ProcessRecord] = []
    with inventory_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            text_path = _resolve_process_text_path(
                dataset_dir,
                row["process_id"].strip(),
                row["txt_file"].strip(),
            )
            processes.append(
                ProcessRecord(
                    process_id=row["process_id"].strip(),
                    process_name=row["process_name"].strip(),
                    department=row["department"].strip(),
                    role=row["role"].strip(),
                    owner=row["owner"].strip(),
                    mentioned_applications=_split_apps(row["mentioned_applications"]),
                    txt_file=text_path.name,
                    documentation=_extract_documentation(text_path),
                )
            )
    return processes


def load_entities(dataset_dir: Path = DATASET_DIR) -> dict[str, Entity]:
    entities_path = dataset_dir / "cmdb_entities.csv"
    entities: dict[str, Entity] = {}
    with entities_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            entity = Entity(
                source_id=row["id"].strip(),
                name=row["name"].strip(),
                entity_type=row["entity_type"].strip(),
                owner_name=row["owner_name"].strip(),
                server_type=row["server_type"].strip(),
            )
            entities[entity.source_id] = entity
    return entities


def load_relations(dataset_dir: Path = DATASET_DIR) -> list[dict[str, str]]:
    relations_path = dataset_dir / "cmdb_relations.csv"
    with relations_path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _application_aliases() -> dict[str, str]:
    return {
        "sap fi": "SAP S/4HANA FI",
        "sap co": "SAP S/4HANA CO",
        "sap mm": "SAP S/4HANA MM",
        "sap sd": "SAP S/4HANA SD",
        "crm": "Microsoft Dynamics CRM",
        "dynamics crm": "Microsoft Dynamics CRM",
        "ad": "Active Directory Domain Services",
        "active directory": "Active Directory Domain Services",
        "wms": "WarehousePro WMS",
        "warehousepro": "WarehousePro WMS",
        "mes": "MES FactoryLine",
        "plantview": "SCADA PlantView",
        "scada": "SCADA PlantView",
        "powerbi": "Power BI Service",
        "power bi": "Power BI Service",
        "teams": "Microsoft Teams",
        "sharepoint": "Microsoft SharePoint Online",
        "exchange": "Microsoft Exchange Online",
        "github": "GitHub Enterprise Cloud",
        "workday": "Workday Recruiting",
        "successfactors": "SAP SuccessFactors",
        "invoice ocr": "Invoice OCR Service",
        "datev": "DATEV Unternehmen Online",
        "webshop": "Webshop Portal",
        "contenthub": "PIM ContentHub",
        "pim": "PIM ContentHub",
        "servicenow": "ServiceNow ITSM",
        "splunk": "Splunk Enterprise Security",
        "defender": "Microsoft Defender for Endpoint",
        "entra id": "Microsoft Entra ID",
        "fortigate": "Fortinet FortiGate Cluster",
        "palo alto": "Palo Alto Firewall Management",
        "veeam": "Veeam Backup & Replication",
        "talend": "Talend Data Integration",
        "bi warehouse": "BI Data Warehouse",
        "bi dwh": "BI Data Warehouse",
        "opentext archive": "OpenText Archive Center",
        "travelexpense": "TravelExpense Cloud",
        "riskradar": "RiskRadar GRC",
        "customer portal": "Customer Self Service Portal",
        "edi": "EDI Gateway",
        "assettrack": "AssetTrack CMMS",
        "prtg": "PRTG Network Monitor",
        "zabbix": "Zabbix Monitoring",
        "zendesk": "Zendesk Support",
        "monitoring": "PRTG Network Monitor",
        "pki": "PKI Certificate Services",
        "clockwise": "Clockwise Time Tracking",
        "learninghub": "LearningHub LMS",
        "qms": "QMSuite",
        "docusign": "DocuSign CLM",
    }


def _capability_by_department() -> dict[str, str]:
    return {
        "Buchhaltung": "Financial Governance",
        "Controlling": "Financial Governance",
        "Einkauf": "Supply Chain Coordination",
        "Logistik": "Supply Chain Coordination",
        "Produktion": "Production Continuity",
        "Qualitaetsmanagement": "Quality Assurance",
        "Personal": "Workforce Enablement",
        "Marketing": "Customer Growth",
        "Vertrieb": "Customer Growth",
        "Kundenservice": "Customer Support",
        "Informationssicherheit": "Security Oversight",
        "IT-Betrieb": "Technology Reliability",
        "Facility Management": "Operational Services",
        "Geschaeftsfuehrung": "Strategic Steering",
        "Rechtsabteilung": "Governance and Compliance",
    }


def _motivation_bundle() -> list[tuple[str, str, str]]:
    return [
        ("stakeholder.executive", "Stakeholder", "Unternehmensleitung"),
        ("driver.stability", "Driver", "Bedarf an stabilen Kernprozessen"),
        ("goal.reliable", "Goal", "Verlaessliche und nachvollziehbare Betriebsprozesse"),
        ("principle.ownership", "Principle", "Klare Verantwortlichkeit fuer Prozesse und Systeme"),
        ("requirement.owner", "Requirement", "Kritische Prozesse und Systeme muessen dokumentierte Verantwortliche haben"),
        ("constraint.integration", "Constraint", "Uneinheitliche Benennungen und Integrationsdokumentation begrenzen die Modellkonsistenz"),
        ("assessment.risk", "Assessment", "Risiko inkonsistenter Verantwortlichkeits- und Systemsicht"),
    ]


def _relationship_key(source: str, rel_type: str, target: str) -> str:
    return f"{source}|{rel_type}|{target}"


class ModelBuilder:
    def __init__(self) -> None:
        self.elements: dict[str, dict[str, str]] = {}
        self.relationships: dict[str, dict[str, str]] = {}
        self.assumptions: list[str] = []

    def add_element(self, key: str, xsi_type: str, name: str, documentation: str = "") -> str:
        identifier = _identifier("elem", key)
        self.elements[identifier] = {
            "identifier": identifier,
            "key": key,
            "type": xsi_type,
            "name": name,
            "documentation": documentation,
        }
        return identifier

    def add_relationship(
        self,
        source_id: str,
        rel_type: str,
        target_id: str,
        documentation: str = "",
    ) -> str:
        key = _relationship_key(source_id, rel_type, target_id)
        identifier = _identifier("rel", key)
        if identifier not in self.relationships:
            self.relationships[identifier] = {
                "identifier": identifier,
                "source": source_id,
                "target": target_id,
                "type": rel_type,
                "documentation": documentation,
            }
        return identifier


def build_model(dataset_dir: Path = DATASET_DIR) -> tuple[ET.ElementTree, list[str]]:
    processes = load_processes(dataset_dir)
    entities = load_entities(dataset_dir)
    relations = load_relations(dataset_dir)
    builder = ModelBuilder()

    actor_ids: dict[str, str] = {}
    role_ids: dict[str, str] = {}
    process_ids: dict[str, str] = {}
    app_ids: dict[str, str] = {}
    interface_ids: dict[str, str] = {}
    server_ids: dict[str, str] = {}
    capability_ids: dict[str, str] = {}

    alias_map = {_normalize_key(key): value for key, value in _application_aliases().items()}
    entity_by_name = {_normalize_key(entity.name): entity for entity in entities.values()}

    for process in processes:
        actor_name = process.owner or process.department
        actor_key = f"actor:{actor_name}"
        if actor_key not in actor_ids:
            actor_ids[actor_key] = builder.add_element(actor_key, "BusinessActor", actor_name)
        role_key = f"role:{process.role}"
        if role_key not in role_ids:
            role_ids[role_key] = builder.add_element(role_key, "BusinessRole", process.role)
        process_key = f"process:{process.process_id}"
        process_ids[process.process_id] = builder.add_element(
            process_key,
            "BusinessProcess",
            process.process_name,
            documentation=process.documentation,
        )
        builder.add_relationship(actor_ids[actor_key], "Assignment", process_ids[process.process_id])
        builder.add_relationship(actor_ids[actor_key], "Assignment", role_ids[role_key])
        builder.add_relationship(role_ids[role_key], "Assignment", process_ids[process.process_id])

    for entity in entities.values():
        owner_key = f"actor:{entity.owner_name}"
        if entity.owner_name and owner_key not in actor_ids:
            actor_ids[owner_key] = builder.add_element(owner_key, "BusinessActor", entity.owner_name)
        key = f"{entity.entity_type}:{entity.source_id}"
        documentation = ""
        if entity.entity_type == "application":
            app_ids[entity.source_id] = builder.add_element(key, "ApplicationComponent", entity.name, documentation)
            if entity.owner_name:
                builder.add_relationship(actor_ids[owner_key], "Assignment", app_ids[entity.source_id])
        elif entity.entity_type == "interface":
            interface_ids[entity.source_id] = builder.add_element(key, "ApplicationInterface", entity.name, documentation)
            if entity.owner_name:
                builder.add_relationship(actor_ids[owner_key], "Assignment", interface_ids[entity.source_id])
        elif entity.entity_type == "server":
            server_ids[entity.source_id] = builder.add_element(key, "Node", entity.name, documentation)
            if entity.owner_name:
                builder.add_relationship(actor_ids[owner_key], "Assignment", server_ids[entity.source_id])

    for relation in relations:
        source_id = relation["source_id"].strip()
        target_id = relation["target_id"].strip()
        relation_type = relation["relation_type"].strip()
        if relation_type == "RUNS_ON" and source_id in app_ids and target_id in server_ids:
            builder.add_relationship(app_ids[source_id], "Realization", server_ids[target_id])
        elif relation_type == "USES_INTERFACE" and source_id in app_ids and target_id in interface_ids:
            builder.add_relationship(app_ids[source_id], "Composition", interface_ids[target_id])

    department_to_capability = _capability_by_department()
    for capability_name in sorted(set(department_to_capability.values())):
        capability_key = f"capability:{capability_name}"
        capability_ids[capability_name] = builder.add_element(capability_key, "Capability", capability_name)

    for process in processes:
        capability_name = department_to_capability[process.department]
        builder.add_relationship(
            process_ids[process.process_id],
            "Serving",
            capability_ids[capability_name],
        )

    process_linked_apps: set[str] = set()
    for process in processes:
        for mentioned_app in process.mentioned_applications:
            normalized = _normalize_key(mentioned_app)
            resolved_name = alias_map.get(normalized)
            entity = entity_by_name.get(_normalize_key(resolved_name or mentioned_app))
            if entity is None:
                synthetic_key = f"synthetic-app:{mentioned_app}"
                synthetic_id = builder.add_element(
                    synthetic_key,
                    "ApplicationComponent",
                    mentioned_app,
                    documentation="Application name is taken from process documentation and has no CMDB counterpart.",
                )
                builder.add_relationship(synthetic_id, "Serving", process_ids[process.process_id])
                process_linked_apps.add(mentioned_app)
                builder.assumptions.append(
                    f"Application '{mentioned_app}' was modeled as a standalone ApplicationComponent because no CMDB entity matched it."
                )
                continue
            app_identifier = app_ids[entity.source_id]
            builder.add_relationship(app_identifier, "Serving", process_ids[process.process_id])
            process_linked_apps.add(entity.name)

    motivation_ids: dict[str, str] = {}
    for key, xsi_type, name in _motivation_bundle():
        motivation_ids[key] = builder.add_element(key, xsi_type, name)

    builder.add_relationship(motivation_ids["stakeholder.executive"], "Association", motivation_ids["driver.stability"])
    builder.add_relationship(motivation_ids["driver.stability"], "Influence", motivation_ids["goal.reliable"])
    builder.add_relationship(motivation_ids["principle.ownership"], "Influence", motivation_ids["requirement.owner"])
    builder.add_relationship(motivation_ids["constraint.integration"], "Influence", motivation_ids["requirement.owner"])
    builder.add_relationship(motivation_ids["assessment.risk"], "Influence", motivation_ids["requirement.owner"])

    for capability_id in capability_ids.values():
        builder.add_relationship(capability_id, "Realization", motivation_ids["goal.reliable"])
        builder.add_relationship(capability_id, "Realization", motivation_ids["principle.ownership"])

    for actor_id in actor_ids.values():
        builder.add_relationship(actor_id, "Association", motivation_ids["requirement.owner"])

    builder.assumptions.extend(
        [
            "BusinessActor elements represent organizational units from process owners, departments, and CMDB owner fields.",
            "Servers are modeled uniformly as Node elements to keep the technology layer simple and BRIDGR-friendly.",
            "CMDB relation RUNS_ON is represented as Realization from ApplicationComponent to Node.",
            "CMDB relation USES_INTERFACE is represented as Composition from ApplicationComponent to ApplicationInterface to remain compatible with the current BRIDGR ArchiMate mapping.",
            "Missing process owners fall back to the process department for BusinessActor ownership assignment.",
            "Capabilities are modeled generically per department cluster rather than per individual process.",
            "The motivation layer is intentionally generic and supplements the test dataset because these concepts are not directly extractable from the source files.",
        ]
    )

    model = ET.Element(
        f"{{{ARCHIMATE_NS}}}model",
        {
            "identifier": _identifier("model", "nordstern-archimate-3.1"),
            f"{{{XSI_NS}}}schemaLocation": (
                f"{ARCHIMATE_NS} {ARCHIMATE_NS}archimate3_Model.xsd "
                f"{DC_NS} {ARCHIMATE_NS}dc.xsd"
            ),
        },
    )
    ET.SubElement(model, f"{{{ARCHIMATE_NS}}}name", {"{http://www.w3.org/XML/1998/namespace}lang": "de"}).text = (
        "Nordstern Werke GmbH - ArchiMate 3.1 Testmodell"
    )
    metadata = ET.SubElement(model, f"{{{ARCHIMATE_NS}}}metadata")
    ET.SubElement(metadata, f"{{{ARCHIMATE_NS}}}schema").text = DC_NS
    ET.SubElement(metadata, f"{{{ARCHIMATE_NS}}}schemaversion").text = "1.1"
    ET.SubElement(metadata, f"{{{DC_NS}}}title").text = "BRIDGR Nordstern Testmodell"
    ET.SubElement(metadata, f"{{{DC_NS}}}creator").text = "Codex"

    elements_node = ET.SubElement(model, f"{{{ARCHIMATE_NS}}}elements")
    for element in sorted(builder.elements.values(), key=lambda item: (item["type"], item["name"])):
        element_node = ET.SubElement(
            elements_node,
            f"{{{ARCHIMATE_NS}}}element",
            {
                "identifier": element["identifier"],
                f"{{{XSI_NS}}}type": element["type"],
            },
        )
        ET.SubElement(element_node, f"{{{ARCHIMATE_NS}}}name", {"{http://www.w3.org/XML/1998/namespace}lang": "de"}).text = element["name"]
        if element["documentation"]:
            ET.SubElement(
                element_node,
                f"{{{ARCHIMATE_NS}}}documentation",
                {"{http://www.w3.org/XML/1998/namespace}lang": "de"},
            ).text = element["documentation"]

    relationships_node = ET.SubElement(model, f"{{{ARCHIMATE_NS}}}relationships")
    for relationship in sorted(
        builder.relationships.values(),
        key=lambda item: (item["type"], item["source"], item["target"]),
    ):
        rel_node = ET.SubElement(
            relationships_node,
            f"{{{ARCHIMATE_NS}}}relationship",
            {
                "identifier": relationship["identifier"],
                "source": relationship["source"],
                "target": relationship["target"],
                f"{{{XSI_NS}}}type": relationship["type"],
            },
        )
        if relationship["documentation"]:
            ET.SubElement(
                rel_node,
                f"{{{ARCHIMATE_NS}}}documentation",
                {"{http://www.w3.org/XML/1998/namespace}lang": "de"},
            ).text = relationship["documentation"]

    tree = ET.ElementTree(model)
    ET.indent(tree, space="  ")
    return tree, sorted(set(builder.assumptions))


def write_outputs(
    xml_output: Path = OUTPUT_XML,
    assumptions_output: Path = OUTPUT_ASSUMPTIONS,
    dataset_dir: Path = DATASET_DIR,
) -> tuple[Path, Path]:
    tree, assumptions = build_model(dataset_dir)
    xml_output.parent.mkdir(parents=True, exist_ok=True)
    tree.write(xml_output, encoding="utf-8", xml_declaration=True)

    lines = [
        "# Annahmen fuer das Nordstern-Archimate-Modell",
        "",
        "Dieses Dokument haelt die bei der Modellgenerierung getroffenen Annahmen fest.",
        "",
    ]
    lines.extend(f"- {entry}" for entry in assumptions)
    assumptions_output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return xml_output, assumptions_output


def main() -> None:
    xml_path, assumptions_path = write_outputs()
    print(f"Wrote {xml_path}")
    print(f"Wrote {assumptions_path}")


if __name__ == "__main__":
    main()
