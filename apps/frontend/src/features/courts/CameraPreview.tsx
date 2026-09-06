import { useCallback, useEffect, useRef, useState } from 'react';
import { Icon } from '@courtvision/design-system';
import { localAgentPreviewUrl, localAgentStatusUrl } from '../../lib/api';
import type { OwnerCamera } from '../../lib/api';

type DetectorState = {
  status: string;
  detail: string;
  lastGestureAt: string | null;
  lastGestureConfidence: number | null;
  people: number;
  trackedPeople: number;
  fps: number;
  inferenceMs: number;
};

const detectorLabels: Record<string, string> = {
  running: 'Detector activo',
  loading: 'Iniciando detector',
  reconnecting: 'Reconectando detector',
  degraded: 'Detector con rendimiento bajo',
  unavailable: 'Detector no disponible',
  idle: 'Detección en pausa',
  offline: 'Cámara sin señal',
  disabled: 'Detección manual',
  error: 'Detector no disponible',
};

export function CloudCameraStatus({ camera }: { camera: OwnerCamera }) {
  const connected = camera.agent_linked && camera.status !== 'offline';
  const detectorRunning = connected && camera.detector_status === 'running';
  const title = connected ? 'Cámara conectada' : 'Cámara sin conexión';
  const signal = connected ? 'Online' : 'Offline';
  const detector = detectorRunning
    ? `Activo · ${camera.detector_fps.toFixed(1)} FPS`
    : camera.detector_status === 'disabled'
      ? 'Modo manual'
      : connected ? 'En espera' : 'Sin reporte';

  return (
    <div className={`camera-cloud camera-cloud--${camera.status}`}>
      <div className="camera-cloud__head">
        <span className="camera-cloud__icon" aria-hidden="true"><Icon name="camera" size={20} /></span>
        <div>
          <b>{title}</b>
          <span>Último reporte {camera.last_seen}</span>
        </div>
        <span className="camera-cloud__signal"><i aria-hidden="true" /> {signal}</span>
      </div>
      <dl className="camera-cloud__metrics">
        <div><dt>Equipo local</dt><dd>{camera.agent_linked ? 'Vinculado' : 'Sin vincular'}</dd></div>
        <div><dt>Detector</dt><dd>{detector}</dd></div>
      </dl>
      <p className="camera-cloud__note">La imagen en vivo se controla desde vivoo en la PC de la cancha.</p>
    </div>
  );
}

/**
 * Vista de la cámara servida por el agente local de la cancha.
 * Estados explícitos: conectando, imagen viva, o equipo local inalcanzable —
 * con el motivo, porque es la causa más habitual de que una cancha no capture.
 */
