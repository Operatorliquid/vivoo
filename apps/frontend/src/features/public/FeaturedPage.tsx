import { useEffect, useState } from 'react';
import { EmptyState, Icon, Skeleton } from '@courtvision/design-system';
import { featuredClubSlugFromPath, goToView } from '../../app/routes';
import { VivooLogo } from '../../components/Brand';
import { getPublicMonthlyFavorites, publicMediaUrl } from '../../lib/api';
import type { PublicMonthlyFavoritesPage } from '../../lib/api';

const monthName = new Intl.DateTimeFormat('es-AR', { month: 'long', year: 'numeric' });
const momentDate = new Intl.DateTimeFormat('es-AR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });

export function FeaturedPage() {
  const slug = featuredClubSlugFromPath(window.location.pathname);
  const [page, setPage] = useState<PublicMonthlyFavoritesPage | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!slug) { setError('Esta página no existe.'); return; }
    getPublicMonthlyFavorites(slug)
      .then(setPage)
      .catch((reason) => setError(reason instanceof Error ? reason.message : 'No pudimos abrir los destacados.'));
  }, [slug]);

  return (
    <div className="public featured-public">
      <header className="public__bar">
        <span className="public__brand"><VivooLogo /></span>
        <button className="public__owner" type="button" onClick={() => goToView('owner')}>
          Soy del club <Icon name="arrowRight" size={14} />
        </button>
      </header>

      <main className="featured-public__main page-enter">
        {error ? (
          <EmptyState icon="warning" title={error}>Revisá el enlace o pedile uno nuevo al club.</EmptyState>
        ) : !page ? (
          <div className="featured-public__loading"><Skeleton w="34%" h={18} /><Skeleton w="62%" h={48} /><Skeleton w="100%" h={360} /></div>
        ) : (
          <>
            <header className="featured-public__hero">
              <div className="featured-public__identity">
                {page.club_logo_data_url ? <img src={page.club_logo_data_url} alt={`Logo de ${page.club_name}`} /> : <span><Icon name="star" size={20} /></span>}
                <div>
                  <span className="t-label">{monthName.format(new Date())}</span>
                  <h1 className="t-display">Favoritos del mes</h1>
                  <p>{page.club_name}{page.club_city ? ` · ${page.club_city}` : ''}</p>
                </div>
              </div>
              <strong>{page.items.length} {page.items.length === 1 ? 'momento' : 'momentos'}</strong>
            </header>

            {page.items.length > 0 ? (
              <ul className="featured-public__grid">
                {page.items.map((item, index) => (
                  <li key={item.id} className={index === 0 ? 'is-lead' : ''}>
                    <video controls playsInline preload="metadata" src={publicMediaUrl(item.media_path)} />
                    <div>
                      <span className="featured-public__rank">{String(index + 1).padStart(2, '0')}</span>
                      <div>
                        <b>{item.field_name}</b>
                        <p>{item.players.length > 0 ? item.players.join(', ') : momentDate.format(new Date(item.occurred_at))}</p>
                      </div>
                      <small>{item.duration_seconds}s</small>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState icon="star" title="La selección de este mes está por llegar">
                El club está preparando sus próximos momentos destacados.
              </EmptyState>
            )}
          </>
        )}
      </main>
    </div>
  );
}
