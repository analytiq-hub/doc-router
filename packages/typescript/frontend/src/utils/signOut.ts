import { invalidateSessionCache } from '@/utils/api';
import { signOutClient } from '@/utils/backendAuth';

export async function signOut(): Promise<void> {
  invalidateSessionCache();
  await signOutClient();
  window.location.href = '/auth/signin';
}
