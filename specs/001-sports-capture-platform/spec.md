# Feature Specification: Sports Capture Platform

**Feature Branch**: `001-sports-capture-platform`

**Created**: 2026-08-07

**Status**: Draft

**Input**: User description: "Crear una plataforma profesional para clubes deportivos, comenzando por pádel, donde los dueños administren clubes, canchas, cámaras y videos; los jugadores escaneen un QR para asociar un partido a sus datos; una cámara grabe el partido; un gesto o acción de respaldo guarde los 30 segundos anteriores como highlight; y el sistema envíe automáticamente el resultado por WhatsApp. La plataforma debe poder extenderse luego a fútbol y otros deportes."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Iniciar un partido desde la cancha (Priority: P1)

Como jugador de pádel, quiero escanear un QR de la cancha, identificarme con mi nombre y número de celular, y comenzar una sesión de partido sin instalar una aplicación, para que la grabación quede asociada a mí.

**Why this priority**: Sin una sesión correctamente identificada, los videos no pueden entregarse al jugador ni organizarse para el club.

**Independent Test**: En una cancha configurada, un jugador escanea el QR, completa el registro y confirma la sesión; el sistema muestra la cancha, el deporte y el horario correctos y deja la sesión lista para grabar.

**Acceptance Scenarios**:

1. **Given** una cancha activa con un QR válido, **When** el jugador escanea el QR, **Then** ve una pantalla de inicio que identifica el club y la cancha.
2. **Given** que el jugador está en la pantalla de inicio, **When** ingresa un nombre y un número de celular válidos y acepta la grabación, **Then** se crea una sesión asociada a esa cancha, fecha, horario y jugador.
3. **Given** que el jugador ingresa datos inválidos o incompletos, **When** intenta iniciar la sesión, **Then** recibe una explicación clara y puede corregirlos sin perder el progreso.
4. **Given** que existe una sesión activa para la cancha, **When** otro jugador escanea el QR, **Then** puede asociarse a la sesión existente sin crear una sesión duplicada.

### User Story 2 - Guardar y recibir un highlight (Priority: P1)

Como jugador, quiero realizar un gesto visible o utilizar una alternativa de respaldo para guardar mi mejor jugada, para recibir automáticamente un clip con los 30 segundos anteriores.

**Why this priority**: El highlight instantáneo es la propuesta de valor principal para el jugador y el contenido que el club puede compartir.

**Independent Test**: Durante una sesión activa, se activa un evento de highlight y se verifica que el clip corresponda a la sesión correcta, contenga la ventana previa de 30 segundos y sea enviado al jugador.

**Acceptance Scenarios**:

1. **Given** una sesión activa y una cámara disponible, **When** el sistema reconoce el gesto configurado con suficiente confianza, **Then** marca el momento y conserva los 30 segundos previos como un highlight.
2. **Given** que el gesto no puede reconocerse, **When** el jugador utiliza la alternativa de respaldo habilitada, **Then** el sistema conserva igualmente los 30 segundos previos.
3. **Given** que un highlight fue creado, **When** finaliza su procesamiento, **Then** el jugador recibe un enlace privado por WhatsApp con el clip y la identificación del club y la cancha.
4. **Given** que el procesamiento o el envío falla temporalmente, **When** el sistema detecta el fallo, **Then** conserva el highlight, informa su estado y permite reintentarlo sin crear clips o mensajes duplicados.
5. **Given** que se activan varios highlights en una ventana muy corta, **When** el sistema los procesa, **Then** evita sobrescribir silenciosamente un highlight confirmado y muestra cada resultado con su hora.

### User Story 3 - Consultar el partido y sus momentos (Priority: P1)

Como jugador, quiero acceder a una página privada con mis highlights y, cuando el club lo habilite, con el partido completo, para revisar o compartir mis jugadas.

**Why this priority**: El enlace privado permite entregar valor más allá del mensaje inicial y reduce la necesidad de una aplicación móvil obligatoria.

**Independent Test**: Un jugador recibe un enlace válido, visualiza únicamente el contenido de su sesión y puede compartir un highlight; un enlace vencido o revocado deja de mostrar el contenido.

**Acceptance Scenarios**:

1. **Given** que una sesión tiene highlights procesados, **When** el jugador abre su enlace privado, **Then** ve los clips ordenados por momento y puede reproducirlos.
2. **Given** que el partido completo está disponible y autorizado, **When** el jugador abre su página, **Then** puede acceder al partido completo separado de los highlights.
3. **Given** que un enlace fue vencido o revocado, **When** alguien intenta abrirlo, **Then** el contenido no se muestra y se informa que el acceso ya no está disponible.
4. **Given** que un jugador comparte un highlight, **When** otra persona abre el enlace, **Then** solo puede ver el contenido permitido por la configuración de privacidad.

