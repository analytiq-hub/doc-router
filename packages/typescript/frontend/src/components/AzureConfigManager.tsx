'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { DocRouterAccountApi } from '@/utils/api';
import { getApiErrorMsg } from '@/utils/api';
import type { AzureServicePrincipalConfig } from '@docrouter/sdk';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { FormDialog } from '@/components/FormDialog';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field';
import { Input } from '@/components/ui/input';

const AzureConfigManager: React.FC = () => {
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), []);
  const [config, setConfig] = useState<AzureServicePrincipalConfig | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [tenantId, setTenantId] = useState('');
  const [clientId, setClientId] = useState('');
  const [clientSecret, setClientSecret] = useState('');
  const [apiBase, setApiBase] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [deleteOpen, setDeleteOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const c = await docRouterAccountApi.getAzureConfig();
        if (!cancelled) setConfig(c);
      } catch {
        if (!cancelled) setConfig(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [docRouterAccountApi]);

  const handleOpenEdit = () => {
    setTenantId(config?.tenant_id?.trim() ?? '');
    setClientId(config?.client_id?.trim() ?? '');
    setClientSecret('');
    setApiBase(config?.api_base?.trim() ?? '');
    setError(null);
    setEditOpen(true);
  };

  const handleSave = async () => {
    setError(null);
    const t = tenantId.trim();
    const c = clientId.trim();
    const s = clientSecret.trim();
    const b = apiBase.trim().replace(/\/+$/, '');
    if (!t || !c || !s || !b) {
      setError('Tenant ID, Client ID, Client secret, and API base URL are required.');
      return;
    }
    if (!/^https:\/\//i.test(b)) {
      setError('API base URL must start with https://');
      return;
    }
    try {
      await docRouterAccountApi.createAzureConfig({
        tenant_id: t,
        client_id: c,
        client_secret: s,
        api_base: b,
      });
      setEditOpen(false);
      try {
        setConfig(await docRouterAccountApi.getAzureConfig());
      } catch {
        setConfig(null);
      }
    } catch (e: unknown) {
      setError(getApiErrorMsg(e) || 'Failed to save Azure configuration.');
    }
  };

  const handleDelete = async () => {
    setError(null);
    try {
      await docRouterAccountApi.deleteAzureConfig();
      setConfig(null);
      setDeleteOpen(false);
    } catch (e: unknown) {
      setError(getApiErrorMsg(e) || 'Failed to delete Azure configuration.');
    }
  };

  const configured = Boolean(config?.tenant_id);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3 space-y-0">
          <CardTitle className="text-lg">Microsoft Entra (service principal)</CardTitle>
          <Button type="button" onClick={handleOpenEdit}>
            {configured ? 'Edit credentials' : 'Add credentials'}
          </Button>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Service principal credentials (tenant ID, client ID, client secret) and API base URL used to access
            Microsoft Foundry models. The service principal must be assigned the <b>Cognitive Services User</b> role
            on the Foundry resource.
          </p>
          <p className="text-sm">
            <b>Status:</b>{' '}
            {configured ? (
              <span className="text-green-600">Configured</span>
            ) : (
              <span className="text-amber-600">Not configured</span>
            )}
          </p>
          {configured && config ? (
            <div className="mt-4 space-y-1 font-mono text-sm text-foreground">
              <div>
                <span className="text-muted-foreground">Tenant ID:</span> {config.tenant_id}
              </div>
              <div>
                <span className="text-muted-foreground">Client ID:</span> {config.client_id}
              </div>
              <div>
                <span className="text-muted-foreground">Client secret:</span> {config.client_secret}
              </div>
              <div className="break-all">
                <span className="text-muted-foreground">API base:</span> {config.api_base}
              </div>
            </div>
          ) : null}
          {configured ? (
            <Button type="button" variant="outline" className="mt-2 text-destructive" onClick={() => setDeleteOpen(true)}>
              Remove Azure credentials
            </Button>
          ) : null}
          {error && !editOpen ? (
            <Alert variant="destructive" className="mt-3">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}
        </CardContent>
      </Card>

      <Card className="border-primary/30 bg-primary-soft">
        <CardContent className="pt-6 text-sm text-foreground">
          Change Azure configuration for on-prem installs only.
        </CardContent>
      </Card>

      {editOpen ? (
        <FormDialog
          title="Azure service principal"
          submitLabel="Save"
          submitDisabled={!tenantId.trim() || !clientId.trim() || !clientSecret.trim() || !apiBase.trim()}
          error={error}
          size="wide"
          onSubmit={() => void handleSave()}
          onClose={() => {
            setEditOpen(false);
            setError(null);
          }}
        >
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="azure-tenant">Directory (tenant) ID</FieldLabel>
              <Input
                id="azure-tenant"
                className="font-mono text-sm"
                placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                value={tenantId}
                onChange={(e) => {
                  setTenantId(e.target.value);
                  setError(null);
                }}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="azure-client">Application (client) ID</FieldLabel>
              <Input
                id="azure-client"
                className="font-mono text-sm"
                placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                value={clientId}
                onChange={(e) => {
                  setClientId(e.target.value);
                  setError(null);
                }}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="azure-secret">Client secret</FieldLabel>
              <Input
                id="azure-secret"
                type="password"
                className="font-mono text-sm"
                placeholder="From Certificates & secrets"
                value={clientSecret}
                onChange={(e) => {
                  setClientSecret(e.target.value);
                  setError(null);
                }}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="azure-api-base">API base URL (Foundry endpoint)</FieldLabel>
              <Input
                id="azure-api-base"
                type="url"
                className="font-mono text-sm"
                placeholder="https://your-resource.services.ai.azure.com"
                value={apiBase}
                onChange={(e) => {
                  setApiBase(e.target.value);
                  setError(null);
                }}
              />
            </Field>
          </FieldGroup>
        </FormDialog>
      ) : null}

      <ConfirmDialog
        open={deleteOpen}
        title="Remove Azure credentials"
        message="Remove the stored Entra service principal credentials? Microsoft Foundry models may stop working."
        confirmLabel="Remove"
        onConfirm={() => void handleDelete()}
        onClose={() => setDeleteOpen(false)}
      />
    </div>
  );
};

export default AzureConfigManager;
