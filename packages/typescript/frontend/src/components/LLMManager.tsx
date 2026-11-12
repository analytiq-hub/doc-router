'use client'

import { Pencil, Settings2, Trash2 } from 'lucide-react'
import React, { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import type { LLMProvider } from '@docrouter/sdk'

import { DataTable, type DataTableColumn } from '@/components/data-table'
import { ErrorAlert } from '@/components/ErrorAlert'
import { FormDialog } from '@/components/FormDialog'
import { RowActionsMenu } from '@/components/RowActionsMenu'
import { SearchInput } from '@/components/SearchInput'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Field, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { DocRouterAccountApi } from '@/utils/api'
import { formatLocalDate } from '@/utils/date'

const LLMManager: React.FC = () => {
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), [])
  const [llmProviders, setLLMProviders] = useState<LLMProvider[]>([])
  const [editModalOpen, setEditModalOpen] = useState(false)
  const [editingProvider, setEditingProvider] = useState<string | null>(null)
  const [editTokenValue, setEditTokenValue] = useState('')
  const [editBusy, setEditBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [modelSelectionOpen, setModelSelectionOpen] = useState(false)
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null)

  const refreshProviders = async () => {
    const response = await docRouterAccountApi.listLLMProviders()
    setLLMProviders(response.providers)
  }

  useEffect(() => {
    void (async () => {
      try {
        setLoading(true)
        await refreshProviders()
      } catch (err) {
        console.error('Error fetching LLM providers:', err)
      } finally {
        setLoading(false)
      }
    })()
  }, [docRouterAccountApi])

  const handleEditLLMToken = (provider: string) => {
    setEditingProvider(provider)
    setEditTokenValue('')
    setEditModalOpen(true)
  }

  const handleSaveLLMToken = async () => {
    if (!editingProvider) return
    const provider = llmProviders.find((p) => p.name === editingProvider)
    setEditBusy(true)
    setError(null)
    try {
      await docRouterAccountApi.setLLMProviderConfig(editingProvider, {
        token: editTokenValue,
        enabled: true,
        litellm_models_enabled: provider?.litellm_models_enabled ?? null,
        litellm_models_chat_agent: provider?.litellm_models_chat_agent ?? null,
      })
      setEditModalOpen(false)
      await refreshProviders()
    } catch (err) {
      console.error('Error saving LLM token:', err)
      setError('An error occurred while saving the LLM token. Please try again.')
    } finally {
      setEditBusy(false)
    }
  }

  const handleDeleteLLMToken = async (providerName: string) => {
    const provider = llmProviders.find((p) => p.name === providerName)
    try {
      await docRouterAccountApi.setLLMProviderConfig(providerName, {
        token: '',
        enabled: false,
        litellm_models_enabled: provider?.litellm_models_enabled ?? null,
        litellm_models_chat_agent: provider?.litellm_models_chat_agent ?? null,
      })
      await refreshProviders()
    } catch (err) {
      console.error('Error deleting LLM token:', err)
      setError('An error occurred while deleting the LLM token. Please try again.')
    }
  }

  const handleToggleProvider = async (providerName: string, enabled: boolean) => {
    const provider = llmProviders.find((p) => p.name === providerName)
    try {
      await docRouterAccountApi.setLLMProviderConfig(providerName, {
        enabled,
        token: null,
        litellm_models_enabled: provider?.litellm_models_enabled ?? null,
        litellm_models_chat_agent: provider?.litellm_models_chat_agent ?? null,
      })
      await refreshProviders()
    } catch (err) {
      console.error('Error toggling provider:', err)
      setError('An error occurred while updating the provider. Please try again.')
    }
  }

  const handleToggleModel = async (providerName: string, model: string, enabled: boolean) => {
    try {
      const provider = llmProviders.find((p) => p.name === providerName)
      if (!provider) return
      const updatedModels = enabled
        ? [...provider.litellm_models_enabled, model]
        : provider.litellm_models_enabled.filter((m) => m !== model)
      const chatAgent = provider.litellm_models_chat_agent ?? []
      const updatedChatAgent = chatAgent.filter((m) => updatedModels.includes(m))
      await docRouterAccountApi.setLLMProviderConfig(providerName, {
        enabled: provider.enabled,
        token: null,
        litellm_models_enabled: updatedModels,
        litellm_models_chat_agent: updatedChatAgent,
      })
      await refreshProviders()
    } catch (err) {
      console.error('Error toggling model:', err)
      setError('An error occurred while updating the models. Please try again.')
    }
  }

  const filteredProviders = llmProviders.filter(
    (provider) => searchQuery === '' || provider.name.toLowerCase().includes(searchQuery.toLowerCase()),
  )

  const columns: DataTableColumn<LLMProvider>[] = useMemo(
    () => [
      {
        field: 'name',
        headerName: 'Provider',
        flex: 1,
        minWidth: 150,
        renderCell: ({ row }) => (
          <Link
            to={`/settings/account/development/llm-manager/providers/${row.name}`}
            className="font-medium text-primary hover:underline"
          >
            {row.display_name}
          </Link>
        ),
      },
      {
        field: 'enabled',
        headerName: 'Enabled',
        width: 100,
        sortable: false,
        renderCell: ({ row }) => (
          <Switch
            checked={row.enabled}
            onCheckedChange={(checked) => void handleToggleProvider(row.name, checked === true)}
            aria-label={`Enable ${row.display_name}`}
          />
        ),
      },
      {
        field: 'litellm_models_enabled',
        headerName: 'Enabled models',
        flex: 1,
        minWidth: 160,
        sortable: false,
        renderCell: ({ row }) => {
          const count = row.litellm_models_enabled?.length ?? 0
          return (
            <span className="text-muted-foreground text-sm">
              {count} {count === 1 ? 'model' : 'models'}
            </span>
          )
        },
      },
      {
        field: 'token',
        headerName: 'Token',
        flex: 1,
        minWidth: 160,
        sortable: false,
        renderCell: ({ row }) => (
          <span className="font-mono text-xs">
            {row.token ? `${row.token.slice(0, 16)}••••••••` : 'Not set'}
          </span>
        ),
      },
      {
        field: 'token_created_at',
        headerName: 'Created',
        width: 140,
        renderCell: ({ row }) => (row.token_created_at ? formatLocalDate(row.token_created_at) : '—'),
      },
      {
        field: 'actions',
        headerName: '',
        width: 52,
        sortable: false,
        hideable: false,
        resizable: false,
        renderCell: ({ row }) => (
          <RowActionsMenu
            label={`Actions for ${row.display_name}`}
            actions={[
              {
                label: 'Configure models',
                icon: Settings2,
                to: `/settings/account/development/llm-manager/providers/${row.name}`,
              },
              {
                label: 'Edit token',
                icon: Pencil,
                onSelect: () => handleEditLLMToken(row.name),
              },
              row.token
                ? {
                    label: 'Delete token',
                    icon: Trash2,
                    destructive: true,
                    onSelect: () => void handleDeleteLLMToken(row.name),
                  }
                : null,
            ]}
          />
        ),
      },
    ],
    [llmProviders],
  )

  const providerForModels = selectedProvider
    ? llmProviders.find((p) => p.name === selectedProvider)
    : undefined

  return (
    <Card className="flex h-[calc(100vh-184px)] flex-col">
      <CardHeader className="space-y-0 pb-3">
        <CardTitle className="text-lg">LLM providers</CardTitle>
      </CardHeader>
      <CardContent className="flex min-h-0 flex-1 flex-col gap-4">
        <ErrorAlert error={error} />
        <SearchInput
          className="w-full max-w-md"
          value={searchQuery}
          onChange={setSearchQuery}
          placeholder="Search providers…"
        />
        <DataTable rows={filteredProviders} columns={columns} loading={loading} getRowId={(row) => row.name} />
      </CardContent>

      {editModalOpen && editingProvider ? (
        <FormDialog
          title={`Edit ${editingProvider} token`}
          submitLabel="Save"
          busy={editBusy}
          error={error}
          onSubmit={() => void handleSaveLLMToken()}
          onClose={() => setEditModalOpen(false)}
        >
          <Field>
            <FieldLabel htmlFor="llm-token">Token</FieldLabel>
            <Input
              id="llm-token"
              value={editTokenValue}
              onChange={(e) => setEditTokenValue(e.target.value)}
              placeholder="Enter API token"
              autoFocus
            />
          </Field>
        </FormDialog>
      ) : null}

      <Dialog open={modelSelectionOpen} onOpenChange={setModelSelectionOpen}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Configure models for {selectedProvider}</DialogTitle>
          </DialogHeader>
          <div className="max-h-96 overflow-y-auto">
            {providerForModels?.litellm_models_available.map((model) => (
              <label
                key={model}
                className="flex cursor-pointer items-center gap-2 border-b py-2 text-sm last:border-0"
              >
                <Checkbox
                  checked={providerForModels.litellm_models_enabled.includes(model)}
                  onCheckedChange={(checked) =>
                    selectedProvider &&
                    void handleToggleModel(selectedProvider, model, checked === true)
                  }
                />
                <span>{model}</span>
              </label>
            ))}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setModelSelectionOpen(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  )
}

export default LLMManager