### User Story 4 - Administrar clubes y biblioteca de videos (Priority: P1)

Como dueño de un club, quiero tener una cuenta con mis clubes, canchas, cámaras, partidos y videos organizados, para administrar el servicio y encontrar rápidamente cualquier contenido.

**Why this priority**: La cuenta del dueño convierte el producto en una plataforma profesional y permite operar múltiples clubes y canchas.

**Independent Test**: Un dueño crea o accede a su club, consulta la biblioteca, filtra una sesión y reproduce un highlight sin poder acceder a datos de otro dueño.

**Acceptance Scenarios**:

1. **Given** un dueño autenticado, **When** abre su panel, **Then** ve únicamente los clubes y recursos que administra.
2. **Given** que existen partidos y highlights, **When** el dueño filtra por club, cancha, fecha, jugador o estado, **Then** obtiene resultados correspondientes a esos criterios.
3. **Given** una sesión con highlights, **When** el dueño la abre, **Then** puede consultar el partido, sus clips, los jugadores asociados y los estados de procesamiento y entrega.
4. **Given** que el dueño tiene varias canchas, **When** consulta su panel, **Then** puede distinguir cada cámara y sesión por club y cancha.
5. **Given** un dueño sin autorización sobre otro club, **When** intenta abrir un recurso ajeno, **Then** el sistema rechaza el acceso.

### User Story 5 - Configurar una cancha y preparar una sesión (Priority: P2)

Como administrador de un club, quiero configurar cada cancha, cámara y QR, para que el sistema sepa dónde se juega cada partido y pueda operar con mínima intervención del personal.

**Why this priority**: Una configuración clara permite escalar de una cancha a múltiples clubes sin depender de ajustes manuales en cada partido.

**Independent Test**: Un administrador registra una cancha, la vincula a una cámara y genera su QR; al escanearlo, la sesión identifica correctamente esos recursos.

**Acceptance Scenarios**:

1. **Given** un administrador con permisos de configuración, **When** registra una cancha y una cámara, **Then** puede dejarlas activas para recibir sesiones.
2. **Given** una cancha activa, **When** el administrador genera o consulta su QR, **Then** el QR identifica únicamente esa cancha.
3. **Given** una cámara desconectada, **When** se intenta iniciar una sesión, **Then** el sistema informa el problema antes de prometer una grabación disponible.
4. **Given** que una cancha cambia de cámara, **When** el administrador actualiza la configuración, **Then** las sesiones históricas conservan su asociación original.

### User Story 6 - Preparar la expansión a otros deportes (Priority: P3)

Como operador de la plataforma, quiero que los clubes y sesiones puedan identificar el deporte practicado, para incorporar fútbol y otros deportes sin reconstruir la gestión de cuentas, videos y entregas.

**Why this priority**: La expansión es una meta estratégica, pero no debe retrasar la validación del flujo completo de pádel.

**Independent Test**: Una sesión de pádel se crea y consulta con su identidad deportiva, y la estructura permite registrar otra disciplina sin alterar la sesión histórica de pádel.

**Acceptance Scenarios**:

1. **Given** una cancha configurada para pádel, **When** se crea una sesión, **Then** la sesión conserva el deporte y sus datos de captura.
2. **Given** una nueva configuración para otro deporte, **When** se registra una cancha o campo, **Then** comparte la gestión común del club sin mezclar reglas o análisis específicos.

## Experience Requirements *(cross-cutting)*

La plataforma debe ofrecer una experiencia visual premium y coherente en todos sus
productos: panel del dueño, flujo QR del jugador, página de highlights, estados de
procesamiento, configuración, notificaciones y errores.

- **UX-001**: Every frontend surface MUST use the CourtVision design system defined in `design-system.md` for colors, typography, spacing, elevation, borders, focus states, and motion.
- **UX-002**: The owner experience MUST use a distinctive sports-media composition centered on current courts, camera health, and highlights instead of a generic SaaS dashboard of uniform cards.
- **UX-003**: The player QR flow MUST be mobile-first, visually branded, and limited to one primary action per screen with clear progress and recovery states.
- **UX-004**: Shared components MUST define default, hover, focus, pressed, disabled, loading, success, warning, error, and empty states where applicable.
- **UX-005**: Motion MUST communicate state, hierarchy, or sport energy without delaying tasks; every animation MUST have a reduced-motion behavior.
- **UX-006**: The frontend MUST meet WCAG 2.2 AA contrast, keyboard, focus, responsive, and accessible-name expectations.
- **UX-007**: Visual regression coverage MUST include owner desktop, owner mobile, player mobile, QR success/error/loading, media processing, and camera-offline states.
- **UX-008**: Feature modules MUST NOT introduce one-off colors, typography, radii, shadows, or motion curves outside the shared design-system tokens.

### Edge Cases

