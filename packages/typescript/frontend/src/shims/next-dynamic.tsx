import React, { lazy, Suspense, type ComponentType } from 'react';

type DynamicOptions<P = Record<string, never>> = {
  loading?: () => React.ReactNode;
  ssr?: boolean;
};

/** Vite stand-in for `next/dynamic` (React.lazy + Suspense). */
export default function dynamic<P = Record<string, never>>(
  loader: () => Promise<{ default: ComponentType<P> }>,
  options?: DynamicOptions<P>,
) {
  const Lazy = lazy(loader);
  const Loading = options?.loading;

  function DynamicComponent(props: P) {
    return (
      <Suspense fallback={Loading ? <Loading /> : null}>
        <Lazy {...(props as P & React.JSX.IntrinsicAttributes)} />
      </Suspense>
    );
  }

  return DynamicComponent;
}
