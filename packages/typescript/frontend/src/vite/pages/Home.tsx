import { Link } from 'react-router-dom';
import { useAppSession } from '@/contexts/AppSessionContext';

export function HomePage() {
  const { session, status } = useAppSession();

  return (
    <main className="max-w-lg mx-auto mt-16 p-6 space-y-4">
      <h1 className="text-2xl font-semibold text-gray-900">Doc Router (Vite preview)</h1>
      <p className="text-gray-600 text-sm">
        Experimental SPA shell for the Next → Vite migration. Use Next on port 3000 for the full app.
      </p>
      <div className="rounded-md border border-gray-200 p-4 bg-white text-sm">
        <div>
          Session: <strong>{status}</strong>
        </div>
        {session?.user?.email && (
          <div className="mt-1 text-gray-700">Signed in as {session.user.email}</div>
        )}
      </div>
      {status !== 'authenticated' && (
        <Link className="text-blue-600 hover:underline" to="/auth/signin">
          Sign in
        </Link>
      )}
    </main>
  );
}
