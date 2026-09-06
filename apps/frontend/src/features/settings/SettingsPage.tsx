import { useEffect, useRef, useState } from 'react';
import { Avatar, Button, Icon, SelectField, TextField } from '@courtvision/design-system';
import { initialsOf } from '../../lib/court';
import type { OwnerConsole } from '../../app/useOwnerConsole';
import { connectOwnerWhatsApp, disconnectOwnerWhatsApp, getOwnerWhatsApp } from '../../lib/api';
import type { OwnerProfile, WhatsAppConnection } from '../../lib/api';

const TIMEZONES = [
  { value: 'America/Argentina/Buenos_Aires', label: 'Argentina · Buenos Aires' },
  { value: 'America/Sao_Paulo', label: 'Brasil · São Paulo' },
  { value: 'America/Mexico_City', label: 'México · Ciudad de México' },
];

const LOGO_INPUT_LIMIT = 5 * 1024 * 1024;
const LOGO_DATA_LIMIT = 700_000;
const LOGO_TYPES = ['image/png', 'image/jpeg', 'image/webp'];

async function optimizeLogo(file: File): Promise<string> {
  if (!LOGO_TYPES.includes(file.type)) throw new Error('Elegí una imagen PNG, JPG o WebP.');
  if (file.size > LOGO_INPUT_LIMIT) throw new Error('La imagen supera el máximo de 5 MB.');

  const objectUrl = URL.createObjectURL(file);
  try {
    const image = new Image();
    image.decoding = 'async';
    image.src = objectUrl;
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve();
      image.onerror = () => reject(new Error('No pudimos leer esa imagen.'));
    });

    const maxEdge = 512;
    const scale = Math.min(1, maxEdge / Math.max(image.naturalWidth, image.naturalHeight));
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
    canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
    const context = canvas.getContext('2d');
    if (!context) throw new Error('No pudimos preparar el logo.');
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    const dataUrl = canvas.toDataURL('image/webp', 0.88);
    if (dataUrl.length > LOGO_DATA_LIMIT) throw new Error('La imagen es demasiado compleja. Probá con una versión más liviana.');
    return dataUrl;
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

/**
 * Configuración: club y cuenta. Los botones de guardar sólo se habilitan si
 * algo cambió, así el operador sabe si tiene trabajo pendiente en la pantalla.
 */
export function SettingsPage({ console: data }: { console: OwnerConsole }) {
  return (
    <div className="page page-enter settings">
      <ClubSection console={data} />
      <WhatsAppSection console={data} />
      {data.profile ? <AccountSection console={data} profile={data.profile} /> : null}
    </div>
  );
}

