import { useEffect, useId, useRef, useState } from 'react';
import type { ButtonHTMLAttributes, CSSProperties, InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from 'react';
import { createPortal } from 'react-dom';
import { Activity, Camera, Cctv, Ellipsis, Eye, EyeOff, ImageUp, ScanLine } from 'lucide-react';

/* ==========================================================================
   Estado de captura — el vocabulario central del producto.
   `live` capturando · `ready` conectada en espera · `offline` sin señal ·
   `idle` fuera de servicio. El color nunca comunica solo: siempre lleva texto.
   ========================================================================== */
export type CaptureState = 'live' | 'ready' | 'offline' | 'idle';

export const captureLabel: Record<CaptureState, string> = {
  live: 'Capturando',
  ready: 'Lista',
  offline: 'Sin señal',
  idle: 'Fuera de servicio',
};

/* ==========================================================================
   Iconografía — trazo 1.75 sobre grilla de 24. Solo iconos que aportan
   información o identifican una acción; nunca como relleno decorativo.
   ========================================================================== */
const iconPaths: Record<string, ReactNode> = {
  board: <><path d="M4 4h16v16H4z" /><path d="M4 12h16M12 4v16" /><circle cx="12" cy="12" r="2.4" /></>,
  clip: <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M3 9h18M9 5v4M15 5v4" /><path d="m11 12.5 3.5 2-3.5 2v-4Z" fill="currentColor" stroke="none" /></>,
  bell: <><path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" /><path d="M10 21h4" /></>,
  settings: <><circle cx="12" cy="12" r="3.2" /><path d="M19.4 14.5a1.7 1.7 0 0 0 .34 1.88l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.88-.34 1.7 1.7 0 0 0-1.03 1.56V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.11-1.56 1.7 1.7 0 0 0-1.88.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.7 1.7 0 0 0 .34-1.88 1.7 1.7 0 0 0-1.56-1.03H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.56-1.11 1.7 1.7 0 0 0-.34-1.88l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.7 1.7 0 0 0 1.88.34H9a1.7 1.7 0 0 0 1.03-1.56V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1.03 1.56 1.7 1.7 0 0 0 1.88-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.7 1.7 0 0 0-.34 1.88V9a1.7 1.7 0 0 0 1.56 1.03H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1.03Z" /></>,
  qr: <><path d="M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4z" /><path d="M14 14h2v2h-2zM18 18h2v2h-2zM18 14h2M14 18v2" /></>,
  play: <path d="m8 5 11 7-11 7V5Z" fill="currentColor" stroke="none" />,
  record: <circle cx="12" cy="12" r="6" fill="currentColor" stroke="none" />,
  stop: <rect x="6" y="6" width="12" height="12" rx="1.5" fill="currentColor" stroke="none" />,
  arrowRight: <path d="M5 12h14M13 6l6 6-6 6" />,
  arrowLeft: <path d="M19 12H5M11 18l-6-6 6-6" />,
  chevronDown: <path d="m6 9 6 6 6-6" />,
  chevronRight: <path d="m9 6 6 6-6 6" />,
  check: <path d="m5 12 4 4L19 6" />,
  close: <path d="m6 6 12 12M18 6 6 18" />,
  plus: <path d="M12 5v14M5 12h14" />,
  search: <><circle cx="10.8" cy="10.8" r="6.8" /><path d="m16 16 5 5" /></>,
  logout: <><path d="M10 5H5v14h5" /><path d="M14 8l4 4-4 4M8 12h10" /></>,
  gesture: <><path d="M8 11V5.5a1.5 1.5 0 0 1 3 0V11" /><path d="M11 10.5V4.5a1.5 1.5 0 0 1 3 0V11" /><path d="M14 11V6.5a1.5 1.5 0 0 1 3 0V13c0 4-2.5 7-6 7s-6-3-6-7v-2a1.5 1.5 0 0 1 3 0" /></>,
  button: <><circle cx="12" cy="12" r="8" /><circle cx="12" cy="12" r="3.2" /></>,
  link: <><path d="M10 13a5 5 0 0 0 7 0l2-2a5 5 0 0 0-7-7l-1 1" /><path d="M14 11a5 5 0 0 0-7 0l-2 2a5 5 0 0 0 7 7l1-1" /></>,
  copy: <><rect x="9" y="9" width="12" height="12" rx="2" /><path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1" /></>,
  trash: <><path d="M4 7h16M10 11v6M14 11v6" /><path d="M6 7l1 13h10l1-13M9 7V4h6v3" /></>,
  warning: <><path d="M12 4 2.8 20h18.4L12 4Z" /><path d="M12 10v4M12 17.4v.2" /></>,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8v.2" /></>,
  refresh: <><path d="M3 12a9 9 0 0 1 15.5-6.2M21 12a9 9 0 0 1-15.5 6.2" /><path d="M18 3v3.5h-3.5M6 21v-3.5h3.5" /></>,
  menu: <path d="M4 7h16M4 12h16M4 17h16" />,
  user: <><circle cx="12" cy="8" r="3.6" /><path d="M4.5 20a7.5 7.5 0 0 1 15 0" /></>,
  whatsapp: <><path d="M4 20l1.3-4A8 8 0 1 1 8 18.7L4 20Z" /><path d="M9 9.5c0 3 2.5 5.5 5.5 5.5" /></>,
  sun: <><circle cx="12" cy="12" r="3.5" /><path d="M12 2v2M12 20v2M4.93 4.93l1.42 1.42M17.65 17.65l1.42 1.42M2 12h2M20 12h2M4.93 19.07l1.42-1.42M17.65 6.35l1.42-1.42" /></>,
  moon: <path d="M20.5 15.5A8.5 8.5 0 0 1 8.5 3.5 8.5 8.5 0 1 0 20.5 15.5Z" />,
};

export function Icon({ name, size = 18, className = '' }: { name: string; size?: number; className?: string }) {
  const LibraryIcon = name === 'camera' ? Camera : name === 'court' ? Cctv : name === 'more' ? Ellipsis : name === 'activity' ? Activity : name === 'imageUpload' ? ImageUp : name === 'scan' ? ScanLine : name === 'eye' ? Eye : name === 'eyeOff' ? EyeOff : null;
  if (LibraryIcon) {
    return <LibraryIcon className={`cv-icon ${className}`} size={size} strokeWidth={1.75} aria-hidden="true" focusable="false" />;
  }
  return (
    <svg
      className={`cv-icon ${className}`}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {iconPaths[name] ?? iconPaths.info}
    </svg>
  );
}

/* ==========================================================================
   Botones — cuatro niveles de énfasis explícitos. Nunca dos primarios juntos.
   ========================================================================== */
type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';

export function Button({
  variant = 'secondary',
  size = 'md',
  iconBefore,
  iconAfter,
  loading = false,
  children,
  className = '',
  disabled,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: 'sm' | 'md';
  iconBefore?: string;
  iconAfter?: string;
  loading?: boolean;
}) {
  return (
    <button
      className={`cv-btn cv-btn--${variant} cv-btn--${size} ${loading ? 'is-loading' : ''} ${className}`}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading ? <span className="cv-btn__spinner" aria-hidden="true" /> : iconBefore ? <Icon name={iconBefore} size={size === 'sm' ? 14 : 16} /> : null}
      {children ? <span>{children}</span> : null}
      {iconAfter && !loading ? <Icon name={iconAfter} size={size === 'sm' ? 14 : 16} /> : null}
    </button>
  );
}

