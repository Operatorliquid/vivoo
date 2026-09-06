import { useEffect, useState } from 'react';
import { EmptyState, Icon, Skeleton, StatusPill } from '@courtvision/design-system';
import { VivooLogo } from '../../components/Brand';
import { getPlayerMediaPage, publicMediaUrl } from '../../lib/api';
import type { PlayerMediaPage } from '../../lib/api';
import { goToView } from '../../app/routes';
import { sportLabel } from '../../lib/court';

/**
 * Página privada del jugador: el partido completo y sus momentos.
 * Es una pieza de consumo, no de operación — una columna, el video primero.
 */
export function PlayerPage() {
  const accessToken = new URLSearchParams(window.location.search).get('access');
  const [media, setMedia] = useState<PlayerMediaPage | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(Boolean(accessToken));

  useEffect(() => {
    if (!accessToken) return;
    getPlayerMediaPage(accessToken)
      .then(setMedia)
      .catch((reason) => setError(reason instanceof Error ? reason.message : 'No pudimos abrir este partido.'))
      .finally(() => setLoading(false));
  }, [accessToken]);

  useEffect(() => {
    if (!accessToken || !media || ['available', 'expired'].includes(media.recording_status)) return undefined;
    const interval = window.setInterval(() => {
      getPlayerMediaPage(accessToken).then(setMedia).catch(() => undefined);
    }, 5000);
    return () => window.clearInterval(interval);
  }, [accessToken, media?.recording_status]);

  const mediaUrl = (path: string | null) => (path ? publicMediaUrl(path) : '');

  return (
    <div className="public">
      <header className="public__bar">
        <span className="public__brand"><VivooLogo /></span>
        <button className="public__owner" type="button" onClick={() => goToView('owner')}>
          Soy del club <Icon name="arrowRight" size={14} />
        </button>
      </header>

      <main className="player page-enter">
        {!accessToken ? (
          <EmptyState icon="qr" title="Necesitás tu enlace privado">
            Este espacio se abre desde el QR de la cancha o desde el enlace que te enviamos por WhatsApp.
          </EmptyState>
        ) : error ? (
          <EmptyState icon="warning" title={error}>
            Pedile al club un enlace nuevo si el problema continúa.
          </EmptyState>
        ) : loading || !media ? (
          <div className="player__loading">
            <Skeleton w="42%" h={26} />
            <Skeleton w="100%" h={260} />
            <Skeleton w="60%" h={14} />
          </div>
        ) : (
          <>
            <section className="player__head">
              <div>
                <span className="t-label">Acceso privado</span>
                <h1 className="t-display">{media.player_name}, tu partido.</h1>
                <p className="t-meta">
                  {media.field_name} <i aria-hidden="true">·</i> {sportLabel(media.sport_code)} <i aria-hidden="true">·</i> {new Date(media.started_at).toLocaleString('es-AR')}
                </p>
              </div>
              <span className="player__code t-meta">{media.session_id.slice(0, 8).toUpperCase()}</span>
            </section>

            <section className="player__match" aria-labelledby="pl-match">
              <div className="player__match-head">
                <h2 className="t-heading" id="pl-match">Partido completo</h2>
                <StatusPill
                  state={media.recording_status === 'in_progress' ? 'live' : media.recording_status === 'expired' ? 'offline' : 'ready'}
                  pulse={media.recording_status === 'in_progress'}
                >
                  {media.recording_status === 'available' ? 'Disponible' : media.recording_status === 'expired' ? 'Vencido' : media.recording_status === 'processing' ? 'Preparando video' : 'En curso'}
                </StatusPill>
              </div>
              {media.recording_path ? (
                <>
                  <video className="player__video" controls preload="metadata" src={mediaUrl(media.recording_path)} />
                  <a className="player__download" href={mediaUrl(media.recording_path)} download>
                    <Icon name="arrowRight" size={14} /> Descargar partido completo
                  </a>
                  {media.recording_expires_at ? (
                    <p className="player__retention">Disponible hasta {new Date(media.recording_expires_at).toLocaleString('es-AR')}.</p>
                  ) : null}
                </>
              ) : (
                <div className={`player__match-status player__match-status--${media.recording_status}`}>
                  <span className="player__match-status-mark" aria-hidden="true">
                    <Icon name={media.recording_status === 'in_progress' ? 'record' : media.recording_status === 'expired' ? 'info' : 'refresh'} size={18} />
                  </span>
                  <div>
                    <strong>{media.recording_status === 'in_progress' ? 'Partido en curso' : media.recording_status === 'expired' ? 'El partido completo venció' : 'Preparando tu video'}</strong>
                    <p>
                      {media.recording_status === 'in_progress'
                        ? 'La cámara está grabando. El partido completo aparecerá acá cuando finalice.'
                        : media.recording_status === 'expired'
                          ? 'Los partidos completos se conservan durante 48 horas. Tus highlights siguen disponibles.'
                          : 'El partido terminó y estamos procesando el archivo para que puedas verlo y descargarlo.'}
                    </p>
                  </div>
                </div>
              )}
            </section>

            <section className="player__clips" aria-labelledby="pl-clips">
              <div className="player__match-head">
                <h2 className="t-heading" id="pl-clips">Tus momentos</h2>
                <span className="t-meta">{media.highlights.length}</span>
              </div>
              {media.highlights.length > 0 ? (
                <ul className="clip-grid">
                  {media.highlights.map((highlight) => (
                    <li key={highlight.id} className="clip">
                      {highlight.media_path ? (
                        <video controls preload="metadata" src={mediaUrl(highlight.media_path)} />
                      ) : (
                        <div className="clip__pending">
                          <Icon name="play" size={16} />
                          <span>{highlight.status === 'processing' ? 'Procesando' : 'No disponible'}</span>
                        </div>
                      )}
                      <div className="clip__meta">
                        <b>{highlight.title}</b>
                        <span className="t-meta">
                          {new Date(highlight.occurred_at).toLocaleTimeString('es-AR')} <i aria-hidden="true">·</i> {highlight.duration_seconds}s
                        </span>
                        {highlight.media_path ? <a href={mediaUrl(highlight.media_path)} download>Descargar</a> : null}
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <EmptyState icon="gesture" title="Todavía no hay momentos" compact>
                  Aparecen acá cuando se detecta el gesto en la cancha o se presiona el botón de highlights.
                </EmptyState>
              )}
            </section>

            <section className="player__delivery">
              <Icon name="whatsapp" size={17} />
              <p>Los momentos también te llegan por WhatsApp al número que registraste, apenas terminan de procesarse.</p>
            </section>
          </>
        )}
      </main>
    </div>
  );
}
