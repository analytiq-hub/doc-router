import SigninPage from '@/pages/auth/signin';

/** Standalone sign-in (orchestrator-style split layout — no app shell). */
export function SignInPage() {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <SigninPage />
    </div>
  );
}
