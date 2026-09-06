export type View = 'owner' | 'qr' | 'player';
export type ConsoleSection = 'overview' | 'courts' | 'court' | 'library' | 'activity' | 'notifications' | 'settings';

const SECTION_PATH: Record<Exclude<ConsoleSection, 'court'>, string> = {
  overview: '/',
  courts: '/fields',
  library: '/library',
  activity: '/activity',
  notifications: '/notifications',
  settings: '/settings',
};

export function pathToView(path: string): View {
  if (path.startsWith('/qr')) return 'qr';
  if (path.startsWith('/player')) return 'player';
  return 'owner';
}

export function pathToSection(path: string): ConsoleSection {
  if (/^\/fields\/[^/]+/.test(path)) return 'court';
  if (path.startsWith('/fields')) return 'courts';
  if (path.startsWith('/library')) return 'library';
  if (path.startsWith('/activity')) return 'activity';
  if (path.startsWith('/notifications')) return 'notifications';
  if (path.startsWith('/settings') || path.startsWith('/profile')) return 'settings';
  return 'overview';
}

export function courtIdFromPath(path: string): string | null {
  return path.match(/^\/fields\/([^/?]+)/)?.[1] ?? null;
}

/** Navegación push que mantiene sincronizados history y estado de la app. */
export function pushPath(path: string) {
  if (window.location.pathname + window.location.search === path) return;
  window.history.pushState({}, '', path);
  window.dispatchEvent(new PopStateEvent('popstate'));
}

export function goToView(view: View) {
  pushPath(view === 'owner' ? '/' : `/${view}`);
}

export function goToSection(section: Exclude<ConsoleSection, 'court'>) {
  pushPath(SECTION_PATH[section]);
}

export function goToCourt(courtId: string) {
  pushPath(`/fields/${courtId}`);
}
