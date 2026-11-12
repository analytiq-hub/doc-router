'use client'

import { toastActionError } from '@/utils/toastActionError';
import React, { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom';
import { useRouter } from '@/utils/appRouter'
import type { LLMChatModel, OcrMode, OrgOcrConfig } from '@docrouter/sdk'
import type { FlowLogLevel } from '@/types/organizations'
import { OrganizationMember, OrganizationType } from '@/types/index'
import { DocRouterAccountApi } from '@/utils/api';
import { User } from '@docrouter/sdk'
import { Info, MoreVertical, Trash2, TriangleAlert } from 'lucide-react'
import { DataTable, type DataTableColumn, type PaginationModel } from '@/components/data-table'
import { SearchInput } from '@/components/SearchInput'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useAppSession } from '@/contexts/AppSessionContext'
import UserAddToOrgModal from './UserAddToOrgModal'
import { toast } from 'sonner'
import { useOrganizationData } from '@/hooks/useOrganizationData'
import { isSysAdmin, isOrgAdmin } from '@/utils/roles'
import {
  BUILTIN_ADMIN,
  BUILTIN_OPERATOR,
  BUILTIN_PERMISSION_GROUPS,
  memberHasAdminGroup,
  normalizeOrgMember,
  permissionGroupLabel,
  primaryPermissionGroupId,
  sortPermissionGroupIds,
  type BuiltinPermissionGroupId,
} from '@/utils/orgPermissionGroups'

interface OrganizationEditProps {
  organizationId: string
}

const FALLBACK_TEXTRACT_FEATURES = ['LAYOUT', 'TABLES', 'FORMS', 'SIGNATURES'] as const

const FALLBACK_OCR_MODES: OcrMode[] = ['textract', 'mistral', 'mistral_vertex', 'llm', 'pymupdf']

const OCR_MODE_LABELS: Record<OcrMode, string> = {
  textract: 'AWS Textract',
  mistral: 'Mistral OCR',
  mistral_vertex: 'Mistral OCR (Vertex AI)',
  llm: 'LLM OCR',
  pymupdf: 'PyMuPDF (embedded text)',
}

function isOcrMode(s: string): s is OcrMode {
  return s === 'textract' || s === 'mistral' || s === 'mistral_vertex' || s === 'llm' || s === 'pymupdf'
}

function normalizeOcrConfig(raw: OrgOcrConfig): OrgOcrConfig {
  return {
    mode: raw.mode ?? 'textract',
    textract: {
      feature_types:
        raw.textract?.feature_types !== undefined && Array.isArray(raw.textract.feature_types)
          ? [...raw.textract.feature_types]
          : [],
    },
    mistral: raw.mistral ?? {},
    mistral_vertex: raw.mistral_vertex ?? {},
    pymupdf: raw.pymupdf ?? {},
    llm: {
      provider: raw.llm?.provider ?? null,
      model: raw.llm?.model ?? null,
    },
  }
}

const cloneOcrConfig = (c: OrgOcrConfig): OrgOcrConfig =>
  normalizeOcrConfig(JSON.parse(JSON.stringify(c)) as OrgOcrConfig)

