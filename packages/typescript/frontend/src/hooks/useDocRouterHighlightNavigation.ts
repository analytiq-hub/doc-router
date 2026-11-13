import { useEffect, useRef, useState } from 'react';
import type { HighlightInfo } from '@/hooks/useOCRBlocks';
import { findNextHighlightedPage } from '@/lib/findNextHighlightedPage';

export type PageNavigationRequest = { page: number; seq: number };

/** Jump PDF viewer when extraction/forms set `highlightInfo` (match cycling). */
export function useDocRouterHighlightNavigation(
  highlightInfo: HighlightInfo | undefined,
  currentPage: number,
): PageNavigationRequest | undefined {
  const [navigation, setNavigation] = useState<PageNavigationRequest | undefined>();
  const seqRef = useRef(0);
  const lastSearchRef = useRef<{
    promptId: string;
    key?: string;
    value: string;
    lastPage?: number;
  } | null>(null);
  const currentPageRef = useRef(currentPage);
  currentPageRef.current = currentPage;

  useEffect(() => {
    const hasBlocks = (highlightInfo?.blocks?.length ?? 0) > 0;
    const hasPdf = (highlightInfo?.pdfFallbackHits?.length ?? 0) > 0;
    if (!hasBlocks && !hasPdf) {
      lastSearchRef.current = null;
      return;
    }

    const lastSearch = lastSearchRef.current;
    const isSameSearch = !!(
      lastSearch &&
      lastSearch.promptId === highlightInfo!.promptId &&
      lastSearch.key === highlightInfo!.key &&
      lastSearch.value === highlightInfo!.value
    );

    const page = currentPageRef.current;
    const nextPage = findNextHighlightedPage(highlightInfo, page, isSameSearch);

    if (nextPage != null && nextPage !== page) {
      seqRef.current += 1;
      setNavigation({ page: nextPage, seq: seqRef.current });
      lastSearchRef.current = {
        promptId: highlightInfo!.promptId,
        key: highlightInfo!.key,
        value: highlightInfo!.value,
        lastPage: nextPage,
      };
    } else if (!isSameSearch) {
      lastSearchRef.current = {
        promptId: highlightInfo!.promptId,
        key: highlightInfo!.key,
        value: highlightInfo!.value,
        lastPage: nextPage ?? page,
      };
    }
  }, [highlightInfo]);

  return navigation;
}
