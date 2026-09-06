import { useCallback, useEffect, useRef, useState } from 'react';
import {
  createOwnerCamera, createOwnerField, deleteAllOwnerNotifications, deleteOwnerCamera, deleteOwnerField, deleteOwnerHighlight,
  deleteOwnerHighlights, deleteOwnerRecording, deleteOwnerRecordings,
  getOwnerActivity, getOwnerCameras, getOwnerDashboard, getOwnerFields, getOwnerHighlights, getOwnerNotifications, getOwnerProfile, getOwnerRecordings,
  markAllOwnerNotificationsRead, markOwnerNotificationRead, updateOwnerButton, updateOwnerCamera,
  startOwnerFieldRecording, stopOwnerFieldRecording, updateOwnerClub, updateOwnerField, updateOwnerProfile,
} from '../lib/api';
import type {
  CreatedCamera, CreatedField, OwnerActivity, OwnerCamera, OwnerDashboard, OwnerField, OwnerHighlight, OwnerLibraryRecording, OwnerNotification,
  OwnerProfile, OwnerSession,
} from '../lib/api';
import { clockNow } from '../lib/court';

export type Notice = { id: number; tone: 'success' | 'error'; text: string };

export type NewCourtPayload = {
  name: string; sport_code: 'padel' | 'football'; detection_mode: 'arms_up' | 'manual';
  camera_name?: string; camera_host?: string; camera_rtsp_port?: number; camera_username?: string;
  camera_password?: string; camera_stream_path?: string; camera_serial_number?: string;
};
export type CameraPayload = {
  field_id: string; name: string; serial_number?: string; host?: string; rtsp_port?: number;
  username?: string; password?: string; stream_path?: string; stream_url?: string;
};
export type CameraPatch = Partial<Pick<OwnerCamera, 'name' | 'serial_number' | 'host' | 'rtsp_port' | 'username' | 'stream_path' | 'stream_url' | 'status'>> & { password?: string };
export type FieldPatch = Partial<Pick<OwnerField, 'name' | 'status' | 'detection_mode'>>;

const message = (error: unknown, fallback: string) => (error instanceof Error ? error.message : fallback);

/**
 * Signed media tickets change on every API refresh. Replacing an otherwise
 * unchanged highlight would therefore replace the video `src` and make the
 * browser restart playback every three seconds.
 */
export function mergeOwnerHighlights(current: OwnerHighlight[], incoming: OwnerHighlight[]): OwnerHighlight[] {
  const currentById = new Map(current.map((item) => [item.id, item]));
  let changed = current.length !== incoming.length;
  const merged = incoming.map((next) => {
    const previous = currentById.get(next.id);
    if (!previous) {
      changed = true;
      return next;
    }
    const sameContent = (
      previous.display_id === next.display_id
      && previous.title === next.title
      && previous.field_id === next.field_id
      && previous.field_name === next.field_name
      && previous.session_id === next.session_id
      && previous.session_code === next.session_code
      && previous.session_started_at === next.session_started_at
      && previous.occurred_at === next.occurred_at
      && previous.duration_seconds === next.duration_seconds
      && previous.confidence === next.confidence
      && previous.status === next.status
      && previous.players.length === next.players.length
      && previous.players.every((player, index) => player === next.players[index])
    );
    if (sameContent) return previous;
    changed = true;
    if (previous.status === next.status && previous.media_path) {
      return { ...next, media_path: previous.media_path, download_path: previous.download_path };
    }
    return next;
  });
  return changed ? merged : current;
}

export function mergeOwnerRecordings(current: OwnerLibraryRecording[], incoming: OwnerLibraryRecording[]): OwnerLibraryRecording[] {
  const currentById = new Map(current.map((item) => [item.id, item]));
  let changed = current.length !== incoming.length;
  const merged = incoming.map((next) => {
    const previous = currentById.get(next.id);
    if (!previous) {
      changed = true;
      return next;
    }
    const sameContent = (
      previous.display_id === next.display_id
      && previous.field_name === next.field_name
      && previous.ended_at === next.ended_at
      && previous.expires_at === next.expires_at
      && previous.duration_seconds === next.duration_seconds
      && previous.status === next.status
      && previous.players.length === next.players.length
      && previous.players.every((player, index) => player === next.players[index])
    );
    if (sameContent) return previous;
    changed = true;
    if (previous.status === next.status && previous.media_path) {
      return { ...next, media_path: previous.media_path, download_path: previous.download_path };
    }
    return next;
  });
  return changed ? merged : current;
}

