import { Icon, StatusPill } from '@courtvision/design-system';
import type { CaptureState } from '@courtvision/design-system';
import type { OwnerDashboard } from '../lib/api';

type Moment = OwnerDashboard['recent_highlights'][number];

const MOMENT_STATE: Record<string, { state: CaptureState; label: string }> = {
  available: { state: 'live', label: 'Listo' },
  processing: { state: 'ready', label: 'Procesando' },
  failed: { state: 'offline', label: 'Falló' },
};

/**
 * Momentos capturados, como lista de registros.
 *
 * No se dibuja una miniatura: la API no entrega imagen de portada, y fabricar
 * una ilustración de cancha haría pasar por contenido algo que no existe. La
 * hora, la cancha y el estado de procesamiento son los datos reales y son los
 * que el operador necesita para saber si el clip ya se puede enviar.
 */
export function MomentList({ moments }: { moments: Moment[] }) {
  return (
    <ul className="moment-list">
      {moments.map((moment) => {
        const status = MOMENT_STATE[moment.status] ?? { state: 'idle' as CaptureState, label: moment.status };
        return (
          <li key={moment.id} className="moment-row">
            <span className="moment-row__time t-meta">{moment.occurred_at}</span>
            <span className={`moment-row__mark moment-row__mark--${status.state}`} aria-hidden="true">
              <Icon name={moment.status === 'available' ? 'check' : moment.status === 'failed' ? 'warning' : 'clip'} size={12} />
            </span>
            <span className="moment-row__body">
              <b>{moment.title}</b>
              <span className="t-meta">{moment.field_name} <i aria-hidden="true">·</i> {moment.id}</span>
            </span>
            <StatusPill state={status.state} pulse={false}>{status.label}</StatusPill>
          </li>
        );
      })}
    </ul>
  );
}
