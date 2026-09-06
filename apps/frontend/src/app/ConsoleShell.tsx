import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { Avatar, Button, Icon, ThemeToggle, useTheme } from '@courtvision/design-system';
import { Brand } from '../components/Brand';
import { NotificationList } from '../components/NotificationList';
import { QuickSearch } from '../components/QuickSearch';
import { goToSection } from './routes';
import type { ConsoleSection } from './routes';
import type { OwnerConsole } from './useOwnerConsole';
import type { OwnerSession } from '../lib/api';
import { initialsOf } from '../lib/court';

type NavItem = { section: Exclude<ConsoleSection, 'court'>; label: string; icon: string; matches: ConsoleSection[] };

/** Destinos de la barra inferior en móvil y del primer grupo del riel. */
const NAV: NavItem[] = [
  { section: 'overview', label: 'Operación', icon: 'board', matches: ['overview'] },
  { section: 'courts', label: 'Canchas', icon: 'court', matches: ['courts', 'court'] },
  { section: 'library', label: 'Biblioteca', icon: 'clip', matches: ['library'] },
  { section: 'activity', label: 'Actividad', icon: 'activity', matches: ['activity'] },
];

const NAV_GENERAL: NavItem[] = [
  { section: 'settings', label: 'Configuración', icon: 'settings', matches: ['settings'] },
];

/**
 * Armazón de la consola.
 *
 * Escritorio: riel de navegación fijo + barra superior que siempre dice dónde
 * estás y cuándo se sincronizó el dato. Móvil: barra inferior con los cuatro
 * destinos al alcance del pulgar — antes el riel simplemente se ocultaba y
 * Canchas y Biblioteca quedaban inalcanzables desde el teléfono.
 */
