/**
 * Contrato TypeScript del sistema visual.
 *
 * Los valores apuntan a custom properties para que SVG, canvas y cualquier
 * componente calculado respondan al tema activo sin duplicar hexadecimales.
 */
export const tokens = {
  color: {
    canvas: 'var(--canvas)',
    surface: 'var(--surface)',
    surfaceRaised: 'var(--surface-raised)',
    surfaceSubtle: 'var(--surface-2)',
    textPrimary: 'var(--text-primary)',
    textSecondary: 'var(--text-secondary)',
    textMuted: 'var(--text-muted)',
    border: 'var(--line)',
    brand: 'var(--brand-500)',
    warning: 'var(--warn-500)',
    danger: 'var(--danger-500)',
    info: 'var(--info-500)',
  },
  captureState: {
    live: 'var(--brand-500)',
    ready: 'var(--warn-500)',
    offline: 'var(--danger-500)',
    idle: 'var(--idle-500)',
  },
  typography: {
    display: 'var(--font-display)',
    ui: 'var(--font-ui)',
  },
  spacing: { 1: 'var(--space-1)', 2: 'var(--space-2)', 3: 'var(--space-3)', 4: 'var(--space-4)', 5: 'var(--space-5)', 6: 'var(--space-6)', 8: 'var(--space-8)', 10: 'var(--space-10)', 12: 'var(--space-12)', 16: 'var(--space-16)' },
  radius: { xs: 'var(--radius-xs)', sm: 'var(--radius-sm)', md: 'var(--radius-md)', lg: 'var(--radius-lg)', xl: 'var(--radius-xl)', round: 'var(--radius-round)' },
  motion: { instant: 'var(--dur-instant)', fast: 'var(--dur-fast)', base: 'var(--dur-base)', slow: 'var(--dur-slow)', easeOut: 'var(--ease-out)' },
  zIndex: { content: 1, sticky: 10, nav: 20, toast: 30, dialog: 40 },
} as const;

export type CourtVisionTokens = typeof tokens;
