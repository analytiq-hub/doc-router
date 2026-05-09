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
import { credentialKindKeyFromBinding } from './flowNodeCredentialSlots';
import { flowLabelClass, flowSelectClass } from './flowUiClasses';
import { applyParameterPatch } from './flowSchemaParameterUtils';

export const FLOWS_HTTP_REQUEST_KEY = 'flows.http_request';

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

function slotForKind(slots: FlowCredentialSlot[] | undefined, kindKey: string): FlowCredentialSlot | undefined {
  if (!slots?.length) return undefined;
  return slots.find((s) => credentialKindKeyFromBinding(s.docrouter_binding) === kindKey);
}

export type AuthDisplayMode = 'none' | 'generic' | 'predefined';

/** Resolve editor mode when ``authentication`` was never persisted (legacy flows). */
export function resolveHttpRequestAuthDisplay(
  rawParams: Record<string, unknown>,
  mergedParams: Record<string, unknown>,
  credentials: Record<string, string> | undefined,
): { mode: AuthDisplayMode; genericSlot: string } {
  const creds = credentials || {};
  const slotKeys = Object.keys(creds);
  const explicit = rawParams['authentication'];
  const slots = (
    mergedParams['generic_auth_slot'] != null ? String(mergedParams['generic_auth_slot']) : ''
  ).trim();
  if (explicit === 'none' || explicit === 'generic' || explicit === 'predefined') {
    const fallbackSlot = slotKeys[0] || 'httpBearerAuth';
    return {
      mode: explicit,
      genericSlot: slots || fallbackSlot,
    };
  }
  if (slotKeys.length === 0) {
    return { mode: 'none', genericSlot: slots || 'httpBearerAuth' };
  }
  return { mode: 'generic', genericSlot: slotKeys[0] };
}

