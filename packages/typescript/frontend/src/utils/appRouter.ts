/**
 * App navigation helpers (React Router). Replaces `next/navigation` in client code.
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
    refresh: () => {},
    back: () => navigate(-1),
    forward: () => navigate(1),
    prefetch: (_href: string) => {},
  };
}

/** Matches the App Router API: a read-only search params object, not a tuple. */
export function useSearchParams() {
  const [searchParams] = useRouterSearchParams();
  return searchParams;
}

export function useParams<T extends Record<string, string | undefined> = Record<string, string | undefined>>() {
  return useRouterParams() as T;
}
