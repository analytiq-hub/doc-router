'use client';

import React, { useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { ChevronDownIcon } from '@heroicons/react/20/solid';
import { Menu, MenuButton, MenuItem, MenuItems } from '@headlessui/react';
import FlowList from '@/components/flows/FlowList';
import FlowCreate from '@/components/flows/FlowCreate';
import FlowCredentials from '@/components/flows/FlowCredentials';
import FlowExecutionsAll from '@/components/flows/FlowExecutionsAll';
import {
  flowWorkspaceDropdownItemClass,
  flowWorkspaceMenuPanelClass,
} from '@/components/flows/flowWorkspaceMenu';

export type FlowsTab = 'flows' | 'credentials' | 'executions';

export default function FlowsPageClient({
  organizationId,
  tab,
  newFlow,
  newCredential,
}: {
  organizationId: string;
  tab: FlowsTab;
  newFlow: boolean;
  newCredential: boolean;
}) {
  const router = useRouter();

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

  const onCredentialAutoOpenHandled = useCallback(() => {
    stripQueryKeys(['newCredential']);
  }, [stripQueryKeys]);

  const dismissNewFlow = useCallback(() => {
    stripQueryKeys(['newFlow']);
  }, [stripQueryKeys]);

  const createFlowPrimaryClass =
    'inline-flex items-center justify-center rounded-l-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-blue-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/60';

  const createFlowChevronClass =
    'inline-flex items-center justify-center rounded-r-md border-l border-blue-500 bg-blue-600 px-2 py-2 text-white shadow-sm transition hover:bg-blue-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/60';

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

        <div className="flex shrink-0 items-center gap-2 pb-2 sm:pb-4">
          <div className="inline-flex rounded-md shadow-sm">
            <button
              type="button"
              className={createFlowPrimaryClass}
              onClick={() =>
                pushWithSearch((q) => {
                  q.set('tab', 'flows');
                  q.set('newFlow', '1');
                })
              }
            >
              Create flow
            </button>
            <Menu as="div" className="relative -ml-px block">
              <MenuButton
                type="button"
                className={createFlowChevronClass}
                aria-label="More create options"
              >
                <ChevronDownIcon className="h-5 w-5" aria-hidden />
              </MenuButton>
              <MenuItems anchor="bottom end" portal className={flowWorkspaceMenuPanelClass}>
                <MenuItem>
                  {({ focus }) => (
                    <button
                      type="button"
                      className={`${flowWorkspaceDropdownItemClass} w-full ${focus ? 'bg-gray-100' : ''}`}
                      onClick={() =>
                        pushWithSearch((q) => {
                          q.set('tab', 'credentials');
                          q.set('newCredential', '1');
                        })
                      }
                    >
                      Create credential
                    </button>
                  )}
                </MenuItem>
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
              autoOpenCreate={newCredential}
              onAutoOpenCreateHandled={onCredentialAutoOpenHandled}
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
