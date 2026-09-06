import json
from pathlib import Path

from playwright.sync_api import sync_playwright


OUTPUT = Path("/tmp/tveo-whatsapp-settings.png")
MOBILE_OUTPUT = Path("/tmp/tveo-whatsapp-settings-mobile.png")


def whatsapp_route(route) -> None:
    payload = {
        "status": "connecting",
        "instance_name": "tveo-test",
        "phone": None,
        "profile_name": None,
        "qr_base64": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHZpZXdCb3g9JzAgMCAxMDAgMTAwJz48cGF0aCBmaWxsPScjMDcwYjBhJyBkPSdNMCAwaDEwMHYxMDBIMHonLz48cGF0aCBmaWxsPScjZjRmOGY1JyBkPSdNNyA3aDI4djI4SDd6bTU4IDBoMjh2MjhINjV6TTcgNjVoMjh2MjhIN3ptNDIgMGg4djhoLTh6bTE2IDE2aDI4djEySDY1ek0xNSAxNWgxMnYxMkgxNXptNTggMGgxMnYxMkg3M3ptLTU4IDU4aDEydjEySDE1eicvPjwvc3ZnPg==",
        "pairing_code": "1234-5678",
    }
    route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1050}, device_scale_factor=1)
    page.route("**/api/owner/whatsapp**", whatsapp_route)
    page.goto("http://127.0.0.1:5173")
    page.wait_for_load_state("networkidle")
    page.get_by_label("Email").fill("owner@courtvision.local")
    page.get_by_role("textbox", name="Contraseña", exact=True).fill("courtvision-demo")
    page.get_by_role("button", name="Entrar").click()
    page.wait_for_load_state("networkidle")
    page.get_by_role("button", name="Configuración", exact=True).click()
    page.get_by_role("heading", name="WhatsApp").wait_for()

    assert page.locator(".whatsapp-connect__qr img").is_visible()
    assert page.get_by_role("button", name="Generar otro QR").is_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    page.screenshot(path=str(OUTPUT), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    assert page.get_by_role("button", name="Generar otro QR").is_visible()
    page.screenshot(path=str(MOBILE_OUTPUT), full_page=True)
    browser.close()

print(OUTPUT)
print(MOBILE_OUTPUT)
