import { useEffect, useState } from 'react';
import { Button, EmptyState, Icon, Skeleton } from '@courtvision/design-system';
import { ConsoleShell } from './ConsoleShell';
import { useOwnerConsole } from './useOwnerConsole';
import { courtIdFromPath, goToSection } from './routes';
import type { ConsoleSection } from './routes';
import { OverviewPage } from '../features/overview/OverviewPage';
import { CourtsPage } from '../features/courts/CourtsPage';
import { CourtDetailPage } from '../features/courts/CourtDetailPage';
import { LibraryPage } from '../features/library/LibraryPage';
import { ActivityPage } from '../features/notifications/NotificationsPage';
import { NotificationCenterPage } from '../features/notifications/NotificationCenterPage';
import { SettingsPage } from '../features/settings/SettingsPage';
import type { OwnerSession } from '../lib/api';

/** Contenedor de la consola: resuelve la sección activa y la envuelve en el armazón. */
export function OwnerConsoleApp({
  session,
  section,
  onLogout,
}: { session: OwnerSession; section: ConsoleSection; onLogout: () => void }) {
  const data = useOwnerConsole(session);
  const [courtId, setCourtId] = useState(() => courtIdFromPath(window.location.pathname));

  useEffect(() => {
    const sync = () => setCourtId(courtIdFromPath(window.location.pathname));
    window.addEventListener('popstate', sync);
    sync();
    return () => window.removeEventListener('popstate', sync);
  }, [section]);

  const court = section === 'court' ? data.fields.find((field) => field.id === courtId) ?? null : null;
  const clubName = data.dashboard?.club.name?.trim() || 'Club sin nombre';
  const clubCity = data.dashboard?.club.city?.trim();

  const chrome = titleFor(section, {
    clubName, clubCity,
    courtName: court?.name,
    courts: data.fields.length,
    cameras: data.cameras.length,
    loading: data.loading,
  });

  return (
    <ConsoleShell
      console={data}
      section={section}
      session={session}
      onLogout={onLogout}
      title={
        section === 'court' ? (
          <span className="topbar__back-title">
            <button type="button" className="topbar__back" onClick={() => goToSection('courts')} aria-label="Volver a canchas">
              <Icon name="arrowLeft" size={16} />
            </button>
            {chrome.title}
          </span>
        ) : chrome.title
      }
      context={chrome.context}
    >
      {section === 'overview' ? <OverviewPage console={data} /> : null}
      {section === 'courts' ? <CourtsPage console={data} /> : null}
      {section === 'library' ? <LibraryPage console={data} /> : null}
      {section === 'activity' ? <ActivityPage console={data} /> : null}
      {section === 'notifications' ? <NotificationCenterPage console={data} /> : null}
      {section === 'settings' ? <SettingsPage console={data} /> : null}
      {section === 'court' ? (
        court ? (
          <CourtDetailPage console={data} field={court} ownerToken={session.access_token} />
        ) : data.loading ? (
          <div className="page"><Skeleton className="cv-skeleton--panel" /></div>
        ) : (
          <div className="page page-enter">
            <EmptyState
              icon="search"
              title="No encontramos esta cancha"
              action={<Button variant="secondary" size="sm" iconAfter="arrowRight" onClick={() => goToSection('courts')}>Ver todas las canchas</Button>}
            >
              Puede haber sido eliminada, o el enlace apunta a otro club.
            </EmptyState>
          </div>
        )
      ) : null}
    </ConsoleShell>
  );
}

function titleFor(
  section: ConsoleSection,
  ctx: { clubName: string; clubCity?: string; courtName?: string; courts: number; cameras: number; loading: boolean },
): { title: string; context?: string } {
  const club = ctx.clubCity ? `${ctx.clubName} · ${ctx.clubCity}` : ctx.clubName;
  switch (section) {
    case 'courts':
      return {
        title: 'Canchas',
        context: ctx.loading ? 'Sincronizando…' : `${ctx.courts} ${ctx.courts === 1 ? 'cancha' : 'canchas'} · ${ctx.cameras} ${ctx.cameras === 1 ? 'cámara' : 'cámaras'}`,
      };
    case 'court':
      return { title: ctx.courtName ?? 'Cancha', context: club };
    case 'library':
      return { title: 'Biblioteca', context: 'Momentos capturados en el club' };
    case 'notifications':
      return { title: 'Notificaciones', context: club };
    case 'activity':
      return { title: 'Actividad', context: club };
    case 'settings':
      return { title: 'Configuración', context: 'Club y cuenta' };
    default:
      return { title: 'Operación', context: club };
  }
}
