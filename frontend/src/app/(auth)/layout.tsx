import "@/styles/globals.css";
import React from 'react';
import SessionProvider from "@/components/SessionProvider"
import ThemeRegistry from '@/components/ThemeRegistry';
import { getAppServerSession } from '@/utils/session';
import { Toaster } from 'react-hot-toast';
import { ToastContainer } from 'react-toastify';

export const metadata = {
  title: 'Smart Document Router - Authentication',
  description: 'Smart Document Router Authentication',
  icons: {
    icon: '/favicon.ico',
  },
};

export default async function AuthLayout({
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
            <div className="min-h-screen bg-gray-50">
              {children}
            </div>
          </SessionProvider>
        </ThemeRegistry>
        <ToastContainer position="top-right" />
        <Toaster position="top-right" />
      </body>
    </html>
  );
} 