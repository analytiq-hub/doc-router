'use client';

import React from 'react';
import createCache from '@emotion/cache';
import { CacheProvider } from '@emotion/react';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import theme from '../styles/theme';

export default function ThemeRegistry({ children }: { children: React.ReactNode }) {
  const cache = React.useMemo(() => {
    const emotionCache = createCache({ key: 'mui', prepend: true });
    emotionCache.compat = true;
    return emotionCache;
  }, []);

  return (
    <CacheProvider value={cache}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </CacheProvider>
  );
}
