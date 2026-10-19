import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { SESSION_COOKIE_NAME } from '@/constants/sessionCookie';
import { appSessionFromApiToken } from '@/utils/sessionFromToken';

const cookieOptions = () => ({
  httpOnly: true,
  sameSite: 'lax' as const,
  secure: process.env.NODE_ENV === 'production',
  path: '/',
});

export async function GET() {
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE_NAME)?.value;
  if (!token) {
    return NextResponse.json({ session: null });
  }
  const session = await appSessionFromApiToken(token);
  if (!session) {
    cookieStore.delete(SESSION_COOKIE_NAME);
    return NextResponse.json({ session: null });
  }
  return NextResponse.json({ session });
}

export async function POST(req: Request) {
  const body = await req.json().catch(() => null);
  const token = body?.token;
  if (!token || typeof token !== 'string') {
    return NextResponse.json({ error: 'Missing token' }, { status: 400 });
  }

  const session = await appSessionFromApiToken(token);
  if (!session) {
    return NextResponse.json({ error: 'Invalid token' }, { status: 401 });
  }

  const cookieStore = await cookies();
  cookieStore.set(SESSION_COOKIE_NAME, token, cookieOptions());
  return NextResponse.json({ session });
}

export async function DELETE() {
  const cookieStore = await cookies();
  cookieStore.delete(SESSION_COOKIE_NAME);
  return NextResponse.json({ ok: true });
}
