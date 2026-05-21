'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { isAxiosError } from 'axios';
import type {
  FlowCredentialSlot,
  FlowCredentialHeader,
  FlowNode,
  FlowNodeType,
  ListFlowCredentialsResponse,
} from '@docrouter/sdk';
import { apiClient, type DocRouterOrgApi } from '@/utils/api';
import { flowLabelClass, flowSelectClass } from './flowUiClasses';
import { parameterSchemaUsesCredentialAuthenticationWidget } from './flowSchemaParameterUtils';

function formatCredentialLoadError(e: unknown): string {
  if (isAxiosError(e)) {
    if (e.code === 'ERR_NETWORK' || e.message === 'Network Error') {
      return (
        'Could not reach the API. If you use local dev, run the FastAPI backend on port 8000 and open the app via ' +
        'the Next.js dev server so requests to /fastapi are proxied (see next.config.mjs rewrites).'
      );
    }
    const detail = (e.response?.data as { detail?: unknown } | undefined)?.detail;
    if (typeof detail === 'string') return detail;
    if (e.response?.status) return `Request failed (HTTP ${e.response.status})`;
  }
  if (e instanceof Error) return e.message;
  return 'Failed to load credentials';
}

export function credentialKindKeyFromBinding(binding: string | undefined): string | null {
  const prefix = 'organization_credential_kind:';
  if (!binding?.startsWith(prefix)) return null;
  const k = binding.slice(prefix.length).trim();
  return k || null;
}

/**
 * Per-slot dropdowns for saved org credentials (filtered by slot kind).
 */
export const FlowNodeCredentialSlots: React.FC<{
  flowOrgApi: DocRouterOrgApi | null | undefined;
  node: FlowNode;
  nodeType: FlowNodeType | null;
  onChange: (patch: Partial<FlowNode>) => void;
  readOnly?: boolean;
  /** When true, render above parameters (no top border / section chrome). */
  placement?: 'top' | 'bottom';
}> = ({ flowOrgApi, node, nodeType, onChange, readOnly = false, placement = 'bottom' }) => {
  const slots = nodeType?.credential_slots;
  const [items, setItems] = useState<FlowCredentialHeader[]>([]);
  const [err, setErr] = useState<string | null>(null);

  const organizationId = flowOrgApi?.organizationId;

  useEffect(() => {
    if (!organizationId || !slots?.length) return;
    let cancelled = false;
    const pageSize = 200;
    void (async () => {
      const acc: FlowCredentialHeader[] = [];
      let offset = 0;
      try {
        for (;;) {
          const res = await apiClient.get<ListFlowCredentialsResponse>(
            `/v0/orgs/${organizationId}/credentials`,
            { params: { limit: pageSize, offset } },
          );
          acc.push(...res.data.items);
          if (acc.length >= res.data.total || res.data.items.length === 0) break;
          offset += res.data.items.length;
        }
        if (!cancelled) {
          setItems(acc);
          setErr(null);
        }
      } catch (e: unknown) {
        if (!cancelled) setErr(formatCredentialLoadError(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [organizationId, slots?.length]);

  const creds = node.credentials || {};

  const bySlot = useMemo(() => {
    const m = new Map<string, FlowCredentialHeader>();
    for (const c of items) {
      m.set(c.credential_id, c);
    }
    return m;
  }, [items]);

  if (parameterSchemaUsesCredentialAuthenticationWidget(nodeType?.parameter_schema)) {
    return null;
  }

  if (!slots?.length) return null;

  const setSlot = (slot: FlowCredentialSlot, credentialId: string) => {
    const next = { ...creds };
    if (!credentialId) {
      delete next[slot.slot];
    } else {
      next[slot.slot] = credentialId;
    }
    onChange({ credentials: Object.keys(next).length > 0 ? next : undefined });
  };

  const shellClass =
    placement === 'top' ? 'mb-4' : 'mt-4 border-t border-[#eceff2] pt-4';

  return (
    <div className={shellClass}>
      {placement === 'bottom' ? (
        <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-[#9ca3af]">Credentials</div>
      ) : null}
      {err && <div className="mb-2 text-xs text-red-600">{err}</div>}
      <div className="space-y-3">
        {slots.map((slot) => {
          const kindKey = credentialKindKeyFromBinding(slot.docrouter_binding);
          const options = kindKey ? items.filter((c) => c.kind_key === kindKey) : items;
          const value = creds[slot.slot] ?? '';
          const selected = value ? bySlot.get(value) : undefined;
          return (
            <div key={slot.slot}>
              <label className={flowLabelClass} htmlFor={`cred-slot-${slot.slot}`}>
                {slot.label}
                {slot.required ? ' *' : ''}
                {kindKey ? (
                  <span className="ml-1 font-normal text-gray-400">({kindKey})</span>
                ) : null}
              </label>
              <select
                id={`cred-slot-${slot.slot}`}
                className={flowSelectClass}
                disabled={readOnly || !organizationId}
                value={value}
                onChange={(e) => setSlot(slot, e.target.value)}
              >
                <option value="">— None —</option>
                {options.map((c) => (
                  <option key={c.credential_id} value={c.credential_id}>
                    {c.name}
                  </option>
                ))}
              </select>
              {readOnly && selected && (
                <div className="mt-0.5 text-[10px] text-gray-500">{selected.credential_id}</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
