import React from 'react';
import { ThemeProvider } from '@mui/material/styles';
import ScopedCssBaseline from '@mui/material/ScopedCssBaseline';
import theme from '@/styles/theme';

/** MUI theme scope for PDF viewer stack only (Phase 8 island). */
export function MuiPdfThemeIsland({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider theme={theme}>
      <ScopedCssBaseline sx={{ display: 'flex', flexDirection: 'column', minHeight: 0, flex: 1 }}>
        {children}
      </ScopedCssBaseline>
    </ThemeProvider>
  );
}
