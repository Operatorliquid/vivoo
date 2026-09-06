import { useEffect, useMemo, useState } from 'react';
import { Button, Dialog, EmptyState, Icon, SelectField, StatusPill, TextField } from '@courtvision/design-system';
import { CopyValue } from '../../components/CopyValue';
import { CameraPreview, CloudCameraStatus } from './CameraPreview';
import { AgentPairing } from './AgentPairing';
import { CameraDialog } from './CameraDialog';
import { DetectorCalibration } from './DetectorCalibration';
import { CourtQrCard } from './CourtQrCard';
import { cameraEndpoint, courtState, courtStateLabel, courtStateReason, sportLabel } from '../../lib/court';
import { getDesktopRuntime, publicAppOrigin } from '../../lib/api';
import { goToSection } from '../../app/routes';
import type { OwnerConsole } from '../../app/useOwnerConsole';
import type { OwnerField } from '../../lib/api';

/**
 * Detalle de cancha — todo lo que hace falta para que esa cancha capture.
 *
 * A la izquierda, lo que se mira: la imagen de la cámara y su vínculo con el
 * equipo local. A la derecha, lo que se configura, agrupado por decisión y con
 * la acción destructiva separada al final.
 */
export function CourtDetailPage({
  console: data,
  field,
  ownerToken,
}: { console: OwnerConsole; field: OwnerField; ownerToken: string }) {
  const camera = data.cameras.find((item) => item.field_id === field.id) ?? field.camera ?? null;
  const state = courtState(field);
  const reason = courtStateReason(field);
  const endpoint = cameraEndpoint(camera);

  const [pending, setPending] = useState<string | null>(null);
  const [name, setName] = useState(field.name);
  const [deviceId, setDeviceId] = useState(field.button?.device_id ?? '');
  const [secret, setSecret] = useState('');
  const [cameraOpen, setCameraOpen] = useState(false);
  const [liveOpen, setLiveOpen] = useState(false);
  const [deleteCourtOpen, setDeleteCourtOpen] = useState(false);
  const [deleteCameraOpen, setDeleteCameraOpen] = useState(false);
  const [stopRecordingOpen, setStopRecordingOpen] = useState(false);
  const [calibrationOpen, setCalibrationOpen] = useState(false);
  const [savingButton, setSavingButton] = useState(false);
  const [qrOrigin, setQrOrigin] = useState(window.location.origin);
  const [desktopAvailable, setDesktopAvailable] = useState(false);

  useEffect(() => { setName(field.name); }, [field.id, field.name]);
  useEffect(() => { setDeviceId(field.button?.device_id ?? ''); }, [field.id, field.button?.device_id]);
  useEffect(() => { void publicAppOrigin().then(setQrOrigin); }, []);
  useEffect(() => { void getDesktopRuntime().then((runtime) => setDesktopAvailable(Boolean(runtime))); }, []);

  const nameDirty = name.trim() !== field.name && name.trim().length > 0;
  const qrLink = useMemo(() => `${qrOrigin}${field.qr_url}`, [field.qr_url, qrOrigin]);
  const recording = field.recording ?? { status: 'idle', session_id: null, started_at: null, started_by: null };
  const recordingActive = recording.status !== 'idle';
  const recordingState = recording.status === 'recording' ? 'live' : recording.status === 'idle' ? 'ready' : 'ready';
  const recordingLabel = { idle: 'En espera', starting: 'Iniciando', recording: 'Grabando', stopping: 'Finalizando' }[recording.status];

  const apply = async (key: string, patch: Parameters<OwnerConsole['actions']['saveField']>[1]) => {
    setPending(key);
    await data.actions.saveField(field.id, patch);
    setPending(null);
  };

  return (
    <div className="page page-enter court-detail">
      <section className={`court-hero court-hero--${state}`}>
        <span className="court-hero__keyline" aria-hidden="true" />
        <div className="court-hero__text">
          <StatusPill state={state}>{courtStateLabel(field)}</StatusPill>
          {reason ? <p className="court-hero__reason">{reason}</p> : null}
          <span className="t-meta">
            {sportLabel(field.sport_code)} <i aria-hidden="true">·</i> {field.last_seen}
            {endpoint ? <> <i aria-hidden="true">·</i> {endpoint}</> : null}
          </span>
        </div>
        <div className="court-hero__actions">
          <Button variant="secondary" size="sm" iconBefore="qr" onClick={() => void copy(qrLink, data, `Enlace de ${field.name} copiado.`)}>Copiar enlace</Button>
          {camera && desktopAvailable ? <Button variant="secondary" size="sm" iconBefore="play" onClick={() => setLiveOpen(true)}>Ver en vivo</Button> : null}
        </div>
      </section>

      <div className="detail-grid">
        <div className="detail-col">
          <section className="card" aria-labelledby="cd-camera">
            <header className="card__head">
              <div>
                <h2 className="t-heading" id="cd-camera">Cámara</h2>
                <p>{desktopAvailable ? 'Señal local de la cancha' : 'Estado informado por el equipo de la cancha'}</p>
              </div>
              {camera
                ? <Button size="sm" variant="secondary" onClick={() => setCameraOpen(true)}>Editar conexión</Button>
                : <Button size="sm" variant="primary" iconBefore="plus" onClick={() => setCameraOpen(true)}>Asignar cámara</Button>}
            </header>
            <div className="card__pad">
            {camera ? (
              <>
                {desktopAvailable
                  ? <CameraPreview camera={camera} paused={liveOpen || calibrationOpen} onFullscreen={() => setLiveOpen(true)} />
                  : <CloudCameraStatus camera={camera} />}
                <dl className="spec-list">
                  <div><dt>Cámara</dt><dd>{camera.name}</dd></div>
                  <div><dt>Origen</dt><dd className="t-meta">{endpoint ?? 'Sin definir'}</dd></div>
                  <div><dt>Serie</dt><dd className="t-meta">{camera.serial_number || '—'}</dd></div>
                  <div><dt>Credenciales</dt><dd>{camera.password_configured ? 'Guardadas' : 'Sin contraseña'}</dd></div>
                </dl>
                <AgentPairing
                  camera={camera}
                  ownerToken={ownerToken}
                  onNotice={data.announce}
                  onUnlinked={() => void data.refresh()}
                  onLinked={() => void data.refresh()}
                  desktopAvailable={desktopAvailable}
                />
                <div className="detail-secondary">
                  <Button variant="ghost" size="sm" iconBefore="trash" onClick={() => setDeleteCameraOpen(true)}>Desvincular cámara</Button>
                </div>
              </>
            ) : (
              <EmptyState
                icon="camera"
                accent="volt"
                title="Sin cámara asignada"
                action={<Button size="sm" variant="primary" iconBefore="plus" onClick={() => setCameraOpen(true)}>Asignar cámara</Button>}
              >
                Sin cámara, esta cancha no puede grabar partidos ni generar momentos.
              </EmptyState>
            )}
            </div>
          </section>

        </div>

        <div className="detail-col detail-col--config">
          <section className="card" aria-labelledby="cd-capture">
            <header className="card__head">
              <div>
                <h2 className="t-heading" id="cd-capture">Captura</h2>
              </div>
            </header>
            <div className="config-block card__pad">
              <div className={`recording-control recording-control--${recording.status}`}>
                <div className="recording-control__status">
                  <StatusPill state={recordingState} pulse={recording.status === 'recording'}>{recordingLabel}</StatusPill>
                  <div>
                    <b>{recordingActive ? 'Partido en curso' : 'Sin partido activo'}</b>
                    {recording.started_at ? (
                      <span>
                        Desde {new Intl.DateTimeFormat('es-AR', { hour: '2-digit', minute: '2-digit' }).format(new Date(recording.started_at))}
                        {' · '}{recording.started_by === 'player' ? 'Iniciado por QR' : 'Iniciado desde el panel'}
                      </span>
                    ) : <span>La grabación comienza con el QR o desde este control.</span>}
                  </div>
                </div>
                {recordingActive ? (
                  <Button
                    variant="secondary"
                    size="sm"
                    iconBefore="stop"
                    disabled={recording.status === 'stopping'}
                    onClick={() => setStopRecordingOpen(true)}
                  >
                    Detener
                  </Button>
                ) : (
                  <Button
                    variant="primary"
                    size="sm"
                    iconBefore="record"
                    loading={pending === 'recording-start'}
                    disabled={!camera || field.camera_status === 'offline' || field.status !== 'active'}
                    onClick={async () => {
                      setPending('recording-start');
                      await data.actions.setFieldRecording(field.id, true);
                      setPending(null);
                    }}
                  >
                    Iniciar grabación
                  </Button>
                )}
              </div>
              <div className="config-row">
                <SelectField
                  label="Estado de la cancha"
                  value={field.status}
                  disabled={pending === 'status'}
                  onChange={(event) => void apply('status', { status: event.target.value as OwnerField['status'] })}
                  hint={field.status === 'active' ? 'Acepta partidos desde el QR.' : 'No acepta nuevos partidos.'}
                >
                  <option value="active">Activa</option>
                  <option value="inactive">Inactiva</option>
                  <option value="maintenance">En mantenimiento</option>
                </SelectField>
                <SelectField
                  label="Cómo se marca un momento"
                  value={field.detection_mode}
                  disabled={pending === 'detection'}
                  onChange={(event) => void apply('detection', { detection_mode: event.target.value as OwnerField['detection_mode'] })}
                  hint={field.detection_mode === 'arms_up' ? 'Gesto reconocido por la cámara.' : 'Solo con el botón físico.'}
                >
                  <option value="arms_up">Brazos arriba</option>
                  <option value="manual">Botón manual</option>
                </SelectField>
              </div>
              {camera && desktopAvailable && field.detection_mode === 'arms_up' ? (
                <div className="detector-config-row">
                  <div className="detector-config-row__copy">
                    <b>Zona que analiza la IA</b>
                    <span>Excluí pasillos y personas fuera de la cancha.</span>
                  </div>
                  <Button
                    className="detector-config-row__action"
                    variant="secondary"
                    iconBefore="scan"
                    onClick={() => setCalibrationOpen(true)}
                  >
                    Calibrar zona
                  </Button>
                </div>
              ) : null}
              <div className="capture-identity" role="group" aria-labelledby="cd-identity">
                <div className="capture-identity__head">
                  <h3 id="cd-identity">Nombre</h3>
                  <p>Lo que ven los jugadores al escanear el QR</p>
                </div>
                <TextField
                  label="Nombre de la cancha"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                />
                <div className="config-actions">
                  {nameDirty ? <Button variant="ghost" size="sm" onClick={() => setName(field.name)}>Descartar</Button> : <span />}
                  <Button
                    variant="primary"
                    size="sm"
                    disabled={!nameDirty}
                    loading={pending === 'name'}
                    onClick={() => void apply('name', { name: name.trim() })}
                  >
                    Guardar nombre
                  </Button>
                </div>
              </div>
            </div>
          </section>
        </div>

        <section className="card detail-grid__wide" aria-labelledby="cd-qr">
          <header className="card__head">
            <div>
              <h2 className="t-heading" id="cd-qr">Acceso QR</h2>
              <p>Enlace que se imprime y se deja en la cancha</p>
            </div>
          </header>
          <div className="card__pad">
            <CourtQrCard
              fieldName={field.name}
              url={qrLink}
              onNotice={data.announce}
            />
          </div>
        </section>

        <div className="detail-grid__bottom">
          <section className="card" aria-labelledby="cd-button">
            <header className="card__head">
              <div>
                <h2 className="t-heading" id="cd-button">Botón físico</h2>
                <p>Alternativa al gesto para guardar momentos</p>
              </div>
            </header>
            <div className="config-block card__pad">
              <p className="config-note">
                Alternativa al gesto: cada pulsación guarda los 30 segundos anteriores.
                {field.button ? ' El agente local valida la clave en cada pulsación.' : ''}
              </p>
              {field.button ? (
                <p className="config-status">
                  <Icon name="button" size={14} /> {field.button.device_id} <i aria-hidden="true">·</i> {field.button.last_seen}
                </p>
              ) : null}
              <div className="config-row">
                <TextField label="ID del dispositivo" value={deviceId} onChange={(event) => setDeviceId(event.target.value)} placeholder="CV-BTN-05" />
                <TextField label="Clave del dispositivo" type="password" value={secret} onChange={(event) => setSecret(event.target.value)} autoComplete="new-password" />
              </div>
              <div className="config-actions">
                <span />
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={!deviceId.trim() || !secret}
                  loading={savingButton}
                  onClick={async () => {
                    setSavingButton(true);
                    const ok = await data.actions.saveButton(field.id, { device_id: deviceId.trim(), secret });
                    setSavingButton(false);
                    if (ok) setSecret('');
                  }}
                >
                  {field.button ? 'Actualizar botón' : 'Vincular botón'}
                </Button>
              </div>
            </div>
          </section>

          <section className="card danger-zone" aria-labelledby="cd-danger">
            <header className="card__head">
              <div>
                <h2 className="t-heading" id="cd-danger">Eliminar cancha</h2>
                <p>Acción irreversible</p>
              </div>
            </header>
            <div className="config-block card__pad">
              <p className="config-note">
                Se desvinculan su cámara, su botón y su QR. Los videos ya procesados no se borran.
              </p>
              <div className="config-actions">
                <span />
                <Button variant="danger" size="sm" iconBefore="trash" onClick={() => setDeleteCourtOpen(true)}>Eliminar {field.name}</Button>
              </div>
            </div>
          </section>
        </div>
      </div>

      <CameraDialog
        open={cameraOpen}
        field={field}
        camera={camera}
        onClose={() => setCameraOpen(false)}
        onCreate={data.actions.createCamera}
        onUpdate={data.actions.saveCamera}
      />

      {camera && desktopAvailable ? (
        <>
          <Dialog open={liveOpen} onClose={() => setLiveOpen(false)} size="lg" title={`${field.name} en vivo`} description={camera.name}>
            <CameraPreview camera={camera} mode="live" />
          </Dialog>
          <DetectorCalibration open={calibrationOpen} camera={camera} onClose={() => setCalibrationOpen(false)} onNotice={data.announce} />
        </>
      ) : null}

      <Dialog
        open={stopRecordingOpen}
        onClose={() => setStopRecordingOpen(false)}
        size="sm"
        title="Detener grabación"
        description={field.name}
        footer={
          <>
            <Button variant="ghost" onClick={() => setStopRecordingOpen(false)}>Continuar grabando</Button>
            <Button
              variant="primary"
              iconBefore="stop"
              loading={pending === 'recording-stop'}
              onClick={async () => {
                setPending('recording-stop');
                const ok = await data.actions.setFieldRecording(field.id, false);
                setPending(null);
                if (ok) setStopRecordingOpen(false);
              }}
            >
              Finalizar partido
            </Button>
          </>
        }
      >
        <p className="dialog-copy">
          La cámara dejará de capturar y el partido completo comenzará a subirse.
        </p>
      </Dialog>

      <Dialog
        open={deleteCourtOpen}
        onClose={() => setDeleteCourtOpen(false)}
        size="sm"
        tone="danger"
        title={`Eliminar ${field.name}`}
        description="Esta acción no se puede deshacer."
        footer={
          <>
            <Button variant="ghost" onClick={() => setDeleteCourtOpen(false)}>Cancelar</Button>
            <Button
              variant="danger"
              onClick={async () => {
                const ok = await data.actions.removeField(field.id);
                setDeleteCourtOpen(false);
                if (ok) goToSection('courts');
              }}
            >
              Eliminar cancha
            </Button>
          </>
        }
      >
        <p className="dialog-copy">
          Los jugadores que escaneen el QR de esta cancha dejarán de poder iniciar partidos.
          Los videos ya procesados se conservan.
        </p>
      </Dialog>

      {camera ? (
        <Dialog
          open={deleteCameraOpen}
          onClose={() => setDeleteCameraOpen(false)}
          size="sm"
          tone="danger"
          title="Desvincular cámara"
          footer={
            <>
              <Button variant="ghost" onClick={() => setDeleteCameraOpen(false)}>Cancelar</Button>
              <Button
                variant="danger"
                onClick={async () => { await data.actions.removeCamera(camera.id); setDeleteCameraOpen(false); }}
              >
                Desvincular
              </Button>
            </>
          }
        >
          <p className="dialog-copy">
            <b>{field.name}</b> deja de grabar hasta que asignes otra cámara.
          </p>
        </Dialog>
      ) : null}
    </div>
  );
}

async function copy(value: string, data: OwnerConsole, message: string) {
  try {
    await navigator.clipboard?.writeText(value);
    data.announce('success', message);
  } catch {
    data.announce('error', 'El navegador bloqueó el acceso al portapapeles.');
  }
}
