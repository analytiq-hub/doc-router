import colors from 'tailwindcss/colors';

/**
 * Doc Router UI colors — matches legacy Tailwind `blue-*` chrome (header `bg-blue-600`, etc.).
 * `primary-*` utilities use this scale so they stay visually identical to pre-branding-refactor `blue-*`.
 */
export const brandPalette = {
  50: colors.blue[50],
  100: colors.blue[100],
  200: colors.blue[200],
  300: colors.blue[300],
  400: colors.blue[400],
  500: colors.blue[500],
  600: colors.blue[600],
  700: colors.blue[700],
  800: colors.blue[800],
  900: colors.blue[900],
  950: colors.blue[950],
  DEFAULT: colors.blue[600],
} as const;

export const brandMain = colors.blue[600];
export const brandLight = colors.blue[400];
export const brandDark = colors.blue[800];
export const brandSoft = colors.blue[50];
