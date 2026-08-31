from ui.layout import ALL_TABS, DEFAULT_ROLE, ROLE_OPTIONS, ROLE_TAB_MAP, get_visible_tabs


def test_default_role_is_most_restrictive():
    assert DEFAULT_ROLE == "Benutzer"
    assert ROLE_TAB_MAP[DEFAULT_ROLE] == ("chat",)


def test_every_role_only_exposes_known_tabs_in_canonical_order():
    for role in ROLE_OPTIONS:
        visible = ROLE_TAB_MAP[role]
        assert set(visible).issubset(set(ALL_TABS))
        assert list(visible) == [tab for tab in ALL_TABS if tab in visible]


def test_chat_is_visible_to_every_role():
    for role in ROLE_OPTIONS:
        assert "chat" in ROLE_TAB_MAP[role]


def test_architekt_extends_experte_with_ea_modell():
    assert set(ROLE_TAB_MAP["Experte"]).issubset(set(ROLE_TAB_MAP["Architekt"]))
    assert ROLE_TAB_MAP["Architekt"] == ROLE_TAB_MAP["Experte"] + ("archimate",)


def test_unknown_role_falls_back_to_all_tabs():
    assert get_visible_tabs("nicht-existent") == ALL_TABS
