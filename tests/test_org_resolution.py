from core.org_resolution import resolve_organization
from skills.graph_writer import GraphWriter
from services.cmdb_service import resolve_cmdb_owner_assignments
from processing.cmdb import CmdbEntity, NormalizedCmdb


def test_alias_target_order_cannot_change_ownership():
    class Client:
        def __init__(self, rows): self.rows = rows
        def execute_read(self, *args): return self.rows
    rows = [{"alias_normalized": "ops", "org_unit_name": name} for name in ("France", "Germany")]
    cmdb = NormalizedCmdb([CmdbEntity(entity_id="a1", name="ERP", entity_type="application", owner_name="ops")], [])
    for order in (rows, list(reversed(rows))):
        aliases = GraphWriter().load_org_unit_aliases_from_neo4j(Client(order))
        assert aliases == {"ops": ("France", "Germany")}
        assert resolve_organization("ops", {}, aliases).status == "ambiguous"
        assert resolve_cmdb_owner_assignments(cmdb, {}, aliases) == {}


def test_duplicate_alias_target_is_still_unique():
    assert resolve_organization(" OPS ", {}, {"ops": ("Operations", "Operations")}).name == "Operations"


def test_missing_alias_stays_missing():
    assert resolve_organization("missing", {}, {}).status == "missing"
