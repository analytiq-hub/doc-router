/**
 * Vite-only stand-in for `next/navigation` (aliased in vite.config.ts).
 * Next builds use the real package; shared components keep their imports.
 */
import {
  useLocation,
  useNavigate,
  useParams as useRouterParams,
  useSearchParams as useRouterSearchParams,
} from 'react-router-dom';

export function usePathname(): string {
  return useLocation().pathname;
}

export function useRouter() {
  const navigate = useNavigate();
  return {
    push: (href: string) => navigate(href),
    replace: (href: string) => navigate(href, { replace: true }),
    refresh: () => navigate(0),
    back: () => navigate(-1),
    forward: () => navigate(1),
    prefetch: (_href: string) => {},
  };
}

export function useSearchParams() {
  const [searchParams] = useRouterSearchParams();
  return searchParams;
}

export function useParams<T extends Record<string, string | undefined> = Record<string, string | undefined>>() {
  return useRouterParams() as T;
}

export function redirect(url: string): never {
  if (typeof window !== 'undefined') {
    window.location.assign(url);
  }
  throw new Error(`redirect to ${url}`);
}
