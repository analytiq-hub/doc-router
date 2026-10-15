'use client';

import { toastActionError } from '@/utils/toastActionError';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ChevronDownIcon } from '@heroicons/react/24/outline';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import DownloadIcon from '@mui/icons-material/Download';
import RefreshIcon from '@mui/icons-material/Refresh';
import DescriptionOutlinedIcon from '@mui/icons-material/DescriptionOutlined';
import { Divider, Menu, MenuItem } from '@mui/material';
import { styled, alpha } from '@mui/material/styles';
import Link from 'next/link';
import {
  CaseLlmResultsResponse,
  GetLLMResultResponse,
  JsonValue,
  Prompt,
} from '@docrouter/sdk';
import { DocRouterOrgApi, getApiErrorMsg } from '@/utils/api';
import { toast } from 'react-toastify';
import DraggablePanel from '@/components/DraggablePanel';
import LlmResultTree from '@/components/extraction/LlmResultTree';
import { formatLocalDate } from '@/utils/date';

type Props = {
  organizationId: string;
  caseId: string;
  caseTagIds: string[];
};

const StyledMenuItem = styled(MenuItem)(({ theme }) => ({
  fontSize: '0.875rem',
  padding: '4px 16px',
  '& .MuiSvgIcon-root': {
    color: alpha(theme.palette.text.primary, 0.6),
  },
}));

function promptsMatchingCaseTags(all: Prompt[], caseTagIds: string[]): Prompt[] {
  const caseTags = new Set(caseTagIds);
  if (caseTags.size === 0) return [];
  return all.filter((p) => (p.tag_ids ?? []).some((tid) => caseTags.has(tid)));
}

function caseResultsToLlmResponse(
  prompt: Prompt,
  data: CaseLlmResultsResponse
): GetLLMResultResponse | null {
  const run = data.case_run;
  if (!run?.llm_result || Object.keys(run.llm_result).length === 0) return null;
  return {
    prompt_revid: run.prompt_revid,
    prompt_id: prompt.prompt_id,
    prompt_version: run.prompt_version,
    document_id: '',
    llm_result: run.llm_result as Record<string, JsonValue>,
    updated_llm_result: run.llm_result as Record<string, JsonValue>,
    is_edited: false,
    is_verified: false,
    created_at: run.created_at,
    updated_at: run.created_at,
    run: {
      ...run.run,
      document_ids: run.document_ids,
    },
  };
}

