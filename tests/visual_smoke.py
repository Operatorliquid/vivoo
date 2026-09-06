"""Recorrido visual de CourtVision sobre la consola rediseñada.

Levanta un navegador, recorre los flujos reales del producto (login, operación,
canchas, detalle, alta y baja de cancha, actividad, configuración, QR del
jugador) y deja capturas en /tmp. Requiere la API en :8000 y el front en
COURTVISION_BASE_URL (por defecto :5173).
"""

from pathlib import Path
import os
import re

from playwright.sync_api import expect, sync_playwright

ROOT = Path('/tmp')
BASE_URL = os.getenv('COURTVISION_BASE_URL', 'http://127.0.0.1:5173')
DESKTOP = {'width': 1440, 'height': 1000}
MOBILE = {'width': 390, 'height': 844}


def shot(page, name: str) -> None:
    page.wait_for_timeout(500)
    page.screenshot(path=str(ROOT / f'courtvision-{name}.png'), full_page=True)


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport=DESKTOP)

    # --- Acceso ---------------------------------------------------------------
    page.goto(BASE_URL)
    page.wait_for_load_state('networkidle')
    expect(page.get_by_role('heading', name='Iniciar sesión')).to_be_visible()
    shot(page, 'login')
    page.get_by_label('Email').fill('owner@courtvision.local')
    page.get_by_label('Contraseña').fill('courtvision-demo')
    page.get_by_role('button', name='Entrar').click()

    # --- Operación ------------------------------------------------------------
    expect(page.get_by_role('heading', name='Operación')).to_be_visible(timeout=8000)
    expect(page.locator('.donut__chart')).to_be_visible()
    expect(page.locator('#ov-courts')).to_be_visible()
    initial_courts = page.locator('.row').count()
    assert initial_courts >= 1
    shot(page, 'overview')

    # El tema es una capacidad del sistema, no un override por pantalla. Se
    # verifica en la consola y después de recargar para cubrir persistencia.
    page.get_by_role('button', name='Usar modo oscuro').click()
    expect(page.locator('html')).to_have_attribute('data-theme', 'dark')
    shot(page, 'overview-dark')
    page.reload()
    expect(page.locator('html')).to_have_attribute('data-theme', 'dark')
    page.get_by_role('button', name='Usar modo claro').click()
    expect(page.locator('html')).to_have_attribute('data-theme', 'light')

    # --- Listado de canchas ----------------------------------------------------
    page.get_by_role('button', name=re.compile(r'^Canchas')).first.click()
    page.wait_for_url(re.compile(r'/fields$'))
    expect(page.locator('.row-legend')).to_be_visible()
    assert page.locator('.row').count() == initial_courts
    shot(page, 'courts')

    # Filtrado por estado de captura.
    page.get_by_role('button', name=re.compile(r'^Capturando')).click()
    assert page.locator('.row--live').count() == page.locator('.row').count()
    page.get_by_role('button', name=re.compile(r'^Todas')).click()

    # --- Detalle de cancha ------------------------------------------------------
    page.locator('.row__link').first.click()
    page.wait_for_url(re.compile(r'/fields/[^/?]+$'))
    field_token = page.url.rstrip('/').rsplit('/', 1)[-1]
    expect(page.locator('#cd-camera')).to_be_visible(timeout=5000)
    expect(page.locator('#cd-capture')).to_be_visible()
    expect(page.locator('#cd-qr')).to_be_visible()
    shot(page, 'court-detail')

    # La grabación se aplica al instante y el estado derivado lo refleja.
    recording = page.get_by_role('switch')
    toggle = page.get_by_text('Grabación automática', exact=True)
    was_on = recording.is_checked()
    toggle.click()
    expect(page.locator('.toast')).to_be_visible(timeout=5000)
    page.wait_for_timeout(900)
    assert recording.is_checked() is not was_on
    toggle.click()
    page.wait_for_timeout(1200)
    assert recording.is_checked() is was_on

    # --- Alta de cancha en dos pasos ---------------------------------------------
    page.go_back()
    page.wait_for_url(re.compile(r'/fields$'))
    page.get_by_role('button', name='Nueva cancha').click()
    dialog = page.get_by_role('dialog', name='Nueva cancha')
    expect(dialog).to_be_visible()
    dialog.get_by_label('Nombre de la cancha').fill('Cancha Visual')
    shot(page, 'new-court-step1')
    dialog.get_by_role('button', name='Continuar').click()
    dialog.get_by_label('Host o IP').fill('192.168.1.80')
    dialog.get_by_label('Ruta del stream').fill('/Streaming/Channels/101')
    shot(page, 'new-court-step2')
    dialog.get_by_role('button', name='Crear cancha').click()

    # Tras crearla se abre su detalle: falta vincular el equipo local.
    page.wait_for_url(re.compile(r'/fields/[^/?]+$'), timeout=8000)
    expect(page.get_by_role('heading', name='Cancha Visual')).to_be_visible(timeout=5000)
    expect(page.get_by_text('Equipo local sin vincular')).to_be_visible(timeout=5000)

    # --- Baja de cancha ------------------------------------------------------------
    page.get_by_role('button', name='Eliminar Cancha Visual').click()
    confirm = page.get_by_role('dialog', name='Eliminar Cancha Visual')
    confirm.get_by_role('button', name='Eliminar cancha').click()
    page.wait_for_url(re.compile(r'/fields$'), timeout=8000)
    page.wait_for_function(
        f"() => document.querySelectorAll('.row').length === {initial_courts}",
        timeout=8000,
    )

    # --- Actividad -------------------------------------------------------------------
    page.get_by_role('button', name=re.compile(r'^Actividad')).first.click()
    page.wait_for_url(re.compile(r'/notifications$'))
    expect(page.locator('h1', has_text='Actividad')).to_be_visible()
    shot(page, 'activity')

    # --- Biblioteca -------------------------------------------------------------------
    page.get_by_role('button', name='Biblioteca').first.click()
    page.wait_for_url(re.compile(r'/library$'))
    expect(page.locator('#lib-moments')).to_be_visible()
    shot(page, 'library')

    # --- Configuración -----------------------------------------------------------------
    page.get_by_role('button', name='Configuración de la cuenta').click()
    page.wait_for_url(re.compile(r'/settings$'))
    expect(page.locator('#st-club')).to_be_visible()
    assert page.get_by_label('Email de acceso').input_value() == 'owner@courtvision.local'
    # Guardar sólo se habilita cuando hay algo por guardar.
    save_club = page.get_by_role('button', name='Guardar club')
    assert save_club.is_disabled()
    page.get_by_label('Ciudad').fill('Buenos Aires')
    assert save_club.is_enabled()
    page.get_by_role('button', name='Descartar').first.click()
    shot(page, 'settings')

    # --- Consola en móvil: la navegación inferior debe estar presente -------------------
    page.set_viewport_size(MOBILE)
    page.goto(BASE_URL)
    page.wait_for_load_state('networkidle')
    tabs = page.locator('.tab-nav__item')
    assert tabs.count() == 4
    shot(page, 'overview-mobile')
    page.get_by_role('button', name='Usar modo oscuro').click()
    expect(page.locator('html')).to_have_attribute('data-theme', 'dark')
    shot(page, 'overview-mobile-dark')

    # --- Flujo del jugador ---------------------------------------------------------------
    page.goto(f'{BASE_URL}/qr?field={field_token}')
    page.wait_for_load_state('networkidle')
    expect(page.get_by_role('heading', name=re.compile('Jugá'))).to_be_visible()
    shot(page, 'qr-mobile')
    page.get_by_role('button', name='Entrar al partido').click()
    page.get_by_label('Tu nombre').fill('Martín')
    page.get_by_label('Tu WhatsApp').fill('+54 9 11 5555 0118')
    page.get_by_role('button', name='Confirmar y jugar').click()
    expect(page.get_by_text('Tu código de jugador')).to_be_visible(timeout=8000)
    shot(page, 'qr-ready-mobile')

    page.get_by_role('button', name='Ver mi partido').click()
    page.wait_for_url(re.compile(r'/player'))
    expect(page.get_by_role('heading', name='Partido completo')).to_be_visible(timeout=8000)
    shot(page, 'player-mobile')

    browser.close()
    print('Recorrido visual completo. Capturas en /tmp/courtvision-*.png')
