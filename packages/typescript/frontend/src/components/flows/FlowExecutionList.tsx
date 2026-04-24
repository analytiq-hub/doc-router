'use client';

import React, { useCallback, useEffect, useState } from 'react';
import type { FlowExecution } from '@docrouter/sdk';
import { Button, Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow } from '@mui/material';
import { DocRouterOrgApi } from '@/utils/api';

function statusRunning(e: FlowExecution) {
  return e.status === 'queued' || e.status === 'running';
}

function formatDuration(e: FlowExecution) {
  const end = e.finished_at ? new Date(e.finished_at).getTime() : Date.now();
  const start = new Date(e.started_at).getTime();
  if (!Number.isFinite(end) || !Number.isFinite(start)) return '—';
  const s = Math.max(0, Math.round((end - start) / 1000));
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

const FlowExecutionList: React.FC<{
  orgApi: DocRouterOrgApi;
  flowId: string;
}> = ({ orgApi, flowId }) => {
  const [items, setItems] = useState<FlowExecution[]>([]);
  const [total, setTotal] = useState(0);
  const [err, setErr] = useState<string>('');
  const [expanded, setExpanded] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setErr('');
      const res = await orgApi.listExecutions(flowId, { limit: 50, offset: 0 });
      setItems(res.items);
      setTotal(res.total);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : 'Failed to load executions');
    } finally {
      setLoading(false);
    }
  }, [orgApi, flowId]);

  useEffect(() => {
    void load();
  }, [load]);

  const anyActive = items.some(statusRunning);
  useEffect(() => {
    if (!anyActive) return;
    const id = setInterval(() => {
      void load();
    }, 3000);
    return () => clearInterval(id);
  }, [anyActive, load]);

  const onStop = async (executionId: string) => {
    try {
      await orgApi.stopExecution(flowId, executionId);
      await load();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : 'Stop failed');
    }
  };

  if (loading && items.length === 0) {
    return <div className="text-sm text-gray-500">Loading executions…</div>;
  }

  return (
    <div className="space-y-2">
      {err && <div className="text-sm text-red-600">{err}</div>}
      <div className="text-xs text-gray-500">Showing {items.length} of {total} executions</div>
      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Started</TableCell>
              <TableCell>Mode</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Duration</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {items.map((e) => {
              const open = expanded === e.execution_id;
              return (
                <React.Fragment key={e.execution_id}>
                  <TableRow
                    hover
                    className="cursor-pointer"
                    onClick={() => setExpanded((x) => (x === e.execution_id ? null : e.execution_id))}
                    selected={open}
                  >
                    <TableCell>{new Date(e.started_at).toLocaleString()}</TableCell>
                    <TableCell>{e.mode}</TableCell>
                    <TableCell>{e.status}</TableCell>
                    <TableCell>{formatDuration(e)}</TableCell>
                    <TableCell align="right">
                      {statusRunning(e) && (
                        <Button
                          size="small"
                          onClick={(ev) => {
                            ev.stopPropagation();
                            void onStop(e.execution_id);
                          }}
                        >
                          Stop
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                  {open && (
                    <TableRow onClick={(ev) => ev.stopPropagation()}>
                      <TableCell colSpan={5} className="!border-t-0 bg-gray-50">
                        <pre className="text-[11px] overflow-auto max-h-80 p-2 rounded border border-gray-200">
                          {JSON.stringify(
                            { run_data: e.run_data, error: e.error, trigger: e.trigger, last_node: e.last_node_executed },
                            null,
                            2,
                          )}
                        </pre>
                      </TableCell>
                    </TableRow>
                  )}
                </React.Fragment>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
      {items.length === 0 && !loading && <div className="text-sm text-gray-600">No executions yet. Run the flow from the editor tab.</div>}
    </div>
  );
};

export default FlowExecutionList;
