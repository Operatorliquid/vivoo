import { useEffect, useState } from 'react';
import QRCode from 'qrcode';
import { Button, Icon, Skeleton } from '@courtvision/design-system';
import { CopyValue } from '../../components/CopyValue';

type CourtQrCardProps = {
  fieldName: string;
  url: string;
  onNotice: (tone: 'success' | 'error', message: string) => void;
};

async function createPrintAsset(url: string): Promise<Blob> {
  const canvas = document.createElement('canvas');
  canvas.width = 1800;
  canvas.height = 1800;
  await QRCode.toCanvas(canvas, url, {
    errorCorrectionLevel: 'H',
    margin: 4,
    width: 1800,
    color: { dark: '#090d0b', light: '#ffffff' },
  });

  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('No pudimos exportar el QR.'))), 'image/png');
  });
}

export function qrDownloadName(fieldName: string) {
  const slug = fieldName.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
  return `vivoo-qr-${slug || 'cancha'}.png`;
}

export function CourtQrCard({ fieldName, url, onNotice }: CourtQrCardProps) {
  const [preview, setPreview] = useState('');
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setPreview('');
    setError('');
    void QRCode.toDataURL(url, {
      errorCorrectionLevel: 'H',
      margin: 2,
      width: 720,
      color: { dark: '#090d0b', light: '#ffffff' },
    }).then((image) => {
      if (active) setPreview(image);
    }).catch(() => {
      if (active) setError('No pudimos generar la vista previa del QR.');
    });
    return () => { active = false; };
  }, [url]);

  const download = async () => {
    setGenerating(true);
    setError('');
    try {
      const blob = await createPrintAsset(url);
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = objectUrl;
      anchor.download = qrDownloadName(fieldName);
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
      onNotice('success', `QR de ${fieldName} descargado.`);
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : 'No pudimos descargar el QR.';
      setError(message);
      onNotice('error', message);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="court-qr">
      <div className="court-qr__code" aria-label={`Vista previa del QR de ${fieldName}`}>
        {preview ? <img src={preview} alt={`Código QR de registro para ${fieldName}`} /> : <Skeleton w="100%" h={280} />}
      </div>

      <div className="court-qr__controls">
        <div className="court-qr__summary">
          <span className="court-qr__seal"><Icon name="qr" size={18} /></span>
          <div>
            <b>QR permanente de esta cancha</b>
            <p>Descargalo una vez. Cada registro queda asociado a {fieldName}.</p>
          </div>
        </div>
        <CopyValue value={url} label="enlace de registro" onCopied={() => onNotice('success', 'Enlace de registro copiado.')} />
        {error ? <p className="court-qr__error"><Icon name="warning" size={14} />{error}</p> : null}
        <div className="court-qr__actions">
          <Button variant="primary" size="sm" iconBefore="download" loading={generating} disabled={!preview} onClick={() => void download()}>
            Descargar PNG
          </Button>
          <Button variant="secondary" size="sm" iconBefore="externalLink" onClick={() => window.open(url, '_blank', 'noopener,noreferrer')}>
            Probar registro
          </Button>
        </div>
      </div>
    </div>
  );
}
