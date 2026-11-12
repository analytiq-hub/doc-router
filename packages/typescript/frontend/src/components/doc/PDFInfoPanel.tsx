'use client';

import { useEffect, useMemo, useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import type { GetDocumentResponse } from '@docrouter/sdk';
import { DocRouterOrgApi } from '@/utils/api';

type PDFInfoPanelProps = {
  organizationId: string;
  documentId: string;
};

function Detail({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="py-2 text-sm">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words">{children ?? '—'}</dd>
    </div>
  );
}

export default function PDFInfoPanel({ organizationId, documentId }: PDFInfoPanelProps) {
  const [doc, setDoc] = useState<GetDocumentResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [metaOpen, setMetaOpen] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    const api = new DocRouterOrgApi(organizationId);
    api
      .getDocument({ documentId, fileType: 'pdf', includeContent: false })
      .then((res) => {
        if (!cancelled) setDoc(res);
      })
      .catch(() => {
        if (!cancelled) setError('Could not load document details.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [organizationId, documentId]);

  const metadataEntries = useMemo(
    () => Object.entries(doc?.metadata ?? {}),
    [doc?.metadata],
  );

  if (loading) {
    return <p className="text-sm text-muted-foreground">Loading details…</p>;
  }
  if (error || !doc) {
    return <p className="text-sm text-destructive">{error ?? 'Document not found.'}</p>;
  }

  return (
    <div className="flex flex-col gap-1">
      <dl className="divide-y divide-border">
        <Detail label="Name">{doc.document_name}</Detail>
        <Detail label="Type">{doc.type || '—'}</Detail>
        <Detail label="State">{doc.state}</Detail>
        <Detail label="Uploaded by">{doc.uploaded_by}</Detail>
        <Detail label="Uploaded">{new Date(doc.upload_date).toLocaleString()}</Detail>
        <Detail label="Document ID">{doc.id}</Detail>
        {doc.pdf_id ? <Detail label="PDF ID">{doc.pdf_id}</Detail> : null}
      </dl>
      {metadataEntries.length > 0 ? (
        <section aria-label="Metadata" className="mt-2">
          <button
            type="button"
            className="flex w-full items-center gap-1 rounded-md py-1 text-left text-sm font-medium outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50"
            aria-expanded={metaOpen}
            onClick={() => setMetaOpen((v) => !v)}
          >
            {metaOpen ? (
              <ChevronDown className="size-4 shrink-0" aria-hidden />
            ) : (
              <ChevronRight className="size-4 shrink-0" aria-hidden />
            )}
            Metadata
            <span className="font-normal text-muted-foreground">({metadataEntries.length})</span>
          </button>
          {metaOpen ? (
            <dl className="divide-y divide-border pl-5">
              {metadataEntries.map(([key, value]) => (
                <Detail key={key} label={key}>
                  {value}
                </Detail>
              ))}
            </dl>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
