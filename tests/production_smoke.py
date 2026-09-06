"""Read-only browser smoke test for a deployed CourtVision installation."""

from pathlib import Path
import os
import re

from playwright.sync_api import expect, sync_playwright


BASE_URL = os.getenv("COURTVISION_BASE_URL", "http://127.0.0.1:5173")
OWNER_EMAIL = os.getenv("COURTVISION_OWNER_EMAIL", "owner@courtvision.local")
OWNER_PASSWORD = os.getenv("COURTVISION_OWNER_PASSWORD", "courtvision-demo")
ARTIFACT_DIR = Path(os.getenv("COURTVISION_ARTIFACT_DIR", "/tmp"))


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    browser_errors: list[str] = []
    failed_responses: list[str] = []
    def capture_console_error(message: object) -> None:
        if getattr(message, "type", "") != "error":
            return
        text = str(getattr(message, "text", ""))
        expected = (
            "401 (Unauthorized)" in text
            or "127.0.0.1:8781" in text
            or text == "Failed to load resource: net::ERR_FAILED"
        )
        if not expected:
            browser_errors.append(text)

    page.on("console", capture_console_error)
    page.on("pageerror", lambda error: browser_errors.append(str(error)))
    page.on(
        "response",
        lambda response: failed_responses.append(f"{response.status} {response.url}")
        if response.status >= 500
        else None,
    )

    page.goto(BASE_URL, wait_until="networkidle")
    expect(page.get_by_role("heading", name="Iniciar sesión")).to_be_visible()
    page.get_by_label("Email").fill(OWNER_EMAIL)
    page.get_by_label("Contraseña").fill("clave-incorrecta")
    page.get_by_role("button", name="Entrar").click()
    expect(page.get_by_text("El email o la contraseña no son correctos.")).to_be_visible(timeout=10_000)
    expect(page.get_by_text(re.compile(r"\[object Object\]"))).to_have_count(0)
    page.get_by_label("Contraseña").fill(OWNER_PASSWORD)
    page.get_by_role("button", name="Entrar").click()
    expect(page.get_by_role("heading", name="Operación")).to_be_visible(timeout=10_000)

    page.get_by_role("button", name=re.compile(r"^Canchas")).first.click()
    page.wait_for_url(re.compile(r"/fields$"))
    expect(page.locator(".row").first).to_be_visible(timeout=10_000)
    page.locator(".row__link").first.click()
    page.wait_for_url(re.compile(r"/fields/[^/?]+$"))
    expect(page.locator("#cd-camera")).to_be_visible(timeout=10_000)
    page.screenshot(path=str(ARTIFACT_DIR / "courtvision-production-smoke.png"), full_page=True)

    page.get_by_role("button", name="Biblioteca").first.click()
    page.wait_for_url(re.compile(r"/library$"))
    expect(page.locator(".library")).to_be_visible(timeout=10_000)

    session_token = page.evaluate(
        "JSON.parse(localStorage.getItem('courtvision.owner.session')).access_token"
    )
    page.get_by_role("button", name="Cerrar sesión").click()
    expect(page.get_by_role("heading", name="Iniciar sesión")).to_be_visible(timeout=10_000)
    revoked = page.request.get(
        f"{BASE_URL}/api/auth/me",
        headers={"Authorization": f"Bearer {session_token}"},
    )
    assert revoked.status == 401, f"logout did not revoke the owner session: {revoked.status}"

    browser.close()
    if browser_errors or failed_responses:
        raise AssertionError(
            f"browser_errors={browser_errors}; failed_responses={failed_responses}"
        )
    print("production browser smoke passed")
