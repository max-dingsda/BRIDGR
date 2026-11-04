from core.i18n import translate_source


def test_translate_source_leaves_arbitrary_chat_text_untouched() -> None:
    answer = (
        "55 Prozesse, 60 Anwendungen, 20 Schnittstellen und 61 Server haben keine "
        "zugeordnete verantwortliche Organisationseinheit."
    )

    assert translate_source(answer, "en") == answer


def test_translate_source_still_translates_catalogued_ui_text() -> None:
    assert translate_source("Datenpflege", "en") == "Data maintenance"


def test_translate_source_translates_accessible_review_selection_label() -> None:
    source = "Zuordnung für {application} im Prozess {process} auswählen"
    english_template = translate_source(source, "en")
    german_template = translate_source(source, "de")

    assert english_template.format(application="Billing", process="Invoice") == (
        "Select mapping for Billing in process Invoice"
    )
    assert german_template.format(application="Abrechnung", process="Rechnung") == (
        "Zuordnung für Abrechnung im Prozess Rechnung auswählen"
    )
