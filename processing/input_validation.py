from __future__ import annotations

import re


MAX_MANUAL_APPLICATION_NAME_LENGTH = 120
MANUAL_APPLICATION_NAME_PATTERN = re.compile(r"^[A-Za-z0-9 _./()&,+-]+$")


def validate_manual_application_name(raw_value: str) -> str:
    normalized_value = " ".join(raw_value.strip().split())
    if not normalized_value:
        raise ValueError("Bitte einen nicht-leeren Anwendungsnamen eingeben.")
    if len(normalized_value) > MAX_MANUAL_APPLICATION_NAME_LENGTH:
        raise ValueError(
            f"Anwendungsnamen dürfen höchstens {MAX_MANUAL_APPLICATION_NAME_LENGTH} Zeichen lang sein."
        )
    if not MANUAL_APPLICATION_NAME_PATTERN.fullmatch(normalized_value):
        raise ValueError(
            "Anwendungsnamen dürfen nur Buchstaben, Zahlen, Leerzeichen und einfache Trennzeichen enthalten."
        )
    return normalized_value
