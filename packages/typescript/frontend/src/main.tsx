import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { RouterProvider } from 'react-router-dom';

import '@/vite/vite-shell.css';
import '@/vite/tailwind-prelude.css';
import '@/vite/formio-tailwind';
import '@/styles/formio-custom.css';
import '@/vite/tailwind-utilities.css';
import '@/vite/app-theme.css';
import '@/styles/markdown-prose.css';
import { ensureFormioStyles } from '@/vite/ensureFormioStyles';
import { AppProviders } from '@/vite/AppProviders';

ensureFormioStyles();
import { router } from './router';

const root = document.getElementById('root');
if (!root) {
  throw new Error('Missing #root element');
}

createRoot(root).render(
  <StrictMode>
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>
  </StrictMode>,
);
