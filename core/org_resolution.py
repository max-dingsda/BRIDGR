"""Preserve ambiguity at the organization lookup boundary."""
from dataclasses import dataclass


@dataclass(frozen=True)
class OrganizationResolution:
    status: str
    candidates: tuple[str, ...]

    @property
    def name(self) -> str:
        return self.candidates[0] if self.status == "unique" else ""


def resolve_organization(raw_name: str, organizations: dict[str, str], aliases: dict) -> OrganizationResolution:
    normalized = " ".join(raw_name.strip().casefold().split())
    if normalized in organizations:
        return OrganizationResolution("unique", (organizations[normalized],))
    targets = aliases.get(normalized, ())
    if isinstance(targets, str):
        targets = (targets,)
    candidates = tuple(sorted(set(targets)))
    status = "unique" if len(candidates) == 1 else "ambiguous" if candidates else "missing"
    return OrganizationResolution(status, candidates)