/* ==========================================================================
   Menú contextual — acciones secundarias que no deben competir con el contenido.
   ========================================================================== */
export function OverflowMenu({
  label,
  open,
  onOpenChange,
  children,
  className = '',
}: {
  label: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: ReactNode;
  className?: string;
}) {
  const rootRef = useRef<HTMLDivElement>(null);
  const menuId = useId();

  useEffect(() => {
    if (!open) return undefined;
    const closeFromOutside = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) onOpenChange(false);
    };
    const closeFromKeyboard = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onOpenChange(false);
    };
    document.addEventListener('pointerdown', closeFromOutside);
    document.addEventListener('keydown', closeFromKeyboard);
    return () => {
      document.removeEventListener('pointerdown', closeFromOutside);
      document.removeEventListener('keydown', closeFromKeyboard);
    };
  }, [open, onOpenChange]);

  return (
    <div ref={rootRef} className={`cv-overflow ${open ? 'is-open' : ''} ${className}`}>
      <button
        type="button"
        className="cv-overflow__trigger"
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onClick={() => onOpenChange(!open)}
      >
        <Icon name="more" size={19} />
      </button>
      {open ? <div id={menuId} className="cv-overflow__menu" role="menu">{children}</div> : null}
    </div>
  );
}

export function MenuItem({
  icon,
  tone = 'default',
  children,
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  icon?: string;
  tone?: 'default' | 'danger';
}) {
  return (
    <button type="button" role="menuitem" className={`cv-menu-item cv-menu-item--${tone} ${className}`} {...props}>
      {icon ? <Icon name={icon} size={15} /> : null}
      <span>{children}</span>
    </button>
  );
}

