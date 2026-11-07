'use client';

import { use } from 'react';

/** Next passes `params` (Promise); Vite passes resolved param fields synchronously. */
export type RouteParamsProps<P extends Record<string, string>> =
  | ({ params: Promise<P> } & Partial<Record<never, never>>)
  | P;

export function useRouteParams<P extends Record<string, string>>(props: RouteParamsProps<P>): P {
  if (typeof props === 'object' && props !== null && 'params' in props && props.params) {
    return use(props.params);
  }
  return props as P;
}