function WhatsAppSection({ console: data }: { console: OwnerConsole }) {
  const [connection, setConnection] = useState<WhatsAppConnection | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const refresh = async () => {
    try {
      const next = await getOwnerWhatsApp(data.ownerToken);
      setConnection((current) => mergeWhatsAppPairing(current, next));
      setError('');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'No pudimos consultar WhatsApp.');
    }
  };

  useEffect(() => { void refresh(); }, [data.ownerToken]);
  useEffect(() => {
    if (connection?.status !== 'connecting') return undefined;
    const interval = window.setInterval(() => void refresh(), 3000);
    return () => window.clearInterval(interval);
  }, [connection?.status, data.ownerToken]);

  const connect = async () => {
    setBusy(true);
    setError('');
    try {
      setConnection(await connectOwnerWhatsApp(data.ownerToken));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'No pudimos generar el QR.');
    } finally {
      setBusy(false);
    }
  };

  const disconnect = async () => {
    setBusy(true);
    try {
      setConnection(await disconnectOwnerWhatsApp(data.ownerToken));
      data.announce('success', 'WhatsApp desconectado.');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'No pudimos desconectar WhatsApp.');
    } finally {
      setBusy(false);
    }
  };

  const status = connection?.status ?? 'loading';
  return (
    <section className="card whatsapp-connect" aria-labelledby="st-whatsapp">
      <header className="card__head">
        <div>
          <h2 className="t-heading" id="st-whatsapp">WhatsApp</h2>
          <p>Entrega automática de highlights</p>
        </div>
        <span className={`whatsapp-connect__status whatsapp-connect__status--${status}`}>
          <i aria-hidden="true" />
          {status === 'connected' ? 'Conectado' : status === 'connecting' ? 'Esperando escaneo' : status === 'unavailable' ? 'No disponible' : status === 'loading' ? 'Consultando…' : 'Sin conectar'}
        </span>
      </header>

      <div className="whatsapp-connect__body card__pad">
        <div className="whatsapp-connect__intro">
          <span className="whatsapp-connect__mark" aria-hidden="true"><Icon name="whatsapp" size={24} /></span>
          <div>
            <b>{status === 'connected' ? connection?.profile_name || 'Cuenta vinculada' : 'Conectá el WhatsApp del club'}</b>
            <p>{status === 'connected' ? connection?.phone || 'La cuenta está lista para enviar videos.' : 'Escaneá una vez desde el teléfono que enviará los highlights.'}</p>
          </div>
        </div>

        {connection?.qr_base64 && status === 'connecting' ? (
          <div className="whatsapp-connect__pairing">
            <div className="whatsapp-connect__qr">
              <img src={connection.qr_base64} alt="Código QR para vincular WhatsApp" />
            </div>
            <div className="whatsapp-connect__steps">
              <span>01</span><p>Abrí WhatsApp en el teléfono.</p>
              <span>02</span><p>Entrá en Dispositivos vinculados.</p>
              <span>03</span><p>Escaneá este código.</p>
              {connection.pairing_code ? <small>Código alternativo: <b>{connection.pairing_code}</b></small> : null}
            </div>
          </div>
        ) : null}

        {error ? <div className="whatsapp-connect__error"><Icon name="warning" size={15} />{error}</div> : null}

        <div className="config-actions">
          {status === 'connected' ? (
            <Button variant="danger" size="sm" loading={busy} onClick={() => void disconnect()}>Desconectar</Button>
          ) : (
            <Button variant="primary" size="sm" iconBefore="qr" loading={busy} disabled={status === 'unavailable'} onClick={() => void connect()}>
              {status === 'connecting' ? 'Generar otro QR' : 'Conectar WhatsApp'}
            </Button>
          )}
          {status === 'connecting' ? <Button variant="secondary" size="sm" iconBefore="refresh" onClick={() => void refresh()}>Comprobar</Button> : null}
        </div>
      </div>
    </section>
  );
}

export function mergeWhatsAppPairing(
  current: WhatsAppConnection | null,
  next: WhatsAppConnection,
): WhatsAppConnection {
  if (next.status !== 'connecting' || next.qr_base64 || current?.status !== 'connecting') return next;
  return {
    ...next,
    qr_base64: current.qr_base64,
    pairing_code: current.pairing_code,
  };
}

function ClubSection({ console: data }: { console: OwnerConsole }) {
  const club = data.dashboard?.club;
  const [name, setName] = useState(club?.name ?? '');
  const [city, setCity] = useState(club?.city ?? '');
  const [logoDataUrl, setLogoDataUrl] = useState(club?.logo_data_url ?? '');
  const [logoError, setLogoError] = useState('');
  const [processingLogo, setProcessingLogo] = useState(false);
  const [saving, setSaving] = useState(false);
  const logoInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setName(club?.name ?? '');
    setCity(club?.city ?? '');
    setLogoDataUrl(club?.logo_data_url ?? '');
  }, [club?.name, club?.city, club?.logo_data_url]);

  const dirty = name !== (club?.name ?? '') || city !== (club?.city ?? '') || logoDataUrl !== (club?.logo_data_url ?? '');
  const clubInitial = (name.trim() || club?.name?.trim() || 'C').charAt(0).toUpperCase();

  const chooseLogo = async (file: File | undefined) => {
    if (!file) return;
    setProcessingLogo(true);
    setLogoError('');
    try {
      setLogoDataUrl(await optimizeLogo(file));
    } catch (error) {
      setLogoError(error instanceof Error ? error.message : 'No pudimos preparar el logo.');
    } finally {
      setProcessingLogo(false);
      if (logoInput.current) logoInput.current.value = '';
    }
  };

  return (
    <section className="card" aria-labelledby="st-club">
      <header className="card__head">
        <div>
          <h2 className="t-heading" id="st-club">Club</h2>
          <p>{club ? `${club.fields_count} canchas configuradas` : 'Datos del club'}</p>
        </div>
      </header>
      <div className="config-block card__pad">
        <div className="club-branding">
          <div className={`club-branding__preview ${logoDataUrl ? 'has-image' : ''}`} aria-label={logoDataUrl ? 'Vista previa del logo' : 'Logo pendiente'}>
            {logoDataUrl ? <img src={logoDataUrl} alt="Vista previa del logo del club" /> : <span>{clubInitial}</span>}
          </div>
          <div className="club-branding__body">
            <div>
              <b>Logo del club</b>
              <p>Se muestra en la navegación del dashboard. PNG, JPG o WebP, hasta 5 MB.</p>
            </div>
            <div className="club-branding__actions">
              <input
                ref={logoInput}
                className="u-visually-hidden"
                type="file"
                accept="image/png,image/jpeg,image/webp"
                aria-label="Elegir logo del club"
                onChange={(event) => void chooseLogo(event.target.files?.[0])}
              />
              <Button type="button" variant="secondary" size="sm" iconBefore="imageUpload" loading={processingLogo} onClick={() => logoInput.current?.click()}>
                {logoDataUrl ? 'Cambiar logo' : 'Subir logo'}
              </Button>
              {logoDataUrl ? <Button type="button" variant="ghost" size="sm" onClick={() => { setLogoDataUrl(''); setLogoError(''); }}>Quitar</Button> : null}
            </div>
            {logoError ? <p className="club-branding__error"><Icon name="warning" size={14} />{logoError}</p> : null}
          </div>
        </div>

        <div className="config-row">
          <TextField label="Nombre del club" value={name} onChange={(event) => setName(event.target.value)} placeholder="Club Central" />
          <TextField label="Ciudad" value={city} onChange={(event) => setCity(event.target.value)} placeholder="Buenos Aires" />
        </div>
        <div className="config-actions">
          {dirty ? <Button variant="ghost" size="sm" onClick={() => { setName(club?.name ?? ''); setCity(club?.city ?? ''); setLogoDataUrl(club?.logo_data_url ?? ''); setLogoError(''); }}>Descartar</Button> : <span />}
          <Button
            variant="primary"
            size="sm"
            disabled={!dirty || !name.trim() || processingLogo}
            loading={saving}
            onClick={async () => { setSaving(true); await data.actions.saveClub({ name: name.trim(), city: city.trim(), logo_data_url: logoDataUrl }); setSaving(false); }}
          >
            Guardar club
          </Button>
        </div>
      </div>
    </section>
  );
}

