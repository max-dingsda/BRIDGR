"""Opt-in Playwright smoke test against an already running local BRIDGR app."""
import os
from pathlib import Path

import pytest


@pytest.mark.skipif(os.getenv("BRIDGR_RUN_BROWSER_TESTS") != "1", reason="Opt into a running local app with BRIDGR_RUN_BROWSER_TESTS=1")
def test_configuration_and_organization_in_browser(tmp_path):
    from playwright.sync_api import sync_playwright, expect
    output = Path(os.getenv("BRIDGR_BROWSER_ARTIFACTS", str(tmp_path)))
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel=os.getenv("BRIDGR_BROWSER_CHANNEL", "msedge"), headless=True)
        try:
            page = browser.new_page(viewport={"width": 1365, "height": 960})
            page.goto(os.getenv("BRIDGR_BROWSER_URL", "http://localhost:8504"), wait_until="domcontentloaded")
            expect(page.get_by_role("tab").first).to_be_visible(timeout=45000)
            page.get_by_role("combobox").nth(0).click()
            page.get_by_role("option", name="Konfigurator", exact=True).click()
            page.get_by_role("tab", name="Konfiguration", exact=True).click()
            user = page.get_by_label("Neo4j-Chat-Benutzer (nur Lesen)", exact=True)
            expect(user).to_be_visible()
            expect(page.get_by_label("Neo4j-Chat-Passwort", exact=True)).to_have_attribute("type", "password")
            user.scroll_into_view_if_needed()
            page.screenshot(path=str(output / "configuration_de.png"))
            page.get_by_role("combobox").nth(1).click()
            page.get_by_role("option", name="English", exact=True).click()
            page.get_by_role("tab", name="Configuration", exact=True).click()
            expect(page.get_by_label("Neo4j chat password", exact=True)).to_have_attribute("type", "password")
            page.get_by_label("Neo4j chat password", exact=True).scroll_into_view_if_needed()
            page.screenshot(path=str(output / "configuration_en.png"))
            page.get_by_text("Dark", exact=True).click()
            expect(page.get_by_label("Dark", exact=True)).to_be_checked()
            page.get_by_label("Neo4j chat password", exact=True).scroll_into_view_if_needed()
            page.screenshot(path=str(output / "configuration_en_dark.png"))
            expect(page.get_by_test_id("stException")).to_have_count(0)
            # Role and language changes are session-local; no configuration is saved.
            page.get_by_role("combobox").nth(0).click()
            page.get_by_role("option", name="Architect", exact=True).click()
            page.get_by_role("tab", name="Organization", exact=True).click()
            expect(page.get_by_role("heading", name="Organization", exact=True)).to_be_visible(timeout=30000)
            expect(page.get_by_role("heading", name="History", exact=True)).to_be_attached(timeout=30000)
            expect(page.get_by_test_id("stException")).to_have_count(0)
            page.screenshot(path=str(output / "organization_en.png"))
        finally:
            browser.close()