export function CameraPreview({
  camera,
  mode = 'preview',
  onFullscreen,
  paused = false,
}: { camera: OwnerCamera; mode?: 'preview' | 'live'; onFullscreen?: () => void; paused?: boolean }) {
  const [streamUrl, setStreamUrl] = useState('');
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [agentAvailable, setAgentAvailable] = useState(false);
  const [streamRevision, setStreamRevision] = useState(0);
  const [detector, setDetector] = useState<DetectorState>({ status: 'idle', detail: 'Iniciá la grabación para detectar gestos', lastGestureAt: null, lastGestureConfidence: null, people: 0, trackedPeople: 0, fps: 0, inferenceMs: 0 });
  const retryTimer = useRef<number | null>(null);
  const retryDelay = useRef(2000);
  const streamTimeout = useRef<number | null>(null);

  const scheduleReconnect = useCallback(() => {
    if (streamTimeout.current !== null) {
      window.clearTimeout(streamTimeout.current);
      streamTimeout.current = null;
    }
    setState('error');
    if (retryTimer.current !== null) return;
    retryTimer.current = window.setTimeout(() => {
      retryTimer.current = null;
      retryDelay.current = Math.min(retryDelay.current * 2, 10_000);
      setStreamRevision((current) => current + 1);
    }, retryDelay.current);
  }, []);

  useEffect(() => {
    let active = true;
    const refreshStatus = () => {
      fetch(localAgentStatusUrl(camera.id))
        .then((response) => { if (!response.ok) throw new Error('agent offline'); return response.json(); })
        .then((status) => {
          if (!active || status?.camera?.host !== camera.host) throw new Error('camera not assigned');
          setAgentAvailable(true);
          setDetector({
            status: status?.state?.gesture_detector_status ?? 'idle',
            detail: status?.state?.gesture_detector_detail ?? 'Iniciá la grabación para detectar gestos',
            lastGestureAt: status?.state?.last_gesture_at ?? null,
            lastGestureConfidence: status?.state?.last_gesture_confidence ?? null,
            people: status?.state?.gesture_people_count ?? 0,
            trackedPeople: status?.state?.gesture_tracked_people ?? 0,
            fps: status?.state?.gesture_inference_fps ?? 0,
            inferenceMs: status?.state?.gesture_inference_ms ?? 0,
          });
        })
        .catch(() => {
          if (!active) return;
          setAgentAvailable(false);
          setState('error');
          setDetector({
            status: camera.agent_linked ? camera.detector_status || 'idle' : 'offline',
            detail: camera.agent_linked ? 'Último estado informado por el equipo local' : 'El agente local no responde',
            lastGestureAt: null,
            lastGestureConfidence: null,
            people: 0,
            trackedPeople: 0,
            fps: camera.detector_fps || 0,
            inferenceMs: 0,
          });
        });
    };
    refreshStatus();
    const interval = window.setInterval(refreshStatus, 5000);
    return () => { active = false; window.clearInterval(interval); };
  }, [camera.id, camera.host, camera.agent_linked, camera.detector_status, camera.detector_fps, mode]);

  useEffect(() => {
    if (!agentAvailable || paused) {
      setStreamUrl('');
      return;
    }
    setState('loading');
    setStreamUrl(localAgentPreviewUrl(mode, camera.id));
    streamTimeout.current = window.setTimeout(scheduleReconnect, 12_000);
    return () => {
      if (streamTimeout.current !== null) {
        window.clearTimeout(streamTimeout.current);
        streamTimeout.current = null;
      }
    };
  }, [agentAvailable, camera.id, mode, paused, scheduleReconnect, streamRevision]);

  useEffect(() => () => {
    if (retryTimer.current !== null) window.clearTimeout(retryTimer.current);
  }, []);

  const markReady = () => {
    if (streamTimeout.current !== null) {
      window.clearTimeout(streamTimeout.current);
      streamTimeout.current = null;
    }
    retryDelay.current = 2000;
    setState('ready');
  };

  const gestureDetected = detector.lastGestureAt
    ? Date.now() - new Date(detector.lastGestureAt).getTime() < 20_000
    : false;
  const detectorStatus = gestureDetected ? 'detected' : detector.status;
  const detectorLabel = gestureDetected ? 'Gesto detectado' : (detectorLabels[detector.status] ?? 'Estado del detector');
  const lastGestureLabel = detector.lastGestureConfidence !== null
    ? `último gesto ${Math.round(detector.lastGestureConfidence * 100)} %`
    : '';
  const detectorDetail = gestureDetected
    ? detector.lastGestureConfidence !== null
      ? `Confianza ${Math.round(detector.lastGestureConfidence * 100)} % · highlight registrado`
      : 'Highlight registrado'
    : detector.status === 'running' || detector.status === 'degraded'
      ? detector.people > 0
        ? `${detector.trackedPeople}/${detector.people} en seguimiento · ${detector.fps.toFixed(1)} FPS${lastGestureLabel ? ` · ${lastGestureLabel}` : ''}`
        : `Analizando · ${detector.fps.toFixed(1)} FPS · sin personas visibles${lastGestureLabel ? ` · ${lastGestureLabel}` : ''}`
      : detector.detail;

  return (
    <div className={`preview preview--${mode}`}>
      <div className="preview__stage">
        {streamUrl && state !== 'error' ? (
          <>
            <img className="preview__image" src={streamUrl} alt={`Imagen en vivo de ${camera.name}`} onLoad={markReady} onError={scheduleReconnect} />
            {state === 'loading' ? (
              <div className="preview__overlay">
                <span className="preview__spinner" aria-hidden="true" />
                <span>Esperando imagen…</span>
              </div>
            ) : null}
          </>
        ) : (
          <div className="preview__overlay preview__overlay--static">
            <Icon name="camera" size={22} />
            <b>{state === 'loading' ? 'Buscando el equipo local…' : agentAvailable ? 'Reconectando cámara…' : 'Equipo local sin conexión'}</b>
            <p>
              {state === 'loading'
                ? 'Consultando el agente instalado en la PC de la cancha.'
                : agentAvailable
                  ? 'La señal se interrumpió. vivoo volverá a conectarla automáticamente.'
                  : 'Abrí vivoo en la PC de la cancha para ver la imagen.'}
            </p>
          </div>
        )}

        {state === 'ready' ? (
          <span className="preview__tag">
            <i aria-hidden="true" /> {mode === 'live' ? 'En vivo' : 'Imagen local · 1 fps'}
          </span>
        ) : null}
      </div>

      <div className={`preview__detector preview__detector--${detectorStatus}`} title={`${detectorDetail}${detector.inferenceMs ? ` · ${detector.inferenceMs.toFixed(0)} ms por inferencia` : ''}`}>
        <i aria-hidden="true" />
        <span>{detectorLabel}</span>
        <small>{detectorDetail}</small>
      </div>

      {mode === 'preview' && onFullscreen ? (
        <button type="button" className="preview__expand" onClick={onFullscreen} disabled={state !== 'ready'}>
          Ver en pantalla completa <Icon name="arrowRight" size={13} />
        </button>
      ) : null}
    </div>
  );
}
