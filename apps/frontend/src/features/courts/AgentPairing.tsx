import { useState } from 'react';
import { Button, Icon } from '@courtvision/design-system';
import {
  cloudApiUrlForAgent,
  createOwnerCameraAgentToken,
  localAgentCheckUrl,
  localAgentConfigUrl,
  localAgentRemoveUrl,
  localAgentStatusUrl,
  unlinkOwnerCameraAgent,
} from '../../lib/api';
import type { OwnerCamera } from '../../lib/api';

/**
 * Vinculación del equipo local: el paso que conecta la cámara de la cancha con
 * la nube. Es una secuencia (generar token → configurar la PC), así que se
 * presenta como tal y no como una fila de botones equivalentes.
 */
export function AgentPairing({
  camera,
  ownerToken,
  onNotice,
  onUnlinked,
  onLinked,
  desktopAvailable,
}: {
  camera: OwnerCamera;
  ownerToken: string;
  onNotice: (tone: 'success' | 'error', text: string) => void;
  onUnlinked: () => void;
  onLinked: () => void;
  desktopAvailable: boolean;
}) {
  const [busy, setBusy] = useState<'configure' | 'check' | 'unlink' | null>(null);
  const [token, setToken] = useState(() => window.sessionStorage.getItem(`cv-agent-token:${camera.id}`) ?? '');

  const configure = async () => {
    setBusy('configure');
    try {
      const local = await fetch(localAgentStatusUrl());
      if (!local.ok) throw new Error('local agent unavailable');
      const nextToken = token || (await createOwnerCameraAgentToken(ownerToken, camera.id)).token;
      setToken(nextToken);
      window.sessionStorage.setItem(`cv-agent-token:${camera.id}`, nextToken);
      const response = await fetch(localAgentConfigUrl(), {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cloud_api_url: await cloudApiUrlForAgent(), agent_token: nextToken, camera: { camera_id: camera.id } }),
      });
      if (!response.ok) throw new Error('local agent unavailable');
      onNotice('success', 'Cámara vinculada a esta PC.');
      onLinked();
    } catch {
      onNotice('error', 'Abrí vivoo en la PC de la cancha e intentá nuevamente.');
    } finally {
      setBusy(null);
    }
  };

  const check = async () => {
    setBusy('check');
    try {
      const response = await fetch(localAgentCheckUrl(camera.id), { method: 'POST' });
      const status = await response.json();
      if (!response.ok || status?.agent?.camera_id !== camera.id || status?.state?.camera_status !== 'online') {
        throw new Error('camera unavailable');
      }
      onNotice('success', 'Cámara conectada y recibiendo imagen.');
      onLinked();
    } catch {
      onNotice('error', 'Esta PC no está recibiendo la imagen de la cámara. Revisá la conexión RTSP.');
    } finally {
      setBusy(null);
    }
  };

  const unlink = async () => {
    setBusy('unlink');
    try {
      await unlinkOwnerCameraAgent(ownerToken, camera.id);
      if (desktopAvailable) await fetch(localAgentRemoveUrl(camera.id), { method: 'DELETE' }).catch(() => null);
      window.sessionStorage.removeItem(`cv-agent-token:${camera.id}`);
      setToken('');
      onNotice('success', 'Equipo local desvinculado.');
      onUnlinked();
    } catch {
      onNotice('error', 'No pudimos desvincular el equipo local.');
    } finally {
      setBusy(null);
    }
  };

  if (camera.agent_linked) {
    return (
      <div className="pairing pairing--linked">
        <span className="pairing__icon" aria-hidden="true"><Icon name="link" size={15} /></span>
        <div className="pairing__body">
          <b>Equipo local vinculado</b>
          <p>{desktopAvailable ? 'La cámara está asociada a esta cancha.' : `Último reporte ${camera.last_seen}.`}</p>
        </div>
        <div className="pairing__actions">
          {desktopAvailable ? <Button variant="secondary" size="sm" loading={busy === 'check'} onClick={() => void check()}>Probar conexión</Button> : null}
          <Button variant="danger" size="sm" loading={busy === 'unlink'} onClick={() => void unlink()}>Desvincular</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="pairing">
      <span className="pairing__icon" aria-hidden="true"><Icon name="warning" size={15} /></span>
      <div className="pairing__body">
        <b>{desktopAvailable ? 'Conectar esta PC' : 'Equipo local sin vincular'}</b>
        <p>La vinculación se realiza desde vivoo en la PC de la cancha.</p>
      </div>
      <div className="pairing__actions">
        {desktopAvailable ? <Button variant="primary" size="sm" loading={busy === 'configure'} onClick={() => void configure()}>Vincular esta PC</Button> : null}
      </div>
    </div>
  );
}
