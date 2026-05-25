import pytest

from input_validation import validate_manual_application_name


def test_validate_manual_application_name_returns_normalized_value() -> None:
    assert validate_manual_application_name("  SAP   Sales  ") == "SAP Sales"


def test_validate_manual_application_name_rejects_empty_value() -> None:
    with pytest.raises(ValueError):
        validate_manual_application_name("   ")


def test_validate_manual_application_name_rejects_overlong_value() -> None:
    with pytest.raises(ValueError):
        validate_manual_application_name("A" * 121)


def test_validate_manual_application_name_rejects_invalid_characters() -> None:
    with pytest.raises(ValueError):
        validate_manual_application_name("SAP Sales <script>")
