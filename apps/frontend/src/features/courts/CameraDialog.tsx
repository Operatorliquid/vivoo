import { useEffect, useState } from 'react';
import { Button, Dialog, TextField } from '@courtvision/design-system';
import type { OwnerCamera, OwnerField } from '../../lib/api';
import type { CameraPatch, CameraPayload } from '../../app/useOwnerConsole';
import { TAPO_STREAM_PATH } from './NewCourtDialog';

/**
 * Alta y edición de la cámara de una cancha. Mismo formulario para los dos
 * casos: sólo cambia el título y el verbo de la acción.
 */
export function CameraDialog({
  open,
  field,
  camera,
  onClose,
  onCreate,
  onUpdate,
}: {
  open: boolean;
  field: OwnerField;
  camera: OwnerCamera | null;
  onClose: () => void;
  onCreate: (payload: CameraPayload) => Promise<unknown>;
  onUpdate: (cameraId: string, payload: CameraPatch) => Promise<boolean>;
}) {
  const [form, setForm] = useState(() => initial(field, camera));
  const [touched, setTouched] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => { if (open) { setForm(initial(field, camera)); setTouched(false); } }, [open, field, camera]);

  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) => setForm((current) => ({ ...current, [key]: value }));
  const valid = form.name.trim() && form.host.trim() && form.path.trim();

  const submit = async () => {
    setTouched(true);
    if (!valid) return;
    setSaving(true);
    const payload = {
      name: form.name.trim(),
      serial_number: form.serial.trim() || undefined,
      host: form.host.trim(),
      rtsp_port: Number(form.port) || 554,
      username: form.username.trim() || undefined,
      password: form.password || undefined,
      stream_path: form.path.trim(),
    };
    const done = camera ? await onUpdate(camera.id, payload) : await onCreate({ field_id: field.id, ...payload });
    setSaving(false);
    if (done) onClose();
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={camera ? 'Editar cámara' : 'Asignar cámara'}
      description={`${field.name} · conexión RTSP del equipo local`}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button variant="primary" loading={saving} onClick={() => void submit()}>{camera ? 'Guardar cámara' : 'Asignar cámara'}</Button>
        </>
      }
    >
      <div className="form-grid">
        <TextField
          label="Nombre de la cámara"
          autoFocus
          value={form.name}
          onChange={(event) => set('name', event.target.value)}
          error={touched && !form.name.trim() ? 'Requerido' : undefined}
          className="form-grid__wide"
        />
        <TextField label="Host o IP" value={form.host} onChange={(event) => set('host', event.target.value)} placeholder="192.168.1.40" error={touched && !form.host.trim() ? 'Requerido' : undefined} />
        <TextField label="Puerto RTSP" inputMode="numeric" value={form.port} onChange={(event) => set('port', event.target.value)} />
        <TextField
          label="Ruta del stream"
          value={form.path}
          onChange={(event) => set('path', event.target.value)}
          placeholder="/Streaming/Channels/101"
          error={touched && !form.path.trim() ? 'Requerido' : undefined}
          className="form-grid__wide"
        />
        <TextField label="Usuario" value={form.username} onChange={(event) => set('username', event.target.value)} autoComplete="off" />
        <TextField
          label="Contraseña"
          type="password"
          value={form.password}
          onChange={(event) => set('password', event.target.value)}
          autoComplete="new-password"
          hint={camera?.password_configured ? 'Ya hay una guardada. Dejala vacía para no cambiarla.' : undefined}
        />
        <TextField label="Número de serie" value={form.serial} onChange={(event) => set('serial', event.target.value)} hint="Opcional. Ayuda a identificar el equipo en el club." className="form-grid__wide" />
      </div>
    </Dialog>
  );
}

function initial(field: OwnerField, camera: OwnerCamera | null) {
  return {
    name: camera?.name ?? `${field.name} · Cámara`,
    serial: camera?.serial_number ?? '',
    host: camera?.host ?? '',
    port: String(camera?.rtsp_port ?? 554),
    username: camera?.username ?? '',
    password: '',
    path: camera?.stream_path || TAPO_STREAM_PATH,
  };
}
