import type { ComponentType } from 'react';
import { useParams } from 'react-router-dom';

import type { RouteParamsProps } from '@/utils/useRouteParams';

/** Bridge App Router pages to React Router (sync props — no `use(Promise)` on the client). */
export function withRouteParams<P extends Record<string, string>>(
  paramKeys: (keyof P)[],
  Page: ComponentType<RouteParamsProps<P>>,
) {
  function Wrapped() {
    const routeParams = useParams();
    const resolved = {} as Record<string, string>;
    for (const key of paramKeys) {
      const value = routeParams[key as string];
      if (!value) return null;
      resolved[key as string] = value;
    }
    return <Page {...(resolved as P)} />;
  }
  return Wrapped;
}
