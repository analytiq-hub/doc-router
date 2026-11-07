import { publicAppFavicon, publicAppName } from '@/config/publicEnv';

export const DEFAULT_APP_NAME = 'Smart Document Router';

export const appName = publicAppName(DEFAULT_APP_NAME);

/** Browser tab / metadata icon URL (default app/favicon.ico). */
export const appFaviconUrl = publicAppFavicon('/favicon.ico');
