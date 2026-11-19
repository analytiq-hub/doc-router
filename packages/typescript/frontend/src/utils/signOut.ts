import { invalidateSessionCache } from '@/utils/api';
import { signOutClient } from '@/utils/backendAuth';
import { forgetNavigation } from '@/utils/navMemory';

export async function signOut(): Promise<void> {
  invalidateSessionCache();
  forgetNavigation();
  await signOutClient();
  window.location.href = '/auth/signin';
}
