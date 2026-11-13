import React, { useEffect, useState, useMemo, useRef, useId } from 'react';
import { Check, ChevronDown, ChevronRight, ChevronsDownUp, ChevronsUpDown, Download, FileText, Maximize2, Pencil, Play, Plus, RefreshCw, X } from 'lucide-react';
import { ExtractionPromptRow } from '@/components/pdf/ExtractionPromptRow';
import { resultPreview } from '@/lib/results';
import {
  resultCellText,
  resultCollapsibleNodes,
  resultContainerStartsCollapsed,
  blankResultValue,
  coerceEditedValue,
  removeResultItemAtPath,
  resultItemSummary,
  resultListSample,
  resultValueAtPath,
  setResultValueAtPath,
} from '@/lib/resultTree';
import { cn } from '@/lib/utils';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Spinner } from '@/components/ui/spinner';
import { DocRouterAccountApi, DocRouterOrgApi } from '@/utils/api';
import type { Organization } from '@docrouter/sdk';
import type { Prompt } from '@docrouter/sdk';
import { useOCRBlocks } from '@/hooks/useOCRBlocks';
import type { GetLLMResultResponse } from '@docrouter/sdk';
import type { HighlightInfo } from '@/hooks/useOCRBlocks';
import { usePromptResults } from '@/hooks/usePromptResults';
import DraggablePanel from '@/components/DraggablePanel';
import type { PDFDocumentProxy } from 'pdfjs-dist';

interface Props {
  organizationId: string;
  id: string;
  pdfDocument?: PDFDocumentProxy | null;
  onHighlight: (highlight: HighlightInfo) => void;
}

interface EditingState {
  promptId: string;
  key: string;
  value: string;
}

// Update the type definition to handle nested structures
type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

/** Shared look for clickable result rows: full-width, quiet until hovered or focused. */
/**
 * Fields are laid out on a shared grid so values line up in one column: names (as wide as the
 * longest name, at most 40%), values, and a slot for row actions. Rows join it as subgrids.
 */
const RESULT_GRID_CLASS = 'grid grid-cols-[fit-content(40%)_minmax(0,1fr)_auto] gap-x-2';

const DISCLOSURE_HINT = 'Alt/Option-click to open or close everything inside';

const RESULT_ROW_CLASS =
  'min-w-0 flex-1 rounded-sm px-1 text-left outline-none enabled:hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring/50';