const CaseResultsSidebar: React.FC<Props> = ({ organizationId, caseId, caseTagIds }) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [matchingPrompts, setMatchingPrompts] = useState<Prompt[]>([]);
  const [loadingPromptsList, setLoadingPromptsList] = useState(true);
  const [expandedPromptRevId, setExpandedPromptRevId] = useState('');
  const [llmResults, setLlmResults] = useState<Record<string, GetLLMResultResponse>>({});
  const [staleByPromptId, setStaleByPromptId] = useState<
    Record<string, { stale: boolean; reasons: string[] }>
  >({});
  const [loadingPrompts, setLoadingPrompts] = useState<Set<string>>(new Set());
  const [failedPrompts, setFailedPrompts] = useState<Set<string>>(new Set());
  const [runningPrompts, setRunningPrompts] = useState<Set<string>>(new Set());

  const [kebabAnchorEl, setKebabAnchorEl] = useState<HTMLElement | null>(null);
  const [kebabPromptRevId, setKebabPromptRevId] = useState<string | null>(null);
  const [runInfoOpen, setRunInfoOpen] = useState(false);
  const [runInfoPromptRevId, setRunInfoPromptRevId] = useState<string | null>(null);
  const [runInfoResult, setRunInfoResult] = useState<GetLLMResultResponse | null>(null);

  const promptByRevId = useMemo(() => {
    const m = new Map<string, Prompt>();
    for (const p of matchingPrompts) m.set(p.prompt_revid, p);
    return m;
  }, [matchingPrompts]);

  useEffect(() => {
    void (async () => {
      setLoadingPromptsList(true);
      try {
        const pageSize = 100;
        const all: Prompt[] = [];
        for (let skip = 0; ; skip += pageSize) {
          const res = await docRouterOrgApi.listPrompts({ skip, limit: pageSize });
          all.push(...res.prompts);
          if (res.prompts.length < pageSize) break;
        }
        setMatchingPrompts(promptsMatchingCaseTags(all, caseTagIds));
      } catch (error) {
        toastActionError('Failed to load prompts', error);
      } finally {
        setLoadingPromptsList(false);
      }
    })();
  }, [docRouterOrgApi, caseTagIds]);

  // Returns true when a result is available. When ``afterRunId`` is given (a run id, or null if no run
  // existed yet), only a run different from it counts, so a re-run is not mistaken for its stale predecessor.
  const fetchCaseResult = useCallback(
    async (prompt: Prompt, afterRunId?: string | null): Promise<boolean> => {
      const revId = prompt.prompt_revid;
      setLoadingPrompts((prev) => new Set(prev).add(revId));
      try {
        const data = await docRouterOrgApi.getCaseLlmResults({
          caseId,
          promptId: prompt.prompt_id,
        });
        setStaleByPromptId((prev) => ({
          ...prev,
          [prompt.prompt_id]: { stale: data.stale, reasons: data.stale_reasons },
        }));
        const mapped = caseResultsToLlmResponse(prompt, data);
        if (mapped) {
          setLlmResults((prev) => ({ ...prev, [revId]: mapped }));
          setFailedPrompts((prev) => {
            const next = new Set(prev);
            next.delete(revId);
            return next;
          });
          return afterRunId === undefined || data.case_run?.run_id !== afterRunId;
        }
        setLlmResults((prev) => {
          const next = { ...prev };
          delete next[revId];
          return next;
        });
        return false;
      } catch (error) {
        console.error(error);
        setFailedPrompts((prev) => new Set(prev).add(revId));
        return false;
      } finally {
        setLoadingPrompts((prev) => {
          const next = new Set(prev);
          next.delete(revId);
          return next;
        });
      }
    },
    [caseId, docRouterOrgApi]
  );

  const handlePromptToggle = async (prompt: Prompt) => {
    const revId = prompt.prompt_revid;
    if (expandedPromptRevId === revId) {
      setExpandedPromptRevId('');
      return;
    }
    setExpandedPromptRevId(revId);
    if (!llmResults[revId] && !loadingPrompts.has(revId)) {
      await fetchCaseResult(prompt);
    }
  };

  const handleRunPrompt = async (prompt: Prompt) => {
    const revId = prompt.prompt_revid;
    setRunningPrompts((prev) => new Set(prev).add(revId));
    try {
      const before = await docRouterOrgApi.getCaseLlmResults({ caseId, promptId: prompt.prompt_id });
      const baselineRunId = before.case_run?.run_id ?? null;
      await docRouterOrgApi.startCaseLlmRun({ caseId, promptId: prompt.prompt_id });
      toast.success('Case prompt run queued');
      for (let i = 0; i < 20; i++) {
        await new Promise((r) => setTimeout(r, 2000));
        if (await fetchCaseResult(prompt, baselineRunId)) break;
      }
    } catch (error) {
      toastActionError('Failed to start run', error);
    } finally {
      setRunningPrompts((prev) => {
        const next = new Set(prev);
        next.delete(revId);
        return next;
      });
    }
  };

  const handleDownload = (promptRevId: string) => {
    const result = llmResults[promptRevId];
    const prompt = promptByRevId.get(promptRevId);
    if (!result || !prompt) return;
    const blob = new Blob([JSON.stringify(result.llm_result, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${prompt.name}_${result.prompt_revid}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleOpenRunInfo = (promptRevId: string) => {
    handleCloseKebabMenu();
    setRunInfoPromptRevId(promptRevId);
    setRunInfoResult(llmResults[promptRevId] ?? null);
    setRunInfoOpen(true);
  };

  const handleCloseKebabMenu = () => {
    setKebabAnchorEl(null);
    setKebabPromptRevId(null);
  };

  const renderPromptBody = (prompt: Prompt) => {
    const revId = prompt.prompt_revid;
    const result = llmResults[revId];
    const staleInfo = staleByPromptId[prompt.prompt_id];

    if (loadingPrompts.has(revId) || runningPrompts.has(revId)) {
      return (
        <div className="p-4 text-sm text-gray-500">
          {runningPrompts.has(revId) ? 'Running case prompt…' : 'Loading…'}
        </div>
      );
    }
    if (failedPrompts.has(revId)) {
      return <div className="p-4 text-sm text-red-500">Failed to load results</div>;
    }
    if (!result) {
      return (
        <div className="p-4 text-sm text-gray-500">
          No case run yet. Use reload to run this prompt on all documents in the case.
        </div>
      );
    }
    return (
      <>
        {staleInfo?.stale && (
          <div className="mx-4 mt-3 p-2 text-xs bg-amber-50 border border-amber-200 rounded text-amber-900">
            Stale ({staleInfo.reasons.join(', ')}). Reload to refresh.
          </div>
        )}
        <LlmResultTree value={result.updated_llm_result} />
      </>
    );
  };

  const noCaseTags = caseTagIds.length === 0;

  return (
    <div className="w-full h-full flex flex-col border-r border-black/10 bg-white">
      <div className="h-12 min-h-[48px] flex items-center px-4 bg-gray-100 text-black font-bold border-b border-black/10">
        <div className="flex bg-gray-200 rounded-md p-1">
          <span className="px-3 py-1 text-sm rounded bg-white text-gray-900 shadow-sm">Extraction</span>
        </div>
      </div>

      <div className="h-12 min-h-[48px] flex items-center justify-between px-4 bg-gray-100 text-black font-bold border-b border-black/10">
        <span>Prompts</span>
      </div>

      <div className="overflow-auto flex-grow min-h-0">
        {loadingPromptsList ? (
          <div className="px-4 py-3 text-sm text-gray-500">Loading prompts…</div>
        ) : noCaseTags ? (
          <div className="px-4 py-3 text-sm text-gray-500">
            Add tags to this case to see matching prompts here.
          </div>
        ) : matchingPrompts.length === 0 ? (
          <div className="px-4 py-3 text-sm text-gray-500">
            No tagged prompts match this case. Tag prompts with the same tags as the case.
          </div>
        ) : (
          matchingPrompts.map((prompt) => {
            const revId = prompt.prompt_revid;
            const isExpanded = expandedPromptRevId === revId;
            const retrievedVersion = llmResults[revId]?.prompt_version;
            return (
              <div key={revId} className="border-b border-black/10">
                <div
                  onClick={() => void handlePromptToggle(prompt)}
                  className="w-full min-h-[48px] flex items-center justify-between px-4 bg-gray-100/[0.6] hover:bg-gray-100/[0.8] transition-colors cursor-pointer"
                >
                  <span className="text-sm text-gray-900 min-w-0 truncate pr-2">
                    {prompt.name}{' '}
                    <span className="text-gray-500 text-xs">
                      {isExpanded && retrievedVersion !== undefined
                        ? `(v${retrievedVersion})`
                        : `(v${prompt.prompt_version})`}
                    </span>
                  </span>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <div
                      onClick={(e) => {
                        e.stopPropagation();
                        void handleRunPrompt(prompt);
                      }}
                      className="p-1 rounded-full hover:bg-black/5 transition-colors cursor-pointer"
                      title="Run on case"
                    >
                      {runningPrompts.has(revId) ? (
                        <div className="w-4 h-4 border-2 border-[#2B4479]/60 border-t-transparent rounded-full animate-spin" />
                      ) : (
                        <RefreshIcon fontSize="small" className="text-gray-600" />
                      )}
                    </div>
                    <div
                      onClick={(e) => {
                        e.stopPropagation();
                        setKebabAnchorEl(e.currentTarget);
                        setKebabPromptRevId(revId);
                      }}
                      className="p-1 rounded-full hover:bg-black/5 transition-colors cursor-pointer"
                      title="More actions"
                    >
                      <MoreVertIcon fontSize="small" className="text-gray-600" />
                    </div>
                    <ChevronDownIcon
                      className={`w-5 h-5 text-gray-600 transition-transform ${
                        isExpanded ? 'rotate-180' : ''
                      }`}
                    />
                  </div>
                </div>
                <div className={`transition-all duration-200 ease-in-out bg-white ${isExpanded ? '' : 'hidden'}`}>
                  {renderPromptBody(prompt)}
                </div>
              </div>
            );
          })
        )}
      </div>

      <Menu
        anchorEl={kebabAnchorEl}
        open={Boolean(kebabAnchorEl)}
        onClose={handleCloseKebabMenu}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        MenuListProps={{ dense: true }}
      >
        <StyledMenuItem
          onClick={() => {
            if (!kebabPromptRevId) return;
            handleCloseKebabMenu();
            handleDownload(kebabPromptRevId);
          }}
        >
          <DownloadIcon fontSize="small" sx={{ mr: 1 }} />
          Download
        </StyledMenuItem>
        <StyledMenuItem
          onClick={() => {
            const prompt = kebabPromptRevId ? promptByRevId.get(kebabPromptRevId) : undefined;
            if (!prompt) return;
            handleCloseKebabMenu();
            void handleRunPrompt(prompt);
          }}
        >
          <RefreshIcon fontSize="small" sx={{ mr: 1 }} />
          Reload
        </StyledMenuItem>
        <Divider />
        <StyledMenuItem
          onClick={() => {
            if (!kebabPromptRevId) return;
            handleOpenRunInfo(kebabPromptRevId);
          }}
        >
          <DescriptionOutlinedIcon fontSize="small" sx={{ mr: 1 }} />
          Run Info
        </StyledMenuItem>
      </Menu>

      {runInfoOpen && runInfoResult && (
        <>
          <div
            className="fixed inset-0 z-[70] bg-black bg-opacity-50"
            onClick={() => setRunInfoOpen(false)}
            role="presentation"
          />
          <DraggablePanel
            open={runInfoOpen}
            resetToken={`${caseId}-${runInfoPromptRevId ?? ''}`}
            anchorPercent={{ x: 50, y: 45 }}
            width="min(100vw - 32px, 42rem)"
            height="min(90vh, 820px)"
            zIndex={71}
            ariaLabel="Run info"
            title={
              <>
                <DescriptionOutlinedIcon className="shrink-0 text-blue-600" fontSize="small" />
                <span className="truncate">Run Info</span>
              </>
            }
            headerActions={
              <button
                type="button"
                onClick={() => setRunInfoOpen(false)}
                className="rounded-md bg-blue-600 px-3 py-1.5 text-xs text-white hover:bg-blue-700"
              >
                Close
              </button>
            }
          >
            <div className="flex min-h-0 flex-1 flex-col overflow-hidden px-6 pb-6 pt-2">
              <div className="space-y-4 overflow-y-auto">
                <div>
                  <label className="mb-1 block text-sm font-semibold text-gray-700">Prompt</label>
                  <div className="break-words rounded border bg-gray-50 p-2 text-sm">
                    <Link
                      href={`/orgs/${organizationId}/prompts/${encodeURIComponent(runInfoResult.prompt_revid)}`}
                      className="font-mono text-blue-600 hover:underline"
                    >
                      {runInfoResult.prompt_revid}
                    </Link>
                    <span className="text-gray-600"> (v{runInfoResult.prompt_version})</span>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="mb-1 block text-xs font-semibold text-gray-700">Created</label>
                    <div className="rounded border bg-gray-50 p-2 text-xs">
                      {formatLocalDate(runInfoResult.created_at)}
                    </div>
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-semibold text-gray-700">Case</label>
                    <div className="rounded border bg-gray-50 p-2 font-mono text-xs">{caseId}</div>
                  </div>
                </div>
                {runInfoResult.run?.document_ids && runInfoResult.run.document_ids.length > 0 && (
                  <div>
                    <label className="mb-1 block text-xs font-semibold text-gray-700">Documents in run</label>
                    <ul className="list-disc pl-4 text-sm">
                      {runInfoResult.run.document_ids.map((docId) => (
                        <li key={docId}>
                          <Link
                            href={`/orgs/${organizationId}/docs/${docId}`}
                            className="text-blue-600 hover:underline font-mono text-xs"
                          >
                            {docId}
                          </Link>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                <div>
                  <label className="mb-1 block text-sm font-semibold text-gray-700">
                    Context sent to model
                  </label>
                  <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words rounded border bg-gray-50 p-2 font-mono text-xs">
                    {runInfoResult.run?.prompt?.trim() ||
                      'No prompt text reported by the backend for this run.'}
                  </pre>
                </div>
              </div>
            </div>
          </DraggablePanel>
        </>
      )}
    </div>
  );
};

export default CaseResultsSidebar;
