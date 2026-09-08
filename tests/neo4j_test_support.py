from contextlib import nullcontext


class ScopedClientStub:
    """Scope support for orchestration tests; ACID is verified against real Neo4j."""
    def transaction(self):
        return nullcontext(self)

    serialized_writes = transaction

    def stage_artifact(self, path, payload):
        from processing.run_artifacts import atomic_write_json
        atomic_write_json(path, payload)

    def read_staged_artifact(self, path):
        return None