const PDFExtractionSidebarContent = ({ organizationId, id, pdfDocument, onHighlight }: Props) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), []);
  const { loadOCRBlocks, findBlocksWithContext } = useOCRBlocks();
  const [matchingPrompts, setMatchingPrompts] = useState<Prompt[]>([]);
  const [runningPrompts, setRunningPrompts] = useState<Set<string>>(new Set());
  const [expandedPrompt, setExpandedPrompt] = useState<string>('default');
  const [editing, setEditing] = useState<EditingState | null>(null);
  const [editMode, setEditMode] = useState<boolean>(false);
  const [resultNodeOverrides, setResultNodeOverrides] = useState<Map<string, boolean>>(new Map());
  /** The row last located in the document, so it stays marked while the user reads the PDF. */
  const [activeFindKey, setActiveFindKey] = useState<string | null>(null);
  /** A list of objects opened as a full table in a floating panel. */
  const [tableView, setTableView] = useState<{ promptId: string; path: string; label: string } | null>(null);
  const [documentState, setDocumentState] = useState<string | null>(null);
  /** Cycle index for repeated Search on the same extraction (first click = 1st match, then next match). */
  const extractionFindCycleRef = useRef<{ sig: string; index: number } | null>(null);

  const [documentName, setDocumentName] = useState<string | null>(null);
  const [organization, setOrganization] = useState<Organization | null>(null);

  const [runInfoOpen, setRunInfoOpen] = useState(false);
  const [runInfoPromptId, setRunInfoPromptId] = useState<string | null>(null);
  const [runInfoLoading, setRunInfoLoading] = useState(false);
  const [runInfoResult, setRunInfoResult] = useState<GetLLMResultResponse | null>(null);

  useEffect(() => {
    extractionFindCycleRef.current = null;
    setResultNodeOverrides(new Map());
    setActiveFindKey(null);
    setTableView(null);
  }, [id]);

  const promptResultIds = useMemo(
    () => [
      ...(organization?.default_prompt_enabled === false ? [] : ['default']),
      ...matchingPrompts.map((prompt) => prompt.prompt_revid),
    ],
    [matchingPrompts, organization?.default_prompt_enabled],
  );
  const isDocumentProcessing =
    documentState === 'ocr_processing' || documentState === 'llm_processing';
  const {
    byPrompt: promptResultState,
    results: llmResults,
    setResult: setPromptResult,
    fetchResult: fetchPromptResult,
  } = usePromptResults({
    organizationId,
    documentId: id,
    promptRevIds: promptResultIds,
    enabled: !isDocumentProcessing,
  });

  // Fetch document metadata and matching prompts. Prompt results are shared TanStack queries below.
  useEffect(() => {
    const fetchData = async () => {
      let fetchedName: string | null = null;

      try {
        try {
          const orgResponse = await docRouterAccountApi.getOrganization(organizationId);
          setOrganization(orgResponse);
        } catch (error) {
          console.error('Error fetching organization metadata:', error);
        }

        try {
          const docResponse = await docRouterOrgApi.getDocument({
            documentId: id,
            fileType: 'pdf',
            includeContent: false,
          });
          fetchedName = docResponse.document_name ?? null;
          setDocumentState(docResponse.state);
          setDocumentName(fetchedName);
        } catch (error) {
          console.error('Error fetching document metadata:', error);
        }

        const promptsResponse = await docRouterOrgApi.listPrompts({ document_id: id, limit: 100 });
        setMatchingPrompts(promptsResponse.prompts);
      } catch (error) {
        console.error('Error fetching prompts:', error);
      }
    };

    fetchData();
  }, [organizationId, id, docRouterOrgApi, docRouterAccountApi]);

  // Poll document state when processing
  useEffect(() => {
    const defaultPromptEnabled = organization ? organization.default_prompt_enabled !== false : true;
    if (!defaultPromptEnabled || !documentState || (documentState !== 'ocr_processing' && documentState !== 'llm_processing')) {
      return;
    }
    const pollInterval = setInterval(async () => {
      try {
        const docResponse = await docRouterOrgApi.getDocument({ documentId: id, fileType: 'pdf', includeContent: false });
        setDocumentState(docResponse.state);
      } catch (error) {
        console.error('Error polling document state:', error);
      }
    }, 2000);
    return () => clearInterval(pollInterval);
  }, [documentState, id, docRouterOrgApi, organization]);

  useEffect(() => {
    if (documentName) {
      loadOCRBlocks(organizationId, id, documentName);
    }
  }, [id, organizationId, documentName, loadOCRBlocks]);

  const handlePromptChange = (promptId: string) => {
    if (expandedPrompt === promptId) {
      setExpandedPrompt('');
      return;
    }

    setExpandedPrompt(promptId);
  };

  const handleRunPrompt = async (promptId: string) => {
    setRunningPrompts(prev => new Set(prev).add(promptId));
    try {
      await docRouterOrgApi.runLLM({
        documentId: id,
        promptRevId: promptId,
        force: true
      });
      
      await fetchPromptResult(promptId, false);
    } catch (error) {
      console.error('Error running prompt:', error);
    } finally {
      setRunningPrompts(prev => {
        const next = new Set(prev);
        next.delete(promptId);
        return next;
      });
    }
  };

  const handleOpenRunInfo = async (promptId: string) => {
    setRunInfoPromptId(promptId);
    setRunInfoOpen(true);
    const cachedResult = llmResults[promptId];
    if (cachedResult) {
      setRunInfoResult(cachedResult);
      setRunInfoLoading(false);
      return;
    }

    setRunInfoLoading(true);
    setRunInfoResult(null);
    try {
      const result = await fetchPromptResult(promptId, true);
      setRunInfoResult(result);
    } catch (err) {
      console.error('Error loading run info:', err);
      setRunInfoResult(null);
    } finally {
      setRunInfoLoading(false);
    }
  };

  const handleFind = async (promptId: string, key: string, value: string) => {
    // Make sure value is not empty or null
    if (!value || value === 'null') return;
    
    // Clean up the value if needed
    const searchValue = value.trim();
    if (searchValue === '') return;
    
    const full = await findBlocksWithContext(searchValue, promptId, key, pdfDocument);
    const ocrCount = full.blocks.length;
    const pdfHits = full.pdfFallbackHits ?? [];
    const pdfCount = pdfHits.length;

    if (ocrCount === 0 && pdfCount === 0) {
      extractionFindCycleRef.current = null;
      console.log('No matches found for:', searchValue);
      return;
    }

    const sig = `${promptId}\0${key ?? ''}\0${searchValue}`;
    const total = ocrCount > 0 ? ocrCount : pdfCount;

    let idx: number;
    const prev = extractionFindCycleRef.current;
    if (!prev || prev.sig !== sig) {
      idx = 0;
    } else {
      idx = (prev.index + 1) % total;
    }
    extractionFindCycleRef.current = { sig, index: idx };

    const highlightInfo: HighlightInfo =
      ocrCount > 0
        ? { ...full, blocks: [full.blocks[idx]], pdfFallbackHits: undefined }
        : { ...full, blocks: [], pdfFallbackHits: [pdfHits[idx]] };

    setActiveFindKey(resultNodeKey(promptId, key));
    onHighlight(highlightInfo);
  };

  const handleEdit = (promptId: string, key: string, value: string) => {
    if (!editMode) return; // Only allow editing when edit mode is enabled
    setEditing({ promptId, key, value });
  };

  /** Apply a change to a copy of the stored result and save it. Returns whether it was saved. */
  const saveResultChange = async (promptId: string, mutate: (draft: JsonValue) => boolean) => {
    const current = llmResults[promptId];
    if (!current) return false;
    const draft = JSON.parse(JSON.stringify(current.updated_llm_result)) as JsonValue;
    if (!mutate(draft)) {
      console.error('Result path not found; nothing saved.');
      return false;
    }
    // Use the stored prompt_revid from the result (not the requested key) so that
    // when GET was done with fallback=true we update the actual stored record.
    const result = await docRouterOrgApi.updateLLMResult({
      documentId: id,
      promptId: current.prompt_revid,
      result: draft as Record<string, JsonValue>,
      isVerified: false,
    });
    setPromptResult(promptId, result);
    return true;
  };

  const handleSave = async () => {
    if (!editing) return;
    try {
      const saved = await saveResultChange(editing.promptId, (draft) =>
        setResultValueAtPath(
          draft,
          editing.key,
          coerceEditedValue(resultValueAtPath(draft, editing.key), editing.value),
        ),
      );
      if (saved) setEditing(null);
    } catch (error) {
      console.error('Error saving edit:', error);
    }
  };

  // Leaving edit mode closes any open input; an unsaved change there is dropped, as with Cancel.
  useEffect(() => {
    if (!editMode) setEditing(null);
  }, [editMode]);

  const handleCancel = () => {
    setEditing(null);
  };

  // Replace the isKeyValuePairs function with a more flexible approach
  const isEditableValue = (value: unknown): boolean => {
    return typeof value === 'string' || 
           typeof value === 'number' || 
           value === null ||
           typeof value === 'boolean';
  };

  const resultNodeKey = (promptId: string, path: string) => `${promptId}\0${path || '$root'}`;

  const setResultNodeOpen = (promptId: string, path: string, open: boolean) => {
    setResultNodeOverrides((previous) => {
      const next = new Map(previous);
      next.set(resultNodeKey(promptId, path), open);
      return next;
    });
  };

  const collapsibleNodes = (promptId: string) => {
    const payload = llmResults[promptId]?.updated_llm_result;
    return payload ? resultCollapsibleNodes(payload as { [key: string]: JsonValue }) : [];
  };

  /** Open or close every group at `path` and below (all groups when `path` is empty). */
  const setResultSubtree = (promptId: string, path: string, open: boolean) => {
    const inside = (nodePath: string) =>
      !path || nodePath === path || nodePath.startsWith(`${path}.`) || nodePath.startsWith(`${path}[`);
    setResultNodeOverrides((previous) => {
      const next = new Map(previous);
      collapsibleNodes(promptId)
        .filter((node) => inside(node.path))
        .forEach((node) => next.set(resultNodeKey(promptId, node.path), open));
      return next;
    });
  };

  /** Alt/Option-click opens or closes everything inside a group; a plain click toggles just it. */
  const toggleResultNode = (event: React.MouseEvent, promptId: string, path: string, open: boolean) => {
    if (event.altKey) setResultSubtree(promptId, path, !open);
    else setResultNodeOpen(promptId, path, !open);
  };

  const isNodeOpen = (promptId: string, path: string, defaultOpen: boolean) =>
    resultNodeOverrides.get(resultNodeKey(promptId, path)) ?? defaultOpen;

  /** Indent the first two levels only; deeper nesting relies on its group headers. */
  const groupBodyClass = (level: number) =>
    cn(RESULT_GRID_CLASS, level <= 2 && 'ml-1.5 border-l border-border pl-1.5');

  /** Open a value for editing, first saving any other edit in progress so it is not lost. */
  const startEdit = async (promptId: string, path: string, stringValue: string) => {
    if (editing && (editing.promptId !== promptId || editing.key !== path)) {
      const stored = resultValueAtPath(
        (llmResults[editing.promptId]?.updated_llm_result ?? null) as JsonValue,
        editing.key,
      );
      if ((stored?.toString() ?? '') !== editing.value) await handleSave();
    }
    handleEdit(promptId, path, stringValue);
  };

  /**
   * A single value. Clicking the row finds the value in the document, or, in edit mode,
   * opens it for editing. Names sit in the grid's first column, values in the second.
   */
  const renderLeaf = (
    promptId: string,
    label: string | null,
    path: string,
    value: JsonValue,
    options: { actions?: React.ReactNode } = {},
  ) => {
    const stringValue = value?.toString() ?? '';
    const isEmpty = stringValue.trim() === '' || stringValue === 'null';

    if (editing && editing.promptId === promptId && editing.key === path) {
      return (
        <div key={path} className="col-span-full grid grid-cols-subgrid items-center px-1 py-0.5 text-sm">
          {label ? (
            <span className="truncate text-primary" title={label}>
              {label}
            </span>
          ) : null}
          <div className={cn('flex min-w-0 items-center gap-0.5', label ? 'col-span-2' : 'col-span-full')}>
            <Input
              type="text"
              value={editing.value}
              onChange={(e) => setEditing({ ...editing, value: e.target.value })}
              onKeyDown={(e) => {
                if (e.key === 'Enter') void handleSave();
                if (e.key === 'Escape') handleCancel();
              }}
              className="h-7 min-w-0 flex-1 px-2 text-sm md:text-sm"
              autoFocus
            />
            <Button type="button" variant="ghost" size="icon-xs" onClick={handleSave} title="Save changes">
              <Check className="text-success" />
            </Button>
            <Button type="button" variant="ghost" size="icon-xs" onClick={handleCancel} title="Cancel">
              <X className="text-destructive" />
            </Button>
          </div>
        </div>
      );
    }

    return (
      <div key={path} className="col-span-full grid grid-cols-subgrid items-start">
        <button
          type="button"
          disabled={isEmpty && !editMode}
          title={editMode || isEmpty ? undefined : 'Find in document'}
          onClick={() =>
            void (editMode
              ? startEdit(promptId, path, stringValue)
              : handleFind(promptId, path, stringValue))
          }
          className={cn(
            RESULT_ROW_CLASS,
            'col-span-2 grid grid-cols-subgrid py-1 text-sm',
            editMode && 'cursor-text',
            activeFindKey === resultNodeKey(promptId, path) && 'bg-primary/10',
          )}
        >
          {label ? (
            <span className="truncate text-primary" title={label}>
              {label}
            </span>
          ) : null}
          <span
            className={cn(
              'min-w-0 break-words whitespace-pre-wrap',
              !label && 'col-span-2',
              isEmpty ? 'text-muted-foreground' : 'font-medium text-foreground',
              editMode && !isEmpty && 'underline decoration-muted-foreground/50 decoration-dotted underline-offset-4',
            )}
          >
            {isEmpty ? '—' : stringValue}
          </span>
        </button>
        {options.actions}
      </div>
    );
  };

  /** A label with nothing under it (empty list or object). */
  const renderEmpty = (path: string, label: string | null, text: string, action?: React.ReactNode) => (
    <div key={path} className="col-span-full grid min-h-7 grid-cols-subgrid items-center px-1 text-sm">
      {label ? (
        <span className="truncate text-primary" title={label}>
          {label}
        </span>
      ) : null}
      <div className={cn('flex min-w-0 items-center gap-1.5', label ? 'col-span-2' : 'col-span-full')}>
        <span className="flex-1 text-muted-foreground">{text}</span>
        {action}
      </div>
    </div>
  );

  /** One-line disclosure header (`▸ line_items · 12`) with its content underneath. */
  const renderGroup = (
    promptId: string,
    label: string,
    path: string,
    count: string,
    level: number,
    defaultOpen: boolean,
    body: () => React.ReactNode,
    headerActions?: React.ReactNode,
  ) => {
    const open = isNodeOpen(promptId, path, defaultOpen);
    return (
      <div key={path} className="col-span-full min-w-0">
        <div className="flex min-w-0 items-center gap-0.5">
          <button
            type="button"
            className={cn(RESULT_ROW_CLASS, 'flex items-center gap-1 py-1 text-sm')}
            aria-expanded={open}
            title={DISCLOSURE_HINT}
            onClick={(event) => toggleResultNode(event, promptId, path, open)}
          >
            {open ? (
              <ChevronDown className="size-3.5 shrink-0 text-muted-foreground" aria-hidden />
            ) : (
              <ChevronRight className="size-3.5 shrink-0 text-muted-foreground" aria-hidden />
            )}
            <span className="min-w-0 truncate font-semibold text-foreground">{label}</span>
            <span className="shrink-0 text-muted-foreground">· {count}</span>
          </button>
          {headerActions}
        </div>
        {open ? <div className={groupBodyClass(level)}>{body()}</div> : null}
      </div>
    );
  };

  const renderObjectFields = (
    promptId: string,
    path: string,
    value: { [key: string]: JsonValue },
    level: number,
  ) =>
    Object.entries(value).map(([key, child]) =>
      renderEntry(promptId, key, path ? `${path}.${key}` : key, child, level + 1),
    );

  /** An object inside a list: collapsed to a one-line summary until opened. */
  const renderListItem = (
    promptId: string,
    path: string,
    item: { [key: string]: JsonValue },
    index: number,
    level: number,
  ) => {
    const open = isNodeOpen(promptId, path, false);
    const summary = resultItemSummary(item);
    const hasFields = Object.keys(item).length > 0;
    return (
      <div key={path} className="col-span-full min-w-0">
        <div className="flex min-w-0 items-center gap-0.5">
          <button
            type="button"
            className={cn(RESULT_ROW_CLASS, 'flex items-center gap-1 py-1 text-sm')}
            aria-expanded={open}
            disabled={!hasFields}
            title={hasFields ? DISCLOSURE_HINT : undefined}
            onClick={(event) => toggleResultNode(event, promptId, path, open)}
          >
            {open ? (
              <ChevronDown className="size-3.5 shrink-0 text-muted-foreground" aria-hidden />
            ) : (
              <ChevronRight className="size-3.5 shrink-0 text-muted-foreground" aria-hidden />
            )}
            <span className="min-w-0 flex-1 truncate font-medium">
              {summary.title ?? (hasFields ? `Item ${index + 1}` : 'No fields')}
            </span>
            {summary.value ? (
              <span className="shrink-0 text-muted-foreground tabular-nums">{summary.value}</span>
            ) : null}
          </button>
          {editMode ? (
            <Button
              type="button"
              variant="ghost"
              size="icon-xs"
              onClick={() => handleArrayItemDelete(promptId, path)}
              title="Delete item"
            >
              <X className="text-destructive" />
            </Button>
          ) : null}
        </div>
        {open ? (
          <div className={groupBodyClass(level + 1)}>
            {renderObjectFields(promptId, path, item, level + 1)}
          </div>
        ) : null}
      </div>
    );
  };

  const renderListItems = (promptId: string, path: string, value: JsonValue[], level: number) => {
    return (
      <>
        {value.map((item, index) => {
          const itemPath = `${path}[${index}]`;
          if (isEditableValue(item)) {
            return renderLeaf(
              promptId,
              String(index + 1),
              itemPath,
              item,
              {
                actions: editMode ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-xs"
                  onClick={() => handleArrayItemDelete(promptId, itemPath)}
                  title="Delete item"
                >
                  <X className="text-destructive" />
                </Button>
              ) : null,
              },
            );
          }
          if (Array.isArray(item)) {
            return renderEntry(promptId, String(index + 1), itemPath, item, level + 1);
          }
          return renderListItem(promptId, itemPath, item as { [key: string]: JsonValue }, index, level);
        })}
      </>
    );
  };

  /** One labelled field of the result: a value row, or a group for a list or object. */
  const renderEntry = (
    promptId: string,
    label: string,
    path: string,
    value: JsonValue,
    level: number,
  ): React.ReactNode => {
    if (isEditableValue(value)) {
      return renderLeaf(promptId, label, path, value);
    }

    if (Array.isArray(value)) {
      if (value.length === 0) {
        return renderEmpty(
          path,
          label,
          'None',
          editMode ? (
            <Button
              type="button"
              variant="outline"
              size="xs"
              onClick={() => void handleArrayAdd(promptId, path)}
            >
              Add item
            </Button>
          ) : null,
        );
      }
      const isObjectList = value.every(
        (item) => item !== null && typeof item === 'object' && !Array.isArray(item),
      );
      return renderGroup(
        promptId,
        label,
        path,
        String(value.length),
        level,
        !resultContainerStartsCollapsed(value, level),
        () => renderListItems(promptId, path, value, level),
        <>
          {editMode ? (
            <Button
              type="button"
              variant="ghost"
              size="icon-xs"
              onClick={() => void handleArrayAdd(promptId, path)}
              title="Add item"
            >
              <Plus />
            </Button>
          ) : null}
          {isObjectList ? (
            <Button
              type="button"
              variant="ghost"
              size="icon-xs"
              onClick={() => setTableView({ promptId, path, label })}
              title="Open as table"
            >
              <Maximize2 />
            </Button>
          ) : null}
        </>,
      );
    }

    const fields = value as { [key: string]: JsonValue };
    const fieldCount = Object.keys(fields).length;
    if (fieldCount === 0) {
      return renderEmpty(path, label, 'No fields');
    }
    return renderGroup(
      promptId,
      label,
      path,
      fieldCount === 1 ? '1 field' : `${fieldCount} fields`,
      level,
      !resultContainerStartsCollapsed(fields, level),
      () => renderObjectFields(promptId, path, fields, level),
    );
  };

  const renderPromptResults = (promptId: string) => {
    const result = llmResults[promptId];
    if (!result) {
      const isProcessing = documentState === 'ocr_processing' || documentState === 'llm_processing';

      if (promptResultState[promptId]?.pending && !isProcessing) {
        return (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Spinner className="size-4" aria-label="Loading results" />
          </p>
        );
      }

      if (isProcessing) {
        const processingMessage =
          documentState === 'ocr_processing' ? 'Processing OCR…' : 'Processing LLM…';
        return (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Spinner className="size-4" />
            {processingMessage}
          </p>
        );
      }
      if (promptResultState[promptId]?.failed) {
        return (
          <Alert variant="destructive">
            <AlertDescription>Failed to load results.</AlertDescription>
          </Alert>
        );
      }
      return <p className="text-sm text-muted-foreground">No results on this document yet.</p>;
    }

    const payload = result.updated_llm_result as { [key: string]: JsonValue };
    const entries = Object.entries(payload);
    // A lone field needs no label: show its value (or its fields) directly.
    const lone = entries.length === 1 ? entries[0] : null;
    const loneObject =
      lone && lone[1] !== null && typeof lone[1] === 'object' && !Array.isArray(lone[1])
        ? (lone[1] as { [key: string]: JsonValue })
        : null;
    let content: React.ReactNode;
    if (entries.length === 0) {
      content = <span className="col-span-full px-1 text-sm text-muted-foreground">No fields</span>;
    } else if (lone && isEditableValue(lone[1])) {
      content = renderLeaf(promptId, null, lone[0], lone[1]);
    } else if (lone && loneObject && Object.keys(loneObject).length > 0) {
      content = renderObjectFields(promptId, lone[0], loneObject, 0);
    } else if (lone) {
      content = renderEntry(promptId, lone[0], lone[0], lone[1], 0);
    } else {
      content = renderObjectFields(promptId, '', payload, 0);
    }
    return <div className={RESULT_GRID_CLASS}>{content}</div>;
  };

  /** One button in the prompt header: expand everything, or collapse it once all is open. */
  const expandToggle = (promptId: string) => {
    const nodes = collapsibleNodes(promptId);
    if (nodes.length === 0) return null;
    const allOpen = nodes.every((node) => isNodeOpen(promptId, node.path, node.defaultOpen));
    const label = allOpen ? 'Collapse all' : 'Expand all';
    return (
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        onClick={() => setResultSubtree(promptId, '', !allOpen)}
        title={label}
        aria-label={label}
      >
        {allOpen ? <ChevronsDownUp /> : <ChevronsUpDown />}
      </Button>
    );
  };

  const collapsedPreview = (promptId: string): { text: string; failed?: boolean } => {
    const result = llmResults[promptId];
    if (result) {
      return { text: resultPreview(result.updated_llm_result as Record<string, unknown>) };
    }
    if (promptResultState[promptId]?.pending) {
      return { text: '' };
    }
    const isProcessing = documentState === 'ocr_processing' || documentState === 'llm_processing';
    if (runningPrompts.has(promptId) || isProcessing) {
      if (isProcessing) {
        return {
          text:
            documentState === 'ocr_processing' ? 'Processing OCR…' : 'Processing LLM…',
        };
      }
      return { text: runningPrompts.has(promptId) ? 'Running…' : 'Loading…' };
    }
    if (promptResultState[promptId]?.failed) {
      return { text: 'Failed to load results', failed: true };
    }
    return { text: 'Not run yet' };
  };

  const promptRowActions = (promptId: string) => {
    const hasResult = Boolean(llmResults[promptId]);
    const running = runningPrompts.has(promptId);
    return [
      {
        label: hasResult ? 'Run again' : 'Run',
        icon: hasResult ? RefreshCw : Play,
        onSelect: () => void handleRunPrompt(promptId),
        disabled: running,
      },
      hasResult && {
        label: 'Correct',
        icon: Pencil,
        onSelect: () => {
          setEditMode(true);
          if (expandedPrompt !== promptId) {
            void handlePromptChange(promptId);
          }
        },
      },
      hasResult && {
        label: 'Download',
        icon: Download,
        onSelect: () => void handleDownloadResult(promptId),
      },
      {
        label: 'Run info',
        icon: FileText,
        onSelect: () => void handleOpenRunInfo(promptId),
      },
    ];
  };

  const listBaseId = useId();

  const handleArrayItemDelete = async (promptId: string, itemPath: string) => {
    if (!editMode) return;
    try {
      await saveResultChange(promptId, (draft) => removeResultItemAtPath(draft, itemPath));
    } catch (error) {
      console.error('Error deleting array item:', error);
    }
  };

  /** Append a blank item shaped like the list's other items, open it, and start naming it. */
  const handleArrayAdd = async (promptId: string, arrayPath: string) => {
    if (!editMode) return;
    try {
      let itemPath = '';
      let item: JsonValue = '';
      const saved = await saveResultChange(promptId, (draft) => {
        const list = resultValueAtPath(draft, arrayPath);
        if (!Array.isArray(list)) return false;
        const sample = resultListSample(draft, arrayPath);
        item = sample === undefined ? '' : blankResultValue(sample);
        itemPath = `${arrayPath}[${list.length}]`;
        list.push(item);
        return true;
      });
      if (!saved) return;

      setResultNodeOpen(promptId, arrayPath, true);
      const added = item as JsonValue;
      if (isEditableValue(added)) {
        setEditing({ promptId, key: itemPath, value: added?.toString() ?? '' });
      } else if (added !== null && !Array.isArray(added)) {
        setResultNodeOpen(promptId, itemPath, true);
        const firstLeaf = Object.entries(added).find(([, value]) => isEditableValue(value));
        if (firstLeaf) {
          setEditing({
            promptId,
            key: `${itemPath}.${firstLeaf[0]}`,
            value: firstLeaf[1]?.toString() ?? '',
          });
        }
      }
    } catch (error) {
      console.error('Error adding array item:', error);
    }
  };

  const handleDownloadResult = async (promptId: string) => {
    try {
      // Try to get the latest result from the API, even if not currently loaded
      const result = await docRouterOrgApi.getLLMResult({
        documentId: id,
        promptRevId: promptId,
        promptRevIdFallback: true
      });

      // Get prompt name for filename
      let promptName = 'unknown_prompt';
      if (promptId === 'default') {
        promptName = 'document_summary';
      } else {
        // Find the prompt in matchingPrompts
        const prompt = matchingPrompts.find(p => p.prompt_revid === promptId);
        if (prompt) {
          promptName = prompt.name.toLowerCase().replace(/\s+/g, '_');
        }
      }

      // Create the download data
      const downloadData = {
        prompt_revid: result.prompt_revid,
        prompt_id: result.prompt_id,
        document_id: id,
        organization_id: organizationId,
        extraction_result: result.updated_llm_result,
        metadata: {
          prompt_version: result.prompt_version,
          created_at: result.created_at,
          updated_at: result.updated_at,
          is_edited: result.is_edited,
          is_verified: result.is_verified
        }
      };

      // Create and download the file
      const blob = new Blob([JSON.stringify(downloadData, null, 2)], {
        type: 'application/json'
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${promptName}_${result.prompt_revid}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Error downloading result:', error);
      // Fallback to local result if API call fails
      const localResult = llmResults[promptId];
      if (localResult) {
        // Get prompt name for filename
        let promptName = 'unknown_prompt';
        if (promptId === 'default') {
          promptName = 'document_summary';
        } else {
          // Find the prompt in matchingPrompts
          const prompt = matchingPrompts.find(p => p.prompt_revid === promptId);
          if (prompt) {
            promptName = prompt.name.toLowerCase().replace(/\s+/g, '_');
          }
        }

        const downloadData = {
          prompt_revid: localResult.prompt_revid,
          prompt_id: localResult.prompt_id,
          document_id: id,
          organization_id: organizationId,
          extraction_result: localResult.updated_llm_result,
          metadata: {
            prompt_version: localResult.prompt_version,
            created_at: localResult.created_at,
            updated_at: localResult.updated_at,
            is_edited: localResult.is_edited,
            is_verified: localResult.is_verified
          }
        };

        const blob = new Blob([JSON.stringify(downloadData, null, 2)], {
          type: 'application/json'
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${promptName}_${localResult.prompt_revid}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      }
    }
  };

  // Rows for the open table view, read live so corrections and re-runs show up.
  const tableSource = tableView
    ? resultValueAtPath(
        (llmResults[tableView.promptId]?.updated_llm_result ?? null) as JsonValue,
        tableView.path,
      )
    : undefined;
  const tableRows = Array.isArray(tableSource)
    ? tableSource.filter(
        (row): row is { [key: string]: JsonValue } =>
          row !== null && typeof row === 'object' && !Array.isArray(row),
      )
    : null;
  const tableColumns = tableRows ? [...new Set(tableRows.flatMap((row) => Object.keys(row)))] : [];

  const defaultPromptEnabledForRender = organization?.default_prompt_enabled !== false;

  return (
    <div className="flex h-full w-full min-h-0 flex-col">
      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-border pb-2">
        <span className="text-sm font-medium text-foreground">Results</span>
        <div className="flex items-center gap-1.5">
          {editMode ? (
            <Badge variant="secondary" className="font-normal">
              Editing
            </Badge>
          ) : null}
          <Button
            type="button"
            variant={editMode ? 'secondary' : 'ghost'}
            size="icon-sm"
            onClick={() => setEditMode((prev) => !prev)}
            title={editMode ? 'Disable editing' : 'Enable editing'}
            aria-pressed={editMode}
          >
            <Pencil />
          </Button>
        </div>
      </div>

      <div className="@container min-h-0 flex-1 overflow-auto overscroll-y-contain">
        {defaultPromptEnabledForRender ? (
          <ExtractionPromptRow
            ariaLabel={llmResults.default?.prompt_display_name ?? 'Document Summary'}
            title={llmResults.default?.prompt_display_name ?? 'Document Summary'}
            versionLabel={
              llmResults.default?.prompt_version !== undefined
                ? `v${llmResults.default.prompt_version}`
                : undefined
            }
            open={expandedPrompt === 'default'}
            preview={collapsedPreview('default').text}
            previewFailed={collapsedPreview('default').failed}
            running={runningPrompts.has('default')}
            loading={promptResultState.default?.pending}
            failed={promptResultState.default?.failed}
            isVerified={llmResults.default?.is_verified}
            isEdited={llmResults.default?.is_edited}
            bodyId={`${listBaseId}-default`}
            onToggle={() => void handlePromptChange('default')}
            actions={promptRowActions('default')}
            headerActions={expandToggle('default')}
          >
            {renderPromptResults('default')}
          </ExtractionPromptRow>
        ) : null}

        {matchingPrompts.length === 0 ? (
          <p className="py-3 text-sm text-muted-foreground">
            No tagged prompts match this document. Add prompts whose tags overlap this document&apos;s tags
            to see them here.
          </p>
        ) : (
          matchingPrompts.map((prompt) => {
            const promptId = prompt.prompt_revid;
            const isExpanded = expandedPrompt === promptId;
            const llmResult = llmResults[promptId];
            const version = isExpanded && llmResult?.prompt_version !== undefined
              ? llmResult.prompt_version
              : prompt.prompt_version;
            const previewMeta = collapsedPreview(promptId);

            return (
              <ExtractionPromptRow
                key={promptId}
                ariaLabel={prompt.name}
                title={prompt.name}
                versionLabel={`v${version}`}
                open={isExpanded}
                preview={previewMeta.text}
                previewFailed={previewMeta.failed}
                running={runningPrompts.has(promptId)}
                loading={promptResultState[promptId]?.pending && isExpanded}
                failed={promptResultState[promptId]?.failed}
                isVerified={llmResult?.is_verified}
                isEdited={llmResult?.is_edited}
                bodyId={`${listBaseId}-${promptId}`}
                onToggle={() => void handlePromptChange(promptId)}
                actions={promptRowActions(promptId)}
                headerActions={expandToggle(promptId)}
              >
                {renderPromptResults(promptId)}
              </ExtractionPromptRow>
            );
          })
        )}
      </div>

      {tableRows ? (
        <DraggablePanel
          open
          resetToken={`${id}-${tableView?.promptId ?? ''}-${tableView?.path ?? ''}`}
          anchorPercent={{ x: 50, y: 50 }}
          width="min(100vw - 32px, 56rem)"
          height="min(70vh, 640px)"
          zIndex={60}
          ariaLabel={`${tableView?.label ?? 'Items'} table`}
          title={<span className="truncate">{tableView?.label}</span>}
          headerActions={
            <Button type="button" variant="ghost" size="icon-sm" onClick={() => setTableView(null)} title="Close">
              <X />
            </Button>
          }
        >
          {/* Styled scrollbars stay visible (macOS overlay scrollbars hide the horizontal one) and take
              their own space, so the last column is never under the vertical bar. */}
          <div className="min-h-0 min-w-0 flex-1 overflow-auto [&::-webkit-scrollbar]:size-2.5 [&::-webkit-scrollbar-corner]:bg-transparent [&::-webkit-scrollbar-thumb]:rounded-sm [&::-webkit-scrollbar-thumb]:bg-muted-foreground/40 [&::-webkit-scrollbar-track]:bg-transparent">
            <table className="w-full border-collapse text-sm">
              <thead className="sticky top-0 z-10 bg-muted text-left text-xs text-muted-foreground">
                <tr>
                  <th className="w-8 px-2 py-1.5 font-medium">#</th>
                  {tableColumns.map((column) => (
                    <th key={column} className="min-w-36 px-2 py-1.5 font-medium whitespace-nowrap">
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {tableRows.map((row, index) => (
                  <tr key={index} className="border-t border-border align-top">
                    <td className="px-2 py-1 text-xs text-muted-foreground tabular-nums">{index + 1}</td>
                    {tableColumns.map((column) => {
                      const cell = row[column];
                      const cellPath = `${tableView!.path}[${index}].${column}`;
                      const findable = isEditableValue(cell) && cell !== null && cell !== undefined && String(cell).trim() !== '';
                      return (
                        <td key={column} className="p-0">
                          <button
                            type="button"
                            disabled={!findable}
                            title={findable ? 'Find in document' : undefined}
                            onClick={() => void handleFind(tableView!.promptId, cellPath, String(cell))}
                            className={cn(
                              'w-full px-2 py-1 text-left whitespace-pre-wrap [overflow-wrap:anywhere] outline-none enabled:hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring/50 disabled:text-muted-foreground',
                              activeFindKey === resultNodeKey(tableView!.promptId, cellPath) && 'bg-primary/10',
                            )}
                          >
                            {resultCellText(cell)}
                          </button>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </DraggablePanel>
      ) : null}

      {runInfoOpen && (
        <>
          <div
            className="fixed inset-0 z-[70] bg-black/50"
            onClick={() => {
              setRunInfoOpen(false);
              setRunInfoPromptId(null);
            }}
            role="presentation"
          />
          <DraggablePanel
            open={runInfoOpen}
            resetToken={`${id}-${runInfoPromptId ?? ''}`}
            anchorPercent={{ x: 50, y: 45 }}
            width="min(100vw - 32px, 42rem)"
            height="min(90vh, 820px)"
            zIndex={71}
            ariaLabel="Run info"
            title={
              <>
                <FileText className="size-4 shrink-0 text-primary" aria-hidden />
                <span className="truncate">Run Info</span>
              </>
            }
            headerActions={
              <button
                type="button"
                onClick={() => {
                  setRunInfoOpen(false);
                  setRunInfoPromptId(null);
                }}
                className="rounded-md bg-primary-600 px-3 py-1.5 text-xs text-white hover:bg-primary-700"
              >
                Close
              </button>
            }
          >
            <div className="flex min-h-0 flex-1 flex-col overflow-hidden px-6 pb-6 pt-2">
            {runInfoLoading ? (
              <div className="flex items-center gap-3 py-6">
                <div
                  className="h-5 w-5 animate-spin rounded-full border-2 border-gray-300 border-t-primary-600"
                  aria-hidden
                />
                <span className="text-sm italic text-gray-500">Loading run info...</span>
              </div>
            ) : runInfoResult ? (
              (() => {
                const runMeta = runInfoResult.run;
                const hasPeerBlock =
                  !!runMeta &&
                  ((runMeta.match_values && Object.keys(runMeta.match_values).length > 0) ||
                    (!!runMeta.match_document_ids && runMeta.match_document_ids.length > 0));
                const promptUsedText = runMeta?.prompt?.trim();
                // The backend prompt editor route expects `promptRevId` to be a Mongo ObjectId.
                // Our "default" prompt is synthetic and uses `prompt_revid="default"`, so
                // linking to `/prompts/default` would fail. Route to the prompts list instead.
                const promptEditHref =
                  runInfoResult.prompt_revid === 'default'
                    ? `/orgs/${organizationId}/prompts`
                    : `/orgs/${organizationId}/prompts/${encodeURIComponent(runInfoResult.prompt_revid)}`;
                const promptLinkLabel =
                  runInfoResult.prompt_revid === 'default'
                    ? 'Document Summary'
                    : runInfoResult.prompt_revid;
                const showDisplayNamePrefix =
                  !!runInfoResult.prompt_display_name && runInfoResult.prompt_revid !== 'default';
                return (
                  <div className="flex min-h-0 flex-1 flex-col gap-4">
                    <div className="min-h-0 shrink overflow-y-auto [&::-webkit-scrollbar]:w-2.5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-gray-300 [&::-webkit-scrollbar-track]:bg-transparent">
                      <div className="space-y-4">
                    <div>
                      <label className="mb-1 block text-sm font-semibold text-gray-700">Prompt</label>
                      <div className="break-words rounded border bg-gray-50 p-2 text-sm text-gray-900">
                        {showDisplayNamePrefix ? (
                          <span className="text-gray-800">{runInfoResult.prompt_display_name} · </span>
                        ) : null}
                        <a
                          href={promptEditHref}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="break-all font-mono text-primary-600 hover:underline"
                        >
                          {promptLinkLabel}
                        </a>
                        <span className="text-gray-600"> (v{runInfoResult.prompt_version})</span>
                      </div>
                    </div>

                    <div>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label className="mb-1 block text-xs font-semibold text-gray-700">Created</label>
                          <div className="break-all rounded border bg-gray-50 p-2 font-mono text-xs text-gray-900">
                            {runInfoResult.created_at}
                          </div>
                        </div>
                        <div>
                          <label className="mb-1 block text-xs font-semibold text-gray-700">Updated</label>
                          <div className="break-all rounded border bg-gray-50 p-2 font-mono text-xs text-gray-900">
                            {runInfoResult.updated_at}
                          </div>
                        </div>
                        <div>
                          <label className="mb-1 block text-xs font-semibold text-gray-700">Edited</label>
                          <div className="rounded border bg-gray-50 p-2 text-gray-900">
                            {String(runInfoResult.is_edited)}
                          </div>
                        </div>
                        <div>
                          <label className="mb-1 block text-xs font-semibold text-gray-700">Verified</label>
                          <div className="rounded border bg-gray-50 p-2 text-gray-900">
                            {String(runInfoResult.is_verified)}
                          </div>
                        </div>
                      </div>
                    </div>

                    {hasPeerBlock && runMeta && (
                      <div>
                        <div className="grid grid-cols-2 gap-4">
                          {runMeta.match_values && Object.keys(runMeta.match_values).length > 0 && (
                              <div>
                                <label className="mb-1 block text-xs font-semibold text-gray-700">
                                  Match values
                                </label>
                                <div className="rounded border bg-gray-50 p-2 text-sm text-gray-900">
                                  <ul className="list-disc space-y-1 pl-4">
                                    {Object.entries(runMeta.match_values).map(([key, value]) => (
                                      <li key={key} className="break-all">
                                        <span className="font-semibold">{key}</span>
                                        <span className="mx-1 text-gray-400">=</span>
                                        <span className="font-mono text-xs">{String(value)}</span>
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              </div>
                            )}
                          {runMeta.match_document_ids && runMeta.match_document_ids.length > 0 && (
                              <div>
                                <label className="mb-1 block text-xs font-semibold text-gray-700">
                                  Matched peer documents
                                </label>
                                <div className="rounded border bg-gray-50 p-2 text-sm">
                                  <ul className="list-disc space-y-1 pl-4">
                                    {runMeta.match_document_ids.map(docId => (
                                      <li key={docId} className="break-all">
                                        <a
                                          href={`/orgs/${organizationId}/docs/${docId}`}
                                          target="_blank"
                                          rel="noreferrer"
                                          className="font-mono text-sm text-primary-600 hover:underline"
                                        >
                                          {docId}
                                        </a>
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              </div>
                            )}
                        </div>
                      </div>
                    )}
                      </div>
                    </div>

                    <div className="flex min-h-0 flex-1 flex-col">
                      <label className="mb-1 shrink-0 block text-sm font-semibold text-gray-700">
                        Context sent to model
                      </label>
                      <pre className="min-h-0 flex-1 overflow-auto whitespace-pre-wrap break-words rounded border bg-gray-50 p-2 font-mono text-xs leading-relaxed text-gray-800 [&::-webkit-scrollbar]:w-2.5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-gray-300 [&::-webkit-scrollbar-track]:bg-transparent">
                        {promptUsedText
                          ? promptUsedText
                          : 'No prompt text reported by the backend for this run.'}
                      </pre>
                    </div>
                  </div>
                );
              })()
            ) : (
              <p className="py-4 text-sm text-gray-500">No run info available.</p>
            )}
            </div>
          </DraggablePanel>
        </>
      )}
    </div>
  );
};

export default PDFExtractionSidebarContent;
