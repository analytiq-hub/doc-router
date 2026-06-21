'use client';

import { useEffect, useMemo } from 'react';
import { DocRouterOrgApi } from '@/utils/api';
import { documentHasMatchingForms, loadDocumentMatchingForms } from '@/utils/documentForms';

interface Props {
  organizationId: string;
  documentId: string;
  onHasForms: (hasForms: boolean) => void;
}

/** Lightweight probe so the document sidebar can hide the Forms tab when there are no matches. */
export function PDFFormsTabProbe({ organizationId, documentId, onHasForms }: Props) {
  const api = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);

  useEffect(() => {
    onHasForms(false);
    let cancelled = false;

    void (async () => {
      try {
        const { forms, totalCount } = await loadDocumentMatchingForms(api, documentId, { limit: 1 });
        if (!cancelled) {
          onHasForms(documentHasMatchingForms(totalCount, forms));
        }
      } catch {
        if (!cancelled) {
          onHasForms(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [api, documentId, onHasForms]);

  return null;
}
