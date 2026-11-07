import { Link as RouterLink } from 'react-router-dom';
import type { AnchorHTMLAttributes, ReactNode } from 'react';

type LinkProps = AnchorHTMLAttributes<HTMLAnchorElement> & {
  href: string;
  children: ReactNode;
  prefetch?: boolean;
};

/** Vite stand-in for `next/link` (vite.config.ts alias). */
export default function Link({ href, children, prefetch: _prefetch, ...rest }: LinkProps) {
  return (
    <RouterLink to={href} {...rest}>
      {children}
    </RouterLink>
  );
}
