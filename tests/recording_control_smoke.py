"""Real-browser smoke test for owner recording controls against the linked edge agent."""

from pathlib import Path
import os

from playwright.sync_api import expect, sync_playwright


BASE_URL = os.getenv("COURTVISION_BASE_URL", "http://127.0.0.1:5180")
ARTIFACT_DIR = Path(os.getenv("COURTVISION_ARTIFACT_DIR", "/tmp"))


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    console_errors: list[str] = []
    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
    page.on("pageerror", lambda error: console_errors.append(str(error)))

    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")
    page.get_by_label("Email").fill("owner@courtvision.local")
    page.get_by_label("Contraseña").fill("courtvision-demo")
    page.get_by_role("button", name="Entrar").click()
    expect(page.get_by_role("heading", name="Operación")).to_be_visible(timeout=10_000)

    page.goto(f"{BASE_URL}/fields/field-01")
    expect(page.locator("#cd-capture")).to_be_visible(timeout=10_000)
    expect(page.get_by_text("Partido en curso", exact=True)).to_be_visible(timeout=10_000)
    expect(page.get_by_role("button", name="Detener")).to_be_visible()
    page.wait_for_timeout(1000)
    page.screenshot(path=str(ARTIFACT_DIR / "courtvision-recording-active.png"), full_page=True)

    page.get_by_role("button", name="Detener").click()
    dialog = page.get_by_role("dialog", name="Detener grabación")
    expect(dialog).to_be_visible()
    expect(dialog.get_by_role("button", name="Continuar grabando")).to_be_visible()
    dialog.get_by_role("button", name="Finalizar partido").click()
    expect(page.get_by_role("button", name="Iniciar grabación")).to_be_visible(timeout=25_000)

    page.get_by_role("button", name="Iniciar grabación").click()
    expect(page.get_by_text("Grabando", exact=True)).to_be_visible(timeout=25_000)
    page.wait_for_timeout(1000)
    page.screenshot(path=str(ARTIFACT_DIR / "courtvision-recording-confirmed.png"), full_page=True)

    page.get_by_role("button", name="Detener").click()
    page.get_by_role("dialog", name="Detener grabación").get_by_role("button", name="Finalizar partido").click()
    expect(page.get_by_role("button", name="Iniciar grabación")).to_be_visible(timeout=25_000)
    page.wait_for_timeout(1000)
    page.screenshot(path=str(ARTIFACT_DIR / "courtvision-recording-idle.png"), full_page=True)

    browser.close()
    if console_errors:
        raise AssertionError(f"Browser console errors: {console_errors}")
    print("recording control smoke passed")
