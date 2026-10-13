import type { Tag } from '@docrouter/sdk';

export type DocumentListSearchParameters = {
  searchTerm: string;
  selectedTagFilters: Tag[];
  metadataSearch: string;
  caseIdFilter?: string;
  paginationModel?: { page: number; pageSize: number };
};

export function parseAndEncodeMetadataSearch(searchStr: string): string | null {
  try {
    const pairs: string[] = [];
    const rawPairs = searchStr.split(',');

    for (const rawPair of rawPairs) {
      const trimmed = rawPair.trim();
      if (!trimmed) continue;

      const equalIndex = trimmed.indexOf('=');
      if (equalIndex === -1) continue;

      const key = trimmed.substring(0, equalIndex).trim();
      const value = trimmed.substring(equalIndex + 1).trim();

      if (key && value) {
        pairs.push(`${encodeURIComponent(key)}=${encodeURIComponent(value)}`);
      }
    }

    return pairs.length > 0 ? pairs.join(',') : null;
  } catch (error) {
    console.error('Error parsing metadata search:', error);
    return null;
  }
}

export function buildListDocumentsQuery(
  search: DocumentListSearchParameters,
  skip: number,
  limit: number,
  extra?: { sort?: string; filters?: string }
) {
  return {
    skip,
    limit,
    nameSearch: search.searchTerm.trim() || undefined,
    tagIds:
      search.selectedTagFilters.length > 0
        ? search.selectedTagFilters.map((tag) => tag.id).join(',')
        : undefined,
    metadataSearch: search.metadataSearch.trim()
      ? parseAndEncodeMetadataSearch(search.metadataSearch.trim()) || undefined
      : undefined,
    caseId: search.caseIdFilter?.trim() || undefined,
    sort: extra?.sort,
    filters: extra?.filters,
  };
}
