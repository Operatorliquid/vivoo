import { Banner, Button, EmptyState, Icon, Meter } from '@courtvision/design-system';
import { StatCard } from '../../components/StatCard';
import { CourtRow, CourtRowSkeleton } from '../../components/CourtRow';
import { MomentList } from '../../components/MomentList';
import { ActivityTimeline } from '../../components/ActivityTimeline';
import { countByState, courtState, courtStateReason } from '../../lib/court';
import { goToCourt, goToSection } from '../../app/routes';
import type { OwnerConsole } from '../../app/useOwnerConsole';

/**
 * Operación — la pantalla que el club abre veinte veces por día.
 *
 * Orden de lectura: indicadores, qué cancha falla y por qué, el estado de cada
 * cancha, y por último lo capturado. Todo lo que se muestra sale de la API:
 * no hay series inventadas ni comparaciones contra períodos inexistentes.
 */
export function OverviewPage({ console: data }: { console: OwnerConsole }) {
  const { fields, dashboard, activity, loading, loadError } = data;
  const counts = countByState(fields);
  const needsAttention = fields.filter((field) => courtState(field) === 'offline');
  const moments = dashboard?.recent_highlights ?? [];
  const metrics = dashboard?.metrics;
  const active = Number(metrics?.active_sessions ?? 0);
  const capacity = Number(metrics?.capacity ?? fields.length);

  return (
    <div className="page page-enter">
      {loadError ? (
        <Banner
          tone="error"
          title="No pudimos sincronizar el club"
          action={<Button size="sm" variant="secondary" iconBefore="refresh" onClick={() => void data.retry()}>Reintentar</Button>}
        >
          {loadError}
        </Banner>
      ) : null}

      <section className="stat-grid" aria-label="Indicadores del club">
        <StatCard
          label="Canchas capturando"
          icon="camera"
          tone="brand"
          loading={loading}
          value={<>{counts.live}<em>/{fields.length}</em></>}
          footer={
            <span className="stat__breakdown">
              {counts.ready > 0 ? <i className="is-ready">{counts.ready} {counts.ready === 1 ? 'lista' : 'listas'}</i> : null}
              {counts.offline > 0 ? <i className="is-offline">{counts.offline} sin señal</i> : null}
              {counts.idle > 0 ? <i className="is-idle">{counts.idle} fuera de servicio</i> : null}
              {counts.ready + counts.offline + counts.idle === 0 ? <i className="is-live">Todas operativas</i> : null}
            </span>
          }
        />
        <StatCard
          label="Partidos en juego"
          icon="qr"
          loading={loading}
          value={active}
          footer={
            <Meter
              value={active}
              max={capacity}
              label={`${active} de ${capacity} canchas ocupadas`}
              summary={capacity - active >= 0 ? `${capacity - active} libres` : undefined}
            />
          }
        />
        <StatCard
          label="Momentos capturados"
          icon="clip"
          loading={loading}
          value={metrics?.highlights ?? 0}
          footer={<span className="stat__note">{moments.length > 0 ? `Último a las ${moments[0].occurred_at}` : 'Todavía sin clips en la biblioteca'}</span>}
        />
        <StatCard
          label="Jugadores registrados"
          icon="user"
          loading={loading}
          value={metrics?.players ?? 0}
          footer={<span className="stat__note">{metrics?.delivery_rate === '—' ? 'Sin envíos de WhatsApp aún' : `Entregas: ${metrics?.delivery_rate}`}</span>}
        />
      </section>

      {!loading && needsAttention.length > 0 ? (
        <section className="alerts" aria-label="Canchas que necesitan atención">
          {needsAttention.map((field) => (
            <article key={field.id}>
              <span className="alerts__mark" aria-hidden="true"><Icon name="warning" size={16} /></span>
              <div>
                <b>{field.name}</b>
                <p>{courtStateReason(field)}</p>
              </div>
              <Button size="sm" variant="secondary" iconAfter="arrowRight" onClick={() => goToCourt(field.id)}>Revisar</Button>
            </article>
          ))}
        </section>
      ) : null}

      <section className="card" aria-labelledby="ov-courts">
        <header className="card__head">
          <div>
            <h2 className="t-heading" id="ov-courts">Canchas</h2>
            <p>Estado de captura en vivo</p>
          </div>
          <Button size="sm" variant="ghost" iconAfter="arrowRight" onClick={() => goToSection('courts')}>Administrar</Button>
        </header>

        {loading ? (
          <ul className="row-list">{[0, 1, 2].map((key) => <CourtRowSkeleton key={key} density="compact" />)}</ul>
        ) : fields.length > 0 ? (
          <ul className="row-list">
            {fields.map((field, index) => <CourtRow key={field.id} field={field} index={index} density="compact" />)}
          </ul>
        ) : (
          <div className="card__pad">
            <EmptyState
              icon="camera"
              accent="volt"
              title="Todavía no hay canchas"
              action={<Button variant="primary" size="sm" iconBefore="plus" onClick={() => goToSection('courts')}>Crear la primera cancha</Button>}
            >
              Una cancha reúne una cámara, el QR que escanean los jugadores y, si lo usás, el botón físico de highlights.
            </EmptyState>
          </div>
        )}
      </section>

      <div className="split split--even">
        <section className="card" aria-labelledby="ov-moments">
          <header className="card__head">
            <div>
              <h2 className="t-heading" id="ov-moments">Momentos recientes</h2>
              <p>Clips guardados en las canchas</p>
            </div>
            {moments.length > 0 ? <Button size="sm" variant="ghost" iconAfter="arrowRight" onClick={() => goToSection('library')}>Biblioteca</Button> : null}
          </header>
          {moments.length > 0 ? (
            <MomentList moments={moments.slice(0, 4)} />
          ) : (
            <div className="card__pad">
              <EmptyState icon="gesture" accent="flare" title="Sin momentos todavía" compact>
                Se genera uno cuando un jugador levanta los brazos frente a la cámara o presiona el botón de la cancha:
                se guardan los 30 segundos anteriores.
              </EmptyState>
            </div>
          )}
        </section>

        <section className="card" aria-labelledby="ov-activity">
          <header className="card__head">
            <div>
              <h2 className="t-heading" id="ov-activity">Actividad</h2>
              <p>Cámaras, partidos y procesamiento</p>
            </div>
            {activity.length > 0 ? <Button size="sm" variant="ghost" iconAfter="arrowRight" onClick={() => goToSection('activity')}>Ver todo</Button> : null}
          </header>
          {activity.length > 0 ? (
            <ActivityTimeline items={activity.slice(0, 4)} compact />
          ) : (
            <div className="card__pad">
              <EmptyState icon="bell" accent="ice" title="Sin novedades" compact>
                Los partidos, highlights, envíos y estados de cámara aparecerán cuando sucedan.
              </EmptyState>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
