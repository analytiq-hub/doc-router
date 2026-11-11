import { Link, useLocation, useParams } from 'react-router-dom';

/** Fallback when no org child route matches (should be rare). */
export function OrgPlaceholderPage() {
  const { organizationId, '*': splat } = useParams();
  const location = useLocation();
  const subpath =
    typeof splat === 'string' && splat.length > 0
      ? `/${splat}`
      : location.pathname.replace(/^\/orgs\/[^/]+/, '') || '';

  return (
    <main className="mx-auto mt-16 max-w-lg space-y-4 p-6">
      <h1 className="text-xl font-semibold text-gray-900">Unknown org route</h1>
      <p className="text-sm text-gray-600">
        Org <code className="rounded bg-gray-100 px-1 text-xs">{organizationId}</code>
        {subpath && (
          <>
            {' '}
            path <code className="rounded bg-gray-100 px-1 text-xs">{subpath}</code>
          </>
        )}
      </p>
      <p className="text-sm text-gray-600">
        This path is not registered in the Vite router. Check{' '}
        <code className="text-xs">src/router.tsx</code> or file a bug if a screen is missing.
      </p>
      <Link className="text-sm text-primary-600 hover:underline" to={`/orgs/${organizationId}/dashboard`}>
        Go to org dashboard
      </Link>
    </main>
  );
}
