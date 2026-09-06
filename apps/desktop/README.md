# vivoo

Aplicación de escritorio para el equipo local de la cancha. Abre el dashboard de
vivoo y levanta el agente local que conecta la cámara, mantiene la
grabación y sincroniza eventos con la nube.

## Instalación en el club

El cliente instala un único archivo:

- macOS: `vivoo-*.dmg`
- Windows: `vivoo-*.exe`

La aplicación abre el panel en la nube y ejecuta en segundo plano el agente de
cámara, el detector de pose, FFmpeg y MediaMTX. Se inicia con el sistema y
reinicia automáticamente los servicios locales si alguno falla. El usuario no
debe instalar Python ni abrir una terminal.

Cerrar la ventana sólo oculta vivoo: la captura sigue activa en la bandeja del
sistema. El watchdog comprueba el agente cada 15 segundos, lo reinicia con
backoff si deja de responder y vuelve a validar cámara y detector al reanudar el
equipo. Mientras vivoo está abierto bloquea la suspensión del proceso para que
Windows o macOS no congelen una grabación. **Salir y detener captura** es la única
acción de la bandeja que apaga deliberadamente los servicios.

En Windows la primera ejecución registra `VivooCaptureService` en el Programador
de tareas del usuario, con reinicio al minuto si el proceso principal falla y
sin límite de ejecución. El desinstalador retira esa tarea. Si Windows impide el
registro, vivoo vuelve automáticamente al inicio de sesión estándar.

Una sola instalación administra varias cámaras. Cada cámara conserva token,
credenciales, detector, grabación, buffer y almacenamiento local aislados; una
falla no cambia la configuración de las demás.

Después de iniciar sesión, se crea la cámara desde **Canchas**, se abre su
detalle y se pulsa **Vincular esta PC**. El dashboard entrega y configura el
token automáticamente. La cámara queda en la red local; a la nube solo se
sincronizan estados, eventos y los videos terminados.

## Desarrollo

```bash
pnpm install
pnpm --dir apps/desktop dev
```

El modo de desarrollo requiere Python 3.12 y FFmpeg/FFprobe. Los instaladores
no tienen ese requisito. El agente escucha exclusivamente en
`http://127.0.0.1:8781`.

## Generar instaladores

En cada sistema operativo:

```bash
pnpm install
uv pip install --python apps/capture-agent/.venv/bin/python pyinstaller
pnpm --dir apps/desktop runtime:prepare
apps/capture-agent/.venv/bin/python apps/desktop/scripts/build-agent.py
pnpm --dir apps/desktop dist:mac # o dist:win en Windows
```

El build descarga MediaMTX desde su release fijado y valida SHA-256. El modelo
de pose, FFmpeg y FFprobe se incluyen como recursos de la aplicación.

## Actualizaciones automáticas

vivoo consulta el canal de actualizaciones al iniciar y cada seis horas. Descarga
la nueva versión en segundo plano y la instala automáticamente cuando ninguna
cámara está grabando; nunca corta un partido en curso.

Después de generar un instalador, preparar el canal que sirve el dashboard:

```bash
pnpm --dir apps/desktop update:stage
```

El comando copia el manifiesto, instalador y `blockmap` a
`infra/deploy/desktop-updates/<plataforma>/<arquitectura>`. El despliegue normal
sincroniza ese directorio y Nginx lo publica en `/desktop-updates/`. Para usar
otro canal, definir `COURTVISION_UPDATE_URL` al empaquetar o ejecutar vivoo.

Al publicar una etiqueta `desktop-v*`, GitHub Actions construye macOS y Windows
en sus sistemas nativos. Primero publica instaladores y `blockmap`; los
manifiestos se publican al final para que ningún cliente reciba una actualización
incompleta. El repositorio necesita los secretos `DESKTOP_UPDATE_HOST`,
`DESKTOP_UPDATE_USER`, `DESKTOP_UPDATE_SSH_KEY` y
`DESKTOP_UPDATE_KNOWN_HOSTS`.

## Firma para distribución

Los pilotos internos pueden usar builds sin firmar. Para entregar el producto
a clientes, macOS requiere certificado Developer ID y notarización; Windows,
un certificado de firma de código. Las credenciales se inyectan únicamente en
CI y nunca se guardan en el repositorio.

La URL del dashboard puede cambiarse con `COURTVISION_DASHBOARD_URL`; el agente
siempre escucha solo en loopback y no publica la cámara en internet.