function AccountSection({ console: data, profile }: { console: OwnerConsole; profile: OwnerProfile }) {
  const [displayName, setDisplayName] = useState(profile.display_name);
  const [phone, setPhone] = useState(profile.phone);
  const [timezone, setTimezone] = useState(profile.timezone);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setDisplayName(profile.display_name);
    setPhone(profile.phone);
    setTimezone(profile.timezone);
  }, [profile]);

  const dirty = displayName !== profile.display_name || phone !== profile.phone || timezone !== profile.timezone;

  return (
    <section className="card" aria-labelledby="st-account">
      <header className="card__head">
        <div>
          <h2 className="t-heading" id="st-account">Cuenta</h2>
          <p>Datos de acceso y avisos</p>
        </div>
      </header>
      <div className="config-block card__pad">
        <div className="account-identity">
          <Avatar initials={initialsOf(displayName || profile.display_name)} />
          <div>
            <b>{displayName || profile.display_name}</b>
            <span className="t-meta">{profile.email} <i aria-hidden="true">·</i> {profile.role}</span>
          </div>
        </div>

        <div className="config-row">
          <TextField label="Nombre visible" value={displayName} onChange={(event) => setDisplayName(event.target.value)} />
          <TextField label="Email de acceso" value={profile.email} disabled hint="No se puede cambiar desde acá." />
          <TextField
            label="WhatsApp operativo"
            inputMode="tel"
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
            hint="A este número llegan los avisos del club."
          />
          <SelectField label="Zona horaria" value={timezone} onChange={(event) => setTimezone(event.target.value)} hint="Define los horarios de partidos y momentos.">
            {TIMEZONES.map((zone) => <option key={zone.value} value={zone.value}>{zone.label}</option>)}
          </SelectField>
        </div>

        <div className="config-actions">
          {dirty ? (
            <Button variant="ghost" size="sm" onClick={() => { setDisplayName(profile.display_name); setPhone(profile.phone); setTimezone(profile.timezone); }}>Descartar</Button>
          ) : <span />}
          <Button
            variant="primary"
            size="sm"
            disabled={!dirty || !displayName.trim()}
            loading={saving}
            onClick={async () => {
              setSaving(true);
              await data.actions.saveProfile({ display_name: displayName.trim(), phone: phone.trim(), timezone });
              setSaving(false);
            }}
          >
            Guardar cambios
          </Button>
        </div>
      </div>
    </section>
  );
}