/** Control compacto de tema. El texto accesible explica el resultado. */
export function ThemeToggle({ theme, onToggle, className = '' }: { theme: 'light' | 'dark'; onToggle: () => void; className?: string }) {
  const next = theme === 'light' ? 'oscuro' : 'claro';
  return (
    <button
      type="button"
      className={`cv-theme-toggle ${className}`}
      aria-label={`Usar modo ${next}`}
      title={`Usar modo ${next}`}
      onClick={onToggle}
    >
      <span className="cv-theme-toggle__icons" aria-hidden="true">
        <Icon name="sun" size={16} className="cv-theme-toggle__sun" />
        <Icon name="moon" size={16} className="cv-theme-toggle__moon" />
      </span>
    </button>
  );
}

/* ==========================================================================
   Indicadores de estado
   ========================================================================== */
export function StatusDot({ state, pulse = false }: { state: CaptureState; pulse?: boolean }) {
  return <span className={`cv-dot cv-dot--${state} ${pulse && state === 'live' ? 'cv-dot--pulse' : ''}`} aria-hidden="true" />;
}

export function StatusPill({ state, children, pulse = true }: { state: CaptureState; children?: ReactNode; pulse?: boolean }) {
  return (
    <span className={`cv-pill cv-pill--${state}`}>
      <StatusDot state={state} pulse={pulse} />
      {children ?? captureLabel[state]}
    </span>
  );
}

/** Medidor de progreso basado en datos; la geometría y el movimiento son globales. */
export function Meter({ value, max, label, summary }: { value: number; max: number; label: string; summary?: ReactNode }) {
  const safeMax = Math.max(0, max);
  const safeValue = Math.max(0, Math.min(value, safeMax));
  const percentage = safeMax > 0 ? (safeValue / safeMax) * 100 : 0;
  return (
    <div
      className="cv-meter"
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={safeMax}
      aria-valuenow={safeValue}
      style={{ '--cv-meter-value': `${percentage}%` } as CSSProperties}
    >
      <span className="cv-meter__track"><i /></span>
      {summary ? <span className="cv-meter__summary">{summary}</span> : null}
    </div>
  );
}

/* ==========================================================================
   Formularios
   ========================================================================== */
