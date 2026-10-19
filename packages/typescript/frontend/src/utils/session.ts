import { cookies } from 'next/headers';
import { AppSession } from '@/types/AppSession';
import { SESSION_COOKIE_NAME } from '@/constants/sessionCookie';
import { appSessionFromApiToken } from '@/utils/sessionFromToken';

export async function getAppServerSession(): Promise<AppSession | null> {
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE_NAME)?.value;
  if (!token) {
    return null;
  }
  return appSessionFromApiToken(token);
}
