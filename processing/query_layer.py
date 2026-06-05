from __future__ import annotations

import re


def sanitize_cypher_response(raw_response: str) -> str:
    cleaned_response = raw_response.strip()
    if cleaned_response.startswith("```"):
        lines = cleaned_response.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned_response = "\n".join(lines).strip()
    return cleaned_response
