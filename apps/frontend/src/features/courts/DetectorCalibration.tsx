import { useEffect, useState } from 'react';
import { Button, Dialog } from '@courtvision/design-system';
import { getLocalDetectorConfig, localAgentPreviewUrl, updateLocalDetectorConfig } from '../../lib/api';
import type { OwnerCamera } from '../../lib/api';

type Roi = [number, number, number, number];
type Edge = 0 | 1 | 2 | 3;

const FULL_FRAME: Roi = [0, 0, 1, 1];

export function DetectorCalibration({
  open,
  camera,
  onClose,
  onNotice,
}: {
  open: boolean;
  camera: OwnerCamera;
  onClose: () => void;
  onNotice: (tone: 'success' | 'error', text: string) => void;
}) {
  const [roi, setRoi] = useState<Roi>(FULL_FRAME);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [available, setAvailable] = useState(true);
  const [streamUrl, setStreamUrl] = useState('');

  useEffect(() => {
    if (!open) return;
    let active = true;
    setLoading(true);
    setAvailable(true);
    setStreamUrl(localAgentPreviewUrl('preview', camera.id));
    getLocalDetectorConfig(camera.id)
      .then((config) => {
        if (!active) return;
        setRoi(config.detector.roi ?? FULL_FRAME);
      })
      .catch(() => { if (active) setAvailable(false); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [open, camera.id]);

  const setEdge = (edge: Edge, value: number) => {
    setRoi((current) => {
      const next: Roi = [...current];
      next[edge] = value;
      if (edge === 0) next[0] = Math.min(next[0], next[2] - 0.1);
      if (edge === 1) next[1] = Math.min(next[1], next[3] - 0.1);
      if (edge === 2) next[2] = Math.max(next[2], next[0] + 0.1);
      if (edge === 3) next[3] = Math.max(next[3], next[1] + 0.1);
      return next;
    });
  };

  const save = async () => {
    setSaving(true);
    try {
      await updateLocalDetectorConfig(camera.id, { pose_roi: roi });
      onNotice('success', 'Zona del detector guardada en el equipo local.');
      onClose();
    } catch (error) {
      onNotice('error', error instanceof Error ? error.message : 'No pudimos guardar la zona.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      size="lg"
      title="Zona de detección"
      description={`${camera.name} · solo las personas dentro del marco pueden crear highlights`}
      footer={
        <>
          <Button variant="ghost" onClick={() => setRoi(FULL_FRAME)} disabled={!available}>Usar imagen completa</Button>
          <Button variant="primary" loading={saving} disabled={!available || loading} onClick={() => void save()}>Guardar zona</Button>
        </>
      }
    >
      {available ? (
        <div className="detector-calibration">
          <div className="detector-calibration__stage">
            {streamUrl ? <img src={streamUrl} alt={`Imagen de ${camera.name} para calibrar el detector`} /> : null}
            <div
              className="detector-calibration__roi"
              style={{ left: `${roi[0] * 100}%`, top: `${roi[1] * 100}%`, width: `${(roi[2] - roi[0]) * 100}%`, height: `${(roi[3] - roi[1]) * 100}%` }}
            >
              <span>Zona activa</span>
            </div>
          </div>
          <div className="detector-calibration__controls">
            <Range label="Izquierda" value={roi[0]} max={roi[2] - 0.1} onChange={(value) => setEdge(0, value)} />
            <Range label="Derecha" value={roi[2]} min={roi[0] + 0.1} onChange={(value) => setEdge(2, value)} />
            <Range label="Arriba" value={roi[1]} max={roi[3] - 0.1} onChange={(value) => setEdge(1, value)} />
            <Range label="Abajo" value={roi[3]} min={roi[1] + 0.1} onChange={(value) => setEdge(3, value)} />
          </div>
        </div>
      ) : (
        <div className="detector-calibration__offline">
          <b>Equipo local no disponible</b>
          <p>Abrí esta configuración desde la PC de la cancha con vivoo en ejecución.</p>
        </div>
      )}
    </Dialog>
  );
}

function Range({ label, value, min = 0, max = 1, onChange }: { label: string; value: number; min?: number; max?: number; onChange: (value: number) => void }) {
  return (
    <label>
      <span>{label}<b>{Math.round(value * 100)}%</b></span>
      <input type="range" min={min} max={max} step="0.01" value={value} onChange={(event) => onChange(Number(event.target.value))} />
    </label>
  );
}
