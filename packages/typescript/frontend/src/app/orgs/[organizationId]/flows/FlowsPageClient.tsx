'use client';

import React, { useCallback, useLayoutEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ChevronDownIcon } from '@heroicons/react/20/solid';
import { Menu, MenuButton, MenuItem, MenuItems } from '@headlessui/react';
import FlowList from '@/components/flows/FlowList';
import FlowCreate from '@/components/flows/FlowCreate';
import FlowCredentials from '@/components/flows/FlowCredentials';
import FlowExecutionsAll from '@/components/flows/FlowExecutionsAll';
import {
  loadFlowNamesTakenLower,
  NEW_FLOW_URL_SEGMENT,
  nextSequentialDisplayName,
} from '@/components/flows/flowDefaultNames';
import { useFlowApi } from '@/components/flows/useFlowApi';
import { getApiErrorMsg } from '@/utils/api';

export type FlowsTab = 'flows' | 'credentials' | 'executions';

export default function FlowsPageClient({
  organizationId,
  tab,
  newFlow,
  autoCreateCredential,
}: {
  organizationId: string;
  tab: FlowsTab;
  newFlow: boolean;
  /** Open the new-credential dialog (`newCredential` / `bootstrapCredential` in URL, or header on Credentials tab). */
  autoCreateCredential: boolean;
}) {
  const router = useRouter();
  const api = useFlowApi(organizationId);
  const splitRef = useRef<HTMLDivElement>(null);
  const [splitWidthPx, setSplitWidthPx] = useState<number | null>(null);
  const [createFlowBusy, setCreateFlowBusy] = useState(false);
  const [createFlowError, setCreateFlowError] = useState('');

  const measureSplitWidth = useCallback(() => {
    const el = splitRef.current;
    setSplitWidthPx(el ? el.offsetWidth : null);
  }, []);

  useLayoutEffect(() => {
    measureSplitWidth();
    const el = splitRef.current;
    if (!el || typeof ResizeObserver === 'undefined') {
      return undefined;
    }
    const ro = new ResizeObserver(() => measureSplitWidth());
    ro.observe(el);
    return () => ro.disconnect();
  }, [measureSplitWidth]);

  const pushWithSearch = useCallback(
    (mutate: (q: URLSearchParams) => void) => {
      const q = new URLSearchParams(typeof window !== 'undefined' ? window.location.search : '');
      mutate(q);
      router.push(`/orgs/${organizationId}/flows?${q.toString()}`);
    },
    [organizationId, router],
  );

  const replaceWithSearch = useCallback(
    (mutate: (q: URLSearchParams) => void) => {
      const q = new URLSearchParams(typeof window !== 'undefined' ? window.location.search : '');
      mutate(q);
      const qs = q.toString();
      router.replace(`/orgs/${organizationId}/flows${qs ? `?${qs}` : ''}`);
    },
    [organizationId, router],
  );

  const handleTabChange = (newValue: FlowsTab) => {
    pushWithSearch((q) => {
      q.set('tab', newValue);
      q.delete('newFlow');
      q.delete('newCredential');
      q.delete('bootstrapCredential');
    });
  };

  const stripQueryKeys = useCallback(
    (keys: string[]) => {
      replaceWithSearch((q) => {
        for (const k of keys) {
          q.delete(k);
        }
      });
    },
    [replaceWithSearch],
  );

  const onCredentialBootstrapHandled = useCallback(() => {
    stripQueryKeys(['newCredential', 'bootstrapCredential']);
  }, [stripQueryKeys]);

  const dismissNewFlow = useCallback(() => {
    stripQueryKeys(['newFlow']);
  }, [stripQueryKeys]);

  const handleCreateFlowNavigate = useCallback(async () => {
    if (createFlowBusy) return;
    setCreateFlowError('');
    try {
      setCreateFlowBusy(true);
      const taken = await loadFlowNamesTakenLower(api);
      const name = nextSequentialDisplayName(taken, 'My workflow');
      const q = new URLSearchParams();
      q.set('proposedName', name);
      router.push(`/orgs/${organizationId}/flows/${NEW_FLOW_URL_SEGMENT}?${q.toString()}`);
    } catch (err) {
      setCreateFlowError(getApiErrorMsg(err) || 'Failed to create flow');
    } finally {
      setCreateFlowBusy(false);
    }
  }, [api, createFlowBusy, organizationId, router]);

  /** Primary: centered label with symmetric padding; min-w fits longest label. Menu rows match for alignment. */
  const createSplitPrimaryMinW = 'min-w-[142px]';
  const createSplitTypography = 'min-h-8 font-sans text-[13px] font-medium leading-5 antialiased';
  const createSplitPad = 'px-1.5';
  const createFlowPrimaryClass =
    `inline-flex shrink-0 ${createSplitTypography} ${createSplitPad} items-center justify-center rounded-l-md border border-blue-600 bg-blue-600 text-white shadow-sm transition hover:bg-blue-700 hover:border-blue-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/60 disabled:cursor-not-allowed disabled:opacity-60 ${createSplitPrimaryMinW}`;

  const createFlowChevronClass =
    `inline-flex min-h-8 w-5 shrink-0 items-center justify-center rounded-r-md border border-l-0 border-blue-600 bg-blue-600 text-white shadow-sm transition hover:bg-blue-700 hover:border-blue-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/60 disabled:cursor-not-allowed disabled:opacity-60`;

  const createSplitMenuItemClass = (focused: boolean) =>
    `${createSplitTypography} ${createSplitPad} flex w-full cursor-pointer items-center justify-center border-0 text-center text-gray-800 hover:bg-gray-100 ${focused ? 'bg-gray-100' : ''}`;

  const createMenuPanelClass =
    'z-[280] mt-1 rounded-md bg-white p-0 shadow-[0_4px_14px_rgba(15,23,42,0.08)] ring-1 ring-gray-200 outline-none';

  const primaryActionDisabled = tab === 'credentials' ? false : createFlowBusy;
  const menuButtonDisabled = createFlowBusy;

  return (
    <div className="p-4">
      <div className="mb-6 flex flex-col gap-4 border-b border-gray-200 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex gap-8">
          <button
            type="button"
            onClick={() => handleTabChange('flows')}
            className={`pb-4 px-1 relative font-semibold text-base ${
              tab === 'flows'
                ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            Flows
          </button>
          <button
            type="button"
            onClick={() => handleTabChange('credentials')}
            className={`pb-4 px-1 relative font-semibold text-base ${
              tab === 'credentials'
                ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            Credentials
          </button>
          <button
            type="button"
            onClick={() => handleTabChange('executions')}
            className={`pb-4 px-1 relative font-semibold text-base ${
              tab === 'executions'
                ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            Executions
          </button>
        </div>

        <div className="flex shrink-0 flex-col items-end gap-1 pb-2 sm:flex-row sm:items-center sm:pb-4">
          {createFlowError ? <div className="text-sm text-red-600">{createFlowError}</div> : null}
          <div ref={splitRef} className="inline-flex rounded-md shadow-sm">
            <button
              type="button"
              className={createFlowPrimaryClass}
              disabled={primaryActionDisabled}
              onClick={() => {
                if (tab === 'credentials') {
                  pushWithSearch((q) => {
                    q.set('tab', 'credentials');
                    q.set('newCredential', '1');
                    q.delete('bootstrapCredential');
                  });
                  return;
                }
                void handleCreateFlowNavigate();
              }}
            >
              {tab === 'credentials'
                ? 'Create credential'
                : createFlowBusy
                  ? 'Creating…'
                  : 'Create flow'}
            </button>
            <Menu as="div" className="relative -ml-px block">
              <MenuButton
                type="button"
                disabled={menuButtonDisabled}
                className={createFlowChevronClass}
                aria-label="More create options"
              >
                <ChevronDownIcon className="h-3 w-3" aria-hidden />
              </MenuButton>
              <MenuItems
                anchor="bottom end"
                portal
                className={createMenuPanelClass}
                style={splitWidthPx != null ? { width: splitWidthPx } : undefined}
              >
                {tab === 'credentials' ? (
                  <MenuItem>
                    {({ focus }) => (
                      <button
                        type="button"
                        className={createSplitMenuItemClass(focus)}
                        onClick={() => void handleCreateFlowNavigate()}
                      >
                        Create flow
                      </button>
                    )}
                  </MenuItem>
                ) : (
                  <MenuItem>
                    {({ focus }) => (
                      <button
                        type="button"
                        className={createSplitMenuItemClass(focus)}
                        onClick={() =>
                          pushWithSearch((q) => {
                            q.set('tab', 'credentials');
                            q.delete('newCredential');
                            q.set('bootstrapCredential', '1');
                          })
                        }
                      >
                        Create credential
                      </button>
                    )}
                  </MenuItem>
                )}
              </MenuItems>
            </Menu>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto">
        <div role="tabpanel" hidden={tab !== 'flows'}>
          {tab === 'flows' && (
            <>
              {newFlow && (
                <div className="mb-4 rounded-lg border border-gray-200 bg-white p-4">
                  <div className="mb-3 flex justify-end">
                    <button
                      type="button"
                      onClick={dismissNewFlow}
                      className="text-sm font-medium text-gray-600 hover:text-gray-900"
                    >
                      Dismiss
                    </button>
                  </div>
                  <FlowCreate organizationId={organizationId} />
                </div>
              )}
              <FlowList organizationId={organizationId} />
            </>
          )}
        </div>
        <div role="tabpanel" hidden={tab !== 'credentials'}>
          {tab === 'credentials' && (
            <FlowCredentials
              organizationId={organizationId}
              autoBootstrapCredential={autoCreateCredential}
              onAutoBootstrapCredentialHandled={onCredentialBootstrapHandled}
            />
          )}
        </div>
        <div role="tabpanel" hidden={tab !== 'executions'}>
          {tab === 'executions' && <FlowExecutionsAll organizationId={organizationId} />}
        </div>
      </div>
    </div>
  );
}
