"use client";

import { useState, ReactNode, useEffect, useLayoutEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useRouter, usePathname } from '@/utils/appRouter';
import { useAppSession } from '@/contexts/AppSessionContext';
import AuthButton from '@/components/AuthButton';
import UserMenu from '@/components/UserMenu';
import PDFViewerControls from '@/components/PDFViewerControls';
import OrganizationSwitcher from './OrganizationSwitcher';
import { useOrganization } from '@/contexts/OrganizationContext';
import {
  Menu,
  LayoutDashboard,
  FileText,
  FolderOpen,
  Tag,
  Braces,
  MessageSquareText,
  ClipboardList,
  GitBranch,
  Library,
  Settings,
  type LucideIcon,
} from 'lucide-react';
import TourGuide from '@/components/TourGuide';
import LicenseBanner from '@/components/LicenseBanner';
import { appName } from '@/config/branding';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

import type { DocSidebarTab } from '@/utils/docPageUrl';

export interface PDFViewerControlsType {
  showRightPanel: boolean;
  setShowRightPanel: React.Dispatch<React.SetStateAction<boolean>>;
  showPdfPanel: boolean;
  setShowPdfPanel: React.Dispatch<React.SetStateAction<boolean>>;
  isSmallScreen?: boolean;
  rightPanelTab?: DocSidebarTab;
}

declare global {
  interface Window {
    pdfViewerControls?: PDFViewerControlsType;
  }
}

interface MenuItem {
  text: string;
  icon: LucideIcon;
  href: string;
  tooltip: string;
}

interface LayoutProps {
  children: ReactNode;
}

