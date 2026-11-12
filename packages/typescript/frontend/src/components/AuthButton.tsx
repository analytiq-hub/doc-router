"use client"

import { useRouter } from '@/utils/appRouter';
import { signOut } from '@/utils/signOut';
import { useAppSession } from '@/contexts/AppSessionContext';
import { Button } from '@/components/ui/button';

function AuthButton() {
  const { session } = useAppSession();
  const router = useRouter();

  if (session) {
    return (
      <div className="flex items-center gap-3 text-brand-foreground">
        <span className="hidden text-sm sm:inline">{session.user?.name}</span>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="text-brand-foreground hover:bg-brand-foreground/10 hover:text-brand-foreground"
          onClick={() => void signOut()}
        >
          Sign out
        </Button>
      </div>
    );
  }

  return (
    <Button
      type="button"
      variant="secondary"
      size="sm"
      className="bg-card text-foreground shadow-sm ring-1 ring-brand-foreground/20 hover:bg-card/90"
      onClick={() => router.push('/auth/signin')}
    >
      Sign in or Register
    </Button>
  );
}

export default AuthButton;
