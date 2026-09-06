import type { CaptureState } from '@courtvision/design-system';
import { countByState } from '../lib/court';
import type { OwnerField } from '../lib/api';

const ORDER: Array<{ state: CaptureState; label: string }> = [
  { state: 'live', label: 'Capturando' },
  { state: 'ready', label: 'Listas' },
  { state: 'offline', label: 'Sin señal' },
  { state: 'idle', label: 'Fuera de servicio' },
];

const RADIUS = 62;
const STROKE = 18;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

/**
 * Reparto de canchas por estado de captura.
 *
 * Es la única gráfica de la consola porque es la única que se puede construir
 * con datos reales: la API no entrega series temporales, y dibujar una curva
 * inventada sería peor que no dibujar nada.
 */
export function CourtStateDonut({ fields }: { fields: OwnerField[] }) {
  const counts = countByState(fields);
  const total = fields.length || 1;
  let offset = 0;

  const segments = ORDER.map(({ state, label }) => {
    const value = counts[state];
    const length = (value / total) * CIRCUMFERENCE;
    const segment = { state, label, value, length, offset };
    offset += length;
    return segment;
  }).filter((segment) => segment.value > 0);

  return (
    <div className="donut">
      <div className="donut__chart">
        <svg viewBox="0 0 160 160" role="img" aria-label={`${counts.live} de ${fields.length} canchas capturando`}>
          <circle cx="80" cy="80" r={RADIUS} fill="none" stroke="var(--surface-3)" strokeWidth={STROKE} />
          {segments.map((segment) => (
            <circle
              key={segment.state}
              className={`donut__seg donut__seg--${segment.state}`}
              cx="80"
              cy="80"
              r={RADIUS}
              fill="none"
              strokeWidth={STROKE}
              strokeLinecap="round"
              strokeDasharray={`${Math.max(segment.length - 6, 1)} ${CIRCUMFERENCE}`}
              strokeDashoffset={-segment.offset}
              transform="rotate(-90 80 80)"
            />
          ))}
        </svg>
        <div className="donut__center">
          <b className="t-figure">{counts.live}</b>
          <span>de {fields.length}</span>
        </div>
      </div>

      <ul className="donut__legend">
        {ORDER.map(({ state, label }) => (
          <li key={state} className={counts[state] === 0 ? 'is-empty' : ''}>
            <i className={`donut__key donut__key--${state}`} aria-hidden="true" />
            <span>{label}</span>
            <b>{counts[state]}</b>
          </li>
        ))}
      </ul>
    </div>
  );
}
