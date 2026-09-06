import { useCallback, useEffect, useState } from 'react';

export type Theme = 'light' | 'dark';

const STORAGE_KEY = 'courtvision-theme';
const media = () => window.matchMedia('(prefers-color-scheme: dark)');

export function preferredTheme(): Theme {
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === 'light' || stored === 'dark') return stored;
  return media().matches ? 'dark' : 'light';
}

export function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
  const themeColor = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]');
  if (themeColor) {
    const value = window.getComputedStyle(document.documentElement).getPropertyValue('--browser-chrome').trim();
    if (value) themeColor.content = value;
  }
}

/** Ejecutar antes del primer render evita el flash del tema equivocado. */
export function initializeTheme() {
  const theme = preferredTheme();
  applyTheme(theme);
  return theme;
}

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(() => preferredTheme());

  const setTheme = useCallback((next: Theme) => {
    window.localStorage.setItem(STORAGE_KEY, next);
    applyTheme(next);
    setThemeState(next);
  }, []);

  useEffect(() => {
    applyTheme(theme);
    const preference = media();
    const syncPreference = (event: MediaQueryListEvent) => {
      if (window.localStorage.getItem(STORAGE_KEY)) return;
      const next = event.matches ? 'dark' : 'light';
      applyTheme(next);
      setThemeState(next);
    };
    preference.addEventListener('change', syncPreference);
    return () => preference.removeEventListener('change', syncPreference);
  }, [theme]);

  return { theme, setTheme, toggleTheme: () => setTheme(theme === 'light' ? 'dark' : 'light') };
}
