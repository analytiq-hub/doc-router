import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

/** Shared org hub page width + padding (matches documents, cases, schemas, …). */
export function OrgPageContainer({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn('mx-auto max-w-6xl p-4', className)}>{children}</div>;
}
