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

El API y el worker comprueban el estado de esa sesión antes de entregar. Si las
credenciales persistidas siguen siendo válidas, Evolution se reconecta sin
intervención. Los mensajes pendientes quedan en una outbox SQLite dentro del
volumen de media durante hasta 48 horas, con backoff; reiniciar el worker no los
pierde y un callback caído no provoca un envío duplicado. Si WhatsApp revoca la
sesión, Configuración vuelve a mostrar el QR.

## Backups y recuperación

El servicio `backup` genera cada seis horas dos dumps consistentes: vivoo y la
base de Evolution. Antes de declararlos válidos levanta PostgreSQL de forma
aislada y restaura ambos dumps completos. Sólo después calcula checksums, los
sube a S3 y registra el heartbeat que expone `/health`. Conserva siete días en
el volumen local. Si `AWS_S3_BACKUP_BUCKET` queda vacío utiliza
`AWS_S3_MEDIA_BUCKET` bajo `backups/vivoo/`; para producción se recomienda un
bucket privado separado con versionado y cifrado.

Ver el último backup verificado:

```bash
docker compose --env-file .env -f infra/deploy/compose.yml exec backup sh -c 'cat /backups/latest && cat /backups/last-success.epoch'
```

Restaurar es deliberadamente manual. Primero se detienen los consumidores, se
ejecuta la restauración con la frase de confirmación y luego se levantan otra vez:

```bash
docker compose --env-file .env -f infra/deploy/compose.yml stop api media-worker evolution-api
docker compose --env-file .env -f infra/deploy/compose.yml run --rm --entrypoint /usr/local/bin/vivoo-restore backup /backups/AAAAMMDDTHHMMSSZ RESTORE_VIVOO_BACKUP
docker compose --env-file .env -f infra/deploy/compose.yml up -d api evolution-api media-worker
```

La instancia necesita al menos 16 GB de disco raíz para alojar la aplicación,
Evolution y el margen operativo de videos temporales. `/health` devuelve 503 si
PostgreSQL, el almacenamiento o el heartbeat del worker no están sanos;
`/health/live` se limita a confirmar que el proceso responde.

La conexión RTSP se ejecuta en CourtVision Desktop dentro de la red del club. El
API cloud solo entrega un token vinculado a la cámara, recibe heartbeat/eventos y
administra el catálogo, QR, videos sincronizados y entregas. No se debe publicar
el puerto RTSP de la cámara en internet.
