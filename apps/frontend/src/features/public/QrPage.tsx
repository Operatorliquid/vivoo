import { useEffect, useState } from 'react';
import { Button, Icon, StatusPill, TextField } from '@courtvision/design-system';
import { VivooLogo } from '../../components/Brand';
import { getFieldContext, startSession } from '../../lib/api';
import type { SessionResponse } from '../../lib/api';
import { normalizeWhatsAppPhone } from '../../lib/phone';
import { goToView, pushPath } from '../../app/routes';

type Step = 'welcome' | 'form' | 'ready';

/**
 * Acceso del jugador desde el QR de la cancha.
 *
 * Superficie clara y una sola acción por pantalla: se usa al aire libre, con
 * sol, de pie y en treinta segundos. Es deliberadamente lo opuesto a la consola
 * del club, que es densa y se lee en interiores.
 */
export function QrPage() {
  const fieldToken = new URLSearchParams(window.location.search).get('field') ?? '';
  const requestStorageKey = `courtvision:qr-registration:${fieldToken}`;
  const createRequestId = () => (typeof crypto.randomUUID === 'function' ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`);
  const [requestId, setRequestId] = useState(() => {
    const stored = window.sessionStorage.getItem(requestStorageKey);
    if (stored) return stored;
    const created = createRequestId();
    window.sessionStorage.setItem(requestStorageKey, created);
    return created;
  });
  const [step, setStep] = useState<Step>('welcome');
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [fieldName, setFieldName] = useState('');
  const [fieldStatus, setFieldStatus] = useState<'active' | 'inactive' | 'maintenance'>('active');
  const [cameraStatus, setCameraStatus] = useState<'live' | 'ready' | 'offline'>('live');
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [recordingStatus, setRecordingStatus] = useState<'idle' | 'starting' | 'recording' | 'stopping'>('idle');
  const [messagingConsent, setMessagingConsent] = useState(true);
  const [apiError, setApiError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!fieldToken) {
      setApiError('Este enlace no identifica una cancha. Escaneá nuevamente el QR del club.');
      setLoaded(true);
      return;
    }
    let disposed = false;
    const refreshContext = async (initial = false) => {
      try {
        const context = await getFieldContext(fieldToken);
        if (disposed) return;
        setFieldName(context.field_name);
        setFieldStatus(context.status);
        setCameraStatus(context.camera_status);
        setActiveSessionId(context.active_session_id);
        setRecordingStatus(context.recording_status);
        setApiError('');
      } catch {
        if (initial && !disposed) setApiError('No pudimos leer el estado de esta cancha. Avisale al personal del club.');
      } finally {
        if (initial && !disposed) setLoaded(true);
      }
    };
    void refreshContext(true);
    const interval = window.setInterval(() => { void refreshContext(); }, 3000);
    return () => {
      disposed = true;
      window.clearInterval(interval);
    };
  }, [fieldToken]);

  const available = Boolean(fieldToken) && !apiError && fieldStatus === 'active' && cameraStatus !== 'offline';
  const phoneDigits = phone.replace(/\D/g, '');
  const normalizedPhone = normalizeWhatsAppPhone(phone);
  const formValid = name.trim().length > 1 && /^\+[1-9][0-9]{7,14}$/.test(normalizedPhone);
  const recordingCopy = {
    idle: { title: `${fieldName || 'La cancha'} está lista`, detail: 'La grabación comienza cuando completes el registro.', pill: 'En espera', state: 'ready' as const },
    starting: { title: `${fieldName || 'La cancha'} está iniciando`, detail: 'El equipo local está preparando la grabación.', pill: 'Iniciando', state: 'ready' as const },
    recording: { title: `${fieldName || 'La cancha'} está grabando`, detail: 'La grabación está activa.', pill: 'Grabando', state: 'live' as const },
    stopping: { title: `${fieldName || 'La cancha'} está finalizando`, detail: 'El partido anterior se está guardando.', pill: 'Finalizando', state: 'ready' as const },
  }[recordingStatus];
  const currentSessionRecording = Boolean(session && activeSessionId === session.session_id && recordingStatus === 'recording');
  const currentSessionStarting = Boolean(session && activeSessionId === session.session_id && recordingStatus === 'starting');

  const handleStart = async () => {
    if (!fieldToken) return;
    setSubmitting(true);
    setApiError('');
    try {
      const result = await startSession(fieldToken, {
        display_name: name.trim(),
        phone_e164: normalizedPhone,
        recording_consent: true,
        messaging_consent: messagingConsent,
      }, requestId);
      window.sessionStorage.removeItem(requestStorageKey);
      setSession(result);
      setStep('ready');
    } catch (error) {
      setApiError(error instanceof Error ? error.message : 'No pudimos registrar el partido.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="public">
      <header className="public__bar">
        <span className="public__brand"><VivooLogo /></span>
        <button className="public__owner" type="button" onClick={() => goToView('owner')}>
          Soy del club <Icon name="arrowRight" size={14} />
        </button>
      </header>

      <main className="public__stage">
        <section className="public__card page-enter">
          <ol className="public__progress" aria-label="Progreso">
            <li className={step === 'welcome' ? 'is-current' : 'is-done'} />
            <li className={step === 'form' ? 'is-current' : step === 'ready' ? 'is-done' : ''} />
            <li className={step === 'ready' ? 'is-current' : ''} />
          </ol>

          {step === 'welcome' ? (
            <>
              <h1 className="t-display">Jugá.<br />Nosotros grabamos.</h1>
              <p className="public__lead">
                Guardamos tus mejores jugadas y te las mandamos por WhatsApp cuando termina el partido.
                Sin instalar nada.
              </p>

              <div className={`court-state court-state--${available ? recordingCopy.state : 'offline'}`}>
                <span className="court-state__mark" aria-hidden="true"><Icon name="camera" size={18} /></span>
                <div>
                  <b>
                    {!loaded ? 'Consultando la cancha…'
                      : !available ? `${fieldName || 'La cancha'} no está disponible`
                      : recordingCopy.title}
                  </b>
                  <small>
                    {!loaded ? 'Un segundo.' : available ? recordingCopy.detail : 'Consultá con el personal del club.'}
                  </small>
                </div>
                {loaded ? (
                  <StatusPill state={available ? recordingCopy.state : 'offline'} pulse={available && recordingStatus === 'recording'}>
                    {available ? recordingCopy.pill : 'Sin señal'}
                  </StatusPill>
                ) : null}
              </div>

              {apiError ? <p className="public__error" role="alert">{apiError}</p> : null}

              <Button variant="primary" disabled={!available || !loaded} iconAfter="arrowRight" onClick={() => setStep('form')}>
                {available ? 'Entrar al partido' : 'Cancha no disponible'}
              </Button>
              <p className="public__fine"><Icon name="check" size={13} /> Sin app, sin contraseña. Tus videos son privados.</p>
            </>
          ) : null}

          {step === 'form' ? (
            <>
              <button className="public__back" onClick={() => setStep('welcome')}><Icon name="arrowLeft" size={15} /> Volver</button>
              <h1 className="t-display">¿A quién se lo mandamos?</h1>
              <p className="public__lead">Solo esto para asociar tus momentos al partido de {fieldName || 'la cancha'}.</p>

              <div className="public__form">
                <TextField label="Tu nombre" autoFocus value={name} onChange={(event) => setName(event.target.value)} placeholder="Martín" />
                <TextField
                  label="Tu WhatsApp"
                  inputMode="tel"
                  value={phone}
                  onChange={(event) => setPhone(event.target.value)}
                  placeholder="+54 9 11 5555 5555"
                  hint={phoneDigits.length >= 8 ? `Se enviará a ${normalizedPhone}` : 'Podés ingresar tu número argentino sin prefijo.'}
                />
                <label className="public__check">
                  <input type="checkbox" checked={messagingConsent} onChange={(event) => setMessagingConsent(event.target.checked)} />
                  <span>Entiendo que el video es privado y acepto recibir mis momentos por WhatsApp.</span>
                </label>
              </div>

              {apiError ? <p className="public__error" role="alert">{apiError}</p> : null}

              <Button variant="primary" disabled={!formValid} loading={submitting} iconAfter="arrowRight" onClick={() => void handleStart()}>
                Confirmar y jugar
              </Button>
              <p className="public__fine"><Icon name="check" size={13} /> Podés pedir que borremos tus videos cuando quieras.</p>
            </>
          ) : null}

          {step === 'ready' ? (
            <>
              <span className="public__seal" aria-hidden="true"><Icon name="check" size={24} /></span>
              <h1 className="t-display">Listo, {name.split(' ')[0]}.</h1>
              <p className="public__lead">
                {currentSessionRecording
                  ? `La grabación está activa en ${fieldName}. Levantá los brazos frente a la cámara para guardar los 30 segundos anteriores.`
                  : currentSessionStarting
                    ? `Estamos iniciando la grabación en ${fieldName}. En unos segundos vas a poder marcar tus jugadas levantando los brazos.`
                    : 'Tu partido quedó registrado. El equipo local está confirmando el estado de la grabación.'}
              </p>
              <div className="public__code">
                <span className="t-label">Tu código de jugador</span>
                <strong>CV-{session ? session.session_id.slice(0, 4).toUpperCase() : '----'}</strong>
                <small>Te escribimos al WhatsApp que registraste.</small>
              </div>
              <Button
                variant="primary"
                iconBefore="play"
                disabled={!session?.access_token}
                onClick={() => session?.access_token && pushPath(`/player?access=${encodeURIComponent(session.access_token)}`)}
              >
                Ver mi partido
              </Button>
              <button className="public__link" onClick={() => {
                const nextRequestId = createRequestId();
                window.sessionStorage.setItem(requestStorageKey, nextRequestId);
                setRequestId(nextRequestId);
                setStep('welcome');
                setSession(null);
                setName('');
                setPhone('');
              }}>
                Registrar otro jugador
              </button>
            </>
          ) : null}
        </section>
      </main>
    </div>
  );
}
