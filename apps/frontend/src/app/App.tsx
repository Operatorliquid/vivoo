import { useEffect, useState } from 'react';
import { OwnerConsoleApp } from './OwnerConsole';
import { LoginPage } from '../features/auth/LoginPage';
import { QrPage } from '../features/public/QrPage';
import { PlayerPage } from '../features/public/PlayerPage';
import { goToView, pathToSection, pathToView } from './routes';
import type { ConsoleSection, View } from './routes';
import { isInvalidSessionError, logoutOwner, refreshOwnerSession } from '../lib/api';
import type { OwnerSession } from '../lib/api';
import { clearOwnerSession, readOwnerSession, saveOwnerSession } from '../lib/auth';
import { BrandMark } from '../components/Brand';
import { AdminRoot } from '../features/admin/AdminRoot';

export function App() {
  if (window.location.pathname.startsWith('/admin')) return <AdminRoot />;
  return <OwnerRoot />;
}

function OwnerRoot() {
  const [view, setView] = useState<View>(() => pathToView(window.location.pathname));
  const [section, setSection] = useState<ConsoleSection>(() => pathToSection(window.location.pathname));
  const [session, setSession] = useState<OwnerSession | null>(null);
  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    const onPop = () => {
      setView(pathToView(window.location.pathname));
      setSection(pathToSection(window.location.pathname));
    };
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  useEffect(() => {
    const stored = readOwnerSession();
    if (!stored) { setAuthChecked(true); return; }
    refreshOwnerSession(stored.access_token)
      .then((rotated) => {
        saveOwnerSession(rotated);
        setSession(rotated);
      })
      .catch((error) => {
        if (isInvalidSessionError(error)) clearOwnerSession();
        else setSession(stored);
      })
      .finally(() => setAuthChecked(true));
  }, []);

  if (view === 'qr') return <QrPage />;
  if (view === 'player') return <PlayerPage />;

  if (!authChecked) {
    return (
      <div className="boot" role="status" aria-live="polite">
        <BrandMark size={26} />
        <span>Verificando acceso…</span>
      </div>
    );
  }

  if (!session) {
    return (
      <LoginPage
        onLogin={(next) => { saveOwnerSession(next); setSession(next); goToView('owner'); }}
      />
    );
  }

  return (
    <OwnerConsoleApp
      session={session}
      section={section}
      onLogout={() => {
        const token = session.access_token;
        clearOwnerSession();
        setSession(null);
        void logoutOwner(token);
      }}
    />
  );
}
