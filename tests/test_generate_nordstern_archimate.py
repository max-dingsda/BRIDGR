from pathlib import Path
import xml.etree.ElementTree as ET

from scripts.generate_nordstern_archimate import ARCHIMATE_NS, build_model


def test_build_model_creates_archimate_31_model() -> None:
    tree, assumptions = build_model()
    root = tree.getroot()

    assert root.tag == f"{{{ARCHIMATE_NS}}}model"
    assert "archimate3_Model.xsd" in root.attrib["{http://www.w3.org/2001/XMLSchema-instance}schemaLocation"]
    assert assumptions

    elements = root.find(f"{{{ARCHIMATE_NS}}}elements")
    relationships = root.find(f"{{{ARCHIMATE_NS}}}relationships")
    assert elements is not None
    assert relationships is not None

    element_types = {
        element.attrib["{http://www.w3.org/2001/XMLSchema-instance}type"]
        for element in elements.findall(f"{{{ARCHIMATE_NS}}}element")
    }
    assert "BusinessProcess" in element_types
    assert "BusinessActor" in element_types
    assert "BusinessRole" in element_types
    assert "ApplicationComponent" in element_types
    assert "ApplicationInterface" in element_types
    assert "Node" in element_types
    assert "Capability" in element_types
    assert "Goal" in element_types
    assert "Driver" in element_types
    assert "Principle" in element_types
    assert "Requirement" in element_types
    assert "Constraint" in element_types
    assert "Assessment" in element_types
    assert "Stakeholder" in element_types

    relationship_types = {
        relationship.attrib["{http://www.w3.org/2001/XMLSchema-instance}type"]
        for relationship in relationships.findall(f"{{{ARCHIMATE_NS}}}relationship")
    }
    assert "Assignment" in relationship_types
    assert "Serving" in relationship_types
    assert "Realization" in relationship_types
    assert "Influence" in relationship_types


def test_generated_model_contains_required_risk_to_requirement_influence() -> None:
    tree, _ = build_model()
    root = tree.getroot()
    elements = root.find(f"{{{ARCHIMATE_NS}}}elements")
    relationships = root.find(f"{{{ARCHIMATE_NS}}}relationships")

    identifiers_by_name = {
        element.findtext(f"{{{ARCHIMATE_NS}}}name"): element.attrib["identifier"]
        for element in elements.findall(f"{{{ARCHIMATE_NS}}}element")
    }
    risk_id = identifiers_by_name["Risiko inkonsistenter Verantwortlichkeits- und Systemsicht"]
    requirement_id = identifiers_by_name["Kritische Prozesse und Systeme muessen dokumentierte Verantwortliche haben"]

    matches = [
        rel
        for rel in relationships.findall(f"{{{ARCHIMATE_NS}}}relationship")
        if rel.attrib["source"] == risk_id
        and rel.attrib["target"] == requirement_id
        and rel.attrib["{http://www.w3.org/2001/XMLSchema-instance}type"] == "Influence"
    ]
    assert matches
