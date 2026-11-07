import type { ComponentType } from 'react';
import { useParams } from 'react-router-dom';

/** Bridge App Router pages (`params` Promise) to React Router URL params. */
export function withRouteParams<P extends Record<string, string>>(
  paramKeys: (keyof P)[],
  Page: ComponentType<{ params: Promise<P> }>,
) {
  function Wrapped() {
    const routeParams = useParams();
    const resolved = {} as Record<string, string>;
    for (const key of paramKeys) {
      const value = routeParams[key as string];
      if (!value) return null;
      resolved[key as string] = value;
    }
    return <Page params={Promise.resolve(resolved as P)} />;
  }
  return Wrapped;
}
