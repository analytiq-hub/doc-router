import { Link, useLocation, useParams } from 'react-router-dom';

/** Stub until org routes are ported from the Next App Router. */
export function OrgPlaceholderPage() {
  const { organizationId, '*': splat } = useParams();
  const location = useLocation();
  const subpath =
    typeof splat === 'string' && splat.length > 0
      ? `/${splat}`
      : location.pathname.replace(/^\/orgs\/[^/]+/, '') || '';

  return (
    <main className="max-w-lg mx-auto mt-16 p-6 space-y-4">
      <h1 className="text-xl font-semibold text-gray-900">Route not migrated yet (Vite)</h1>
      <p className="text-sm text-gray-600">
        Org <code className="text-xs bg-gray-100 px-1 rounded">{organizationId}</code>
        {subpath && (
          <>
            {' '}
            path <code className="text-xs bg-gray-100 px-1 rounded">{subpath}</code>
          </>
        )}
      </p>
      <p className="text-sm text-gray-600">
        Use the full app on{' '}
        <a className="text-blue-600 hover:underline" href={`http://localhost:3000/orgs/${organizationId}${subpath}`}>
          Next.js :3000
        </a>{' '}
        until this screen is ported.
      </p>
      <Link className="text-blue-600 hover:underline text-sm" to="/">
        ← Vite home
      </Link>
    </main>
  );
}
