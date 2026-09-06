import { useState } from 'react';
import { Button, Dialog, SelectField, TextField } from '@courtvision/design-system';
import type { NewCourtPayload } from '../../app/useOwnerConsole';
import { goToCourt } from '../../app/routes';

type Step = 'court' | 'camera';
export const TAPO_STREAM_PATH = '/stream1';

const EMPTY = {
  name: '', sport: 'padel' as const, detection: 'arms_up' as const,
  cameraName: '', host: '', port: '554', username: '', password: '', path: TAPO_STREAM_PATH,
};

/**
 * Alta de cancha en dos pasos: primero la cancha, después la cámara que la
 * cubre. Antes era un formulario que se desplegaba en medio de la grilla y
 * pedía las nueve cosas a la vez; separarlo deja claro qué dato falta y por qué.
 */
export function NewCourtDialog({
  open,
  onClose,
  onCreate,
}: { open: boolean; onClose: () => void; onCreate: (payload: NewCourtPayload) => Promise<{ id: string } | null> }) {
  const [step, setStep] = useState<Step>('court');
  const [form, setForm] = useState({ ...EMPTY, sport: 'padel' as 'padel' | 'football', detection: 'arms_up' as 'arms_up' | 'manual' });
  const [saving, setSaving] = useState(false);
  const [touched, setTouched] = useState(false);

  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) => setForm((current) => ({ ...current, [key]: value }));

  const close = () => {
    setForm({ ...EMPTY, sport: 'padel', detection: 'arms_up' });
    setStep('court');
    setTouched(false);
    onClose();
  };

  const courtValid = form.name.trim().length > 0;
  const cameraValid = form.cameraName.trim().length > 0 && form.host.trim().length > 0 && form.path.trim().length > 0;

  const submit = async () => {
    setTouched(true);
    if (!courtValid || !cameraValid) return;
    setSaving(true);
    const created = await onCreate({
      name: form.name.trim(),
      sport_code: form.sport,
      detection_mode: form.detection,
      camera_name: form.cameraName.trim(),
      camera_host: form.host.trim(),
      camera_rtsp_port: Number(form.port) || 554,
      camera_username: form.username.trim() || undefined,
      camera_password: form.password || undefined,
      camera_stream_path: form.path.trim(),
    });
    setSaving(false);
    if (!created) return;
    close();
    // Se abre la cancha recién creada: todavía falta vincular el equipo local,
    // y ese es el próximo paso real del operador.
    goToCourt(created.id);
  };

  return (
    <Dialog
      open={open}
      onClose={close}
      size="md"
      title="Nueva cancha"
      description={step === 'court' ? 'Paso 1 de 2 · Identidad de la cancha' : 'Paso 2 de 2 · Cámara que la cubre'}
      footer={
        step === 'court' ? (
          <>
            <Button variant="ghost" onClick={close}>Cancelar</Button>
            <Button
              variant="primary"
              iconAfter="arrowRight"
              disabled={!courtValid}
              onClick={() => {
                // La cámara hereda el nombre de la cancha: es el valor que el
                // club usa el 90% de las veces y evita retipearlo.
                if (!form.cameraName.trim()) set('cameraName', `${form.name.trim()} · Cámara`);
                setStep('camera');
              }}
            >
              Continuar
            </Button>
          </>
        ) : (
          <>
            <Button variant="ghost" iconBefore="arrowLeft" onClick={() => setStep('court')}>Volver</Button>
            <Button variant="primary" loading={saving} onClick={() => void submit()}>Crear cancha</Button>
          </>
        )
      }
    >
      <ol className="wizard-steps" aria-label="Progreso del alta">
        <li className={step === 'court' ? 'is-current' : 'is-done'}><span>1</span> Cancha</li>
        <li className={step === 'camera' ? 'is-current' : ''}><span>2</span> Cámara</li>
      </ol>

      {step === 'court' ? (
        <div className="form-grid">
          <TextField
            label="Nombre de la cancha"
            autoFocus
            value={form.name}
            onChange={(event) => set('name', event.target.value)}
            placeholder="Cancha 05"
            error={touched && !courtValid ? 'Poné un nombre para identificarla.' : undefined}
            className="form-grid__wide"
          />
          <SelectField label="Deporte" value={form.sport} onChange={(event) => set('sport', event.target.value as 'padel' | 'football')}>
            <option value="padel">Pádel</option>
            <option value="football">Fútbol</option>
          </SelectField>
          <SelectField
            label="Cómo se marca un momento"
            value={form.detection}
            onChange={(event) => set('detection', event.target.value as 'arms_up' | 'manual')}
            hint={form.detection === 'arms_up' ? 'La cámara reconoce el gesto de brazos arriba.' : 'Solo con el botón físico de la cancha.'}
          >
            <option value="arms_up">Brazos arriba</option>
            <option value="manual">Botón manual</option>
          </SelectField>
        </div>
      ) : (
        <div className="form-grid">
          <p className="form-note form-grid__wide">
            Con estos datos el equipo local se conecta al stream RTSP de la cámara.
            La contraseña se guarda cifrada y no vuelve a mostrarse.
          </p>
          <TextField
            label="Nombre de la cámara"
            autoFocus
            value={form.cameraName}
            onChange={(event) => set('cameraName', event.target.value)}
            placeholder={form.name ? `${form.name} · Cámara` : 'Cámara fija'}
            error={touched && !form.cameraName.trim() ? 'Requerido' : undefined}
            className="form-grid__wide"
          />
          <TextField
            label="Host o IP"
            value={form.host}
            onChange={(event) => set('host', event.target.value)}
            placeholder="192.168.1.40"
            error={touched && !form.host.trim() ? 'Requerido' : undefined}
          />
          <TextField
            label="Puerto RTSP"
            inputMode="numeric"
            value={form.port}
            onChange={(event) => set('port', event.target.value)}
            placeholder="554"
          />
          <TextField
            label="Ruta del stream"
            value={form.path}
            onChange={(event) => set('path', event.target.value)}
            placeholder="/Streaming/Channels/101"
            error={touched && !form.path.trim() ? 'Requerido' : undefined}
            className="form-grid__wide"
          />
          <TextField label="Usuario" value={form.username} onChange={(event) => set('username', event.target.value)} autoComplete="off" />
          <TextField label="Contraseña" type="password" value={form.password} onChange={(event) => set('password', event.target.value)} autoComplete="new-password" />
        </div>
      )}
    </Dialog>
  );
}
