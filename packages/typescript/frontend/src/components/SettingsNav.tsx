import {
  ArrowLeft,
  BookOpen,
  BadgeCheck,
  Boxes,
  Building2,
  ChevronDown,
  ChevronRight,
  Cloud,
  CreditCard,
  Gauge,
  Hexagon,
  ListOrdered,
  KeyRound,
  ScanText,
  SlidersHorizontal,
  Sparkles,
  User,
  Users,
  Webhook,
  type LucideIcon,
} from 'lucide-react'
import { Link } from 'react-router-dom'

import { NavLinkItem } from '@/components/NavLinkItem'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { fastApiDocsHref } from '@/utils/api'

interface SettingsLink {
  text: string
  icon: LucideIcon
  to: string
  /** Match the path only, so a shorter address is not also active on a longer one. */
  exact?: boolean
  /** Other paths that count as this page (a sibling screen of the same setting). */
  also?: string[]
  /** Same-origin or absolute URL opened in a new tab (not a settings route). */
  external?: boolean
}

interface SettingsGroup {
  key: string
  heading: string
  /** Shown beside the heading, the organization this section is about. */
  badge?: string
  items: SettingsLink[]
}

/** Work pages the back link can name, keyed by the segment after `/orgs/:id/`. */
const APP_PAGES: Record<string, string> = {
  dashboard: 'Dashboard',
  docs: 'Documents',
  cases: 'Cases',
  tags: 'Tags',
  schemas: 'Schemas',
  prompts: 'Prompts',
  forms: 'Forms',
  flows: 'Flows',
  'knowledge-bases': 'Knowledge Bases',
}

export function backTarget(lastAppPath: string | null, fallbackTo: string): { to: string; label: string } {
  const page = lastAppPath?.match(/^\/orgs\/[^/]+\/([^/?]+)/)?.[1]
  if (lastAppPath && page && APP_PAGES[page]) return { to: lastAppPath, label: `Back to ${APP_PAGES[page]}` }
  return { to: fallbackTo, label: 'Back to the app' }
}

function matches(pathname: string, path: string, exact?: boolean): boolean {
  return exact ? pathname === path : pathname === path || pathname.startsWith(`${path}/`)
}

export function settingsItemActive(pathname: string, item: SettingsLink): boolean {
  if (matches(pathname, item.to, item.exact)) return true
  return (item.also ?? []).some((path) => matches(pathname, path))
}

/** User, Organization, and (for a sysadmin) System. The open page's section is the one to expand. */
export function settingsNavGroups({
  organizationId,
  organizationName,
  isSysadmin,
}: {
  organizationId: string | null
  organizationName: string | null
  isSysadmin: boolean
}): SettingsGroup[] {
  const groups: SettingsGroup[] = [
    {
      key: 'user',
      heading: 'User',
      items: [
        { text: 'Profile', icon: User, to: '/settings/user/profile' },
        {
          text: 'Account tokens',
          icon: KeyRound,
          to: '/settings/user/developer/account-access-tokens',
          also: ['/settings/user/access-tokens'],
        },
        {
          text: 'API documentation',
          icon: BookOpen,
          to: fastApiDocsHref(),
          external: true,
        },
      ],
    },
  ]

  const yourOrganizations: SettingsLink = {
    text: 'Your organizations',
    icon: Building2,
    to: '/settings/organizations',
    exact: true,
  }
  const organizationItems: SettingsLink[] = organizationId
    ? [
        { text: 'General', icon: SlidersHorizontal, to: `/settings/organizations/${organizationId}`, exact: true },
        { text: 'Users', icon: Users, to: `/settings/organizations/${organizationId}/users` },
        { text: 'OCR', icon: ScanText, to: `/settings/organizations/${organizationId}/ocr` },
        { text: 'Subscription', icon: CreditCard, to: `/settings/organizations/${organizationId}/subscription` },
        { text: 'API tokens', icon: KeyRound, to: '/settings/user/developer/organization-access-tokens' },
        { text: 'Webhooks', icon: Webhook, to: '/settings/user/developer/organization-webhooks' },
        yourOrganizations,
      ]
    : [yourOrganizations]
  groups.push({
    key: 'organization',
    heading: 'Organization',
    badge: organizationName ?? undefined,
    items: organizationItems,
  })

  if (isSysadmin) {
    groups.push({
      key: 'system',
      heading: 'System',
      items: [
        { text: 'Users', icon: Users, to: '/settings/account/users' },
        { text: 'License', icon: BadgeCheck, to: '/settings/account/license' },
        { text: 'LLM', icon: Sparkles, to: '/settings/account/development/llm-manager' },
        {
          text: 'AWS',
          icon: Cloud,
          to: '/settings/account/development/aws-config',
          also: ['/settings/account/development/aws-credentials'],
        },
        { text: 'GCP', icon: Boxes, to: '/settings/account/development/gcp-config' },
        { text: 'Azure', icon: Hexagon, to: '/settings/account/development/azure-config' },
        {
          text: 'Queues',
          icon: ListOrdered,
          to: '/settings/account/queues',
          also: ['/settings/account/development/worker-settings'],
        },
        { text: 'Rate limits', icon: Gauge, to: '/settings/account/limits' },
      ],
    })
  }

  return groups
}

