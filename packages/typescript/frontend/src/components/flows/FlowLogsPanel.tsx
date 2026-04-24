'use client';

import React, { useCallback, useEffect, useState } from 'react';
import type { FlowExecution } from '@docrouter/sdk';
import { IconButton, Tooltip } from '@mui/material';
import { DocRouterOrgApi } from '@/utils/api';
import { formatLocalDate } from '@/utils/date';
import { ChevronDownIcon, ChevronUpIcon, TrashIcon } from '@heroicons/react/24/outline';

function isRunning(e: FlowExecution) {
  return e.status === 'queued' || e.status === 'running';
}

const FlowLogsPanel: React.FC<{
  orgApi: DocRouterOrgApi;
  flowId: string;
  /** When set, this execution is shown (e.g. after a run from the editor). */
  focusExecutionId: string | null;
  onClearFocus: () => void;
  /** Fired when the loaded execution object changes (for node Input/Output in the graph editor). */
  onExecutionChange?: (e: FlowExecution | null) => void;
}> = ({ orgApi, flowId, focusExecutionId, onClearFocus, onExecutionChange }) => {
  const [expanded, setExpanded] = useState(false);
  const [execution, setExecution] = useState<FlowExecution | null>(null);

  useEffect(() => {
    if (focusExecutionId) {
      setExpanded(true);
    }
  }, [focusExecutionId]);

  useEffect(() => {
    onExecutionChange?.(execution);
  }, [execution, onExecutionChange]);
  const [err, setErr] = useState<string>('');
  const [loading, setLoading] = useState(false);

  const load = useCallback(
    async (id: string) => {
      try {
        setErr('');
        setLoading(true);
        const ex = await orgApi.getExecution(flowId, id);
        setExecution(ex);
      } catch (e: unknown) {
        setErr(e instanceof Error ? e.message : 'Failed to load execution');
        setExecution(null);
      } finally {
        setLoading(false);
      }
    },
    [orgApi, flowId],
  );

  useEffect(() => {
    if (focusExecutionId) {
      void load(focusExecutionId);
    } else {
      setExecution(null);
    }
  }, [focusExecutionId, load]);

  useEffect(() => {
    if (!execution || !isRunning(execution)) return;
    const id = setInterval(() => {
      void load(execution.execution_id);
    }, 2000);
    return () => clearInterval(id);
  }, [execution, load]);

  const onClear = () => {
    onClearFocus();
    setExecution(null);
    setErr('');
  };

  return (
    <div
      className="shrink-0 border-t border-[#e2e4e8] bg-[#fbfbfc]"
      data-testid="flow-logs-panel"
    >
      <div className="flex h-11 items-center justify-between gap-2 px-3">
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          className="flex min-w-0 flex-1 items-center gap-2 text-left"
        >
          <span className="text-sm font-semibold text-gray-800">Logs</span>
          {execution && (
            <span className="truncate text-xs text-gray-500">
              {formatLocalDate(execution.started_at)} · {execution.status}
            </span>
          )}
        </button>
        <div className="flex shrink-0 items-center gap-0.5">
          {(execution || focusExecutionId) && (
            <Tooltip title="Clear execution from panel">
              <IconButton size="small" onClick={onClear} aria-label="Clear execution">
                <TrashIcon className="h-4 w-4" />
              </IconButton>
            </Tooltip>
          )}
          <IconButton size="small" onClick={() => setExpanded((e) => !e)} aria-label={expanded ? 'Collapse' : 'Expand'}>
            {expanded ? <ChevronDownIcon className="h-5 w-5" /> : <ChevronUpIcon className="h-5 w-5" />}
          </IconButton>
        </div>
      </div>
      {expanded && (
        <div className="max-h-[min(45vh,480px)] overflow-auto border-t border-[#eceff2] bg-white p-3">
          {err && <div className="mb-2 text-sm text-red-600">{err}</div>}
          {loading && !execution && <div className="text-sm text-gray-500">Loading…</div>}
          {!focusExecutionId && !execution && !loading && (
            <div className="text-sm text-gray-600">
              Run the workflow to capture an execution, or open the <strong>Executions</strong> tab for full
              history.
            </div>
          )}
          {execution && (
            <pre className="overflow-auto rounded border border-gray-200 bg-gray-50 p-2 text-[11px] leading-relaxed">
              {JSON.stringify(
                {
                  execution_id: execution.execution_id,
                  status: execution.status,
                  started_at: execution.started_at,
                  finished_at: execution.finished_at,
                  mode: execution.mode,
                  run_data: execution.run_data,
                  error: execution.error,
                  trigger: execution.trigger,
                  last_node_executed: execution.last_node_executed,
                },
                null,
                2,
              )}
            </pre>
          )}
        </div>
      )}
    </div>
  );
};

export default FlowLogsPanel;