- Si el jugador escanea un QR de una cancha desactivada o inexistente, el sistema debe impedir el inicio y orientar hacia el personal del club.
- Si no hay conexión durante el registro, el sistema debe informar que la sesión no quedó confirmada y no prometer la entrega del video.
- Si la cámara se desconecta durante el partido, el dueño debe ver el incidente y el jugador debe recibir una notificación clara sobre la disponibilidad parcial del contenido.
- Si el gesto ocurre cuando todavía no existen 30 segundos de grabación, el sistema debe guardar únicamente el tiempo disponible e indicarlo.
- Si un jugador abandona la sesión o proporciona un número incorrecto, el dueño debe poder corregir la asociación sin modificar el video histórico.
- Si dos personas intentan iniciar simultáneamente la misma cancha, solo debe existir una sesión activa para ese horario, salvo que un administrador autorice otra.
- Si un jugador solicita eliminar su contenido, el sistema debe aplicar la política de privacidad y conservar únicamente los registros necesarios para auditoría o facturación.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST allow an owner to create an account and manage one or more clubs.
- **FR-001a**: The owner console MUST expose a single owner account type. Staff invitations, delegated users, and role selection are outside the product scope.
- **FR-002**: The system MUST isolate each club's players, sessions, cameras, recordings, highlights, and settings from other owners and clubs.
- **FR-003**: The system MUST allow an authorized administrator to create, activate, deactivate, and edit venues, fields, cameras, and sport assignments.
- **FR-004**: The system MUST provide a QR identifier for each active field that opens the correct club and field context.
- **FR-005**: The system MUST allow a player to start or join a session by providing a name, a mobile number, and consent to the recording and delivery flow.
- **FR-006**: The system MUST associate each session with a club, field, sport, camera, start time, active status, and registered players.
- **FR-007**: The system MUST prevent duplicate active sessions for the same field and time window unless an authorized administrator overrides the conflict.
- **FR-008**: The system MUST continuously capture the active session while the configured camera is available.
- **FR-009**: The system MUST support a configured gesture or equivalent visual event as a highlight trigger.
- **FR-010**: The system MUST provide a manual or physical fallback trigger for cases where the gesture cannot be detected or used.
- **FR-011**: The system MUST preserve the 30 seconds preceding a confirmed trigger as a separate highlight, or the full available duration when the session is shorter than 30 seconds.
- **FR-012**: The system MUST associate every highlight with its source recording, session, trigger time, initiating player when known, and processing status.
- **FR-013**: The system MUST preserve multiple confirmed highlights from the same session without silent overwrites.
- **FR-014**: The system MUST provide a private player page containing the session's processed highlights and the full recording when that recording is available and permitted.
- **FR-015**: The system MUST send the player a private highlight link through WhatsApp after successful processing when the player has provided a valid number and consented to messaging.
- **FR-016**: The system MUST communicate delivery, processing, camera, and recording failures to the appropriate player or owner and support safe retry behavior.
- **FR-017**: The system MUST allow owners to search and filter their media library by club, field, sport, date, session, player, and processing status when those values exist.
- **FR-018**: The system MUST allow owners to inspect the players, recordings, highlights, delivery history, and failure states associated with a session.
- **FR-019**: The system MUST support access expiration or revocation for player-facing media links.
- **FR-020**: The system MUST record consent and privacy-relevant actions associated with recording and delivery.
- **FR-021**: The system MUST retain historical sessions with their original club, field, camera, sport, and media associations after configuration changes.
- **FR-022**: The system MUST represent sport-specific capture and analysis capabilities separately from the common club, player, session, media, and delivery capabilities.
- **FR-023**: The system MUST make data retention and deletion behavior visible to owners and players according to the configured policy.
- **FR-024**: The frontend MUST expose a reusable CourtVision design-system package for all application surfaces.
- **FR-025**: The frontend MUST provide shared components for navigation, buttons, forms, dialogs, toasts, alerts, tables, filters, media cards, video playback, QR onboarding, and empty/loading/error states.
- **FR-026**: The frontend MUST provide design tokens for color, typography, spacing, radius, elevation, borders, z-index, and motion timing.
- **FR-027**: The frontend MUST support dark-first owner and media surfaces plus high-contrast player and QR surfaces using the same brand tokens.
- **FR-028**: The frontend MUST provide responsive layouts for 320px mobile width through large desktop screens without horizontal scrolling in player flows.
- **FR-029**: The frontend MUST expose keyboard-visible focus, accessible names, and reduced-motion behavior for every shared interactive component.
- **FR-030**: The owner dashboard MUST prioritize media and court operations visually, with camera health and current highlights surfaced before secondary administrative data.
- **FR-031**: The frontend MUST include visual regression checks for the shared component states and the critical player and owner journeys.
- **FR-032**: The frontend MUST keep decorative motion and texture subordinate to video controls, readable text, and primary actions.

### Key Entities

