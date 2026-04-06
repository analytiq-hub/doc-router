'use client'

import React, { useState, useEffect, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import type { LLMChatModel, OcrMode, OrgOcrConfig } from '@docrouter/sdk'
import { OrganizationMember, OrganizationType } from '@/types/index'
import { DocRouterAccountApi } from '@/utils/api'
import { isAxiosError } from 'axios'
import { User } from '@docrouter/sdk'
import { 
  DataGrid, 
  GridColDef, 
  GridRenderCellParams 
} from '@mui/x-data-grid'
import { Switch, IconButton, Alert } from '@mui/material'
import DeleteIcon from '@mui/icons-material/Delete'
import { useAppSession } from '@/contexts/AppSessionContext'
import UserAddToOrgModal from './UserAddToOrgModal'
import { toast } from 'react-toastify'
import MoreVertIcon from '@mui/icons-material/MoreVert';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import { useOrganizationData } from '@/hooks/useOrganizationData'
import { isSysAdmin, isOrgAdmin } from '@/utils/roles'

interface OrganizationEditProps {
  organizationId: string
}

const FALLBACK_TEXTRACT_FEATURES = ['LAYOUT', 'TABLES', 'FORMS', 'SIGNATURES'] as const

const FALLBACK_OCR_MODES: OcrMode[] = ['textract', 'mistral', 'llm']

const OCR_MODE_LABELS: Record<OcrMode, string> = {
  textract: 'AWS Textract',
  mistral: 'Mistral OCR',
  llm: 'LLM OCR',
}

function isOcrMode(s: string): s is OcrMode {
  return s === 'textract' || s === 'mistral' || s === 'llm'
}

function normalizeOcrConfig(raw: OrgOcrConfig): OrgOcrConfig {
  return {
    mode: raw.mode ?? 'textract',
    textract: {
      feature_types:
        raw.textract?.feature_types && raw.textract.feature_types.length > 0
          ? raw.textract.feature_types
          : ['LAYOUT'],
    },
    mistral: raw.mistral ?? {},
    llm: {
      provider: raw.llm?.provider ?? null,
      model: raw.llm?.model ?? null,
    },
  }
}

const cloneOcrConfig = (c: OrgOcrConfig): OrgOcrConfig =>
  normalizeOcrConfig(JSON.parse(JSON.stringify(c)) as OrgOcrConfig)

const getAvailableOrganizationTypes = (currentType: OrganizationType, isSystemAdmin: boolean): OrganizationType[] => {
  switch (currentType) {
    case 'individual':
      // Only system admins can upgrade to enterprise
      if (isSystemAdmin) {
        return ['individual', 'team', 'enterprise'];
      }
      return ['individual', 'team'];
    case 'team':
      // Only system admins can upgrade to enterprise
      if (isSystemAdmin) {
        return ['team', 'enterprise'];
      }
      return ['team'];
    case 'enterprise':
      return ['enterprise'];
    default:
      if (isSystemAdmin) {
        return ['individual', 'team', 'enterprise'];
      }
      return ['individual', 'team'];
  }
};

const OrganizationEdit: React.FC<OrganizationEditProps> = ({ organizationId }) => {
  const router = useRouter()
  const { organization, loading, refreshData } = useOrganizationData(organizationId)
  const [name, setName] = useState('')
  const [type, setType] = useState<OrganizationType>('individual')
  const [members, setMembers] = useState<OrganizationMember[]>([])
  const [defaultPromptEnabled, setDefaultPromptEnabled] = useState<boolean>(true)
  const [allUsers, setAllUsers] = useState<User[]>([])
  const [memberSearch, setMemberSearch] = useState('');
  const [originalName, setOriginalName] = useState('')
  const [originalType, setOriginalType] = useState<OrganizationType>('individual')
  const [originalMembers, setOriginalMembers] = useState<OrganizationMember[]>([])
  const [originalDefaultPromptEnabled, setOriginalDefaultPromptEnabled] = useState<boolean>(true)
  const [ocrConfig, setOcrConfig] = useState<OrgOcrConfig | null>(null)
  const [originalOcrConfig, setOriginalOcrConfig] = useState<OrgOcrConfig | null>(null)
  const { session } = useAppSession();
  const [showAddUserModal, setShowAddUserModal] = useState(false);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedMember, setSelectedMember] = useState<{ id: string, isAdmin: boolean } | null>(null);
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), []);

  const [ocrLlmChatModels, setOcrLlmChatModels] = useState<LLMChatModel[]>([])
  const [ocrLlmCatalogLoading, setOcrLlmCatalogLoading] = useState(true)
  const [ocrLlmCatalogError, setOcrLlmCatalogError] = useState<string | null>(null)

  const mistralEnabled = organization?.ocr_catalog?.mistral_enabled !== false

  // Filter current organization members
  const filteredMembers = members.filter(member => {
    const user = allUsers.find(u => u.id === member.user_id);
    return user && (
      user.name?.toLowerCase().includes(memberSearch.toLowerCase()) || 
      user.email.toLowerCase().includes(memberSearch.toLowerCase())
    );
  });

  // Update local state when organization data changes
  useEffect(() => {
    if (organization) {
      setName(organization.name);
      setType(organization.type);
      setMembers(organization.members);
      setDefaultPromptEnabled(
        organization.default_prompt_enabled !== undefined
          ? organization.default_prompt_enabled
          : true
      );

      // Store original values
      setOriginalName(organization.name);
      setOriginalType(organization.type);
      setOriginalMembers(organization.members);
      setOriginalDefaultPromptEnabled(
        organization.default_prompt_enabled !== undefined
          ? organization.default_prompt_enabled
          : true
      );

      const oc = cloneOcrConfig(organization.ocr_config)
      setOcrConfig(oc)
      setOriginalOcrConfig(cloneOcrConfig(organization.ocr_config))
    }
  }, [organization]);

  // Separate useEffect for fetching users
  useEffect(() => {
    const fetchUsers = async () => {
      const isUserOrgAdmin = organization ? isOrgAdmin(organization, session) : false;
      const isUserSysAdmin = isSysAdmin(session);
      
      if (isUserOrgAdmin || isUserSysAdmin) {
        let allUsers: User[] = [];
        let skip = 0;
        const limit = 100;
        let total = 0;

        do {
          const usersResponse = await docRouterAccountApi.listUsers({ organization_id: organizationId, skip, limit });
          allUsers = allUsers.concat(usersResponse.users);
          total = usersResponse.total_count;
          skip += limit;
        } while (allUsers.length < total);

        setAllUsers(allUsers);
      }
    };

    fetchUsers();
  }, [organizationId, organization, session, docRouterAccountApi]);

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      setOcrLlmCatalogLoading(true)
      setOcrLlmCatalogError(null)
      try {
        const res = await docRouterAccountApi.listLLMModels({
          llmEnabled: true,
          providerEnabled: true,
          chatAgentOnly: true,
        })
        if (!cancelled) {
          setOcrLlmChatModels(res.chat_models)
        }
      } catch (e) {
        console.error('Failed to load LLM catalog for OCR:', e)
        if (!cancelled) {
          setOcrLlmChatModels([])
          setOcrLlmCatalogError('Could not load LLM providers and models. Try again later.')
        }
      } finally {
        if (!cancelled) {
          setOcrLlmCatalogLoading(false)
        }
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [docRouterAccountApi])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateAdminPresence(members)) {
      toast.error('Organization must have at least one admin');
      return;
    }

    if (ocrConfig) {
      if (ocrConfig.mode === 'textract' && ocrConfig.textract.feature_types.length === 0) {
        toast.error('Select at least one Textract feature type (e.g. LAYOUT).');
        return;
      }
      if (ocrConfig.mode === 'llm') {
        const p = ocrConfig.llm.provider?.trim() ?? '';
        const m = ocrConfig.llm.model?.trim() ?? '';
        if (!p || !m) {
          toast.error('LLM OCR requires both provider and model.');
          return;
        }
      }
      if (ocrConfig.mode === 'mistral' && !mistralEnabled) {
        toast.error(
          'Mistral OCR is not available: enable the Mistral LLM provider and at least one model in account LLM settings, then try again.'
        );
        return;
      }
    }

    // Validate individual organization member count
    if (type === 'individual' && members.length > 1) {
      toast.error('Individual organizations cannot have multiple members');
      return;
    }

    // Check if user is trying to upgrade to Enterprise without admin privileges
    if ((originalType === 'individual' || originalType === 'team') && type === 'enterprise' && !isSysAdmin(session)) {
      toast.error('Only system administrators can upgrade organizations to Enterprise');
      return;
    }

    try {
      await docRouterAccountApi.updateOrganization(organizationId, { 
        name,
        type,
        members,
        default_prompt_enabled: defaultPromptEnabled,
        ...(ocrConfig ? { ocr_config: ocrConfig as unknown as Record<string, unknown> } : {}),
      });
      await refreshData();
      
      // Update original values after successful save
      setOriginalName(name);
      setOriginalType(type);
      setOriginalMembers(members);
      setOriginalDefaultPromptEnabled(defaultPromptEnabled);
      if (ocrConfig) {
        setOriginalOcrConfig(cloneOcrConfig(ocrConfig))
      }
    } catch (err) {
      if (isAxiosError(err)) {
        toast.error(err.response?.data?.detail || 'Failed to update organization');
      } else {
        toast.error('An unexpected error occurred');
      }
    }
  };

  const handleRoleChange = (userId: string, newRole: 'admin' | 'user') => {
    setMembers(prevMembers => {
      const updatedMembers = prevMembers.map(member => 
        member.user_id === userId ? { ...member, role: newRole } : member
      );
      
      // If the change would result in no admins, prevent it
      if (!validateAdminPresence(updatedMembers)) {
        toast.error('Organization must have at least one admin');
        return prevMembers; // Keep the original state
      }

      return updatedMembers;
    });
  };

  const handleAddMember = async (userId: string): Promise<void> => {
    // Prevent adding members to individual organizations
    if (type === 'individual') {
      toast.error('Individual organizations cannot have multiple members');
      return;
    }

    if (!members.some(member => member.user_id === userId)) {
      setMembers(prev => [...prev, { user_id: userId, role: 'user' }]);
    }
  };

  const handleRemoveMember = (userId: string) => {
    const memberToRemove = members.find(member => member.user_id === userId);
    if (memberToRemove?.role === 'admin') {
      // Check if this is the last admin
      const remainingAdmins = members.filter(m => m.role === 'admin' && m.user_id !== userId);
      if (remainingAdmins.length === 0) {
        toast.error('Cannot remove the last admin. Promote another member to admin first.');
        return;
      }
    }
    
    setMembers(prev => prev.filter(member => member.user_id !== userId));
  };

  // Update getGridRows to use filtered members
  const getGridRows = () => {
    return filteredMembers.map(member => {
      const user = allUsers.find(u => u.id === member.user_id)
      return {
        id: member.user_id,
        name: user?.name || 'Unknown User',
        email: user?.email || '',
        isAdmin: member.role === 'admin'
      }
    })
  }

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, memberId: string, isAdmin: boolean) => {
    setAnchorEl(event.currentTarget);
    setSelectedMember({ id: memberId, isAdmin });
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setSelectedMember(null);
  };

  // Define columns for the grid
  const columns: GridColDef[] = [
    {
      field: 'name',
      headerName: 'User',
      flex: 1,
      minWidth: 300,
      renderCell: (params: GridRenderCellParams) => (
        <button
          onClick={() => router.push(`/settings/account/users/${params.row.id}`)}
          className="text-left hover:text-blue-600 focus:outline-none"
        >
          <span className="font-medium">{params.value}</span>
          <span className="text-gray-500 ml-2">({params.row.email})</span>
        </button>
      )
    },
    {
      field: 'isAdmin',
      headerName: 'Admin',
      width: 120,
      renderCell: (params: GridRenderCellParams) => (
        <span className={params.value ? 'text-blue-600' : ''}>
          {params.value ? 'Admin' : 'User'}
        </span>
      )
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 80,
      renderCell: (params: GridRenderCellParams) => (
        <div>
          <IconButton
            onClick={(e) => handleMenuOpen(e, params.row.id, params.row.isAdmin)}
            className="text-gray-600 hover:bg-gray-50"
          >
            <MoreVertIcon />
          </IconButton>
        </div>
      )
    }
  ]

  const textractFeatureOptions =
    organization?.ocr_catalog?.textract_feature_types?.length
      ? organization.ocr_catalog.textract_feature_types
      : [...FALLBACK_TEXTRACT_FEATURES]

  const ocrModeOptions = useMemo((): OcrMode[] => {
    const fromCatalog = organization?.ocr_catalog?.modes?.filter(isOcrMode) ?? []
    const base = fromCatalog.length > 0 ? fromCatalog : [...FALLBACK_OCR_MODES]
    if (ocrConfig && !base.includes(ocrConfig.mode)) {
      return [...base, ocrConfig.mode]
    }
    return base
  }, [organization?.ocr_catalog?.modes, ocrConfig?.mode])

  const toggleTextractFeature = (ft: string) => {
    setOcrConfig((prev) => {
      if (!prev) return prev
      const types = new Set(prev.textract.feature_types)
      if (types.has(ft)) {
        types.delete(ft)
      } else {
        types.add(ft)
      }
      return {
        ...prev,
        textract: { ...prev.textract, feature_types: Array.from(types) },
      }
    })
  }

  const setOcrMode = (mode: OcrMode) => {
    setOcrConfig((prev) => (prev ? { ...prev, mode } : prev))
  }

  const setLlmField = (field: 'provider' | 'model', value: string) => {
    const trimmed = value.trim()
    setOcrConfig((prev) => {
      if (!prev) return prev
      return {
        ...prev,
        llm: { ...prev.llm, [field]: trimmed === '' ? null : trimmed },
      }
    })
  }

  const ocrLlmProviderOptions = useMemo(() => {
    const m = new Map<string, string>()
    for (const cm of ocrLlmChatModels) {
      const pn = cm.provider_name?.trim()
      if (pn && !m.has(pn)) {
        m.set(pn, (cm.provider_display_name?.trim() || pn) as string)
      }
    }
    return Array.from(m.entries())
      .map(([name, display]) => ({ name, display }))
      .sort((a, b) => a.display.localeCompare(b.display))
  }, [ocrLlmChatModels])

  const ocrLlmProviderOptionsWithLegacy = useMemo(() => {
    const cur = ocrConfig?.llm?.provider?.trim()
    if (!cur || ocrLlmProviderOptions.some((r) => r.name === cur)) {
      return ocrLlmProviderOptions
    }
    return [
      ...ocrLlmProviderOptions,
      { name: cur, display: `${cur} (not available — update account LLM settings)` },
    ].sort((a, b) => a.display.localeCompare(b.display))
  }, [ocrConfig?.llm?.provider, ocrLlmProviderOptions])

  const ocrLlmModelsForProvider = useMemo(() => {
    const p = ocrConfig?.llm?.provider?.trim()
    if (!p) return []
    const names = ocrLlmChatModels
      .filter((cm) => (cm.provider_name?.trim() ?? '') === p)
      .map((cm) => cm.litellm_model)
    return Array.from(new Set(names)).sort((a, b) => a.localeCompare(b))
  }, [ocrLlmChatModels, ocrConfig?.llm?.provider])

  const ocrLlmModelSelectValues = useMemo(() => {
    const cur = ocrConfig?.llm?.model?.trim()
    const base = ocrLlmModelsForProvider
    if (!cur || base.includes(cur)) {
      return base
    }
    return [...base, cur].sort((a, b) => a.localeCompare(b))
  }, [ocrConfig?.llm?.model, ocrLlmModelsForProvider])

  // Check if form has changes
  const hasChanges = () => {
    if (name !== originalName) return true;
    if (type !== originalType) return true;
    if (members.length !== originalMembers.length) return true;
    if (defaultPromptEnabled !== originalDefaultPromptEnabled) return true;
    if (ocrConfig && originalOcrConfig && JSON.stringify(ocrConfig) !== JSON.stringify(originalOcrConfig)) {
      return true;
    }

    // Compare each member and their roles
    const memberChanges = members.some(member => {
      const originalMember = originalMembers.find(m => m.user_id === member.user_id);
      return !originalMember || originalMember.role !== member.role;
    });
    
    return memberChanges;
  };

  // Add this validation function after the hasChanges function
  const validateAdminPresence = (updatedMembers: OrganizationMember[]): boolean => {
    return updatedMembers.some(member => member.role === 'admin');
  };

  // Replace the permission check block with this:
  if (!loading) {
    const isUserOrgAdmin = organization ? isOrgAdmin(organization, session) : false;
    const isUserSysAdmin = isSysAdmin(session);
    
    if (!isUserOrgAdmin && !isUserSysAdmin) {
      return (
        <div className="flex items-center justify-center p-4">
          You don&apos;t have permission to edit this organization. Only organization admins and system admins can edit organizations.
        </div>
      );
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-4">
        <svg className="animate-spin h-5 w-5 mr-2" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
        Loading...
      </div>
    );
  }

  if (!organization) {
    return <div className="flex items-center justify-center p-4">Organization not found</div>
  }

  return (
    <div className="max-w-4xl mx-auto bg-white rounded-lg shadow p-6 min-h-[calc(100vh-80px)] flex flex-col">
      <div className="flex flex-col flex-1 h-0">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-semibold">Edit Organization</h2>
          <div className="flex gap-4">
            {/* Subscription Link - Only show for org admins and sys admins */}
            {(() => {
              const isUserOrgAdmin = organization ? isOrgAdmin(organization, session) : false;
              const isUserSysAdmin = isSysAdmin(session);
              return (isUserOrgAdmin || isUserSysAdmin) ? (
                <>
                  <a
                    href={`/settings/organizations/${organizationId}/subscription`}
                    className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                  >
                    <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
                    </svg>
                    Billing
                  </a>
                </>
              ) : null;
            })()}
            <button
              type="submit"
              form="organization-form"
              disabled={!hasChanges()}
              className={`px-4 py-2 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
                ${hasChanges() 
                  ? 'bg-blue-600 text-white hover:bg-blue-700' 
                  : 'bg-gray-100 text-gray-400 cursor-not-allowed'}`}
            >
              Save Changes
            </button>
            <button
              type="button"
              onClick={() => router.push('/settings/organizations')}
              className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
            >
              Cancel
            </button>
          </div>
        </div>
        
        <form id="organization-form" onSubmit={handleSubmit} className="flex flex-col flex-1">
          {/* Organization Name Section */}
          <div className="bg-gray-50 p-4 rounded-lg mb-6">
            <div className="space-y-4">
              <div>
                <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-1">
                  Organization Name
                </label>
                <input
                  type="text"
                  id="name"
                  name="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                />
              </div>
              
              <div>
                <label htmlFor="type" className="block text-sm font-medium text-gray-700 mb-1">
                  Organization Type
                </label>
                <select
                  id="type"
                  name="type"
                  value={type}
                  onChange={(e) => setType(e.target.value as OrganizationType)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white disabled:bg-gray-100 disabled:cursor-not-allowed"
                >
                  {getAvailableOrganizationTypes(originalType, isSysAdmin(session)).map((orgType) => (
                    <option key={orgType} value={orgType}>
                      {orgType.charAt(0).toUpperCase() + orgType.slice(1)}
                    </option>
                  ))}
                  {/* Show Enterprise option as disabled for non-admin users */}
                  {!isSysAdmin(session) && (originalType === 'individual' || originalType === 'team') && (
                    <option value="enterprise" disabled>
                      Enterprise (Admin Only)
                    </option>
                  )}
                </select>
              </div>

              <div className="flex items-start space-x-2">
                <input
                  id="default-prompt-enabled"
                  type="checkbox"
                  checked={defaultPromptEnabled}
                  onChange={(e) => setDefaultPromptEnabled(e.target.checked)}
                  className="mt-1 h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                />
                <div>
                  <label htmlFor="default-prompt-enabled" className="block text-sm font-medium text-gray-700">
                    Enable default prompt
                  </label>
                  <p className="text-sm text-gray-500">
                    When enabled, the default prompt will run automatically for documents in this organization.
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* OCR settings */}
          {ocrConfig && organization && (
            <div className="bg-gray-50 p-4 rounded-lg mb-6 border border-gray-200">
              <h3 className="text-lg font-medium text-gray-900 mb-2">OCR</h3>

              <div className="flex flex-col gap-1 mb-4">
                <label htmlFor="ocr-mode" className="block text-sm font-medium text-gray-700">
                  OCR engine
                </label>
                <select
                  id="ocr-mode"
                  value={ocrConfig.mode}
                  onChange={(e) => setOcrMode(e.target.value as OcrMode)}
                  className="w-full max-w-md px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                >
                  {ocrModeOptions.map((m) => (
                    <option
                      key={m}
                      value={m}
                      disabled={m === 'mistral' && !mistralEnabled}
                    >
                      {m === 'mistral' && !mistralEnabled
                        ? `${OCR_MODE_LABELS[m]} (unavailable)`
                        : OCR_MODE_LABELS[m]}
                    </option>
                  ))}
                </select>
              </div>

              {!mistralEnabled && ocrConfig.mode === 'mistral' && (
                <Alert severity="warning" sx={{ mb: 2 }}>
                  Mistral OCR is unavailable because the Mistral provider is off or no models are enabled
                  in account LLM settings. Select another engine before you can save.
                </Alert>
              )}

              {ocrConfig.mode === 'textract' && (
                <Alert severity="info" sx={{ mb: 2 }}>
                  Uses AWS Textract AnalyzeDocument. Choose feature types below.
                </Alert>
              )}
              {ocrConfig.mode === 'mistral' && mistralEnabled && (
                <Alert severity="info" sx={{ mb: 2 }}>
                  Uses Mistral OCR (<code className="text-sm">mistral-ocr-latest</code>). The API key is
                  read from the Mistral LLM provider in account settings when a document is processed.
                </Alert>
              )}
              {ocrConfig.mode === 'llm' && (
                <>
                  {ocrLlmCatalogError && (
                    <Alert severity="error" sx={{ mb: 2 }}>
                      {ocrLlmCatalogError}
                    </Alert>
                  )}
                  {ocrLlmCatalogLoading ? (
                    <p className="text-sm text-gray-600 mb-4">Loading LLM providers and models…</p>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                      <div>
                        <label
                          htmlFor="ocr-llm-provider"
                          className="block text-sm font-medium text-gray-700 mb-1"
                        >
                          LLM provider <span className="text-red-500">*</span>
                        </label>
                        <select
                          id="ocr-llm-provider"
                          value={ocrConfig.llm.provider ?? ''}
                          onChange={(e) => {
                            const v = e.target.value
                            setOcrConfig((prev) => {
                              if (!prev) return prev
                              return {
                                ...prev,
                                llm: {
                                  provider: v === '' ? null : v,
                                  model: null,
                                },
                              }
                            })
                          }}
                          required
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                        >
                          <option value="">Select a provider</option>
                          {ocrLlmProviderOptionsWithLegacy.map((row) => (
                            <option key={row.name} value={row.name}>
                              {row.display}
                            </option>
                          ))}
                        </select>
                        <p className="text-xs text-gray-500 mt-1">
                          Enabled accounts with enabled chat models (from account LLM settings).
                        </p>
                      </div>
                      <div>
                        <label
                          htmlFor="ocr-llm-model"
                          className="block text-sm font-medium text-gray-700 mb-1"
                        >
                          Model <span className="text-red-500">*</span>
                        </label>
                        <select
                          id="ocr-llm-model"
                          value={ocrConfig.llm.model ?? ''}
                          onChange={(e) => setLlmField('model', e.target.value)}
                          required
                          disabled={!ocrConfig.llm.provider}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white disabled:bg-gray-100 disabled:text-gray-500"
                        >
                          <option value="">
                            {ocrConfig.llm.provider ? 'Select a model' : 'Select a provider first'}
                          </option>
                          {ocrLlmModelSelectValues.map((m) => (
                            <option key={m} value={m}>
                              {m}
                              {!ocrLlmModelsForProvider.includes(m) ? ' (not available)' : ''}
                            </option>
                          ))}
                        </select>
                        <p className="text-xs text-gray-500 mt-1">
                          Chat models only (same pool as chat/agent). Choose a vision/PDF-capable model
                          for best OCR results.
                        </p>
                      </div>
                    </div>
                  )}
                </>
              )}

              {ocrConfig.mode === 'textract' && (
                <div className="space-y-4">
                  <div className="border-t border-gray-200 pt-4 first:border-t-0 first:pt-0">
                    <p className="text-sm font-medium text-gray-800 mb-2">AWS Textract</p>
                    <p className="text-xs text-gray-500 mb-2">Feature types (AnalyzeDocument)</p>
                    <div className="flex flex-wrap gap-3">
                      {textractFeatureOptions.map((ft) => (
                        <label key={ft} className="inline-flex items-center gap-2 text-sm text-gray-700">
                          <input
                            type="checkbox"
                            checked={ocrConfig.textract.feature_types.includes(ft)}
                            onChange={() => toggleTextractFeature(ft)}
                            className="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                          />
                          {ft}
                        </label>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Members Section - adjust the height calculation */}
          <div className="flex-1 bg-gray-50 p-4 rounded-lg flex flex-col">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-medium text-gray-900">Members</h3>
              
              <button
                type="button"
                onClick={() => setShowAddUserModal(true)}
                disabled={type === 'individual'}
                className={`px-4 py-2 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
                  ${type === 'individual' 
                    ? 'bg-gray-100 text-gray-400 cursor-not-allowed' 
                    : 'bg-blue-600 text-white hover:bg-blue-700'}`}
              >
                Add User
              </button>
            </div>

            <div className="mb-4">
              <input
                type="text"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                placeholder="Search members..."
                value={memberSearch}
                onChange={(e) => setMemberSearch(e.target.value)}
              />
            </div>

            {/* Update the DataGrid container height */}
            <div className="flex-1 bg-white rounded-lg flex flex-col">
              <DataGrid
                rows={getGridRows()}
                columns={columns}
                initialState={{
                  pagination: {
                    paginationModel: { pageSize: 5 }
                  }
                }}
                pageSizeOptions={[5, 10, 20]}
                disableRowSelectionOnClick
                disableColumnMenu
                density="standard"
                sx={{
                  flex: 1,
                  minHeight: 100,
                  height: '100%',
                  '& .MuiDataGrid-row': {
                    height: '60px'
                  },
                  '& .MuiDataGrid-row:nth-of-type(odd)': {
                    backgroundColor: '#f9fafb'
                  },
                  '& .MuiDataGrid-cell': {
                    height: '60px',
                    alignItems: 'center',
                    padding: '0 16px'
                  }
                }}
              />
              {/* Actions Menu for member row */}
              <Menu
                anchorEl={anchorEl}
                open={Boolean(anchorEl)}
                onClose={handleMenuClose}
              >
                <MenuItem
                  onClick={() => {
                    if (selectedMember) {
                      handleRoleChange(
                        selectedMember.id,
                        selectedMember.isAdmin ? 'user' : 'admin'
                      );
                    }
                    handleMenuClose();
                  }}
                  className="flex items-center gap-2"
                  disabled={!selectedMember}
                >
                  <Switch
                    checked={selectedMember?.isAdmin || false}
                    onChange={() => {
                      if (selectedMember) {
                        handleRoleChange(
                          selectedMember.id,
                          selectedMember.isAdmin ? 'user' : 'admin'
                        );
                      }
                      handleMenuClose();
                    }}
                    color="primary"
                    size="small"
                    inputProps={{ 'aria-label': 'Toggle admin' }}
                  />
                  <span>
                    {selectedMember?.isAdmin ? 'Remove Admin' : 'Make Admin'}
                  </span>
                </MenuItem>
                <MenuItem
                  onClick={() => {
                    if (selectedMember) handleRemoveMember(selectedMember.id);
                    handleMenuClose();
                  }}
                  className="flex items-center gap-2"
                  disabled={!selectedMember}
                >
                  <DeleteIcon fontSize="small" className="text-red-600" />
                  <span>Remove</span>
                </MenuItem>
              </Menu>
            </div>
          </div>
        </form>
      </div>

      <UserAddToOrgModal
        open={showAddUserModal}
        onClose={() => setShowAddUserModal(false)}
        onAdd={handleAddMember}
        organizationId={organizationId}
        currentMembers={members.map(member => member.user_id)}
      />
    </div>
  )
}

export default OrganizationEdit 