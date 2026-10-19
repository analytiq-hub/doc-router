import jwt from 'jsonwebtoken';
import { ObjectId } from 'mongodb';
import { AppSession } from '@/types/AppSession';
import { getDatabase } from '@/utils/mongodb';

const SYSTEM_ROLE_SYSADMIN = 'sysadmin';

type SessionJwtPayload = {
  userId: string;
  userName?: string;
  email: string;
  exp?: number;
};

export async function appSessionFromApiToken(token: string): Promise<AppSession | null> {
  const secret = process.env.APP_SECRET;
  if (!secret) {
    return null;
  }

  let payload: SessionJwtPayload;
  try {
    payload = jwt.verify(token, secret) as SessionJwtPayload;
  } catch {
    return null;
  }

  if (!payload.userId || !payload.email) {
    return null;
  }

  const db = getDatabase();
  const user = await db.collection('users').findOne(
    { _id: new ObjectId(payload.userId) },
    { projection: { name: 1, system_role: 1, email: 1 } },
  );
  if (!user) {
    return null;
  }

  const expires = payload.exp
    ? new Date(payload.exp * 1000).toISOString()
    : new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString();

  return {
    user: {
      id: payload.userId,
      email: payload.email,
      name: (user.name as string | undefined) ?? payload.userName ?? null,
      isSysadmin: user.system_role === SYSTEM_ROLE_SYSADMIN,
    },
    apiAccessToken: token,
    providerAccessToken: '',
    expires,
  };
}
