import { useState } from 'react';
import type { FormEvent } from 'react';
import { Banner, Button, TextField, ThemeToggle, useTheme } from '@courtvision/design-system';
import { VivooLogo } from '../../components/Brand';
import { loginOwner } from '../../lib/api';
import type { OwnerSession } from '../../lib/api';

/** Acceso a la consola del club. */
export function LoginPage({ onLogin }: { onLogin: (session: OwnerSession) => void }) {
  const { theme, toggleTheme } = useTheme();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError('');
    try {
      onLogin(await loginOwner(email, password));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'No pudimos iniciar sesión.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="login">
      <ThemeToggle theme={theme} onToggle={toggleTheme} className="login__theme" />
      <section className="login__panel page-enter">
        <span className="login__brand"><VivooLogo /></span>
        <h1 className="t-display">Iniciar sesión</h1>

        <form onSubmit={submit} className="login__form" noValidate>
          <TextField label="Email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" required />
          <TextField label="Contraseña" type="password" passwordReveal value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" required />
          {error ? <Banner tone="error" title="Revisá tus datos">{error}</Banner> : null}
          <Button type="submit" variant="primary" loading={loading} disabled={!email || !password}>Entrar</Button>
        </form>
      </section>
    </main>
  );
}