type OrgMemberRow = {
  id: string
  name: string
  email: string
  permissionGroupIds: string[]
  primaryPermissionGroupId: string
}

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
  const [experimentalFeatures, setExperimentalFeatures] = useState<boolean>(false)
  const [flowLogLevel, setFlowLogLevel] = useState<FlowLogLevel>('ERROR')
  const [allUsers, setAllUsers] = useState<User[]>([])
  const [memberSearch, setMemberSearch] = useState('');
  const [originalName, setOriginalName] = useState('')
  const [originalType, setOriginalType] = useState<OrganizationType>('individual')
  const [originalMembers, setOriginalMembers] = useState<OrganizationMember[]>([])
  const [originalDefaultPromptEnabled, setOriginalDefaultPromptEnabled] = useState<boolean>(true)
  const [originalExperimentalFeatures, setOriginalExperimentalFeatures] = useState<boolean>(false)
  const [originalFlowLogLevel, setOriginalFlowLogLevel] = useState<FlowLogLevel>('ERROR')
  const [ocrConfig, setOcrConfig] = useState<OrgOcrConfig | null>(null)
  const [originalOcrConfig, setOriginalOcrConfig] = useState<OrgOcrConfig | null>(null)
  const { session } = useAppSession();
  const [showAddUserModal, setShowAddUserModal] = useState(false);
  const [memberPagination, setMemberPagination] = useState<PaginationModel>({ page: 0, pageSize: 5 });
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), []);

  const [ocrLlmChatModels, setOcrLlmChatModels] = useState<LLMChatModel[]>([])
  const [ocrLlmCatalogLoading, setOcrLlmCatalogLoading] = useState(true)
  const [ocrLlmCatalogError, setOcrLlmCatalogError] = useState<string | null>(null)

  const mistralEnabled = organization?.ocr_catalog?.mistral_enabled !== false
  const mistralVertexEnabled = organization?.ocr_catalog?.mistral_vertex_enabled === true

  // Filter members for the grid (include unsaved adds not yet returned by listUsers)
  const filteredMembers = members.filter(member => {
    const q = memberSearch.trim().toLowerCase();
    if (!q) {
      return true;
    }
    const user = allUsers.find(u => u.id === member.user_id);
    if (!user) {
      return true;
    }
    return (
      user.name?.toLowerCase().includes(q) ||
      user.email.toLowerCase().includes(q)
    );
  });

  // Update local state when organization data changes
  useEffect(() => {
    if (organization) {
      setName(organization.name);
      setType(organization.type);
      setMembers(organization.members.map((m) => normalizeOrgMember(m)));
      setDefaultPromptEnabled(
        organization.default_prompt_enabled !== undefined
          ? organization.default_prompt_enabled
          : true
      );
      setExperimentalFeatures(organization.experimental_features === true);
      setFlowLogLevel(organization.flow_log_level ?? 'ERROR');
      // Store original values
      setOriginalName(organization.name);
      setOriginalType(organization.type);
      setOriginalMembers(organization.members.map((m) => normalizeOrgMember(m)));
      setOriginalDefaultPromptEnabled(
        organization.default_prompt_enabled !== undefined
          ? organization.default_prompt_enabled
          : true
      );
      setOriginalExperimentalFeatures(organization.experimental_features === true);
      setOriginalFlowLogLevel(organization.flow_log_level ?? 'ERROR');

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
          ocrOnly: true,
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
      if (ocrConfig.mode === 'mistral_vertex' && !mistralVertexEnabled) {
        toast.error(
          'Mistral Vertex OCR is not available: configure GCP credentials in account settings, then try again.'
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
        experimental_features: experimentalFeatures,
        flow_log_level: flowLogLevel,
        ...(ocrConfig ? { ocr_config: ocrConfig as unknown as Record<string, unknown> } : {}),
      });
      await refreshData();
      
      // Update original values after successful save
      setOriginalName(name);
      setOriginalType(type);
      setOriginalMembers(members);
      setOriginalDefaultPromptEnabled(defaultPromptEnabled);
      setOriginalExperimentalFeatures(experimentalFeatures);
      setOriginalFlowLogLevel(flowLogLevel);
      if (ocrConfig) {
        setOriginalOcrConfig(cloneOcrConfig(ocrConfig))
      }
    } catch (err) {
      toastActionError('Failed to update organization', err);
    }
  };

  const handleTogglePermissionGroup = (userId: string, groupId: BuiltinPermissionGroupId) => {
    setMembers((prevMembers) => {
      const member = prevMembers.find((m) => m.user_id === userId);
      if (!member) {
        return prevMembers;
      }

      const current = sortPermissionGroupIds(member.permission_group_ids);
      const hasGroup = current.includes(groupId);
      let nextIds: string[];

      if (hasGroup) {
        if (current.length === 1) {
          toast.error('Each member must belong to at least one group');
          return prevMembers;
        }
        nextIds = current.filter((id) => id !== groupId);
      } else {
        nextIds = sortPermissionGroupIds([...current, groupId]);
      }

      const updatedMembers = prevMembers.map((m) =>
        m.user_id === userId ? { user_id: m.user_id, permission_group_ids: nextIds } : m
      );

      if (!validateAdminPresence(updatedMembers)) {
        toast.error('Organization must have at least one Admin member');
        return prevMembers;
      }

      return updatedMembers;
    });
  };

  const handleAddMember = async (userId: string, user?: User): Promise<void> => {
    // Prevent adding members to individual organizations
    if (type === 'individual') {
      toast.error('Individual organizations cannot have multiple members');
      return;
    }

    if (members.some(member => member.user_id === userId)) {
      return;
    }

    setMembers((prev) => [
      ...prev,
      { user_id: userId, permission_group_ids: [BUILTIN_OPERATOR] },
    ]);

    if (user) {
      setAllUsers(prev =>
        prev.some(u => u.id === userId) ? prev : [...prev, user]
      );
      return;
    }

    try {
      const usersResponse = await docRouterAccountApi.listUsers({ user_id: userId });
      const fetched = usersResponse.users[0];
      if (fetched) {
        setAllUsers(prev =>
          prev.some(u => u.id === userId) ? prev : [...prev, fetched]
        );
      }
    } catch (error) {
      console.error('Failed to load user details for new member:', error);
    }
  };

  const handleRemoveMember = (userId: string) => {
    const memberToRemove = members.find(member => member.user_id === userId);
    if (memberToRemove && memberHasAdminGroup(memberToRemove.permission_group_ids)) {
      const remainingAdmins = members.filter(
        (m) => m.user_id !== userId && memberHasAdminGroup(m.permission_group_ids)
      );
      if (remainingAdmins.length === 0) {
        toast.error('Cannot remove the last Admin. Assign another member to Admin first.');
        return;
      }
    }
    
    setMembers(prev => prev.filter(member => member.user_id !== userId));
  };

  const memberRows = useMemo((): OrgMemberRow[] => {
    return filteredMembers.map((member) => {
      const user = allUsers.find((u) => u.id === member.user_id)
      const permissionGroupIds = sortPermissionGroupIds(member.permission_group_ids)
      return {
        id: member.user_id,
        name: user?.name || 'Unknown User',
        email: user?.email || '',
        permissionGroupIds,
        primaryPermissionGroupId: primaryPermissionGroupId(permissionGroupIds) ?? BUILTIN_OPERATOR,
      }
    })
  }, [filteredMembers, allUsers])

  const memberColumns: DataTableColumn<OrgMemberRow>[] = useMemo(
    () => [
      {
        field: 'name',
        headerName: 'User',
        flex: 1,
        minWidth: 300,
        renderCell: ({ row }) => (
          <button
            type="button"
            onClick={() => router.push(`/settings/account/users/${row.id}`)}
            className="text-left hover:text-primary-600 focus:outline-none"
          >
            <span className="font-medium">{row.name}</span>
            <span className="ml-2 text-gray-500">({row.email})</span>
          </button>
        ),
      },
      {
        field: 'permissionGroupIds',
        headerName: 'Groups',
        flex: 0.6,
        minWidth: 200,
        sortable: false,
        renderCell: ({ row }) => {
          const ids = row.permissionGroupIds
          const primaryId = row.primaryPermissionGroupId
          const stacked = ids.length > 1
          return (
            <div
              className={`flex h-full w-full gap-1 ${
                stacked ? 'flex-wrap content-center items-center py-0.5' : 'items-center'
              }`}
            >
              {ids.map((id) => (
                <span
                  key={id}
                  className={`inline-flex shrink-0 items-center rounded px-2 py-1 text-sm leading-none shadow-sm ${
                    id === primaryId
                      ? 'bg-primary-100 font-medium text-primary-800'
                      : 'bg-gray-100 text-gray-700'
                  }`}
                >
                  {permissionGroupLabel(id)}
                </span>
              ))}
            </div>
          )
        },
      },
      {
        field: 'actions',
        headerName: '',
        width: 52,
        sortable: false,
        hideable: false,
        resizable: false,
        renderCell: ({ row }) => (
          <DropdownMenu>
            <DropdownMenuTrigger
              render={
                <Button variant="ghost" size="icon-sm" className="-ml-2" aria-label={`Actions for ${row.email}`} />
              }
            >
              <MoreVertical />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="max-w-xs">
              {BUILTIN_PERMISSION_GROUPS.map((group) => (
                <DropdownMenuCheckboxItem
                  key={group.id}
                  checked={row.permissionGroupIds.includes(group.id)}
                  onCheckedChange={() => handleTogglePermissionGroup(row.id, group.id)}
                >
                  {group.label}
                </DropdownMenuCheckboxItem>
              ))}
              <DropdownMenuSeparator />
              <DropdownMenuItem
                variant="destructive"
                onClick={() => handleRemoveMember(row.id)}
              >
                <Trash2 />
                Remove
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        ),
      },
    ],
    [router],
  )

  const textractFeatureOptions =
    organization?.ocr_catalog?.textract_feature_types?.length
      ? organization.ocr_catalog.textract_feature_types
      : [...FALLBACK_TEXTRACT_FEATURES]

  const ocrModeOptions = useMemo((): OcrMode[] => {
    const fromCatalog = organization?.ocr_catalog?.modes?.filter(isOcrMode) ?? []
    const base = fromCatalog.length > 0 ? fromCatalog : [...FALLBACK_OCR_MODES]
    const mode = ocrConfig?.mode
    if (mode != null && !base.includes(mode)) {
      return [...base, mode]
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
    if (experimentalFeatures !== originalExperimentalFeatures) return true;
    if (flowLogLevel !== originalFlowLogLevel) return true;
    if (ocrConfig && originalOcrConfig && JSON.stringify(ocrConfig) !== JSON.stringify(originalOcrConfig)) {
      return true;
    }

    // Compare each member and their roles
    const memberChanges = members.some(member => {
      const originalMember = originalMembers.find(m => m.user_id === member.user_id);
      const norm = normalizeOrgMember(member);
      const orig = originalMember ? normalizeOrgMember(originalMember) : null;
      return !orig || orig.permission_group_ids.join() !== norm.permission_group_ids.join();
    });

    return memberChanges;
  };

  const validateAdminPresence = (updatedMembers: OrganizationMember[]): boolean => {
    return updatedMembers.some((member) => memberHasAdminGroup(member.permission_group_ids));
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
          <h2 className="text-lg font-semibold text-gray-900">Edit Organization</h2>
          <div className="flex gap-4">
            {/* Subscription Link - Only show for org admins and sys admins */}
            {(() => {
              const isUserOrgAdmin = organization ? isOrgAdmin(organization, session) : false;
              const isUserSysAdmin = isSysAdmin(session);
              return (isUserOrgAdmin || isUserSysAdmin) ? (
                <>
                  <Link
                    to={`/settings/organizations/${organizationId}/subscription`}
                    className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
                  >
                    <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
                    </svg>
                    Billing
                  </Link>
                </>
              ) : null;
            })()}
            <button
              type="submit"
              form="organization-form"
              disabled={!hasChanges()}
              className={`px-4 py-2 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2
                ${hasChanges() 
                  ? 'bg-primary-600 text-white hover:bg-primary-700' 
                  : 'bg-gray-100 text-gray-400 cursor-not-allowed'}`}
            >
              Save Changes
            </button>
            <button
              type="button"
              onClick={() => router.push('/settings/organizations')}
              className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2"
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
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 bg-white"
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
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 bg-white disabled:bg-gray-100 disabled:cursor-not-allowed"
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

              <div className="flex items-start gap-2">
                <Checkbox
                  id="default-prompt-enabled"
                  className="mt-0.5"
                  checked={defaultPromptEnabled}
                  onCheckedChange={(checked) => setDefaultPromptEnabled(checked === true)}
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

              <div className="flex items-start gap-2">
                <Checkbox
                  id="experimental-features-enabled"
                  className="mt-0.5"
                  checked={experimentalFeatures}
                  onCheckedChange={(checked) => setExperimentalFeatures(checked === true)}
                />
                <div>
                  <label htmlFor="experimental-features-enabled" className="block text-sm font-medium text-gray-700">
                    Show experimental features
                  </label>
                  <p className="text-sm text-gray-500">
                    Experimental features are still under development.
                  </p>
                </div>
              </div>

              <div>
                <label htmlFor="flow-log-level" className="block text-sm font-medium text-gray-700">
                  Flow execution log level
                </label>
                <p className="mt-1 text-sm text-gray-500">
                  Controls detail stored in flow run traces (Logs panel → Trace tab). ERROR records failures
                  only; INFO adds successful HTTP summaries; TRACE adds full HTTP response previews.
                </p>
                <select
                  id="flow-log-level"
                  value={flowLogLevel}
                  onChange={(e) => setFlowLogLevel(e.target.value as FlowLogLevel)}
                  className="mt-2 block w-full max-w-md rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                >
                  <option value="ERROR">ERROR</option>
                  <option value="INFO">INFO</option>
                  <option value="TRACE">TRACE</option>
                </select>
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
                  className="w-full max-w-md px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 bg-white"
                >
                  {ocrModeOptions.map((m) => {
                    const unavailable =
                      (m === 'mistral' && !mistralEnabled) ||
                      (m === 'mistral_vertex' && !mistralVertexEnabled)
                    return (
                      <option key={m} value={m} disabled={unavailable}>
                        {unavailable ? `${OCR_MODE_LABELS[m]} (unavailable)` : OCR_MODE_LABELS[m]}
                      </option>
                    )
                  })}
                </select>
              </div>

              {!mistralEnabled && ocrConfig.mode === 'mistral' && (
                <Alert className="mb-2 border-amber-500/40 bg-amber-50 text-foreground">
                  <TriangleAlert className="text-amber-600" />
                  <AlertDescription>
                    Mistral OCR is unavailable because the Mistral provider is off or no models are enabled
                    in account LLM settings. Select another engine before you can save.
                  </AlertDescription>
                </Alert>
              )}

              {!mistralVertexEnabled && ocrConfig.mode === 'mistral_vertex' && (
                <Alert className="mb-2 border-amber-500/40 bg-amber-50 text-foreground">
                  <TriangleAlert className="text-amber-600" />
                  <AlertDescription>
                    Mistral Vertex OCR is unavailable because GCP credentials are not configured in account
                    settings. Select another engine before you can save.
                  </AlertDescription>
                </Alert>
              )}

              {ocrConfig.mode === 'textract' && (
                <Alert variant="info" className="mb-2">
                  <Info />
                  <AlertDescription>Uses AWS Textract AnalyzeDocument. Choose feature types below.</AlertDescription>
                </Alert>
              )}
              {ocrConfig.mode === 'mistral' && mistralEnabled && (
                <Alert variant="info" className="mb-2">
                  <Info />
                  <AlertDescription>
                    Uses Mistral OCR (<code className="text-sm">mistral-ocr-latest</code>). The API key is
                    read from the Mistral LLM provider in account settings when a document is processed.
                  </AlertDescription>
                </Alert>
              )}
              {ocrConfig.mode === 'mistral_vertex' && mistralVertexEnabled && (
                <Alert variant="info" className="mb-2">
                  <Info />
                  <AlertDescription>
                    Uses Mistral OCR (<code className="text-sm">mistral-ocr-2505</code>) via Google Cloud
                    Vertex AI (region: <code className="text-sm">us-central1</code>). Credentials are read
                    from the GCP service account configured in account settings.
                  </AlertDescription>
                </Alert>
              )}
              {ocrConfig.mode === 'pymupdf' && (
                <Alert variant="info" className="mb-2">
                  <Info />
                  <AlertDescription>
                    Extracts embedded text from PDFs locally (PyMuPDF). Scanned or image-only PDFs need AWS
                    Textract, Mistral OCR, or LLM OCR. This mode uses 0 SPU.
                  </AlertDescription>
                </Alert>
              )}
              {ocrConfig.mode === 'llm' && (
                <>
                  {ocrLlmCatalogError && (
                    <Alert variant="destructive" className="mb-2">
                      <AlertDescription>{ocrLlmCatalogError}</AlertDescription>
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
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 bg-white"
                        >
                          <option value="">Select a provider</option>
                          {ocrLlmProviderOptionsWithLegacy.map((row) => (
                            <option key={row.name} value={row.name}>
                              {row.display}
                            </option>
                          ))}
                        </select>
                        <p className="text-xs text-gray-500 mt-1">
                          Enabled accounts that expose at least one OCR-capable model (account LLM settings).
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
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 bg-white disabled:bg-gray-100 disabled:text-gray-500"
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
                          OCR-approved models only (configured per provider). Prefer vision/PDF-capable
                          models for best results.
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
                    <p className="text-xs text-gray-500 mb-2">
                      Feature types (AnalyzeDocument). If none are selected, Textract uses text detection only
                      (plain text/lines).
                    </p>
                    <div className="flex flex-wrap gap-3">
                      {textractFeatureOptions.map((ft) => (
                        <label key={ft} className="inline-flex items-center gap-2 text-sm text-gray-700">
                          <Checkbox
                            checked={ocrConfig.textract.feature_types.includes(ft)}
                            onCheckedChange={() => toggleTextractFeature(ft)}
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
              
              <Button
                type="button"
                onClick={() => setShowAddUserModal(true)}
                disabled={type === 'individual'}
              >
                Add user
              </Button>
            </div>

            <SearchInput
              className="mb-4 w-full"
              placeholder="Search members…"
              value={memberSearch}
              onChange={setMemberSearch}
            />

            <div className="flex-1 rounded-lg bg-white">
              <DataTable
                rows={memberRows}
                columns={memberColumns}
                paginationModel={memberPagination}
                onPaginationModelChange={setMemberPagination}
                pageSizeOptions={[5, 10, 20]}
                disableColumnMenu
                autoRowHeight
              />
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