export const FlowHttpRequestAuthSection: React.FC<{
  node: FlowNode;
  nodeType: FlowNodeType | null;
  rootSchema: unknown;
  mergedParams: Record<string, unknown>;
  rawParams: Record<string, unknown>;
  onChange: (patch: Partial<FlowNode>) => void;
  flowOrgApi: DocRouterOrgApi | null | undefined;
  readOnly?: boolean;
}> = ({
  node,
  nodeType,
  rootSchema,
  mergedParams,
  rawParams,
  onChange,
  flowOrgApi,
  readOnly = false,
}) => {
  const slots = nodeType?.credential_slots;
  const organizationId = flowOrgApi?.organizationId;
  const [items, setItems] = useState<FlowCredentialHeader[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!organizationId) return;
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
  }, [organizationId]);

  const display = useMemo(
    () => resolveHttpRequestAuthDisplay(rawParams, mergedParams, node.credentials || undefined),
    [rawParams, mergedParams, node.credentials],
  );

  const allowedKindKeys = useMemo(() => {
    const set = new Set<string>();
    for (const s of slots || []) {
      const k = credentialKindKeyFromBinding(s.docrouter_binding);
      if (k) set.add(k);
    }
    return set;
  }, [slots]);

  const predefinedOptions = useMemo(
    () => items.filter((c) => allowedKindKeys.has(c.kind_key)),
    [items, allowedKindKeys],
  );

  const byId = useMemo(() => {
    const m = new Map<string, FlowCredentialHeader>();
    for (const c of items) {
      m.set(c.credential_id, c);
    }
    return m;
  }, [items]);

  const creds = node.credentials || {};

  const applyAuthMode = (mode: AuthDisplayMode) => {
    /** One ``onChange`` so canvas merge never drops ``parameters`` when also updating ``credentials`` (see FlowEditor ``onPatchNodeById``). */
    if (mode === 'none') {
      onChange({
        parameters: applyParameterPatch(rootSchema, mergedParams, { authentication: 'none' }),
        credentials: undefined,
      });
      return;
    }
    if (mode === 'generic') {
      const slot = String(
        mergedParams.generic_auth_slot || display.genericSlot || 'httpBearerAuth',
      );
      const id = creds[slot];
      onChange({
        parameters: applyParameterPatch(rootSchema, mergedParams, {
          authentication: 'generic',
          generic_auth_slot: slot,
        }),
        credentials: id ? { [slot]: id } : undefined,
      });
      return;
    }
    const nextParams = applyParameterPatch(rootSchema, mergedParams, { authentication: 'predefined' });
    const single = Object.entries(creds)[0];
    if (single) {
      const [, id] = single;
      const meta = byId.get(id);
      const sl = meta ? slotForKind(slots, meta.kind_key) : undefined;
      if (meta && sl) {
        onChange({
          parameters: nextParams,
          credentials: { [sl.slot]: id },
        });
        return;
      }
    }
    onChange({
      parameters: nextParams,
      credentials: undefined,
    });
  };

  const setGenericSlot = (slotKey: string) => {
    const prevId = creds[slotKey];
    onChange({
      parameters: applyParameterPatch(rootSchema, mergedParams, {
        authentication: 'generic',
        generic_auth_slot: slotKey,
      }),
      credentials: prevId ? { [slotKey]: prevId } : undefined,
    });
  };

  const setGenericCredential = (slotKey: string, credentialId: string) => {
    if (!credentialId) {
      onChange({ credentials: undefined });
      return;
    }
    onChange({ credentials: { [slotKey]: credentialId } });
  };

  const setPredefinedCredential = (credentialId: string) => {
    if (!credentialId) {
      onChange({ credentials: undefined });
      return;
    }
    const meta = byId.get(credentialId);
    if (!meta) return;
    const slot = slotForKind(slots, meta.kind_key);
    if (!slot) return;
    onChange({ credentials: { [slot.slot]: credentialId } });
  };

  const genericSlotKey =
    (mergedParams.generic_auth_slot as string | undefined) || display.genericSlot || 'httpBearerAuth';
  const genericSlotMeta = slots?.find((s) => s.slot === genericSlotKey);
  const genericKindKey = genericSlotMeta
    ? credentialKindKeyFromBinding(genericSlotMeta.docrouter_binding)
    : null;
  const genericOptions = genericKindKey
    ? items.filter((c) => c.kind_key === genericKindKey)
    : [];

  const predefinedValue =
    Object.keys(creds).length === 1 ? (Object.values(creds)[0] as string | undefined) || '' : '';

  return (
    <div className="mb-3 space-y-3 rounded-md border border-gray-200 bg-gray-50/80 px-3 py-3">
      <div>
        <label className={flowLabelClass} htmlFor="http-request-authentication">
          Authentication
        </label>
        <select
          id="http-request-authentication"
          className={flowSelectClass}
          disabled={readOnly || !organizationId}
          value={display.mode}
          onChange={(e) => applyAuthMode(e.target.value as AuthDisplayMode)}
        >
          <option value="none">None</option>
          <option value="generic">Generic credential type</option>
          <option value="predefined">Predefined credential type</option>
        </select>
        <p className="mt-1 text-[11px] leading-snug text-gray-500">
          Generic: pick an auth style (Bearer, Basic, …) then a saved credential. Predefined: pick any saved
          credential compatible with this node; the correct binding is chosen automatically.
        </p>
      </div>

      {display.mode === 'generic' ? (
        <>
          <div>
            <label className={flowLabelClass} htmlFor="http-request-generic-auth-type">
              Generic auth type
            </label>
            <select
              id="http-request-generic-auth-type"
              className={flowSelectClass}
              disabled={readOnly || !organizationId}
              value={genericSlotKey}
              onChange={(e) => setGenericSlot(e.target.value)}
            >
              {(slots || []).map((s) => (
                <option key={s.slot} value={s.slot}>
                  {s.label}
                  {credentialKindKeyFromBinding(s.docrouter_binding)
                    ? ` (${credentialKindKeyFromBinding(s.docrouter_binding)})`
                    : ''}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className={flowLabelClass} htmlFor="http-request-generic-credential">
              Credential
            </label>
            <select
              id="http-request-generic-credential"
              className={flowSelectClass}
              disabled={readOnly || !organizationId}
              value={creds[genericSlotKey] ?? ''}
              onChange={(e) => setGenericCredential(genericSlotKey, e.target.value)}
            >
              <option value="">— None —</option>
              {genericOptions.map((c) => (
                <option key={c.credential_id} value={c.credential_id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
        </>
      ) : null}

      {display.mode === 'predefined' ? (
        <div>
          <label className={flowLabelClass} htmlFor="http-request-predefined-credential">
            Credential
          </label>
          <select
            id="http-request-predefined-credential"
            className={flowSelectClass}
            disabled={readOnly || !organizationId}
            value={predefinedValue}
            onChange={(e) => setPredefinedCredential(e.target.value)}
          >
            <option value="">— None —</option>
            {predefinedOptions.map((c) => (
              <option key={c.credential_id} value={c.credential_id}>
                {c.name} ({c.kind_key})
              </option>
            ))}
          </select>
        </div>
      ) : null}

      {err ? <div className="text-xs text-red-600">{err}</div> : null}
    </div>
  );
};
