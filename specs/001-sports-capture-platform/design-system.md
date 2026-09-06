# CourtVision Design System

**Estado**: implementado en `packages/design-system` y `apps/frontend/src/styles`.

**Dirección visual**: consola operativa, cálida y precisa. La paleta parte de la
referencia: lienzo hueso, superficies casi blancas, tinta carbón y verde salvia.
En oscuro se conserva la misma jerarquía sobre fondos verde-carbón, sin invertir
colores de forma mecánica. Las capas flotantes usan blur y bordes translúcidos.

## Principios

- El color siempre significa algo. Verde = capturando, ámbar = lista, rojo =
  sin señal, gris = fuera de servicio. Nunca decoración.
- Cada dato que se muestra viene de la API. No hay series temporales
  inventadas ni comparaciones contra períodos que el backend no entrega.
- Aire antes que densidad: tarjetas separadas, tipografía tranquila, sin
  mayúsculas sostenidas fuera de las micro-etiquetas.
- Sin monoespaciada en ninguna superficie.

## Color

| Token | Hex | Uso |
|---|---|---|
| `canvas` | `#EBEAE4` | Fondo cálido de página |
| `surface` | `#FBFCFA` | Tarjetas |
| `surface-2` / `surface-3` | `#F1F2EE` / `#E7E9E4` | Campos, chips y superficies internas |
| `text-primary` | `#171C18` | Tinta carbón principal |
| `brand-500` | `#58836D` | Acción primaria y estado *capturando* |
| `warn-500` | `#B48B45` | Estado *lista*, momentos |
| `danger-500` | `#C85F55` | *Sin señal* y acciones destructivas |
| `info-500` | `#5F7F87` | Actividad e información |

Los únicos valores de color literales viven en `theme.css`. Toda pantalla usa
tokens semánticos (`surface`, `text`, `line`, `overlay`, `on-accent`, etc.).
`tokens.ts` apunta a esas mismas custom properties y no mantiene otra paleta.

## Temas

- `data-theme="light"`: hueso, blanco cálido, carbón y salvia.
- `data-theme="dark"`: verde-carbón, superficies elevadas y salvia clara.
- La preferencia se guarda en `localStorage`; sin preferencia explícita sigue
  `prefers-color-scheme` y también responde a cambios del sistema.
- El selector usa texto accesible, animación propia y aparece en la consola,
  login y flujo público.

Cada estado tiene su tinte al 50 para fondos de píldoras, chips y avisos.

## Tipografía

Una sola familia: **Plus Jakarta Sans**, con contraste por peso y tamaño.
Clases: `.t-hero`, `.t-display`, `.t-title`, `.t-heading`, `.t-body`, `.t-sm`,
`.t-label`, `.t-meta`, `.t-figure` (cifras con numerales tabulares).

## Geometría y elevación

- Radios: 20–26px en tarjetas y diálogos, 14px en controles, pill en botones.
- Sombras muy suaves en dos niveles (`--shadow-card`, `--shadow-pop`); la
  jerarquía la da la superficie, no la sombra.
- `backdrop-filter` con saturación en la barra superior, el panel de actividad,
  el buscador y el fondo de los diálogos.

## Composición

- **Barra superior flotante** con el título de la sección, la búsqueda rápida de
  canchas, la hora de última sincronización, actividad y cuenta.
- **Riel flotante** de alto completo, con la navegación agrupada (Menú /
  General) y la cuenta al pie.
- **Operación**: cuatro tarjetas de indicador, alertas accionables cuando una
  cancha no captura, listado de canchas y rosquilla de reparto por estado, y
  abajo momentos y actividad.
- **Canchas**: tarjeta con filtros por estado y listado en columnas.
- **Detalle de cancha**: monitor de cámara y vínculo con el equipo local a la
  izquierda; captura, nombre, QR, botón físico y zona irreversible a la derecha,
  cada bloque en su propia tarjeta.

## Estado de captura derivado

La API expone el estado administrativo de la cancha y el de su cámara por
separado. La interfaz los resuelve en un único estado con su explicación
(`lib/court.ts`): una cámara "live" con la grabación pausada **no** está
capturando y no debe mostrarse como tal.

`live` capturando · `ready` lista · `offline` sin señal · `idle` fuera de servicio.

## Gráficas

Sólo una, y es real: la rosquilla de reparto de canchas por estado. La API no
entrega series temporales, así que no se dibuja ninguna curva. El resto de los
datos se presenta con cifras, medidores de ocupación y píldoras de estado.

## Movimiento

- Entrada de página 260ms; filas escalonadas en los primeros elementos.
- Tarjetas de indicador con elevación al hover.
- Diálogos y paneles con escala y blur de fondo.
- Punto de estado en vivo con respiración lenta.
- Todo respeta `prefers-reduced-motion`.

## Componentes

`packages/design-system`: superficies/card, `Icon`, `Button` (primary/secondary/ghost/danger),
`StatusDot`, `StatusPill`, `TextField`, `SelectField`, `Switch`, `Segmented`,
`Meter`, `Skeleton`, `EmptyState` (con acento semántico), `Banner`, `Dialog` (foco
atrapado, Escape, retorno de foco), `ThemeToggle` y `Avatar`.

Aplicación: `StatCard`, `CourtStateDonut`, `CourtRow`, `QuickSearch`,
`MomentList`, `NotificationList`, `CopyValue`, `CameraPreview`, `AgentPairing`
y los diálogos de alta de cancha y de cámara.

## Accesibilidad y calidad

- Contraste y teclado según WCAG 2.2 AA.
- Foco visible siempre; en las filas de cancha el anillo marca la fila completa.
- Enlace de salto al contenido; en móvil, barra inferior con los cuatro destinos.
- Los flujos del jugador funcionan a 320px sin scroll horizontal.
- `tests/visual_smoke.py` recorre login, operación, canchas, detalle, alta y baja
  de cancha, actividad, biblioteca, configuración, consola móvil y flujo del
  jugador, y deja capturas en `/tmp`.
