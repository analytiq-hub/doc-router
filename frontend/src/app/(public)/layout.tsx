import "@/styles/globals.css";
import React from 'react';
import SessionProvider from "@/components/SessionProvider"
import ThemeRegistry from '@/components/ThemeRegistry';
import { getAppServerSession } from '@/utils/session';
import { Toaster } from 'react-hot-toast';
import { ToastContainer } from 'react-toastify';

export const metadata = {
  title: 'Smart Document Router',
  description: 'Smart Document Router',
  icons: {
    icon: '/favicon.ico',
  },
};

export default async function PublicLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const appSession = await getAppServerSession();
  return (
    <html lang="en">
      <body>
        <ThemeRegistry>
          <SessionProvider session={appSession}>
            {children}
          </SessionProvider>
        </ThemeRegistry>
        <ToastContainer position="top-right" />
        <Toaster position="top-right" />
      </body>
    </html>
  );
} 