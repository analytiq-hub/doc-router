import { apiClient, getApiErrorMsg } from '@/utils/api';

const FASTAPI_BASE = process.env.NEXT_PUBLIC_FASTAPI_FRONTEND_URL || '/fastapi';

export type LoginResponse = {
  token: string;
  user: {
    id: string;
    email: string;
    name?: string | null;
    is_sysadmin: boolean;
  };
};

export type RegisterResponse = {
  success: boolean;
  message: string;
};

export async function registerWithPassword(
  email: string,
  password: string,
  name: string,
): Promise<RegisterResponse> {
  try {
    const response = await apiClient.post<RegisterResponse>('/v0/account/auth/register', {
      email,
      password,
      name,
    });
    return response.data;
  } catch (error) {
    throw new Error(getApiErrorMsg(error));
  }
}

export async function loginWithPassword(email: string, password: string): Promise<LoginResponse> {
  try {
    const response = await apiClient.post<LoginResponse>('/v0/account/auth/login', { email, password });
    return response.data;
  } catch (error) {
    throw new Error(getApiErrorMsg(error));
  }
}

export function oauthStartUrl(provider: 'google' | 'github', returnTo = '/dashboard'): string {
  const params = new URLSearchParams({ return_to: returnTo });
  return `${FASTAPI_BASE}/v0/account/auth/${provider}/start?${params.toString()}`;
}

export async function persistSessionToken(token: string): Promise<void> {
  const response = await fetch('/api/auth/session', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token }),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error((data as { error?: string }).error || 'Failed to save session');
  }
}

export async function signOutClient(): Promise<void> {
  await fetch('/api/auth/session', { method: 'DELETE' });
}
