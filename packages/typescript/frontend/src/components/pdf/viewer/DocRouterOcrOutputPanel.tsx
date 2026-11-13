import { FileText } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import DraggablePanel from '@/components/DraggablePanel';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Spinner } from '@/components/ui/spinner';
import type { OcrPanelKind } from '@/hooks/useDocRouterOcrOutput';

type Props = {
  documentId: string;
  fileName: string;
  kind: OcrPanelKind;
  metadataType: string | null;
  onClose: () => void;
  onKindChange: (kind: OcrPanelKind) => void;
  onDownload: () => void;
  text: { loading: boolean; error: string | null; content: string };
  markdown: { loading: boolean; error: string | null; content: string };
  html: { loading: boolean; error: string | null; content: string };
};

export function DocRouterOcrOutputPanel({
  documentId,
  fileName,
  kind,
  metadataType,
  onClose,
  onKindChange,
  onDownload,
  text,
  markdown,
  html,
}: Props) {
  return (
    <>
      <div className="fixed inset-0 z-[70] bg-black/50" onClick={onClose} role="presentation" />
      <DraggablePanel
        open
        resetToken={documentId}
        anchorPercent={{ x: 50, y: 45 }}
        width="min(100vw - 32px, 42rem)"
        height="min(90vh, 820px)"
        zIndex={71}
        ariaLabel="OCR Output"
        title={
          <>
            <FileText className="size-4 shrink-0 text-primary" aria-hidden />
            {metadataType ? (
              <span className="shrink-0 rounded bg-primary-soft px-1.5 py-0.5 text-xs font-medium text-primary">
                {metadataType}
              </span>
            ) : null}
            <span className="truncate">{fileName || 'OCR Output'}</span>
          </>
        }
        headerActions={
          <Button type="button" size="sm" variant="default" onClick={onClose}>
            Close
          </Button>
        }
      >
        <Tabs value={kind} onValueChange={(v) => onKindChange(v as OcrPanelKind)} className="flex min-h-0 flex-1 flex-col">
          <TabsList
            variant="line"
            className="mx-2 mt-1 h-9 w-full max-w-full justify-start overflow-x-auto overflow-y-hidden [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
          >
            <TabsTrigger value="text">Text</TabsTrigger>
            <TabsTrigger value="markdown">Markdown</TabsTrigger>
            <TabsTrigger value="html">Web</TabsTrigger>
            <TabsTrigger value="excel">Excel</TabsTrigger>
          </TabsList>
          <TabsContent value="text" className="mt-0 min-h-0 flex-1 overflow-hidden px-4 pt-2">
            {text.loading ? (
              <OcrLoading label="Loading OCR text…" />
            ) : text.error ? (
              <p className="py-4 text-sm text-destructive">{text.error}</p>
            ) : (
              <pre className="max-h-[min(70vh,600px)] overflow-auto whitespace-pre-wrap break-words rounded-md border bg-muted/40 p-2 font-mono text-xs">
                {text.content || 'No OCR text available.'}
              </pre>
            )}
          </TabsContent>
          <TabsContent value="markdown" className="mt-0 min-h-0 flex-1 overflow-auto px-4 pt-2">
            {markdown.loading ? (
              <OcrLoading label="Loading OCR markdown…" />
            ) : markdown.error ? (
              <p className="py-4 text-sm text-destructive">{markdown.error}</p>
            ) : (
              <div className="markdown-prose prose prose-sm max-w-none rounded-md border bg-muted/40 p-3">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{markdown.content || '*No content.*'}</ReactMarkdown>
              </div>
            )}
          </TabsContent>
          <TabsContent value="html" className="mt-0 min-h-0 flex-1 px-4 pt-2">
            {html.loading ? (
              <OcrLoading label="Loading OCR HTML…" />
            ) : html.error ? (
              <p className="py-4 text-sm text-destructive">{html.error}</p>
            ) : (
              <iframe
                title="OCR HTML preview"
                sandbox="allow-same-origin"
                className="min-h-[min(70vh,600px)] w-full flex-1 rounded-md border bg-card"
                srcDoc={html.content || '<p></p>'}
              />
            )}
          </TabsContent>
          <TabsContent value="excel" className="mt-0 px-4 pt-2">
            <p className="text-sm text-foreground">
              Download an Excel workbook from tables detected in the OCR result (one sheet per table).
            </p>
            <p className="mt-2 text-xs text-muted-foreground">If the document has no tables, you will see a notification.</p>
          </TabsContent>
          <div className="flex justify-end border-t px-4 py-3">
            <Button type="button" variant="outline" size="sm" onClick={() => void onDownload()}>
              {kind === 'text'
                ? 'Save as .txt'
                : kind === 'markdown'
                  ? 'Save as .md'
                  : kind === 'html'
                    ? 'Save as .html'
                    : 'Download Excel'}
            </Button>
          </div>
        </Tabs>
      </DraggablePanel>
    </>
  );
}

function OcrLoading({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 py-6">
      <Spinner className="size-5" />
      <span className="text-sm italic text-muted-foreground">{label}</span>
    </div>
  );
}