- **Owner Account**: A person or organization authorized to manage clubs, resources, media, settings, and billing scope.
- **Club**: A sports business managed by an owner and containing one or more venues or fields.
- **Venue**: A physical location belonging to a club.
- **Field**: A padel court, football field, or other sports playing area with a sport assignment and QR identifier.
- **Camera**: A capture source associated with a field and its operational status.
- **Player**: A participant identified by name and mobile number, with consent and access relationships.
- **Session**: A time-bounded sports activity connecting players, a field, a camera, and recordings.
- **Recording**: The source video captured for a session, including availability and processing state.
- **Highlight**: A time-bounded clip derived from a recording and initiated by a gesture, fallback action, or future automatic event.
- **Delivery**: A record of a player-facing link or message, its recipient, channel, status, retry history, expiration, and privacy state.
- **Sport Capability**: The rules and detection options that vary by sport while using the platform's common entities.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new player can scan the QR, register, and confirm a session in under 2 minutes without staff assistance.
- **SC-002**: At least 95% of valid session registrations associate the player, club, field, sport, and camera correctly on the first attempt.
- **SC-003**: At least 95% of confirmed highlight triggers produce a playable clip containing the intended 30-second preceding window when sufficient source video exists.
- **SC-004**: At least 90% of successfully processed highlights reach the consenting player's WhatsApp destination within 2 minutes of processing completion.
- **SC-005**: An owner can locate a specific session from the media library in under 30 seconds using at most three filters.
- **SC-006**: In acceptance testing, no owner can view another owner's club, player, session, or media through normal account actions.
- **SC-007**: At least 90% of pilot players can access a highlight from the received link without staff assistance.
- **SC-008**: A pilot club can operate at least four configured fields with no manual intervention required for ordinary QR registration and highlight delivery.
- **SC-009**: Every confirmed highlight is either delivered, visibly pending, or visibly failed with a retry path; none remains silently lost.
- **SC-010**: Adding a second sport in a test environment does not require changing the account, club, media library, permissions, or delivery user journeys.
- **SC-011**: 100% of production frontend routes use shared design-system tokens and components for interactive controls and status messaging.
- **SC-012**: At least 90% of pilot users rate the interface as professional or very professional in a post-use survey.
- **SC-013**: 95% of primary player and owner tasks remain completable with reduced motion enabled and keyboard navigation where applicable.
- **SC-014**: Visual regression checks cover all critical states without unintended layout, color, typography, or motion regressions before release.

## Assumptions

- The initial release targets pádel clubs and fixed cameras covering the playing area; football and other sports are expansion scopes, not initial analysis requirements.
- A player can access a modern mobile browser and receive WhatsApp messages, while the club provides the camera, network connectivity, and power.
- One registered player can act as the responsible contact for a session; additional players may be associated later when the product supports that flow.
- The default highlight window is the 30 seconds before the trigger, with no post-trigger duration in the initial scope.
- The initial experience offers a gesture trigger and a manual or physical fallback; fully automatic detection of sports events is deferred.
- The platform sends links rather than large video attachments through WhatsApp so the player can access media without exceeding message limits.
- The club controls the retention policy within platform limits, while privacy and deletion behavior must be disclosed and auditable.
- Billing, advanced sports analytics, livestreaming, score tracking, and native mobile applications are outside this baseline feature unless a later specification adds them.
- The initial visual direction is Court After Dark: graphite/ink surfaces, court green, clay, chalk, editorial display typography, and restrained kinetic motion as defined in `design-system.md`.
- Visual quality is treated as a product requirement and release gate, not as a later branding pass.
# Feature Specification: Sports Capture Platform

## Recording session vertical slice

### User scenarios

1. When the first player scans a field QR, registers, and accepts recording
   consent, the platform creates one active field session. The linked edge agent
   starts capture automatically without an owner action.
2. An owner can start a session from the field detail when no session is active,
   including before any player registers. A later QR registration joins that same
   session instead of creating another one.
3. An owner can stop the active session. The edge agent stops capture, finalizes
   the local source, and uploads the full match when full-match retention is
   enabled for the field.
4. During every active session the edge agent keeps short local segments so a
   gesture, dashboard trigger, or physical button can preserve the previous
   30 seconds even when full-match retention is disabled.

### Acceptance criteria

- A field has at most one active session.
- Owner field responses expose the session identifier, truthful capture state,
  start time, and whether the session was started by a player or owner.
- The edge agent acknowledges the session identifier in its heartbeat and starts
  or stops its recorder when cloud state changes.
- Capture source files are segmented and recoverable after a process failure;
  full recordings are assembled only when requested.
- Owner controls use the shared design system, include pending and error states,
  and distinguish “starting”, “recording”, “stopping”, and “idle”.
- QR registration, owner start/stop, edge synchronization, and segment finalizing
  have automated tests.
