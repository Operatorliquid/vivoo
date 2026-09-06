import { useEffect, useState } from 'react';
import { BrandMark } from '../../components/Brand';
import { clearAdminSession, readAdminSession, saveAdminSession } from '../../lib/auth';
import { isInvalidSessionError, logoutAdmin, refreshAdminSession } from '../../lib/api';
import type { OwnerSession } from '../../lib/api';
import { AdminConsole } from './AdminConsole';
import { AdminLoginPage } from './AdminLoginPage';

export function AdminRoot() {
  const [session, setSession] = useState<OwnerSession | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    const stored = readAdminSession();
    if (!stored) { setChecked(true); return; }
    refreshAdminSession(stored.access_token)
      .then((rotated) => { saveAdminSession(rotated); setSession(rotated); })
      .catch((error) => {
        if (isInvalidSessionError(error)) clearAdminSession();
        else setSession(stored);
      })
      .finally(() => setChecked(true));
  }, []);

  if (!checked) return <div className="boot" role="status"><BrandMark size={26} /><span>Verificando acceso…</span></div>;
  if (!session) return <AdminLoginPage onLogin={(next) => { saveAdminSession(next); setSession(next); }} />;
  return <AdminConsole session={session} onLogout={() => { const token = session.access_token; clearAdminSession(); setSession(null); void logoutAdmin(token); }} />;
}
