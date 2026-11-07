import Layout from '@/components/Layout';
import SigninPage from '@/app/auth/signin/page';

/** Same chrome and markup as Next (`Layout` + `auth/layout` gray shell). */
export function SignInPage() {
  return (
    <Layout>
      <div className="min-h-screen bg-gray-50">
        <SigninPage />
      </div>
    </Layout>
  );
}
