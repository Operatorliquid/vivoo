import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { Banner, Button, Dialog, Icon, TextField } from '@courtvision/design-system';
import { CopyValue } from '../../components/CopyValue';
import { createAdminCustomer } from '../../lib/api';
import type { AdminCustomer } from '../../lib/api';

function securePassword() {
  const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#-';
  const values = crypto.getRandomValues(new Uint32Array(18));
  return Array.from(values, (value) => alphabet[value % alphabet.length]).join('');
}

type Access = { customer: AdminCustomer; email: string; password: string };

export function CreateCustomerDialog({
  open,
  token,
  onClose,
  onCreated,
}: {
  open: boolean;
  token: string;
  onClose: () => void;
  onCreated: (customer: AdminCustomer) => void;
}) {
  const [displayName, setDisplayName] = useState('');
  const [email, setEmail] = useState('');
  const [clubName, setClubName] = useState('');
  const [city, setCity] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [access, setAccess] = useState<Access | null>(null);

  useEffect(() => {
    if (!open) return;
    setDisplayName('');
    setEmail('');
    setClubName('');
    setCity('');
    setPassword(securePassword());
    setError('');
    setAccess(null);
  }, [open]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError('');
    try {
      const customer = await createAdminCustomer(token, {
        display_name: displayName.trim(),
        email: email.trim(),
        password,
        club_name: clubName.trim(),
        city: city.trim(),
      });
      setAccess({ customer, email: email.trim(), password });
      onCreated(customer);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'No pudimos crear el usuario.');
    } finally {
      setSaving(false);
    }
  }

  const close = () => { if (!saving) onClose(); };

  return (
    <Dialog
      open={open}
      title={access ? 'Usuario creado' : 'Crear usuario'}
      size="md"
      onClose={close}
      footer={access ? (
        <Button variant="primary" onClick={onClose}>Listo</Button>
      ) : (
        <>
          <Button variant="secondary" onClick={close} disabled={saving}>Cancelar</Button>
          <Button variant="primary" type="submit" form="admin-create-customer" loading={saving}>Crear usuario</Button>
        </>
      )}
    >
      {access ? (
        <div className="admin-access-created">
          <span className="admin-access-created__mark"><Icon name="check" size={22} /></span>
          <div className="admin-access-created__identity">
            <b>{access.customer.club?.name}</b>
            <p>{access.customer.display_name}</p>
          </div>
          <div className="admin-access-created__credentials">
            <label>Email</label>
            <CopyValue value={access.email} label="email" />
            <label>Contraseña inicial</label>
            <CopyValue value={access.password} label="contraseña" masked />
          </div>
          <Banner tone="info" title="Guardá estos accesos">La contraseña no vuelve a mostrarse después de cerrar esta ventana.</Banner>
        </div>
      ) : (
        <form id="admin-create-customer" className="admin-create-form" onSubmit={submit} noValidate>
          <div className="admin-create-form__grid">
            <TextField label="Nombre del titular" value={displayName} onChange={(event) => setDisplayName(event.target.value)} autoComplete="name" required minLength={2} />
            <TextField label="Email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="off" required />
            <TextField label="Club" value={clubName} onChange={(event) => setClubName(event.target.value)} required minLength={2} />
            <TextField label="Ciudad" value={city} onChange={(event) => setCity(event.target.value)} />
          </div>
          <div className="admin-create-form__password">
            <TextField label="Contraseña inicial" type="password" passwordReveal value={password} onChange={(event) => setPassword(event.target.value)} required minLength={10} />
            <button type="button" className="admin-password-generate" onClick={() => setPassword(securePassword())}>
              <Icon name="refresh" size={14} /> Generar otra
            </button>
          </div>
          {error ? <Banner tone="error" title="No pudimos crear el usuario">{error}</Banner> : null}
        </form>
      )}
    </Dialog>
  );
}
