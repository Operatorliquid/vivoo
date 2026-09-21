import { useEffect, useMemo, useState } from 'react';
import QRCode from 'qrcode';
import { Button, EmptyState, Icon, Skeleton } from '@courtvision/design-system';
import type { OwnerConsole } from '../../app/useOwnerConsole';
import { CopyValue } from '../../components/CopyValue';
import { publicMediaUrl } from '../../lib/api';

const dateTime = new Intl.DateTimeFormat('es-AR', { day: '2-digit', month: 'short', year: 'numeric' });
const momentTime = new Intl.DateTimeFormat('es-AR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });

const sameIds = (left: Set<string>, right: Set<string>) => (
  left.size === right.size && [...left].every((id) => right.has(id))
);

async function downloadQr(url: string, clubName: string) {
  const canvas = document.createElement('canvas');
  await QRCode.toCanvas(canvas, url, {
    width: 1800,
    margin: 4,
    errorCorrectionLevel: 'H',
    color: { dark: '#090d0b', light: '#ffffff' },
  });
  const blob = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((value) => value ? resolve(value) : reject(new Error('No pudimos exportar el QR.')), 'image/png');
  });
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  const slug = clubName.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
  anchor.href = objectUrl;
  anchor.download = `vivoo-destacados-${slug || 'club'}.png`;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}

export function FavoritesPage({ console: data }: { console: OwnerConsole }) {
  const [draft, setDraft] = useState<Set<string>>(() => new Set());
  const [saving, setSaving] = useState(false);
  const [qr, setQr] = useState('');
  const favorites = data.monthlyFavorites;
  const saved = useMemo(() => new Set(favorites?.items.map((item) => item.id) ?? []), [favorites]);
  const available = useMemo(
    () => data.highlights.filter((item) => item.status === 'available' && Boolean(item.media_path)),
    [data.highlights],
  );
  const expiryById = useMemo(
    () => new Map(favorites?.items.map((item) => [item.id, item.expires_at]) ?? []),
    [favorites],
  );

  useEffect(() => { setDraft(new Set(saved)); }, [favorites?.items]);
  useEffect(() => {
    let active = true;
    setQr('');
    if (!favorites?.public_url || favorites.items.length === 0) return () => { active = false; };
    void QRCode.toDataURL(favorites.public_url, {
      width: 720,
      margin: 2,
      errorCorrectionLevel: 'H',
      color: { dark: '#090d0b', light: '#ffffff' },
    }).then((value) => { if (active) setQr(value); });
    return () => { active = false; };
  }, [favorites?.public_url, favorites?.items.length]);

  const dirty = !sameIds(draft, saved);
  const toggle = (id: string) => setDraft((current) => {
    const next = new Set(current);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });
  const save = async () => {
    setSaving(true);
    await data.actions.saveMonthlyFavorites([...draft]);
    setSaving(false);
  };

  return (
    <div className="page page-enter favorites-page">
      <section className="favorites-editor">
        <header className="favorites-editor__head">
          <div>
            <h2 className="t-heading">Elegí los destacados</h2>
            <p className="t-meta">Cada video permanece publicado durante 30 días desde que lo seleccionás.</p>
          </div>
          <div className="favorites-editor__actions">
            <span className="favorites-editor__count">{draft.size} {draft.size === 1 ? 'elegido' : 'elegidos'}</span>
            <Button variant="primary" size="sm" iconBefore="check" loading={saving} disabled={!dirty} onClick={() => void save()}>
              Guardar
            </Button>
          </div>
        </header>

        {available.length > 0 ? (
          <ul className="favorites-grid">
            {available.map((highlight) => {
              const selected = draft.has(highlight.id);
              const expiresAt = expiryById.get(highlight.id);
              return (
                <li key={highlight.id} className={`favorite-option ${selected ? 'is-selected' : ''}`}>
                  <button
                    type="button"
                    className="favorite-option__toggle"
                    aria-pressed={selected}
                    aria-label={`${selected ? 'Quitar' : 'Agregar'} ${highlight.field_name} de favoritos del mes`}
                    onClick={() => toggle(highlight.id)}
                  >
                    <span className="favorite-option__check"><Icon name={selected ? 'check' : 'star'} size={16} /></span>
                    <span className="favorite-option__frame">
                      <video
                        muted
                        playsInline
                        preload="metadata"
                        src={publicMediaUrl(highlight.media_path!)}
                        onLoadedMetadata={(event) => {
                          const video = event.currentTarget;
                          if (Number.isFinite(video.duration) && video.duration > 0) video.currentTime = Math.min(0.5, video.duration / 3);
                        }}
                      />
                      <span>{highlight.duration_seconds}s</span>
                    </span>
                    <span className="favorite-option__body">
                      <b>{highlight.field_name}</b>
                      <small>{highlight.players.length > 0 ? highlight.players.join(', ') : momentTime.format(new Date(highlight.occurred_at))}</small>
                      {expiresAt && selected ? <em>Publicado hasta {dateTime.format(new Date(expiresAt))}</em> : null}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        ) : data.loading ? (
          <div className="favorites-loading"><Skeleton h={220} /><Skeleton h={220} /></div>
        ) : (
          <EmptyState icon="star" accent="flare" title="Todavía no hay highlights listos">
            Cuando un momento termine de procesarse, vas a poder seleccionarlo desde acá.
          </EmptyState>
        )}
      </section>

      <aside className="favorites-publish">
        {favorites && favorites.items.length > 0 ? (
          <>
            <header>
              <span className="favorites-publish__mark"><Icon name="star" size={18} /></span>
              <div>
                <h2 className="t-heading">Página pública</h2>
                <p className="t-meta">{favorites.items.length} {favorites.items.length === 1 ? 'video publicado' : 'videos publicados'}</p>
              </div>
            </header>
            <div className="favorites-publish__qr">
              {qr ? <img src={qr} alt={`QR de favoritos del mes de ${favorites.club_name}`} /> : <Skeleton w="100%" h={240} />}
            </div>
            <CopyValue value={favorites.public_url} label="enlace público" onCopied={() => data.announce('success', 'Enlace público copiado.')} />
            <div className="favorites-publish__buttons">
              <Button variant="secondary" size="sm" iconBefore="download" disabled={!qr} onClick={() => void downloadQr(favorites.public_url, favorites.club_name)}>
                Descargar QR
              </Button>
              <Button variant="ghost" size="sm" iconBefore="externalLink" onClick={() => window.open(favorites.public_url, '_blank', 'noopener,noreferrer')}>
                Abrir página
              </Button>
            </div>
          </>
        ) : (
          <EmptyState icon="qr" compact title="Publicá tu primera selección">
            Elegí al menos un highlight y guardá. Acá aparecerán el enlace y el QR para compartir.
          </EmptyState>
        )}
      </aside>
    </div>
  );
}
