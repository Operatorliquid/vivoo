import type { CaptureState } from '@courtvision/design-system';
import type { OwnerCamera, OwnerField } from './api';

/**
 * Estado real de captura de una cancha.
 *
 * La API expone dos cosas distintas que el operador necesita leer juntas:
 * el estado administrativo de la cancha (`status`), el de su cámara y la
 * confirmación de grabación enviada por el agente local.
 */
export function courtState(field: OwnerField): CaptureState {
  if (field.status !== 'active') return 'idle';
  if (field.camera_status === 'offline') return 'offline';
  if (field.camera_status === 'live' && field.recording?.status === 'recording') return 'live';
  return 'ready';
}

export function courtStateLabel(field: OwnerField): string {
  const state = courtState(field);
  if (state === 'idle') return field.status === 'maintenance' ? 'Mantenimiento' : 'Inactiva';
  if (state === 'offline') return field.camera ? 'Cámara sin señal' : 'Sin cámara';
  if (state === 'live') return 'Capturando';
  if (field.recording?.status === 'starting') return 'Iniciando captura';
  if (field.recording?.status === 'stopping') return 'Finalizando partido';
  return 'Cámara lista';
}

/** Por qué la cancha no está capturando, en una línea accionable. */
export function courtStateReason(field: OwnerField): string | null {
  const state = courtState(field);
  if (state === 'live') return null;
  if (field.status === 'maintenance') return 'La cancha está marcada en mantenimiento.';
  if (field.status === 'inactive') return 'La cancha está inactiva y no acepta partidos.';
  if (!field.camera) return 'Todavía no hay una cámara asignada a esta cancha.';
  if (field.camera_status === 'offline') return 'El equipo local no está enviando señal.';
  if (field.recording?.status === 'starting') return 'El equipo local está iniciando la grabación.';
  if (field.recording?.status === 'stopping') return 'El equipo local está finalizando el archivo del partido.';
  return 'La cámara está conectada y esperando un partido.';
}

export function detectionLabel(mode: OwnerField['detection_mode']): string {
  return mode === 'arms_up' ? 'Brazos arriba' : 'Botón manual';
}

export function sportLabel(code: string): string {
  return code === 'padel' ? 'Pádel' : code === 'football' ? 'Fútbol' : code;
}

/** Origen del stream, legible. Los datos técnicos van en fuente mono. */
export function cameraEndpoint(camera: OwnerCamera | null): string | null {
  if (!camera) return null;
  if (camera.host) return `${camera.host}:${camera.rtsp_port}${camera.stream_path || ''}`;
  return camera.stream_url || null;
}

export function initialsOf(name: string): string {
  return name
    .split(' ')
    .filter(Boolean)
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();
}

/** "Cancha 01" → "01". Permite mostrar el número como dato tabular. */
export function courtNumber(name: string, index: number): string {
  const match = name.match(/(\d+)\s*$/);
  return match ? match[1].padStart(2, '0') : String(index + 1).padStart(2, '0');
}

export function countByState(fields: OwnerField[]): Record<CaptureState, number> {
  return fields.reduce<Record<CaptureState, number>>(
    (acc, field) => { acc[courtState(field)] += 1; return acc; },
    { live: 0, ready: 0, offline: 0, idle: 0 },
  );
}

export function clockNow(): string {
  return new Date().toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit', hour12: false });
}
