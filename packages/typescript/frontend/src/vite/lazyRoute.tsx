import { lazy, Suspense, type ComponentType, type ReactNode } from 'react';

export function RouteLoadingFallback() {
  return (
    <div className="flex min-h-[12rem] items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary-600 border-t-transparent" />
    </div>
  );
}

function withSuspense(element: ReactNode) {
  return <Suspense fallback={<RouteLoadingFallback />}>{element}</Suspense>;
}

/** Lazy default export → route element. */
export function lazyRoute(load: () => Promise<{ default: ComponentType }>) {
  const Lazy = lazy(load);
  return withSuspense(<Lazy />);
}

/** Lazy named export → route element. */
export function lazyNamedRoute(
  load: () => Promise<Record<string, ComponentType>>,
  name: string,
) {
  const Lazy = lazy(() =>
    load().then((mod) => {
      const Comp = mod[name];
      if (!Comp) {
        throw new Error(`lazyNamedRoute: "${name}" not exported from module`);
      }
      return { default: Comp };
    }),
  );
  return withSuspense(<Lazy />);
}
