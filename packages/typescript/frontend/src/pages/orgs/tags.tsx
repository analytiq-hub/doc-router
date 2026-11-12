'use client'

import { Plus } from 'lucide-react'
import { useCallback, useRef } from 'react'

import TagList from '@/components/TagList'
import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { useRouteParams } from '@/utils/useRouteParams'
import { useOrgCapability } from '@/hooks/useOrgPermissions'
import { CAP_CONFIG_WRITE } from '@/utils/orgCapabilities'

export default function TagsPage(props: { params: Promise<{ organizationId: string }> }) {
  const { organizationId } = useRouteParams(props)
  const { hasCapability: canConfigWrite } = useOrgCapability(organizationId, CAP_CONFIG_WRITE)
  const newTagRef = useRef<(() => void) | null>(null)
  const registerNewTag = useCallback((open: () => void) => {
    newTagRef.current = open
  }, [])

  return (
    <div className="mx-auto max-w-6xl p-4">
      <PageHeader
        title="Tags"
        subtitle="Tags determine which prompts run on which documents."
        actions={
          canConfigWrite ? (
            <Button onClick={() => newTagRef.current?.()} data-tour="tag-create">
              <Plus data-icon="inline-start" />
              New tag
            </Button>
          ) : null
        }
      />
      <TagList organizationId={organizationId} registerNewTag={registerNewTag} />
    </div>
  )
}
