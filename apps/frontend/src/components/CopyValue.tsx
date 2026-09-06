import { useEffect, useState } from 'react';
import { Icon } from '@courtvision/design-system';

/**
 * Valor técnico copiable (tokens, enlaces QR, hosts). Confirma la copia en el
 * propio control: el operador no tiene que buscar el feedback en otro lado.
 */
export function CopyValue({
  value,
  label,
  masked = false,
  onCopied,
}: { value: string; label: string; masked?: boolean; onCopied?: () => void }) {
  const [copied, setCopied] = useState(false);
  const [revealed, setRevealed] = useState(!masked);

  useEffect(() => {
    if (!copied) return undefined;
    const timeout = window.setTimeout(() => setCopied(false), 2000);
    return () => window.clearTimeout(timeout);
  }, [copied]);

  const copy = async () => {
    try {
      await navigator.clipboard?.writeText(value);
      setCopied(true);
      onCopied?.();
    } catch {
      setCopied(false);
    }
  };

  const shown = revealed ? value : '•'.repeat(Math.min(value.length, 28));

  return (
    <div className="copy-value">
      <code className="copy-value__text t-meta" title={revealed ? value : undefined}>{shown}</code>
      {masked ? (
        <button type="button" className="copy-value__btn" onClick={() => setRevealed((current) => !current)}>
          {revealed ? 'Ocultar' : 'Mostrar'}
        </button>
      ) : null}
      <button type="button" className="copy-value__btn" onClick={() => void copy()} aria-label={`Copiar ${label}`}>
        <Icon name={copied ? 'check' : 'copy'} size={13} />
        {copied ? 'Copiado' : 'Copiar'}
      </button>
    </div>
  );
}
