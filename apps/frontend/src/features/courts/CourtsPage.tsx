import { useMemo, useState } from 'react';
import { Banner, Button, EmptyState, Segmented } from '@courtvision/design-system';
import type { CaptureState } from '@courtvision/design-system';
import { CourtRow, CourtRowSkeleton } from '../../components/CourtRow';
import { NewCourtDialog } from './NewCourtDialog';
import { countByState, courtState } from '../../lib/court';
import { publicAppOrigin } from '../../lib/api';
import type { OwnerConsole } from '../../app/useOwnerConsole';
import type { OwnerField } from '../../lib/api';

type Filter = 'all' | CaptureState;

/**
 * Canchas — inventario operativo.
 *
 * Antes cada cancha era una card con su formulario de nombre siempre abierto:
 * imposible de comparar y sin escala. Ahora es un listado en columnas, y la
 * edición vive en el detalle de cada cancha, donde hay contexto para decidir.
 */
export function CourtsPage({ console: data }: { console: OwnerConsole }) {
  const { fields, loading, loadError } = data;
  const [filter, setFilter] = useState<Filter>('all');
  const [createOpen, setCreateOpen] = useState(false);
  const counts = countByState(fields);

  const visible = useMemo(
    () => (filter === 'all' ? fields : fields.filter((field) => courtState(field) === filter)),
    [fields, filter],
  );

  const copyQr = async (field: OwnerField) => {
    try {
      await navigator.clipboard?.writeText(`${await publicAppOrigin()}${field.qr_url}`);
      data.announce('success', `Enlace QR de ${field.name} copiado.`);
    } catch {
      data.announce('error', 'El navegador bloqueó el acceso al portapapeles.');
    }
  };

  // Los estados con cero canchas se muestran igual —"sin señal 0" es información
  // que tranquiliza— pero no se pueden elegir para no llevar a una lista vacía.
  const options = [
    { value: 'all' as Filter, label: 'Todas', count: fields.length },
    { value: 'live' as Filter, label: 'Capturando', count: counts.live, disabled: counts.live === 0 },
    { value: 'ready' as Filter, label: 'Listas', count: counts.ready, disabled: counts.ready === 0 },
    { value: 'offline' as Filter, label: 'Sin señal', count: counts.offline, disabled: counts.offline === 0 },
    ...(counts.idle > 0 ? [{ value: 'idle' as Filter, label: 'Fuera de servicio', count: counts.idle }] : []),
  ];

  return (
    <div className="page page-enter">
      {loadError ? (
        <Banner tone="error" title="No pudimos leer las canchas" action={<Button size="sm" variant="secondary" iconBefore="refresh" onClick={() => void data.retry()}>Reintentar</Button>}>
          {loadError}
        </Banner>
      ) : null}

      <section className="card" aria-labelledby="courts-list">
        <header className="card__head">
          <div>
            <h2 className="t-heading" id="courts-list">Inventario</h2>
            <p>{fields.length} {fields.length === 1 ? 'cancha' : 'canchas'} · {data.cameras.length} {data.cameras.length === 1 ? 'cámara' : 'cámaras'}</p>
          </div>
          <div className="card__tools">
            <Segmented value={filter} options={options} onChange={setFilter} ariaLabel="Filtrar canchas por estado" />
            <Button variant="primary" iconBefore="plus" onClick={() => setCreateOpen(true)}>Nueva cancha</Button>
          </div>
        </header>

        <div className="row-legend" aria-hidden="true">
          <span>Cancha</span>
          <span>Estado</span>
          <span>Cámara</span>
          <span>Captura</span>
        </div>

        {loading ? (
          <ul className="row-list">{[0, 1, 2, 3].map((key) => <CourtRowSkeleton key={key} />)}</ul>
        ) : visible.length > 0 ? (
          <ul className="row-list">
            {visible.map((field) => (
              <CourtRow key={field.id} field={field} index={fields.indexOf(field)} onCopyQr={(target) => void copyQr(target)} />
            ))}
          </ul>
        ) : fields.length > 0 ? (
          <div className="card__pad">
            <EmptyState icon="search" title="Ninguna cancha en este estado" compact action={<Button size="sm" variant="secondary" onClick={() => setFilter('all')}>Ver todas</Button>}>
              Probá con otro filtro para ver el resto del club.
            </EmptyState>
          </div>
        ) : (
          <div className="card__pad">
            <EmptyState
              icon="camera"
              accent="volt"
              title="Todavía no hay canchas"
              action={<Button variant="primary" size="sm" iconBefore="plus" onClick={() => setCreateOpen(true)}>Crear la primera cancha</Button>}
            >
              Cada cancha reúne una cámara, el QR que escanean los jugadores y, opcionalmente, el botón físico
              para guardar momentos.
            </EmptyState>
          </div>
        )}
      </section>

      <NewCourtDialog open={createOpen} onClose={() => setCreateOpen(false)} onCreate={data.actions.createField} />
    </div>
  );
}
