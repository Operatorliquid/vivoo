# CourtVision button device

El botón físico se instala por cancha y se conecta al agente local de esa cancha. El ESP32 nunca necesita credenciales de AWS ni acceso al frontend.

## Protocolo local

`POST http://<capture-agent>:8790/v1/button/press`

```json
{
  "device_id": "CV-BTN-01",
  "event_id": "press-000123",
  "pressed_at": "2026-08-12T18:00:00Z",
  "signature": "<HMAC-SHA256>"
}
```

La firma usa `HMAC-SHA256(secret, device_id + ":" + event_id + ":" + pressed_at)`. El agente valida el reloj, la firma y el rebote eléctrico. Luego crea un evento `physical_button`, idéntico al flujo de un gesto confirmado.

Para una instalación real conviene usar un pulsador industrial de 24 V con un optoacoplador o un módulo de entrada aislada; el GPIO del ESP32 no debería quedar expuesto al cableado largo de la cancha.
