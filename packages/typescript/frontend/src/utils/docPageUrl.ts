
export type DocSidebarTab = 'extraction' | 'flows' | 'text' | 'info' | 'chat' | 'forms';

const DOC_TABS: DocSidebarTab[] = ['extraction', 'flows', 'text', 'info', 'chat', 'forms'];

export function sidebarTabFromQuery(value: string | null): DocSidebarTab {
  if (value && (DOC_TABS as string[]).includes(value)) return value as DocSidebarTab;
  return 'extraction';
}

/** Build href from current pathname; omits `tab` when extraction (default). */
export function docPageHrefWithSearch(
  pathname: string,
  tab: DocSidebarTab,
  searchParams: URLSearchParams,
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
  searchParams: URLSearchParams,
): string {
  return docPageHrefWithSearch(
    `/orgs/${organizationId}/docs/${documentId}`,
    tab,
    searchParams,
  );
}
