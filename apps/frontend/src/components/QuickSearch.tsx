import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { Icon, StatusPill } from '@courtvision/design-system';
import type { OwnerField } from '../lib/api';
import { courtNumber, courtState, courtStateLabel } from '../lib/court';
import { goToCourt } from '../app/routes';

/**
 * Búsqueda rápida de canchas.
 *
 * Busca sobre las canchas ya cargadas —no inventa un índice ni pide un endpoint
 * que la API no tiene— y lleva directo al detalle. Es el atajo que usa el
 * operador cuando ya sabe qué cancha quiere revisar.
 */
export function QuickSearch({ fields }: { fields: OwnerField[] }) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [cursor, setCursor] = useState(0);
  const boxRef = useRef<HTMLDivElement>(null);
  const listId = useId();

  const results = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) return [];
    return fields
      .map((field, index) => ({ field, index }))
      .filter(({ field }) =>
        field.name.toLowerCase().includes(term)
        || (field.camera?.name ?? '').toLowerCase().includes(term)
        || (field.camera?.host ?? '').toLowerCase().includes(term))
      .slice(0, 6);
  }, [fields, query]);

  useEffect(() => { setCursor(0); }, [query]);

  useEffect(() => {
    if (!open) return undefined;
    const onPointer = (event: PointerEvent) => { if (!boxRef.current?.contains(event.target as Node)) setOpen(false); };
    document.addEventListener('pointerdown', onPointer);
    return () => document.removeEventListener('pointerdown', onPointer);
  }, [open]);

  const choose = (fieldId: string) => {
    goToCourt(fieldId);
    setQuery('');
    setOpen(false);
  };

  return (
    <div className="qsearch" ref={boxRef}>
      <div className="qsearch__field">
        <Icon name="search" size={16} />
        <input
          type="search"
          role="combobox"
          value={query}
          placeholder="Buscar cancha o cámara"
          aria-label="Buscar cancha o cámara"
          aria-autocomplete="list"
          aria-expanded={open && results.length > 0}
          aria-controls={listId}
          autoComplete="off"
          onChange={(event) => { setQuery(event.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          onKeyDown={(event) => {
            if (event.key === 'Escape') { setOpen(false); return; }
            if (results.length === 0) return;
            if (event.key === 'ArrowDown') { event.preventDefault(); setCursor((c) => (c + 1) % results.length); }
            if (event.key === 'ArrowUp') { event.preventDefault(); setCursor((c) => (c - 1 + results.length) % results.length); }
            if (event.key === 'Enter') { event.preventDefault(); choose(results[cursor].field.id); }
          }}
        />
        {query ? (
          <button type="button" aria-label="Limpiar búsqueda" onClick={() => { setQuery(''); setOpen(false); }}>
            <Icon name="close" size={14} />
          </button>
        ) : null}
      </div>

      {open && query.trim() ? (
        <div className="qsearch__panel" id={listId} role="listbox" aria-label="Resultados">
          {results.length > 0 ? (
            results.map(({ field, index }, position) => (
              <button
                key={field.id}
                type="button"
                role="option"
                aria-selected={position === cursor}
                className={position === cursor ? 'is-cursor' : ''}
                onMouseEnter={() => setCursor(position)}
                onClick={() => choose(field.id)}
              >
                <span className={`qsearch__chip qsearch__chip--${courtState(field)}`}>{courtNumber(field.name, index)}</span>
                <span className="qsearch__text">
                  <b>{field.name}</b>
                  <small>{field.camera ? field.camera.name : 'Sin cámara asignada'}</small>
                </span>
                <StatusPill state={courtState(field)} pulse={false}>{courtStateLabel(field)}</StatusPill>
              </button>
            ))
          ) : (
            <p className="qsearch__empty">Ninguna cancha coincide con “{query.trim()}”.</p>
          )}
        </div>
      ) : null}
    </div>
  );
}
