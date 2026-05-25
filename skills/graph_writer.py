from __future__ import annotations

from dataclasses import dataclass

from skills.extract.extract_base import ExtractedProcess
from skills.match import MatchResult


@dataclass(slots=True)
class GraphWritePayload:
    process: ExtractedProcess
    matches: list[MatchResult]


class GraphWriter:
    def build_payload(self, process: ExtractedProcess, matches: list[MatchResult]) -> GraphWritePayload:
        return GraphWritePayload(process=process, matches=matches)