export function ConsoleShell({
  console: data,
  section,
  session,
  title,
  context,
  actions,
  onLogout,
  children,
}: {
  console: OwnerConsole;
  section: ConsoleSection;
  session: OwnerSession;
  title: ReactNode;
  context?: ReactNode;
  actions?: ReactNode;
  onLogout: () => void;
  children: ReactNode;
}) {
  const [activityOpen, setActivityOpen] = useState(false);
  const { theme, toggleTheme } = useTheme();
  const unread = data.notifications.filter((item) => !item.read).length;
  const displayName = data.profile?.display_name ?? session.user.display_name;
  const initials = initialsOf(displayName);
  const clubName = data.dashboard?.club.name?.trim() || 'Club sin nombre';
  const clubCity = data.dashboard?.club.city?.trim();
  const clubLogo = data.dashboard?.club.logo_data_url ?? '';

  useEffect(() => { setActivityOpen(false); }, [section]);

  const navButton = (item: NavItem, variant: 'rail' | 'tab') => {
    const active = item.matches.includes(section);
    const badge = item.section === 'courts' ? data.fields.length : item.section === 'notifications' ? unread : 0;
    return (
      <button
        key={item.section}
        type="button"
        className={`${variant}-nav__item ${active ? 'is-active' : ''}`}
        aria-current={active ? 'page' : undefined}
        onClick={() => goToSection(item.section)}
      >
        <Icon name={item.icon} size={variant === 'tab' ? 20 : 18} />
        <span>{item.label}</span>
        {badge > 0 ? (
          <em className={`${variant}-nav__badge ${item.section === 'notifications' ? 'is-alert' : ''}`}>{badge}</em>
        ) : null}
      </button>
    );
  };

  return (
    <div className="console">
      {/* Con teclado, el riel y la barra superior se saltan de una vez. */}
      <a className="skip-link" href="#contenido">Saltar al contenido</a>

      <aside className="rail">
        <div className="rail__brand"><Brand /></div>

        <button type="button" className="rail__club" onClick={() => goToSection('settings')}>
          {clubLogo ? <img className="rail__club-logo" src={clubLogo} alt="" /> : null}
          <span className="rail__club-text">
            <b className="t-truncate">{clubName}</b>
            <small className="t-truncate">{clubCity || 'Completar datos del club'}</small>
          </span>
          <Icon name="chevronRight" size={14} />
        </button>

        <div className="rail__scroll">
          <p className="rail__group">Menú</p>
          <nav className="rail-nav" aria-label="Secciones de la consola">
            {NAV.map((item) => navButton(item, 'rail'))}
          </nav>

          <p className="rail__group">General</p>
          <nav className="rail-nav" aria-label="Configuración">
            {NAV_GENERAL.map((item) => navButton(item, 'rail'))}
          </nav>
        </div>

        <div className="rail__foot">
          <button type="button" className="rail__account" onClick={() => goToSection('settings')}>
            <Avatar initials={initials} size="sm" />
            <span className="rail__user">
              <b className="t-truncate">{displayName}</b>
              <small className="t-truncate">{session.user.email}</small>
            </span>
          </button>
          <button type="button" className="rail__logout" onClick={onLogout}>
            <Icon name="logout" size={16} /> Cerrar sesión
          </button>
        </div>
      </aside>

      <div className="console__main">
        <header className="topbar">
          <div className="topbar__mobile-brand"><Brand compact /></div>

          <div className="topbar__title">
            <h1 className="t-title">{title}</h1>
            {context ? <p className="topbar__context">{context}</p> : null}
          </div>

          <div className="topbar__search"><QuickSearch fields={data.fields} /></div>

          <div className="topbar__actions">
            {actions}
            <ThemeToggle theme={theme} onToggle={toggleTheme} />
            <button
              type="button"
              className="topbar__sync"
              onClick={() => void data.refresh()}
              disabled={data.refreshing || data.loading}
              title="Volver a leer el estado de las canchas"
            >
              <Icon name="refresh" size={15} className={data.refreshing ? 'is-spinning' : ''} />
              <span className="t-meta">{data.syncedAt ? data.syncedAt : '—'}</span>
            </button>

            <button
              type="button"
              className="topbar__icon"
              aria-label={unread > 0 ? `Notificaciones, ${unread} sin leer` : 'Notificaciones'}
              aria-expanded={activityOpen}
              onClick={() => setActivityOpen((current) => !current)}
            >
              <Icon name="bell" size={18} />
              {unread > 0 ? <i className="topbar__dot" /> : null}
            </button>

            <button
              type="button"
              className="topbar__icon topbar__avatar"
              aria-label="Configuración de la cuenta"
              onClick={() => goToSection('settings')}
            >
              <Avatar initials={initials} size="sm" />
            </button>
          </div>
        </header>

        {activityOpen ? (
          <>
            <div className="activity-scrim" role="presentation" onClick={() => setActivityOpen(false)} />
            <section className="activity-panel" aria-label="Notificaciones recientes">
              <header>
                <span className="t-label">Notificaciones</span>
                <strong>{unread > 0 ? `${unread} sin leer` : 'Todo al día'}</strong>
                <button type="button" aria-label="Cerrar actividad" onClick={() => setActivityOpen(false)}>
                  <Icon name="close" size={15} />
                </button>
              </header>
              <div className="activity-panel__body">
                {data.notifications.length > 0 ? (
                  <NotificationList
                    notifications={data.notifications.slice(0, 6)}
                    onRead={(id) => void data.actions.readNotification(id)}
                    dense
                  />
                ) : (
                  <p className="activity-panel__empty">No hay notificaciones pendientes.</p>
                )}
              </div>
              <footer>
                {unread > 0 ? (
                  <Button variant="ghost" size="sm" onClick={() => void data.actions.readAllNotifications()}>Marcar todo leído</Button>
                ) : <span />}
                <Button variant="secondary" size="sm" iconAfter="arrowRight" onClick={() => { void data.actions.readAllNotifications(); goToSection('notifications'); }}>Ver todo</Button>
              </footer>
            </section>
          </>
        ) : null}

        <main className="canvas" id="contenido" tabIndex={-1}>{children}</main>

        <nav className="tab-nav" aria-label="Secciones de la consola">
          {NAV.map((item) => navButton(item, 'tab'))}
        </nav>
      </div>

      {data.notice ? (
        <div className={`toast toast--${data.notice.tone}`} role="status" key={data.notice.id}>
          <Icon name={data.notice.tone === 'error' ? 'warning' : 'check'} size={15} />
          <span>{data.notice.text}</span>
          <button type="button" aria-label="Cerrar aviso" onClick={data.dismissNotice}><Icon name="close" size={14} /></button>
        </div>
      ) : null}
    </div>
  );
}
