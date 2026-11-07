import '@/styles/globals.css';
import type { Metadata } from 'next';

import { ClientRootLayout } from '@/components/ClientRootLayout';
import { appFaviconUrl, appName } from '@/config/branding';

export function generateMetadata(): Metadata {
  return {
    title: appName,
    description: appName,
    icons: {
      icon: appFaviconUrl,
    },
  };
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="stylesheet" href="/formio.full.css" />
      </head>
      <body suppressHydrationWarning>
        <ClientRootLayout>{children}</ClientRootLayout>
      </body>
    </html>
  );
}
