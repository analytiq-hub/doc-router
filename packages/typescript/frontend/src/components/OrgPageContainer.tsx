import type { ComponentPropsWithoutRef, ReactNode } from 'react';
import { cn } from '@/lib/utils';

/** Shared org hub page width + padding (matches documents, cases, schemas, …). */
export function OrgPageContainer({
  children,
  className,
  ...rest
}: { children: ReactNode; className?: string } & ComponentPropsWithoutRef<'div'>) {
  return (
    <div className={cn('mx-auto max-w-6xl p-4', className)} {...rest}>
      {children}
    </div>
  );
}