/**
 * The left navigation while in Settings: a way back, then sections by whose settings they are.
 * Only the section of the open page is expanded. Closed, every page's icon shows, sections divided by a line.
 */
export function SettingsNav({
  open,
  pathname,
  organizationId,
  organizationName,
  isSysadmin,
  lastAppPath,
  fallbackTo,
}: {
  open: boolean
  pathname: string
  organizationId: string | null
  organizationName: string | null
  isSysadmin: boolean
  lastAppPath: string | null
  fallbackTo: string
}) {
  const back = backTarget(lastAppPath, fallbackTo)
  const groups = settingsNavGroups({ organizationId, organizationName, isSysadmin })

  return (
    <div className="flex min-h-0 flex-col gap-3">
      <NavLinkItem item={{ text: back.label, icon: ArrowLeft, href: back.to, tooltip: back.label }} open={open} active={false} />
      {groups.map((group) => {
        const expanded = group.items.some((item) => settingsItemActive(pathname, item))
        if (!open) {
          return (
            <div key={group.key} className="flex flex-col gap-1">
              <hr className="mx-2 border-border" aria-hidden />
              {group.items.map((item) => (
                <NavLinkItem
                  key={item.to}
                  item={{
                    text: item.text,
                    icon: item.icon,
                    href: item.to,
                    tooltip: item.text,
                    external: item.external,
                  }}
                  open={false}
                  active={settingsItemActive(pathname, item)}
                />
              ))}
            </div>
          )
        }
        const Chevron = expanded ? ChevronDown : ChevronRight
        return (
          <div key={group.key} className="flex flex-col gap-1">
            <Link
              to={group.items[0].to}
              aria-expanded={expanded}
              className={cn(
                'flex h-9 items-center gap-2 rounded-md px-3 text-sm font-semibold outline-none transition-colors hover:bg-accent focus-visible:ring-3 focus-visible:ring-ring',
                expanded ? 'text-foreground' : 'text-muted-foreground',
              )}
            >
              <Chevron className="size-4 shrink-0" aria-hidden />
              {group.heading}
              {group.badge ? (
                <Badge variant="info" className="min-w-0 max-w-32" title={group.badge}>
                  <span className="truncate">{group.badge}</span>
                </Badge>
              ) : null}
            </Link>
            {expanded ? (
              <div className="flex flex-col gap-1 pl-6">
                {group.items.map((item) => (
                  <NavLinkItem
                    key={item.to}
                    item={{
                      text: item.text,
                      icon: item.icon,
                      href: item.to,
                      tooltip: item.text,
                      external: item.external,
                    }}
                    open
                    active={settingsItemActive(pathname, item)}
                  />
                ))}
              </div>
            ) : null}
          </div>
        )
      })}
    </div>
  )
}
