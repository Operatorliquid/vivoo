# Vivoo Desktop

Este proceso se instala en la PC o mini PC que está dentro de la red de la
cancha. Es el único componente que accede a la cámara RTSP. La API cloud nunca
intenta conectarse a una IP privada de la cancha.

## Qué hace

- verifica la cámara desde la red local;
- graba únicamente mientras hay un partido activo y mantiene segmentos locales de cinco segundos;
- cuando no se conserva el partido completo, limita el disco a un búfer circular de aproximadamente un minuto;
- genera desde ese búfer la fuente exacta de los 30 segundos anteriores a cada highlight;
- sube el partido completo al cloud cuando se detiene la grabación o cambia la sesión;
- conserva una cola local de eventos si internet se corta;
- envía heartbeat y eventos a Vivoo cuando vuelve la conexión;
- ofrece una vista local para el dashboard en `http://127.0.0.1:8781`.
- detecta ambos brazos levantados con pose estimation durante una sesión activa;
- mantiene seguimiento temporal separado por persona y descarta cuerpos fuera de la zona calibrada;
- informa FPS, latencia, personas visibles y salud del detector al dashboard y al cloud.

## Instalación de prueba

Requiere Python 3.12 y FFmpeg/FFprobe instalados en la máquina local. Para el
detector de gesto también se instala el extra `vision`; el modelo pose liviano se
descarga una vez en el primer inicio.

```bash
cd apps/capture-agent
python -m pip install -e '.[vision]'
cp config.example.json ~/.courtvision/agent.json
PYTHONPATH=src python -m main --config ~/.courtvision/agent.json
```

El archivo debe usar el token generado desde la configuración de la cámara del
dashboard. El token está vinculado a una sola cámara y vence en 30 días. La
contraseña RTSP se guarda solo en el equipo local con permisos restringidos.

## Comprobación local

```bash
curl http://127.0.0.1:8781/v1/status
curl -X POST http://127.0.0.1:8781/v1/check
```

El dashboard remoto busca este servicio en `127.0.0.1:8781`, por eso la vista de
comprobación funciona cuando el dueño abre la plataforma desde la PC de la
cancha. Desde otra ubicación se muestra el estado sincronizado, no el RTSP
directo.

## Validación del detector

La aceptación se mide por evento, no por precisión de frames. Copiá
`gesture-evaluation.example.json`, agregá videos de partidos y marcá en segundos
el inicio y final de cada gesto intencional. Luego ejecutá:

```bash
PYTHONPATH=src .venv/bin/python tools/evaluate_gestures.py gesture-evaluation.json
```

El comando devuelve recall, gestos perdidos, falsos positivos por hora y
latencia. Sale con código 0 únicamente cuando alcanza al menos 99% de recall y
como máximo 0,1 falsos positivos por hora. Los videos sin gestos son necesarios
para medir saques, remates y movimientos normales como casos negativos.

Para una primera prueba negativa sin copiar videos al repositorio, el evaluador
también acepta anotaciones COCO-17. El resultado es un límite superior: como el
dataset no contiene píxeles, se asume que la comprobación de movimiento local
pasó. Ejemplo con las poses CC BY 4.0 de
[PadelTracker100](https://doi.org/10.5281/zenodo.17020011):

```bash
.venv/bin/python tools/evaluate_coco_pose.py labels/*_pose.json
```

Esta prueba sirve para encontrar falsos candidatos durante saques y remates. La
aceptación comercial todavía requiere videos propios de cada ángulo de cámara,
con gestos intencionales etiquetados mediante `evaluate_gestures.py`.

## Empaquetado inicial

El shell de escritorio ya tiene configuración para generar instaladores
Windows/macOS/Linux:

```bash
pnpm install
pnpm --dir apps/desktop package
```

Este primer paquete requiere Python 3.12 y FFmpeg/FFprobe instalados en la PC.
El siguiente hardening puede incluir esos binarios dentro del instalador y
actualización automática; no cambia el flujo de clubes, QR o jugadores.
