import { useMemo, useState } from 'react';
import { Button, EmptyState, Segmented, SelectField, TextField } from '@courtvision/design-system';
import { ActivityTimeline } from '../../components/ActivityTimeline';
import type { OwnerConsole } from '../../app/useOwnerConsole';

type ActivityFilter = 'all' | 'recording' | 'highlight' | 'delivery' | 'errors';

export function ActivityPage({ console: data }: { console: OwnerConsole }) {
  const [filter, setFilter] = useState<ActivityFilter>('all');
  const [date, setDate] = useState('');
  const [fieldId, setFieldId] = useState('');
  const counts = useMemo(() => ({
    recording: data.activity.filter((item) => item.kind === 'recording').length,
    highlight: data.activity.filter((item) => item.kind === 'highlight').length,
    delivery: data.activity.filter((item) => item.kind === 'delivery').length,
    errors: data.activity.filter((item) => item.status === 'error').length,
  }), [data.activity]);
  const visible = useMemo(() => data.activity.filter((item) => {
    const matchesKind = filter === 'all' || (filter === 'errors' ? item.status === 'error' : item.kind === filter);
    const matchesDate = !date || item.occurred_at.slice(0, 10) === date;
    return matchesKind && matchesDate && (!fieldId || item.field_id === fieldId);
  }), [data.activity, date, fieldId, filter]);
  const hasFilters = filter !== 'all' || Boolean(date) || Boolean(fieldId);
  const clearFilters = () => { setFilter('all'); setDate(''); setFieldId(''); };

  return (
    <div className="page page-enter activity-page">
      {data.activity.length > 0 ? (
        <>
          <header className="activity-page__bar">
          <div>
              <h2 className="t-heading">Actividad</h2>
              <span className="t-meta">{data.activity.length} {data.activity.length === 1 ? 'evento registrado' : 'eventos registrados'}</span>
          </div>
            <Segmented
              value={filter}
              onChange={setFilter}
              ariaLabel="Filtrar actividad"
              options={[
                { value: 'all', label: 'Todo', count: data.activity.length },
                { value: 'recording', label: 'Partidos', count: counts.recording },
                { value: 'highlight', label: 'Highlights', count: counts.highlight },
                { value: 'delivery', label: 'Envíos', count: counts.delivery },
                { value: 'errors', label: 'Fallos', count: counts.errors },
              ]}
            />
          </header>

          <div className="activity-page__filters">
            <TextField label="Fecha" type="date" value={date} onChange={(event) => setDate(event.target.value)} />
            <SelectField label="Cancha" value={fieldId} onChange={(event) => setFieldId(event.target.value)}>
              <option value="">Todas las canchas</option>
              {data.fields.map((field) => <option key={field.id} value={field.id}>{field.name}</option>)}
            </SelectField>
            <div className="activity-page__result">
              <span className="t-meta">{visible.length} de {data.activity.length}</span>
              {hasFilters ? <Button variant="ghost" size="sm" onClick={clearFilters}>Limpiar filtros</Button> : null}
            </div>
          </div>

          {visible.length > 0 ? (
            <section className="activity-page__stream" aria-label="Historial operativo">
              <ActivityTimeline items={visible} />
            </section>
          ) : (
            <EmptyState icon="search" title="No hay actividad para estos filtros" compact action={<Button variant="secondary" size="sm" onClick={clearFilters}>Limpiar filtros</Button>} />
          )}
        </>
      ) : (
        <section className="activity-page__empty">
          <EmptyState icon="bell" accent="ice" title="Todavía no hay actividad">
            Los partidos, highlights, envíos y estados de cámara aparecerán cuando sucedan.
          </EmptyState>
        </section>
      )}
    </div>
  );
}