export function TextField({
  label,
  hint,
  error,
  suffix,
  passwordReveal = false,
  className = '',
  id,
  type,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string; hint?: ReactNode; error?: string; suffix?: ReactNode; passwordReveal?: boolean }) {
  const autoId = useId();
  const fieldId = id ?? autoId;
  const describedBy = error ? `${fieldId}-err` : hint ? `${fieldId}-hint` : undefined;
  const [passwordVisible, setPasswordVisible] = useState(false);
  const canRevealPassword = passwordReveal && type === 'password';
  return (
    <div className={`cv-field ${error ? 'cv-field--invalid' : ''} ${className}`}>
      <label className="cv-field__label" htmlFor={fieldId}>{label}</label>
      <div className={`cv-field__control ${canRevealPassword ? 'cv-field__control--password' : ''}`}>
        <input id={fieldId} type={canRevealPassword && passwordVisible ? 'text' : type} aria-invalid={error ? true : undefined} aria-describedby={describedBy} {...props} />
        {suffix ? <span className="cv-field__suffix">{suffix}</span> : null}
        {canRevealPassword ? (
          <button
            type="button"
            className="cv-field__password-toggle"
            aria-label={passwordVisible ? 'Ocultar contraseña' : 'Mostrar contraseña'}
            aria-pressed={passwordVisible}
            title={passwordVisible ? 'Ocultar contraseña' : 'Mostrar contraseña'}
            onClick={() => setPasswordVisible((current) => !current)}
          >
            <Icon name={passwordVisible ? 'eyeOff' : 'eye'} size={17} />
          </button>
        ) : null}
      </div>
      {error ? (
        <p className="cv-field__error" id={`${fieldId}-err`} role="alert"><Icon name="warning" size={13} />{error}</p>
      ) : hint ? (
        <p className="cv-field__hint" id={`${fieldId}-hint`}>{hint}</p>
      ) : null}
    </div>
  );
}

export function SelectField({
  label,
  hint,
  children,
  className = '',
  id,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & { label: string; hint?: ReactNode }) {
  const autoId = useId();
  const fieldId = id ?? autoId;
  return (
    <div className={`cv-field ${className}`}>
      <label className="cv-field__label" htmlFor={fieldId}>{label}</label>
      <div className="cv-field__control cv-field__control--select">
        <select id={fieldId} aria-describedby={hint ? `${fieldId}-hint` : undefined} {...props}>{children}</select>
        <Icon name="chevronDown" size={15} />
      </div>
      {hint ? <p className="cv-field__hint" id={`${fieldId}-hint`}>{hint}</p> : null}
    </div>
  );
}

export function Switch({
  checked,
  onChange,
  label,
  description,
  disabled,
}: { checked: boolean; onChange: (next: boolean) => void; label: string; description?: string; disabled?: boolean }) {
  return (
    <label className={`cv-switch ${disabled ? 'is-disabled' : ''}`}>
      <input type="checkbox" role="switch" checked={checked} disabled={disabled} onChange={(event) => onChange(event.target.checked)} />
      <span className="cv-switch__track" aria-hidden="true"><i /></span>
      <span className="cv-switch__text">
        <span className="cv-switch__label">{label}</span>
        {description ? <span className="cv-switch__desc">{description}</span> : null}
      </span>
    </label>
  );
}

export function Segmented<T extends string>({
  value,
  options,
  onChange,
  ariaLabel,
}: { value: T; options: Array<{ value: T; label: string; count?: number; disabled?: boolean }>; onChange: (next: T) => void; ariaLabel: string }) {
  return (
    <div className="cv-segmented" role="group" aria-label={ariaLabel}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={option.value === value}
          disabled={option.disabled && option.value !== value}
          className={option.value === value ? 'is-active' : ''}
          onClick={() => onChange(option.value)}
        >
          {option.label}
          {option.count !== undefined ? <em>{option.count}</em> : null}
        </button>
      ))}
    </div>
  );
}

/* ==========================================================================
   Estados de contenido
   ========================================================================== */
export function Skeleton({ w = '100%', h = 12, className = '' }: { w?: string | number; h?: number; className?: string }) {
  return <span className={`cv-skeleton ${className}`} style={{ width: w, height: h }} aria-hidden="true" />;
}

export function EmptyState({
  icon = 'search',
  title,
  children,
  action,
  compact = false,
  accent = 'neutral',
}: { icon?: string; title: string; children?: ReactNode; action?: ReactNode; compact?: boolean; accent?: 'neutral' | 'volt' | 'flare' | 'ice' }) {
  return (
    <div className={`cv-empty cv-empty--${accent} ${compact ? 'cv-empty--compact' : ''}`}>
      <span className="cv-empty__mark" aria-hidden="true"><Icon name={icon} size={compact ? 18 : 22} /></span>
      <div>
        <h3>{title}</h3>
        {children ? <p className="t-measure">{children}</p> : null}
        {action ? <div className="cv-empty__action">{action}</div> : null}
      </div>
    </div>
  );
}

