from core.i18n import translate_source


def test_translate_source_leaves_arbitrary_chat_text_untouched() -> None:
    answer = (
        "55 Prozesse, 60 Anwendungen, 20 Schnittstellen und 61 Server haben keine "
        "zugeordnete verantwortliche Organisationseinheit."
    )

    assert translate_source(answer, "en") == answer


def test_translate_source_still_translates_catalogued_ui_text() -> None:
    assert translate_source("Datenpflege", "en") == "Data maintenance"
