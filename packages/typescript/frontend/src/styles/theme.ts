import { createTheme, ThemeOptions } from '@mui/material/styles';

import { designTokens, primaryScale } from '@/lib/designTokens';

declare module '@mui/material/styles' {
  interface Palette {
    pdf_menubar: Palette['primary'];
  }
  interface PaletteOptions {
    pdf_menubar?: PaletteOptions['primary'];
  }
}

/** MUI bridge — palette values match `styles.css` tokens (hex only; MUI cannot parse oklch). */
const theme = createTheme({
  palette: {
    primary: {
      main: designTokens.primary,
      light: designTokens.brand,
      dark: primaryScale[800],
      contrastText: designTokens.primaryForeground,
    },
    secondary: {
      main: designTokens.destructive,
      light: designTokens.destructiveSoft,
      dark: '#9a1f2a',
      contrastText: designTokens.white,
    },
    pdf_menubar: {
      main: designTokens.secondary,
      contrastText: designTokens.black,
    },
    background: {
      default: designTokens.white,
      paper: designTokens.secondary,
    },
    text: {
      primary: designTokens.foreground,
      secondary: designTokens.mutedForeground,
    },
  },
  components: {
    MuiButton: {
      styleOverrides: {
        contained: {
          textTransform: 'none',
        },
      },
    },
  },
} as ThemeOptions);

export default theme;