export function Banner({
  tone = 'info',
  title,
  children,
  action,
  onDismiss,
}: { tone?: 'info' | 'success' | 'warning' | 'error'; title: string; children?: ReactNode; action?: ReactNode; onDismiss?: () => void }) {
  const icon = tone === 'success' ? 'check' : tone === 'error' || tone === 'warning' ? 'warning' : 'info';
  return (
    <div className={`cv-banner cv-banner--${tone}`} role={tone === 'error' ? 'alert' : 'status'}>
      <span className="cv-banner__mark" aria-hidden="true"><Icon name={icon} size={15} /></span>
      <div className="cv-banner__body">
        <b>{title}</b>
        {children ? <p>{children}</p> : null}
      </div>
      {action}
      {onDismiss ? <button className="cv-banner__close" aria-label="Cerrar aviso" onClick={onDismiss}><Icon name="close" size={14} /></button> : null}
    </div>
  );
}

/* ==========================================================================
   Diálogo — foco atrapado, Escape, scroll bloqueado, retorno de foco.
   ========================================================================== */
const FOCUSABLE = 'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';

export function Dialog({
  open,
  title,
  description,
  children,
  footer,
  onClose,
  size = 'md',
  tone,
}: {
  open: boolean;
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
  onClose: () => void;
  size?: 'sm' | 'md' | 'lg';
  tone?: 'danger';
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  const titleId = useId();
  const descId = useId();

  useEffect(() => {
    if (!open) return undefined;
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    // El foco entra en el contenido, no en la "X": lo primero que hace falta es
    // el primer campo del formulario, no la salida.
    const body = panelRef.current?.querySelector<HTMLElement>('.cv-dialog__body');
    const first = body?.querySelector<HTMLElement>(FOCUSABLE) ?? panelRef.current?.querySelector<HTMLElement>(FOCUSABLE);
    (first ?? panelRef.current)?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.stopPropagation(); onCloseRef.current(); return; }
      if (event.key !== 'Tab' || !panelRef.current) return;
      const nodes = Array.from(panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((node) => node.offsetParent !== null);
      if (nodes.length === 0) return;
      const start = nodes[0];
      const end = nodes[nodes.length - 1];
      if (event.shiftKey && document.activeElement === start) { event.preventDefault(); end.focus(); }
      else if (!event.shiftKey && document.activeElement === end) { event.preventDefault(); start.focus(); }
    };
    document.addEventListener('keydown', onKeyDown, true);
    return () => {
      document.removeEventListener('keydown', onKeyDown, true);
      document.body.style.overflow = overflow;
      previous?.focus?.();
    };
  }, [open]);

  if (!open) return null;
  return createPortal(
    <div className="cv-dialog-layer" role="presentation" onMouseDown={onClose}>
      <div
        ref={panelRef}
        className={`cv-dialog cv-dialog--${size} ${tone ? `cv-dialog--${tone}` : ''}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descId : undefined}
        tabIndex={-1}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="cv-dialog__head">
          <div>
            <h2 id={titleId}>{title}</h2>
            {description ? <p id={descId}>{description}</p> : null}
          </div>
          <button className="cv-dialog__close" aria-label="Cerrar" onClick={onClose}><Icon name="close" size={16} /></button>
        </header>
        <div className="cv-dialog__body">{children}</div>
        {footer ? <footer className="cv-dialog__foot">{footer}</footer> : null}
      </div>
    </div>,
    document.body,
  );
}

/* ==========================================================================
   Identidad
   ========================================================================== */
export function Avatar({ initials, size = 'md' }: { initials: string; size?: 'sm' | 'md' }) {
  return <span className={`cv-avatar cv-avatar--${size}`} aria-hidden="true">{initials}</span>;
}
