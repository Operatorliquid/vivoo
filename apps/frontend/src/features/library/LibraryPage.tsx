import { useEffect, useMemo, useState } from 'react';
import { Button, Dialog, EmptyState, Icon, MenuItem, OverflowMenu, Segmented, StatusPill, TextField } from '@courtvision/design-system';
import type { CaptureState } from '@courtvision/design-system';
import type { OwnerConsole } from '../../app/useOwnerConsole';
import { goToSection } from '../../app/routes';
import { publicMediaUrl } from '../../lib/api';
import type { OwnerHighlight, OwnerLibraryRecording } from '../../lib/api';

type Filter = 'all' | 'recording' | 'highlight';
type LibraryItem = (OwnerHighlight & { kind: 'highlight' }) | (OwnerLibraryRecording & { kind: 'recording' });

const STATUS: Record<LibraryItem['status'], { state: CaptureState; label: string }> = {
  available: { state: 'live', label: 'Listo' },
  processing: { state: 'ready', label: 'Procesando' },
  failed: { state: 'offline', label: 'Falló' },
};

const momentDate = new Intl.DateTimeFormat('es-AR', {
  day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', second: '2-digit',
});

const matchDate = new Intl.DateTimeFormat('es-AR', {
  day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
});

const playersLabel = (players: string[]) => players.length > 0 ? players.join(', ') : 'Sin jugadores asociados';
const durationLabel = (seconds: number) => {
  if (seconds < 60) return `${seconds}s`;
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remaining = seconds % 60;
  return hours > 0 ? `${hours}h ${minutes}m` : `${minutes}:${String(remaining).padStart(2, '0')}`;
};
const dateKey = (value: string) => {
  const date = new Date(value);
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${date.getFullYear()}-${month}-${day}`;
};

export function LibraryPage({ console: data }: { console: OwnerConsole }) {
  const [filter, setFilter] = useState<Filter>('all');
  const [date, setDate] = useState('');
  const [player, setPlayer] = useState('');
  const [active, setActive] = useState<LibraryItem | null>(null);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [selecting, setSelecting] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set());
  const [deleteTargets, setDeleteTargets] = useState<LibraryItem[]>([]);
  const [deleting, setDeleting] = useState(false);
  const moments = useMemo<LibraryItem[]>(() => [
    ...data.recordings.map((recording) => ({ ...recording, kind: 'recording' as const })),
    ...data.highlights.map((highlight) => ({ ...highlight, kind: 'highlight' as const })),
  ].sort((left, right) => new Date(right.occurred_at).getTime() - new Date(left.occurred_at).getTime()), [data.highlights, data.recordings]);
  useEffect(() => {
    const highlightId = new URLSearchParams(window.location.search).get('highlight');
    const recordingId = new URLSearchParams(window.location.search).get('recording');
    const requested = moments.find((moment) => (
      (highlightId && moment.kind === 'highlight' && moment.id === highlightId)
      || (recordingId && moment.kind === 'recording' && moment.id === recordingId)
    ));
    if (requested) setActive(requested);
  }, [moments]);
  useEffect(() => {
    setSelectedIds((current) => {
      const availableIds = new Set(moments.map((moment) => moment.id));
      const next = new Set([...current].filter((id) => availableIds.has(id)));
      return next.size === current.size ? current : next;
    });
  }, [moments]);
  useEffect(() => {
    if (!selecting) return undefined;
    const closeSelection = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setSelecting(false);
        setSelectedIds(new Set());
      }
    };
    window.addEventListener('keydown', closeSelection);
    return () => window.removeEventListener('keydown', closeSelection);
  }, [selecting]);
  const available = moments.filter((moment) => moment.status === 'available').length;
  const processing = moments.filter((moment) => moment.status === 'processing').length;
  const recordings = moments.filter((moment) => moment.kind === 'recording').length;
  const highlights = moments.filter((moment) => moment.kind === 'highlight').length;
  const visible = useMemo(() => {
    const playerQuery = player.trim().toLocaleLowerCase('es');
    return moments.filter((moment) => (
      (filter === 'all' || moment.kind === filter)
      && (!date || dateKey(moment.occurred_at) === date)
      && (!playerQuery || moment.players.some((name) => name.toLocaleLowerCase('es').includes(playerQuery)))
    ));
  }, [date, filter, moments, player]);
  const hasFilters = filter !== 'all' || Boolean(date) || Boolean(player.trim());
  const selectableVisible = visible.filter((moment) => moment.status !== 'processing');
  const allVisibleSelected = selectableVisible.length > 0 && selectableVisible.every((moment) => selectedIds.has(moment.id));
  const clearFilters = () => { setFilter('all'); setDate(''); setPlayer(''); };
  const leaveSelection = () => {
    setSelecting(false);
    setSelectedIds(new Set());
  };
  const toggleSelection = (highlightId: string) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(highlightId)) next.delete(highlightId); else next.add(highlightId);
      return next;
    });
  };
  const toggleAllVisible = () => {
    setSelectedIds((current) => {
      const next = new Set(current);
      selectableVisible.forEach((moment) => {
        if (allVisibleSelected) next.delete(moment.id); else next.add(moment.id);
      });
      return next;
    });
  };
  const requestDelete = (moment: LibraryItem) => {
    setOpenMenuId(null);
    setActive(null);
    setDeleteTargets([moment]);
  };
  const requestBatchDelete = () => {
    const selected = moments.filter((moment) => selectedIds.has(moment.id));
    if (selected.length > 0) setDeleteTargets(selected);
  };
  const confirmDelete = async () => {
    if (deleteTargets.length === 0) return;
    setDeleting(true);
    const removed = await data.actions.removeLibraryItems(deleteTargets.map((moment) => ({ kind: moment.kind, id: moment.id })));
    setDeleting(false);
    if (removed) {
      setDeleteTargets([]);
      leaveSelection();
    }
  };

  return (
    <div className="page page-enter library">
      {moments.length > 0 ? (
        <>
          <header className="library__bar">
            <div>
              <h2 className="t-heading">Videos</h2>
              <span className="t-meta">
                {recordings} {recordings === 1 ? 'partido' : 'partidos'} · {highlights} highlights
                {processing > 0 ? ` · ${processing} procesando` : ` · ${available} listos`}
              </span>
            </div>
            <div className="library__tools">
              <Button
                variant="secondary"
                size="sm"
                iconBefore={selecting ? 'close' : 'check'}
                aria-pressed={selecting}
                disabled={!selecting && !moments.some((moment) => moment.status !== 'processing')}
                onClick={() => selecting ? leaveSelection() : setSelecting(true)}
              >
                {selecting ? 'Cancelar' : 'Seleccionar'}
              </Button>
              <Segmented
                value={filter}
                onChange={setFilter}
                ariaLabel="Filtrar videos"
                options={[
                  { value: 'all', label: 'Todos', count: moments.length },
                  { value: 'recording', label: 'Partidos', count: recordings, disabled: recordings === 0 },
                  { value: 'highlight', label: 'Highlights', count: highlights, disabled: highlights === 0 },
                ]}
              />
            </div>
          </header>

          <div className="library__filters" aria-label="Filtros de la biblioteca">
            <TextField label="Fecha" type="date" value={date} onChange={(event) => setDate(event.target.value)} />
            <TextField
              label="Jugador"
              value={player}
              onChange={(event) => setPlayer(event.target.value)}
              placeholder="Nombre del jugador"
              suffix={<Icon name="search" size={15} />}
            />
            <div className="library__filter-result">
              <span className="t-meta">{visible.length} de {moments.length}</span>
              {hasFilters ? <Button variant="ghost" size="sm" onClick={clearFilters}>Limpiar filtros</Button> : null}
            </div>
          </div>

          {selecting ? (
            <div className="library-selection">
              <div className={`library-selection__summary ${selectedIds.size > 0 ? 'has-selection' : ''}`} aria-live="polite">
                <span className="library-selection__mark" aria-hidden="true"><Icon name="check" size={15} /></span>
                <strong>{selectedIds.size > 0 ? `${selectedIds.size} ${selectedIds.size === 1 ? 'seleccionado' : 'seleccionados'}` : 'Seleccioná los videos'}</strong>
              </div>
              <div className="library-selection__actions">
                <Button variant="ghost" size="sm" disabled={selectableVisible.length === 0} onClick={toggleAllVisible}>
                  {allVisibleSelected ? 'Quitar visibles' : `Seleccionar visibles (${selectableVisible.length})`}
                </Button>
                <Button variant="danger" size="sm" iconBefore="trash" disabled={selectedIds.size === 0} onClick={requestBatchDelete}>
                  Eliminar{selectedIds.size > 0 ? ` (${selectedIds.size})` : ''}
                </Button>
                <Button
                  className="library-selection__close"
                  variant="ghost"
                  size="sm"
                  iconBefore="close"
                  aria-label="Salir de la selección"
                  title="Salir de la selección"
                  onClick={leaveSelection}
                />
              </div>
            </div>
          ) : null}

          {visible.length > 0 ? (
            <ul className="library-grid">
              {visible.map((moment) => {
                const status = STATUS[moment.status];
                const canPlay = Boolean(moment.media_path && moment.status === 'available');
                const isSelected = selectedIds.has(moment.id);
                const canSelect = moment.status !== 'processing';
                return (
                  <li key={`${moment.kind}-${moment.id}`} className={`library-clip library-clip--${moment.status} library-clip--${moment.kind} ${selecting && canSelect ? 'is-selectable' : ''} ${isSelected ? 'is-selected' : ''}`}>
                    {selecting && canSelect ? (
                      <button
                        type="button"
                        className="library-clip__select"
                        aria-label={`${isSelected ? 'Quitar' : 'Seleccionar'} ${moment.title} de ${moment.field_name}`}
                        aria-pressed={isSelected}
                        onClick={() => toggleSelection(moment.id)}
                      >
                        <span aria-hidden="true"><Icon name="check" size={15} /></span>
                      </button>
                    ) : null}
                    <button
                      type="button"
                      className="library-clip__frame"
                      disabled={!canPlay}
                      onClick={() => setActive(moment)}
                      aria-label={canPlay ? `Reproducir ${moment.title} de ${moment.field_name}` : `${moment.title} ${status.label}`}
                    >
                      {moment.media_path ? (
                        <video
                          muted
                          playsInline
                          preload="metadata"
                          src={publicMediaUrl(moment.media_path)}
                          onLoadedMetadata={(event) => {
                            const video = event.currentTarget;
                            if (Number.isFinite(video.duration) && video.duration > 0) video.currentTime = Math.min(0.5, video.duration / 3);
                          }}
                        />
                      ) : (
                        <span className="library-clip__pending" aria-hidden="true">
                          <Icon name={moment.status === 'failed' ? 'warning' : 'clip'} size={22} />
                        </span>
                      )}
                      <span className="library-clip__index" aria-hidden="true">{moment.kind === 'recording' ? 'PARTIDO' : 'HIGHLIGHT'}</span>
                      <span className="library-clip__duration">{durationLabel(moment.duration_seconds)}</span>
                      {canPlay ? <span className="library-clip__play" aria-hidden="true"><Icon name="play" size={16} /></span> : null}
                    </button>

                    {moment.status !== 'processing' && !selecting ? (
                      <OverflowMenu
                        className="library-clip__overflow"
                        label={`Acciones para el video de ${moment.field_name}`}
                        open={openMenuId === moment.id}
                        onOpenChange={(open) => setOpenMenuId(open ? moment.id : null)}
                      >
                        <MenuItem icon="trash" tone="danger" onClick={() => requestDelete(moment)}>
                          Eliminar video
                        </MenuItem>
                      </OverflowMenu>
                    ) : null}

                    <div className="library-clip__body">
                      <div className="library-clip__title">
                        <div>
                          <b>{moment.kind === 'recording' ? 'Partido completo' : moment.field_name}</b>
                          <span className="t-meta">{momentDate.format(new Date(moment.occurred_at))}</span>
                        </div>
                        <StatusPill state={status.state} pulse={false}>{status.label}</StatusPill>
                      </div>
                      <div className="library-clip__people">
                        <Icon name="user" size={13} />
                        <span>{playersLabel(moment.players)}</span>
                      </div>
                      <div className="library-clip__match t-meta">
                        <span>{moment.kind === 'recording' ? moment.field_name : `Partido ${moment.session_code}`}</span>
                        <span className="library-clip__identity">
                          {moment.kind === 'highlight' && moment.confidence !== null
                            ? <strong>Confianza {Math.round(moment.confidence * 100)} %</strong>
                            : null}
                          <span>{moment.display_id}</span>
                        </span>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          ) : (
            <EmptyState
              icon="clip"
              title="No hay videos para estos filtros"
              compact
              action={<Button variant="secondary" size="sm" onClick={clearFilters}>Limpiar filtros</Button>}
            >
              Cambiá la fecha o el nombre del jugador.
            </EmptyState>
          )}
        </>
      ) : (
        <section className="library-empty">
          <EmptyState
            icon="clip"
            accent="flare"
            title="La biblioteca todavía está vacía"
            action={<Button variant="secondary" size="sm" iconAfter="arrowRight" onClick={() => goToSection('courts')}>Ir a canchas</Button>}
          >
            Iniciá un partido. Cuando termine, el video completo y sus highlights aparecerán acá.
          </EmptyState>
        </section>
      )}

      <Dialog
        open={Boolean(active)}
        onClose={() => setActive(null)}
        title={active ? `${active.field_name} · ${active.title}` : 'Video'}
        description={active ? `${playersLabel(active.players)} · Partido ${active.session_code}` : undefined}
        size="lg"
        footer={active ? (
          <>
            {active.status !== 'processing' ? <Button variant="danger" size="sm" iconBefore="trash" onClick={() => requestDelete(active)}>Eliminar video</Button> : null}
            {active.download_path ? (
              <a className="cv-btn cv-btn--secondary cv-btn--sm library-player__download" href={publicMediaUrl(active.download_path)} download>
                <Icon name="arrowRight" size={14} /><span>Descargar video</span>
              </a>
            ) : null}
          </>
        ) : undefined}
      >
        {active?.media_path ? (
          <div className="library-player">
            <video controls autoPlay playsInline preload="auto" src={publicMediaUrl(active.media_path)} />
            <dl className="library-player__meta">
              <div><dt>{active.kind === 'recording' ? 'Duración' : 'Momento'}</dt><dd>{momentDate.format(new Date(active.occurred_at))} · {durationLabel(active.duration_seconds)}</dd></div>
              <div><dt>Partido</dt><dd>{active.session_code} · {matchDate.format(new Date(active.session_started_at))}</dd></div>
              {active.kind === 'recording' && active.expires_at ? (
                <div><dt>Disponible hasta</dt><dd>{matchDate.format(new Date(active.expires_at))}</dd></div>
              ) : null}
              {active.kind === 'highlight' && active.confidence !== null ? (
                <div><dt>Detección</dt><dd>Confianza {Math.round(active.confidence * 100)} %</dd></div>
              ) : null}
            </dl>
          </div>
        ) : active ? (
          <EmptyState
            icon={active.status === 'failed' ? 'warning' : 'clip'}
            accent={active.status === 'failed' ? 'flare' : 'ice'}
            title={active.status === 'failed' ? 'El highlight no pudo procesarse' : active.kind === 'recording' ? 'El partido se está subiendo' : 'El highlight se está procesando'}
            compact
          />
        ) : null}
      </Dialog>

      <Dialog
        open={deleteTargets.length > 0}
        onClose={() => { if (!deleting) setDeleteTargets([]); }}
        title={deleteTargets.length > 1 ? `Eliminar ${deleteTargets.length} videos` : 'Eliminar video'}
        description={deleteTargets.length > 1
          ? `${deleteTargets.length} videos seleccionados`
          : deleteTargets[0] ? `${deleteTargets[0].field_name} · ${momentDate.format(new Date(deleteTargets[0].occurred_at))}` : undefined}
        size="sm"
        tone="danger"
        footer={(
          <>
            <Button variant="ghost" disabled={deleting} onClick={() => setDeleteTargets([])}>Cancelar</Button>
            <Button variant="danger" iconBefore="trash" loading={deleting} onClick={() => void confirmDelete()}>
              {deleteTargets.length > 1 ? `Eliminar ${deleteTargets.length} videos` : 'Eliminar definitivamente'}
            </Button>
          </>
        )}
      >
        <p className="dialog-copy">
          {deleteTargets.length > 1
            ? 'Los videos se eliminarán del almacenamiento y dejarán de estar disponibles para los jugadores. Esta acción no se puede deshacer.'
            : deleteTargets[0]?.kind === 'recording'
              ? 'Se eliminará el partido completo del almacenamiento. Sus highlights seguirán disponibles. Esta acción no se puede deshacer.'
              : 'Se eliminará el clip del almacenamiento y dejará de estar disponible para los jugadores. Esta acción no se puede deshacer.'}
        </p>
      </Dialog>
    </div>
  );
}
