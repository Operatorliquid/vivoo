# vivoo

Plataforma de captura inteligente para clubes deportivos. vivoo conecta las cámaras de cada cancha con un agente local, detecta gestos para crear highlights, conserva los partidos completos temporalmente y entrega el contenido a los jugadores desde una experiencia web vinculada por QR.

## Arquitectura

- `apps/frontend`: dashboard del club, administración y acceso de jugadores.
- `apps/api`: API, autenticación, sesiones, canchas, cámaras y biblioteca.
- `apps/capture-agent`: captura local, grabación resiliente, detector y cola de subida.
- `apps/worker`: procesamiento de videos y entregas.
- `apps/desktop`: aplicación instalable para la PC del club y actualizaciones automáticas.
- `apps/button-device`: integración opcional con el botón físico.
- `infra`: despliegue, Evolution API, almacenamiento y Terraform.

La cámara permanece dentro de la red del club. El agente instalado en la PC consume el stream RTSP, mantiene la grabación aunque se corte Internet y sincroniza eventos y videos cuando vuelve la conexión.

## Desarrollo

Requisitos: Node.js 22, pnpm 10.12.4, Python 3.12 y `uv`.

```bash
corepack pnpm install
cp .env.example .env
corepack pnpm dev
```

La configuración local del agente se guarda fuera del repositorio en `.courtvision/`.

## Verificación

```bash
corepack pnpm lint
corepack pnpm typecheck
corepack pnpm test
corepack pnpm build
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=apps/api/src uv run --python 3.12 --with-editable apps/api --with pytest --with httpx2 pytest -q apps/api/tests
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=apps/capture-agent/src uv run --python 3.12 --with-editable apps/capture-agent --with pytest pytest -q apps/capture-agent/tests
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=apps/media-worker/src uv run --python 3.12 --with-editable apps/media-worker --with pytest pytest -q apps/media-worker/tests
```

## Instaladores

El workflow `vivoo Desktop installers` compila instaladores nativos de macOS y Windows al ejecutarse manualmente o publicar una etiqueta `desktop-v*`. Los binarios, modelos y artefactos generados no se guardan en Git.

## Seguridad

Nunca se deben versionar archivos `.env`, claves PEM, credenciales de cámaras ni datos reales de jugadores. El repositorio contiene únicamente ejemplos de configuración sin secretos.
