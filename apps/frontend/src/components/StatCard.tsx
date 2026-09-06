import type { ReactNode } from 'react';
import { Icon, Skeleton } from '@courtvision/design-system';

/**
 * Tarjeta de indicador. El pie no compara contra un período que la API no
 * entrega: muestra el desglose real que respalda la cifra.
 */
export function StatCard({
  label,
  value,
  icon,
  tone = 'neutral',
  footer,
  loading = false,
}: {
  label: string;
  value: ReactNode;
  icon: string;
  tone?: 'neutral' | 'brand' | 'warn' | 'danger';
  footer?: ReactNode;
  loading?: boolean;
}) {
  return (
    <article className={`stat stat--${tone}`}>
      <header>
        <span className="stat__label">{label}</span>
        <span className="stat__icon" aria-hidden="true"><Icon name={icon} size={17} /></span>
      </header>
      {loading ? (
        <>
          <Skeleton w="52%" h={30} />
          <Skeleton w="70%" h={11} />
        </>
      ) : (
        <>
          <p className="stat__value t-figure">{value}</p>
          {footer ? <div className="stat__footer">{footer}</div> : null}
        </>
      )}
    </article>
  );
}