function NavLinkItem({
  item,
  open,
  active,
  disabled,
}: {
  item: MenuItem;
  open: boolean;
  active: boolean;
  disabled?: boolean;
}) {
  const Icon = item.icon;
  const link = (
    <Link
      to={item.href}
      aria-current={active ? 'page' : undefined}
      aria-disabled={disabled || undefined}
      className={cn(
        'flex h-10 w-full items-center gap-3.5 rounded-md px-3 text-sm font-medium outline-none transition-colors hover:bg-accent focus-visible:ring-3 focus-visible:ring-ring',
        active && 'bg-primary-soft text-primary',
        !active && !disabled && 'text-foreground',
        disabled && 'pointer-events-none cursor-not-allowed opacity-60',
      )}
      onClick={disabled ? (e) => e.preventDefault() : undefined}
    >
      <Icon className="size-5 shrink-0" aria-hidden />
      <span className={cn('truncate', !open && 'sr-only')}>{item.text}</span>
    </Link>
  );

  if (open) {
    return link;
  }

  return (
    <Tooltip>
      <TooltipTrigger render={link} />
      <TooltipContent side="right">{disabled ? 'Select an organization' : item.tooltip}</TooltipContent>
    </Tooltip>
  );
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const { currentOrganization } = useOrganization();

  const [open, setOpen] = useState(true);

  const { session, status } = useAppSession();
  const router = useRouter();
  const pathname = usePathname();
  const isPDFViewer = pathname.includes('/docs/');
  const [forceUpdate, setForceUpdate] = useState(0);
  const [pdfControls, setPdfControls] = useState<PDFViewerControlsType | null>(null);

  const orgIdForLinks =
    (pathname.match(/^\/orgs\/([^/]+)/)?.[1] as string | undefined) ?? currentOrganization?.id ?? null;

  useLayoutEffect(() => {
    const savedSidebarState = localStorage.getItem('sidebarOpen');
    if (savedSidebarState !== null) {
      setOpen(JSON.parse(savedSidebarState) as boolean);
    }
  }, []);

  const toggleSidebar = useCallback(() => {
    setOpen((prev) => {
      const next = !prev;
      localStorage.setItem('sidebarOpen', JSON.stringify(next));
      return next;
    });
  }, []);

  const fileMenuItems: MenuItem[] = orgIdForLinks
    ? [
        { text: 'Dashboard', icon: LayoutDashboard, tooltip: 'Dashboard', href: `/orgs/${orgIdForLinks}/dashboard` },
        { text: 'Documents', icon: FileText, tooltip: 'Documents', href: `/orgs/${orgIdForLinks}/docs` },
        { text: 'Cases', icon: FolderOpen, tooltip: 'Cases', href: `/orgs/${orgIdForLinks}/cases` },
        { text: 'Tags', icon: Tag, tooltip: 'Tags', href: `/orgs/${orgIdForLinks}/tags` },
        { text: 'Schemas', icon: Braces, tooltip: 'Schemas', href: `/orgs/${orgIdForLinks}/schemas` },
        { text: 'Prompts', icon: MessageSquareText, tooltip: 'Prompts', href: `/orgs/${orgIdForLinks}/prompts` },
        { text: 'Forms', icon: ClipboardList, tooltip: 'Forms', href: `/orgs/${orgIdForLinks}/forms` },
        { text: 'Flows', icon: GitBranch, tooltip: 'Flows', href: `/orgs/${orgIdForLinks}/flows` },
        { text: 'Knowledge Bases', icon: Library, tooltip: 'Knowledge Bases', href: `/orgs/${orgIdForLinks}/knowledge-bases` },
      ]
    : [
        { text: 'Dashboard', icon: LayoutDashboard, tooltip: 'Dashboard', href: '#' },
        { text: 'Documents', icon: FileText, tooltip: 'Documents', href: '#' },
        { text: 'Cases', icon: FolderOpen, tooltip: 'Cases', href: '#' },
        { text: 'Tags', icon: Tag, tooltip: 'Tags', href: '#' },
        { text: 'Schemas', icon: Braces, tooltip: 'Schemas', href: '#' },
        { text: 'Prompts', icon: MessageSquareText, tooltip: 'Prompts', href: '#' },
        { text: 'Forms', icon: ClipboardList, tooltip: 'Forms', href: '#' },
        { text: 'Flows', icon: GitBranch, tooltip: 'Flows', href: '#' },
        { text: 'Knowledge Bases', icon: Library, tooltip: 'Knowledge Bases', href: '#' },
      ];

  const systemMenuItems: MenuItem[] = [
    { text: 'Settings', icon: Settings, tooltip: 'Settings', href: '/settings' },
  ];

  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth <= 640) {
        const savedState = localStorage.getItem('sidebarOpen');
        if (savedState === null) {
          setOpen(false);
        }
      }
    };

    window.addEventListener('resize', handleResize);
    const timer = setTimeout(handleResize, 0);
    return () => {
      clearTimeout(timer);
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  useEffect(() => {
    const handleControlsChange = () => {
      setForceUpdate((prev) => prev + 1);
    };

    window.addEventListener('pdfviewercontrols', handleControlsChange);
    return () => window.removeEventListener('pdfviewercontrols', handleControlsChange);
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      setPdfControls(window.pdfViewerControls || null);
    }, 0);
    return () => clearTimeout(timer);
  }, [forceUpdate]);

  useEffect(() => {
    if (
      status === 'unauthenticated' &&
      pathname !== '/' &&
      !pathname.startsWith('/auth/') &&
      !pathname.startsWith('/dashboard')
    ) {
      router.push('/auth/signin');
    }
  }, [status, router, pathname]);

  const renderMenuItem = (item: MenuItem) => {
    const isPlaceholder = item.href === '#';
    const isSelected = !isPlaceholder && (pathname === item.href || pathname.startsWith(`${item.href}/`));

    return (
      <NavLinkItem
        key={item.text}
        item={item}
        open={open}
        active={isSelected}
        disabled={isPlaceholder}
      />
    );
  };

  return (
    <div className="flex h-screen flex-col">
      {/*
        Shell alignment (matches doc-orchestrator Layout):
        - Burger center and nav icons: 30px from the left (header pl-3 + half of 36px button;
          nav p-2 + link px-3 + half of 20px icon).
        - App title and nav labels start at 54px when the drawer is open.
        - With the drawer closed, title shifts ml-7.5 (30px) so it lines up with main content
          (collapsed nav w-15 + typical page inset).
      */}
      <header className="flex h-14 shrink-0 items-center gap-3 border-b-2 border-primary bg-brand pr-4 pl-3 text-brand-foreground">
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="-mr-1.5 size-9 text-brand-foreground hover:bg-brand-foreground/10 hover:text-brand-foreground"
          onClick={toggleSidebar}
          aria-label="Toggle navigation"
        >
          <Menu />
        </Button>
        <Link
          to={session && orgIdForLinks ? `/orgs/${orgIdForLinks}/dashboard` : session ? '/dashboard' : '/'}
          className={cn(
            'flex min-w-0 flex-1 items-center text-lg font-semibold transition-[margin]',
            !open && 'ml-7.5',
          )}
        >
          <span className="truncate">{appName}</span>
        </Link>

        <div className="flex shrink-0 items-center gap-2">
          {session ? <OrganizationSwitcher /> : null}
          {isPDFViewer && pdfControls ? <PDFViewerControls key={forceUpdate} {...pdfControls} /> : null}
          {session ? <UserMenu user={session?.user} /> : <AuthButton />}
        </div>
      </header>

      {status === 'authenticated' ? <LicenseBanner /> : null}

      <div className="flex min-h-0 flex-1 overflow-hidden">
        <nav
          aria-label="Main"
          className={cn(
            'flex h-full shrink-0 flex-col justify-between gap-1 border-r border-border bg-card p-2 transition-[width] duration-300 ease-in-out',
            open ? 'w-56 overflow-hidden' : 'w-15 overflow-visible',
          )}
        >
            {status === 'authenticated' ? (
              <div className="flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto">
                {fileMenuItems.map(renderMenuItem)}
              </div>
            ) : (
              <div />
            )}
            <div>{systemMenuItems.map(renderMenuItem)}</div>
        </nav>

        <main className="min-w-0 flex-1 overflow-auto bg-background">{children}</main>
      </div>

      {status === 'authenticated' ? (
        <TourGuide key={`tour-${session?.user?.email}`} />
      ) : null}
    </div>
  );
};

export default Layout;
