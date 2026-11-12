/**
 * Design token hex values — keep in sync with `src/styles.css` `:root` (orchestrator `ui.md` §3).
 * CSS is authoritative for styling; this module is for the MUI / Data Grid bridge until Phase 3+.
 */
export const designTokens = {
  background: '#ecf0f1',
  foreground: '#2c3e50',
  card: '#ffffff',
  cardForeground: '#2c3e50',
  brand: '#0078d4',
  brandForeground: '#ffffff',
  primary: '#0754a6',
  primarySoft: '#e6f0fa',
  primaryForeground: '#ffffff',
  secondary: '#f3f4f6',
  secondaryForeground: '#1f2937',
  muted: '#f3f4f6',
  mutedForeground: '#4b5563',
  accent: '#f3f4f6',
  border: '#d1d5db',
  input: '#8a919e',
  ring: '#0078d4',
  destructive: '#c62836',
  destructiveSoft: '#fce8eb',
  success: '#16804a',
  white: '#ffffff',
  black: '#000000',
} as const;

/** Legacy Tailwind `primary-*` utilities via `tailwind.config.ts` until shell is fully on semantic classes. */
export const primaryScale = {
  50: designTokens.primarySoft,
  100: '#d6e8f7',
  200: '#adcff0',
  300: '#7eb5e3',
  400: '#3d93d4',
  500: designTokens.brand,
  600: designTokens.primary,
  700: '#064388',
  800: '#04326a',
  900: '#03214c',
  950: '#021a3d',
  DEFAULT: designTokens.primary,
} as const;
