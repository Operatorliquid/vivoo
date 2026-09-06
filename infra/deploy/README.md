# CourtVision en EC2

El gateway publica HTTP/HTTPS, obtiene y renueva el certificado TLS del dominio
configurado y enruta el dashboard hacia Nginx/FastAPI. Antes de iniciar, el DNS
del dominio debe apuntar al servidor y los puertos TCP 80/443 (y UDP 443 para
HTTP/3) deben estar permitidos.

```bash
docker compose --env-file .env -f infra/deploy/compose.yml up -d --build
```

Para una prueba local sin dominio puede usarse `SITE_ADDRESS=http://localhost` y
`PUBLIC_BASE_URL=http://localhost`. Esa configuración no es válida para producción.
En producción, `SITE_ADDRESS`, `PUBLIC_BASE_URL`, `CORS_ALLOWED_ORIGINS` y
`TRUSTED_HOSTS` deben contener el dominio HTTPS real, sin comodines.

PostgreSQL queda en una red interna de Docker y utiliza el volumen `courtvision_postgres`. La configuración del club, canchas, cámaras y botones se persiste allí; los videos usan `courtvision_media` como almacenamiento local temporal hasta conectar S3.

Evolution API también queda exclusivamente en la red interna. El API genera una
instancia opaca por dueño y el QR se muestra en **Configuración → WhatsApp**; la
clave global de Evolution nunca llega al frontend. La sesión de WhatsApp
persiste en `evolution_instances` y su base en `evolution_postgres`.

La instancia necesita al menos 16 GB de disco raíz para alojar la aplicación,
Evolution y el margen operativo de videos temporales. `/health` devuelve 503 si
PostgreSQL, el almacenamiento o el heartbeat del worker no están sanos;
`/health/live` se limita a confirmar que el proceso responde.

La conexión RTSP se ejecuta en CourtVision Desktop dentro de la red del club. El
API cloud solo entrega un token vinculado a la cámara, recibe heartbeat/eventos y
administra el catálogo, QR, videos sincronizados y entregas. No se debe publicar
el puerto RTSP de la cámara en internet.
