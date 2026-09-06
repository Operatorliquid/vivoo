import { Icon, Skeleton, StatusPill } from '@courtvision/design-system';
import type { OwnerField } from '../lib/api';
import { cameraEndpoint, courtNumber, courtState, courtStateLabel, detectionLabel, sportLabel } from '../lib/court';
import { goToCourt } from '../app/routes';

/**
 * Fila de cancha.
 *
 * Es una fila y no una tarjeta porque el operador compara canchas entre sí, y
 * comparar exige columnas alineadas. La ficha numerada toma el color del estado
 * de captura para que la grilla se lea de un vistazo.
 */
export function CourtRow({
  field,
  index,
  density = 'comfortable',
  onCopyQr,
}: { field: OwnerField; index: number; density?: 'compact' | 'comfortable'; onCopyQr?: (field: OwnerField) => void }) {
  const state = courtState(field);
  const endpoint = cameraEndpoint(field.camera);

  return (
    <li className={`row row--${state} row--${density}`}>
      <span className="row__chip" aria-hidden="true">{courtNumber(field.name, index)}</span>

      <span className="row__identity">
        <a className="row__link" href={`/fields/${field.id}`} onClick={(event) => { event.preventDefault(); goToCourt(field.id); }}>
          {field.name}
        </a>
        <span className="row__sub">{sportLabel(field.sport_code)} · {field.last_seen}</span>
      </span>

      <span className="row__state">
        <StatusPill state={state}>{courtStateLabel(field)}</StatusPill>
      </span>

      <span className="row__camera">
        {field.camera ? (
          <>
            <b className="t-truncate">{field.camera.name}</b>
            <span className="row__sub t-truncate">{endpoint ?? 'Sin origen RTSP'}</span>
          </>
        ) : (
          <span className="row__missing">Sin cámara asignada</span>
        )}
      </span>

      <span className="row__config">
        <b className="is-on">Grabación automática</b>
        <span className="row__sub">{detectionLabel(field.detection_mode)}</span>
      </span>

      <span className="row__actions">
        {onCopyQr ? (
          <button type="button" className="row__action" onClick={() => onCopyQr(field)} aria-label={`Copiar enlace QR de ${field.name}`}>
            <Icon name="qr" size={16} />
          </button>
        ) : null}
        <span className="row__chevron" aria-hidden="true"><Icon name="chevronRight" size={16} /></span>
      </span>
    </li>
  );
}

export function CourtRowSkeleton({ density = 'comfortable' }: { density?: 'compact' | 'comfortable' }) {
  return (
    <li className={`row row--skeleton row--${density}`} aria-hidden="true">
      <span className="row__chip"><Skeleton w={20} h={12} /></span>
      <span className="row__identity">
        <Skeleton w="60%" h={14} />
        <Skeleton className="row__skeleton-sub" w="38%" h={10} />
      </span>
      <span className="row__state"><Skeleton className="cv-skeleton--pill" w={96} h={24} /></span>
      <span className="row__camera"><Skeleton w="70%" h={12} /></span>
      <span className="row__config"><Skeleton w="54%" h={12} /></span>
      <span className="row__actions" />
    </li>
  );
}
