// Relative path: `tailwind.config.ts` is loaded by PostCSS (no Vite `@/` aliases).
import { designTokens, primaryScale } from '../lib/designTokens';

/**
 * Doc Router `primary-*` utilities — derived from design tokens (`--primary`, `--brand`, …).
 */
export const brandPalette = primaryScale;

export const brandMain = designTokens.primary;
export const brandLight = designTokens.brand;
export const brandDark = primaryScale[800];
export const brandSoft = designTokens.primarySoft;
