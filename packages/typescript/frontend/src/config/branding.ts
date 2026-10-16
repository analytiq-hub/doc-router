export const DEFAULT_APP_NAME = 'Smart Document Router';

export const appName =
  (typeof process.env.NEXT_PUBLIC_APP_NAME === 'string' &&
    process.env.NEXT_PUBLIC_APP_NAME.trim()) ||
  DEFAULT_APP_NAME;

/** Browser tab / metadata icon URL (default app/favicon.ico). */
export const appFaviconUrl =
  (typeof process.env.NEXT_PUBLIC_APP_FAVICON === 'string' &&
    process.env.NEXT_PUBLIC_APP_FAVICON.trim()) ||
  '/favicon.ico';
