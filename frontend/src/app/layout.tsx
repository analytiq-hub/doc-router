import "@/styles/globals.css";
import React from 'react';
import { getServerSession } from "next-auth/next"
import SessionProvider from "@/components/SessionProvider"
import Layout from '@/components/Layout';
import Layout2 from "@/components/Layout2";
import ThemeRegistry from '@/components/ThemeRegistry';

export const metadata = {
  title: 'Doc Proxy',
  description: 'Smart Document Router',
  icons: {
    icon: '/favicon.ico',
  },
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const session = await getServerSession();
  return (
    <html lang="en">
      <body>
        <ThemeRegistry>
          <SessionProvider session={session}>
            <Layout2>{children}</Layout2>
          </SessionProvider>
        </ThemeRegistry>
      </body>
    </html>
  );
}
