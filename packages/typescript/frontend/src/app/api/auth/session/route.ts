import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { SESSION_COOKIE_NAME } from '@/constants/sessionCookie';
import { appSessionFromApiToken } from '@/utils/sessionFromToken';

// Browsers drop Secure cookies on plain-HTTP origins (other than localhost), so derive
// the flag from the scheme the browser actually used (nginx sets X-Forwarded-Proto).
const isHttpsRequest = (req: Request) => {
  const forwardedProto = req.headers.get('x-forwarded-proto')?.split(',')[0].trim();
  if (forwardedProto) {
    return forwardedProto === 'https';
  }
  return new URL(req.url).protocol === 'https:';
};

const cookieOptions = (req: Request) => ({
  httpOnly: true,
  sameSite: 'lax' as const,
  secure: isHttpsRequest(req),
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
  cookieStore.set(SESSION_COOKIE_NAME, token, cookieOptions(req));
  return NextResponse.json({ session });
}

export async function DELETE() {
  const cookieStore = await cookies();
  cookieStore.delete(SESSION_COOKIE_NAME);
  return NextResponse.json({ ok: true });
}
