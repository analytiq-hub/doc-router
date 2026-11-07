'use client';

import { use } from 'react';

/** Next: `{ params: Promise<P> }`. Vite `withRouteParams` also spreads resolved fields (no `use(Promise)` on the client). */
export type RouteParamsProps<P extends Record<string, string>> =
  | ({ params: Promise<P> } & Partial<P>)
  | P;

type PropsWithPromise<P extends Record<string, string>> = { params: Promise<P> } & Partial<P>;

function hasPromiseParams<P extends Record<string, string>>(
  props: RouteParamsProps<P>,
): props is PropsWithPromise<P> {
  return (
    typeof props === 'object' &&
    props !== null &&
    'params' in props &&
    props.params instanceof Promise
  );
}

function syncParamsFromProps<P extends Record<string, string>>(props: PropsWithPromise<P>): P | null {
  const sync = {} as Partial<P>;
  for (const [key, value] of Object.entries(props)) {
    if (key === 'params' || typeof value !== 'string') continue;
    sync[key as keyof P] = value;
  }
  return Object.keys(sync).length > 0 ? (sync as P) : null;
}

export function useRouteParams<P extends Record<string, string>>(props: RouteParamsProps<P>): P {
  if (hasPromiseParams(props)) {
    const sync = syncParamsFromProps(props);
    if (sync) return sync;
    return use(props.params);
  }
  return props as P;
}
