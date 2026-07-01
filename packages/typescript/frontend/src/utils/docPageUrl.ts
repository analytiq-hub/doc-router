import type { ReadonlyURLSearchParams } from 'next/navigation';

export type DocSidebarTab = 'extraction' | 'flows' | 'forms';

export function sidebarTabFromQuery(value: string | null): DocSidebarTab {
  if (value === 'flows' || value === 'forms') return value;
  return 'extraction';
}

/** Build href from current pathname; omits `tab` when extraction (default). */
export function docPageHrefWithSearch(
  pathname: string,
  tab: DocSidebarTab,
  searchParams: ReadonlyURLSearchParams | URLSearchParams,
): string {
  const params = new URLSearchParams(searchParams.toString());
  if (tab === 'extraction') {
    params.delete('tab');
  } else {
    params.set('tab', tab);
  }
  const qs = params.toString();
  return `${pathname}${qs ? `?${qs}` : ''}`;
}

/** Document viewer href; omits `tab` when extraction (default). Preserves other query params (e.g. bbox). */
export function docPageHref(
  organizationId: string,
  documentId: string,
  tab: DocSidebarTab,
  searchParams: ReadonlyURLSearchParams | URLSearchParams,
): string {
  return docPageHrefWithSearch(
    `/orgs/${organizationId}/docs/${documentId}`,
    tab,
    searchParams,
  );
}
