import { Icon, StatusPill } from '@courtvision/design-system';
import type { CaptureState } from '@courtvision/design-system';
import type { OwnerActivity } from '../lib/api';
import { pushPath } from '../app/routes';

const ICON: Record<OwnerActivity['kind'], string> = {
  recording: 'record',
  highlight: 'clip',
  delivery: 'whatsapp',
  camera: 'camera',
  player: 'user',
};

const STATUS: Record<OwnerActivity['status'], { state: CaptureState; label: string }> = {
  success: { state: 'live', label: 'Correcto' },
  info: { state: 'idle', label: 'Registrado' },
  warning: { state: 'ready', label: 'Atención' },
  error: { state: 'offline', label: 'Falló' },
};

const time = new Intl.DateTimeFormat('es-AR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
const date = new Intl.DateTimeFormat('es-AR', { weekday: 'short', day: '2-digit', month: 'short' });

const targetLabel = (item: OwnerActivity) => {
  if (item.kind === 'highlight' || item.kind === 'delivery') return 'Ver highlight';
  if (item.kind === 'camera') return 'Ver cámara';
  return 'Ver cancha';
};

export function ActivityTimeline({ items, compact = false }: { items: OwnerActivity[]; compact?: boolean }) {
  return (
    <ol className={`activity-timeline ${compact ? 'activity-timeline--compact' : ''}`}>
      {items.map((item) => {
        const status = STATUS[item.status];
        const occurredAt = new Date(item.occurred_at);
        return (
          <li key={item.id} className={`activity-event activity-event--${item.status}`}>
            <span className="activity-event__rail" aria-hidden="true">
              <i><Icon name={ICON[item.kind]} size={16} /></i>
            </span>
            <div className="activity-event__content">
              <div className="activity-event__heading">
                <div>
                  <strong>{item.title}</strong>
                  <p>{item.detail}</p>
                </div>
                {!compact ? <StatusPill state={status.state} pulse={false}>{status.label}</StatusPill> : null}
              </div>
              <div className="activity-event__meta">
                <time dateTime={item.occurred_at}>{date.format(occurredAt)} · {time.format(occurredAt)}</time>
                {item.href ? (
                  <button type="button" onClick={() => pushPath(item.href!)}>
                    {targetLabel(item)}<Icon name="arrowRight" size={13} />
                  </button>
                ) : null}
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