/**
 * Estado y acciones de la consola del club.
 *
 * Centraliza carga, refresco y mutaciones para que las pantallas solo se ocupen
 * de presentar. Expone `loading` y `loadError` reales: antes la UI mostraba
 * ceros mientras cargaba, indistinguibles de un club sin datos.
 */
export function useOwnerConsole(session: OwnerSession) {
  const token = session.access_token;
  const [dashboard, setDashboard] = useState<OwnerDashboard | null>(null);
  const [fields, setFields] = useState<OwnerField[]>([]);
  const [cameras, setCameras] = useState<OwnerCamera[]>([]);
  const [highlights, setHighlights] = useState<OwnerHighlight[]>([]);
  const [recordings, setRecordings] = useState<OwnerLibraryRecording[]>([]);
  const [profile, setProfile] = useState<OwnerProfile | null>(null);
  const [notifications, setNotifications] = useState<OwnerNotification[]>([]);
  const [activity, setActivity] = useState<OwnerActivity[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [syncedAt, setSyncedAt] = useState('');
  const [notice, setNotice] = useState<Notice | null>(null);
  const noticeSeq = useRef(0);
  const highlightStates = useRef(new Map<string, OwnerHighlight['status']>());

  const announce = useCallback((tone: Notice['tone'], text: string) => {
    noticeSeq.current += 1;
    setNotice({ id: noticeSeq.current, tone, text });
  }, []);

  const loadAll = useCallback(async (mode: 'initial' | 'refresh' = 'initial') => {
    if (mode === 'refresh') setRefreshing(true); else setLoading(true);
    try {
      const [nextDashboard, fieldResponse, cameraResponse, highlightResponse, recordingResponse, nextProfile, notificationResponse, activityResponse] = await Promise.all([
        getOwnerDashboard(token), getOwnerFields(token), getOwnerCameras(token),
        getOwnerHighlights(token), getOwnerRecordings(token), getOwnerProfile(token), getOwnerNotifications(token), getOwnerActivity(token),
      ]);
      setDashboard(nextDashboard);
      setFields(fieldResponse.items);
      setCameras(cameraResponse.items);
      setHighlights((current) => mergeOwnerHighlights(current, highlightResponse.items));
      setRecordings((current) => mergeOwnerRecordings(current, recordingResponse.items));
      highlightStates.current = new Map(highlightResponse.items.map((item) => [item.id, item.status]));
      setProfile(nextProfile);
      setNotifications(notificationResponse.items);
      setActivity(activityResponse.items);
      setSyncedAt(clockNow());
      setLoadError('');
    } catch (error) {
      setLoadError(message(error, 'No pudimos sincronizar la configuración del club.'));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [token]);

  useEffect(() => { void loadAll('initial'); }, [loadAll]);

  useEffect(() => {
    if (!notice) return undefined;
    const timeout = window.setTimeout(() => setNotice(null), notice.tone === 'error' ? 6000 : 3400);
    return () => window.clearTimeout(timeout);
  }, [notice]);

  /** Relee la infraestructura tras una mutación, sin pantalla de carga. */
  const resync = useCallback(async () => {
    const [fieldResponse, cameraResponse, nextDashboard, highlightResponse, recordingResponse, activityResponse] = await Promise.all([
      getOwnerFields(token), getOwnerCameras(token), getOwnerDashboard(token), getOwnerHighlights(token), getOwnerRecordings(token), getOwnerActivity(token),
    ]);
    setFields(fieldResponse.items);
    setCameras(cameraResponse.items);
    setDashboard(nextDashboard);
    setHighlights((current) => mergeOwnerHighlights(current, highlightResponse.items));
    setRecordings((current) => mergeOwnerRecordings(current, recordingResponse.items));
    highlightStates.current = new Map(highlightResponse.items.map((item) => [item.id, item.status]));
    setActivity(activityResponse.items);
    setSyncedAt(clockNow());
  }, [token]);

  /** Mantiene el panel alineado con sesiones iniciadas desde el QR o el agente. */
  const syncOperationalState = useCallback(async () => {
    try {
      const [fieldResponse, activityResponse, highlightResponse, recordingResponse] = await Promise.all([
        getOwnerFields(token), getOwnerActivity(token), getOwnerHighlights(token), getOwnerRecordings(token),
      ]);
      setFields(fieldResponse.items);
      setActivity(activityResponse.items);
      const previous = highlightStates.current;
      const registered = highlightResponse.items.find((item) => !previous.has(item.id));
      const completed = highlightResponse.items.find((item) => previous.get(item.id) === 'processing' && item.status === 'available');
      setHighlights((current) => mergeOwnerHighlights(current, highlightResponse.items));
      setRecordings((current) => mergeOwnerRecordings(current, recordingResponse.items));
      highlightStates.current = new Map(highlightResponse.items.map((item) => [item.id, item.status]));
      if (registered) {
        announce(
          'success',
          registered.status === 'available'
            ? 'Momento reconocido y listo en la biblioteca.'
            : 'Momento reconocido. Estamos preparando el video.',
        );
      } else if (completed) {
        announce('success', 'El highlight ya está listo en la biblioteca.');
      }
      const camerasById = new Map(
        fieldResponse.items.flatMap((field) => (field.camera ? [[field.camera.id, field.camera] as const] : [])),
      );
      setCameras((current) => current.map((camera) => camerasById.get(camera.id) ?? camera));
      setSyncedAt(clockNow());
    } catch {
      // El refresco completo muestra errores; este pulso operativo es silencioso.
    }
  }, [token, announce]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      if (document.visibilityState === 'visible') void syncOperationalState();
    }, 3000);
    return () => window.clearInterval(interval);
  }, [syncOperationalState]);

  const saveField = useCallback(async (fieldId: string, payload: FieldPatch) => {
    try {
      const updated = await updateOwnerField(token, fieldId, payload);
      await resync();
      announce('success', `${updated.name} actualizada.`);
      return true;
    } catch (error) {
      announce('error', message(error, 'No pudimos guardar la cancha.'));
      return false;
    }
  }, [token, resync, announce]);

  const setFieldRecording = useCallback(async (fieldId: string, recording: boolean) => {
    try {
      const updated = recording
        ? await startOwnerFieldRecording(token, fieldId)
        : await stopOwnerFieldRecording(token, fieldId);
      setFields((current) => current.map((field) => (field.id === fieldId ? updated : field)));
      await resync();
      announce('success', recording ? 'Grabación iniciada.' : 'Grabación finalizada.');
      return true;
    } catch (error) {
      announce('error', message(error, recording ? 'No pudimos iniciar la grabación.' : 'No pudimos detener la grabación.'));
      return false;
    }
  }, [token, resync, announce]);

  const removeHighlight = useCallback(async (highlightId: string) => {
    try {
      await deleteOwnerHighlight(token, highlightId);
      await resync();
      announce('success', 'Video eliminado y espacio liberado.');
      return true;
    } catch (error) {
      announce('error', message(error, 'No pudimos eliminar el video.'));
      return false;
    }
  }, [token, resync, announce]);

  const removeHighlights = useCallback(async (highlightIds: string[]) => {
    if (highlightIds.length === 0) return false;
    try {
      const result = await deleteOwnerHighlights(token, highlightIds);
      await resync();
      announce('success', `${result.deleted} ${result.deleted === 1 ? 'video eliminado' : 'videos eliminados'} y espacio liberado.`);
      return true;
    } catch (error) {
      await resync().catch(() => undefined);
      announce('error', message(error, 'No pudimos eliminar los videos seleccionados.'));
      return false;
    }
  }, [token, resync, announce]);

  const removeLibraryItems = useCallback(async (items: Array<{ kind: 'highlight' | 'recording'; id: string }>) => {
    if (items.length === 0) return false;
    const highlightIds = items.filter((item) => item.kind === 'highlight').map((item) => item.id);
    const recordingIds = items.filter((item) => item.kind === 'recording').map((item) => item.id);
    try {
      await Promise.all([
        highlightIds.length === 0 ? Promise.resolve() : highlightIds.length === 1
          ? deleteOwnerHighlight(token, highlightIds[0])
          : deleteOwnerHighlights(token, highlightIds),
        recordingIds.length === 0 ? Promise.resolve() : recordingIds.length === 1
          ? deleteOwnerRecording(token, recordingIds[0])
          : deleteOwnerRecordings(token, recordingIds),
      ]);
      await resync();
      announce('success', `${items.length} ${items.length === 1 ? 'video eliminado' : 'videos eliminados'} y espacio liberado.`);
      return true;
    } catch (error) {
      await resync().catch(() => undefined);
      announce('error', message(error, 'No pudimos eliminar los videos seleccionados.'));
      return false;
    }
  }, [token, resync, announce]);

  const createField = useCallback(async (payload: NewCourtPayload): Promise<CreatedField | null> => {
    try {
      const created = await createOwnerField(token, payload);
      if (created.camera && created.agent_token) {
        window.sessionStorage.setItem(`cv-agent-token:${created.camera.id}`, created.agent_token);
      }
      await resync();
      announce('success', `${created.name} creada.`);
      return created;
    } catch (error) {
      announce('error', message(error, 'No pudimos crear la cancha.'));
      return null;
    }
  }, [token, resync, announce]);

  const removeField = useCallback(async (fieldId: string) => {
    try {
      await deleteOwnerField(token, fieldId);
      await resync();
      announce('success', 'Cancha eliminada.');
      return true;
    } catch (error) {
      announce('error', message(error, 'No pudimos eliminar la cancha.'));
      return false;
    }
  }, [token, resync, announce]);

  const saveButton = useCallback(async (fieldId: string, payload: { device_id: string; secret: string }) => {
    try {
      await updateOwnerButton(token, fieldId, payload);
      await resync();
      announce('success', 'Botón físico configurado.');
      return true;
    } catch (error) {
      announce('error', message(error, 'No pudimos configurar el botón.'));
      return false;
    }
  }, [token, resync, announce]);

  const createCamera = useCallback(async (payload: CameraPayload): Promise<CreatedCamera | null> => {
    try {
      const created = await createOwnerCamera(token, payload);
      window.sessionStorage.setItem(`cv-agent-token:${created.id}`, created.agent_token);
      await resync();
      announce('success', 'Cámara cargada. El token del agente quedó disponible en la cancha.');
      return created;
    } catch (error) {
      announce('error', message(error, 'No pudimos cargar la cámara.'));
      return null;
    }
  }, [token, resync, announce]);

  const saveCamera = useCallback(async (cameraId: string, payload: CameraPatch) => {
    try {
      await updateOwnerCamera(token, cameraId, payload);
      await resync();
      announce('success', 'Cámara actualizada.');
      return true;
    } catch (error) {
      announce('error', message(error, 'No pudimos actualizar la cámara.'));
      return false;
    }
  }, [token, resync, announce]);

  const removeCamera = useCallback(async (cameraId: string) => {
    try {
      await deleteOwnerCamera(token, cameraId);
      await resync();
      announce('success', 'Cámara desvinculada.');
      return true;
    } catch (error) {
      announce('error', message(error, 'No pudimos desvincular la cámara.'));
      return false;
    }
  }, [token, resync, announce]);

  const saveClub = useCallback(async (payload: { name: string; city: string; logo_data_url: string }) => {
    try {
      const updated = await updateOwnerClub(token, payload);
      setDashboard((current) => (current ? { ...current, club: updated } : current));
      announce('success', 'Datos del club actualizados.');
      return true;
    } catch (error) {
      announce('error', message(error, 'No pudimos guardar el club.'));
      return false;
    }
  }, [token, announce]);

  const saveProfile = useCallback(async (payload: Pick<OwnerProfile, 'display_name' | 'phone' | 'timezone'>) => {
    try {
      setProfile(await updateOwnerProfile(token, payload));
      announce('success', 'Perfil actualizado.');
      return true;
    } catch (error) {
      announce('error', message(error, 'No pudimos guardar tu perfil.'));
      return false;
    }
  }, [token, announce]);

  const readNotification = useCallback(async (notificationId: string) => {
    try {
      const updated = await markOwnerNotificationRead(token, notificationId);
      setNotifications((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    } catch {
      announce('error', 'No pudimos actualizar la notificación.');
    }
  }, [token, announce]);

  const readAllNotifications = useCallback(async () => {
    try {
      setNotifications((await markAllOwnerNotificationsRead(token)).items);
    } catch {
      announce('error', 'No pudimos actualizar las notificaciones.');
    }
  }, [token, announce]);

  const clearNotifications = useCallback(async () => {
    try {
      await deleteAllOwnerNotifications(token);
      setNotifications([]);
      announce('success', 'Notificaciones eliminadas.');
    } catch {
      announce('error', 'No pudimos eliminar las notificaciones.');
    }
  }, [token, announce]);

  return {
    ownerToken: token,
    dashboard, fields, cameras, highlights, recordings, profile, notifications, activity,
    loading, refreshing, loadError, syncedAt, notice,
    dismissNotice: () => setNotice(null),
    announce,
    refresh: () => loadAll('refresh'),
    retry: () => loadAll('initial'),
    actions: {
      saveField, createField, removeField, saveButton,
      setFieldRecording, removeHighlight, removeHighlights, removeLibraryItems,
      createCamera, saveCamera, removeCamera,
      saveClub, saveProfile,
      readNotification, readAllNotifications, clearNotifications,
    },
  };
}

export type OwnerConsole = ReturnType<typeof useOwnerConsole>;
