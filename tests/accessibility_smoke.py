"""WCAG accessibility gate for the login and authenticated dashboard."""

import os

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright


BASE_URL = os.getenv("COURTVISION_BASE_URL", "http://127.0.0.1:5173")
OWNER_EMAIL = os.getenv("COURTVISION_OWNER_EMAIL", "owner@courtvision.local")
OWNER_PASSWORD = os.getenv("COURTVISION_OWNER_PASSWORD", "courtvision-demo")
WCAG_OPTIONS = {
    "runOnly": {
        "type": "tag",
        "values": ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"],
    },
    "resultTypes": ["violations"],
}


def blocking_violations(axe: Axe, page, label: str) -> list[str]:
    results = axe.run(page, options=WCAG_OPTIONS)
    return [
        f"{label}:{violation['id']} ({violation.get('impact', 'unknown')}) "
        f"nodes={[{'target': node.get('target'), 'summary': node.get('failureSummary')} for node in violation.get('nodes', [])[:5]]}"
        for violation in results.response.get("violations", [])
        if violation.get("impact") in {"serious", "critical"}
    ]


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.emulate_media(reduced_motion="reduce")
    axe = Axe()

    page.goto(BASE_URL, wait_until="networkidle")
    expect(page.get_by_role("heading", name="Iniciar sesión")).to_be_visible()
    page.wait_for_timeout(600)
    violations = blocking_violations(axe, page, "login")

    page.get_by_label("Email").fill(OWNER_EMAIL)
    page.get_by_label("Contraseña").fill(OWNER_PASSWORD)
    page.get_by_role("button", name="Entrar").click()
    expect(page.get_by_role("heading", name="Operación")).to_be_visible(timeout=10_000)
    page.wait_for_timeout(600)
    violations.extend(blocking_violations(axe, page, "dashboard"))

    browser.close()
    if violations:
        raise AssertionError("WCAG violations: " + ", ".join(violations))
    print("accessibility smoke passed")
