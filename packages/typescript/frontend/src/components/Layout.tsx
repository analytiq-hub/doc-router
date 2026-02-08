"use client";

import { useState, ReactNode, useEffect } from 'react';
import Link from 'next/link';
import { useRouter, usePathname } from 'next/navigation';
import { useAppSession } from '@/contexts/AppSessionContext';
import AuthButton from '@/components/AuthButton';
import UserMenu from '@/components/UserMenu';
import PDFViewerControls from '@/components/PDFViewerControls';
import OrganizationSwitcher from './OrganizationSwitcher';
import { useOrganization } from '@/contexts/OrganizationContext';
import { 
  Menu as Bars3Icon,
  //PieChart as ChartPieIcon,
  //FileUpload as ArrowUpTrayIcon,
  FormatListBulleted as ListBulletIcon,
  // Apps as CubeIcon,
  // ViewQuilt as Square3Stack3DIcon,
  //Science as BeakerIcon,
  LocalOffer as LocalOfferIcon,
  DataObject as SchemaIcon,
  Chat as PromptIcon,
  ViewQuilt as FormsIcon,
  Psychology as PsychologyIcon,
  InfoOutlined as AboutIcon
} from '@mui/icons-material';
import { SvgIconProps } from '@mui/material';
import TourGuide from '@/components/TourGuide';

// First, let's fix the type errors
interface PDFViewerControlsType {
  showLeftPanel: boolean;
  setShowLeftPanel: React.Dispatch<React.SetStateAction<boolean>>;
  showPdfPanel: boolean;
  setShowPdfPanel: React.Dispatch<React.SetStateAction<boolean>>;
}

declare global {
  interface Window {
    pdfViewerControls?: PDFViewerControlsType;
  }
}

// Update the icon type
interface MenuItem {
  text: string;
  icon: React.ComponentType<SvgIconProps>;
  href: string;
  tooltip: string;
  dataTour?: string;
}

interface LayoutProps {
  children: ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const { currentOrganization } = useOrganization();
  
  // Initialize with a default value that works for both server and client
  const [open, setOpen] = useState(true);
  const [isClient, setIsClient] = useState(false);
  
  const { session, status } = useAppSession();
  const router = useRouter();
  const pathname = usePathname();
  const isPDFViewer = pathname.includes('/docs/');
  const [forceUpdate, setForceUpdate] = useState(0);
  const [pdfControls, setPdfControls] = useState<PDFViewerControlsType | null>(null);

  // Load sidebar state from localStorage after component mounts (client-side only)
  useEffect(() => {
    setIsClient(true);
    const savedSidebarState = localStorage.getItem('sidebarOpen');
    if (savedSidebarState !== null) {
      setOpen(JSON.parse(savedSidebarState));
    }
  }, []);

  // Save sidebar state to localStorage whenever it changes (client-side only)
  useEffect(() => {
    if (isClient) {
      localStorage.setItem('sidebarOpen', JSON.stringify(open));
    }
  }, [open, isClient]);

  const fileMenuItems = [
    { text: 'Documents', icon: ListBulletIcon, tooltip: 'Documents', href: `/orgs/${currentOrganization?.id}/docs`},
    { text: 'Tags', icon: LocalOfferIcon, tooltip: 'Tags', href: `/orgs/${currentOrganization?.id}/tags`},  
    { text: 'Schemas', icon: SchemaIcon, tooltip: 'Schemas', href: `/orgs/${currentOrganization?.id}/schemas`},
    { text: 'Prompts', icon: PromptIcon, tooltip: 'Prompts', href: `/orgs/${currentOrganization?.id}/prompts`},
    { text: 'Forms', icon: FormsIcon, tooltip: 'Forms', href: `/orgs/${currentOrganization?.id}/forms`},
    { text: 'Knowledge Bases', icon: PsychologyIcon, tooltip: 'Knowledge Bases', href: `/orgs/${currentOrganization?.id}/knowledge-bases`},
  ];

  const systemMenuItems = [
    { text: 'About', icon: AboutIcon, tooltip: 'About Page', href: '/' },
  ];

  useEffect(() => {
    const handleResize = () => {
      // Only auto-close on small screens if no saved state exists
      if (window.innerWidth <= 640) {
        const savedState = localStorage.getItem('sidebarOpen');
        if (savedState === null) {
          setOpen(false);
        }
      }
    };
    
    window.addEventListener('resize', handleResize);
    handleResize();
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Keep the existing PDF controls effects
  useEffect(() => {
    const handleControlsChange = () => {
      setForceUpdate(prev => prev + 1);
    };
    
    window.addEventListener('pdfviewercontrols', handleControlsChange);
    return () => window.removeEventListener('pdfviewercontrols', handleControlsChange);
  }, []);

  useEffect(() => {
    setPdfControls(window.pdfViewerControls || null);
  }, [forceUpdate]);

  useEffect(() => {
    if (status === 'unauthenticated' && 
        pathname !== '/' &&
        !pathname.startsWith('/auth/') &&
        !pathname.startsWith('/dashboard')) {
      router.push('/auth/signin');
    }
  }, [status, router, pathname]);

  // Update the renderMenuItem function to match burger icon size and alignment
  const renderMenuItem = (item: MenuItem) => {
    const Icon = item.icon;
    const isSelected = pathname === item.href || pathname.startsWith(item.href + '/');
    
    return (
      <Link
        key={item.text}
        href={item.href}
        className="block px-2 py-1"
        title={!open ? item.tooltip : ''}
      >
        <div
          className={`
            flex items-center
            h-10 w-full
            rounded-md
            ${isSelected ? 'bg-blue-100' : 'hover:bg-blue-100'}
            transition-colors duration-200
            px-3
          `}
        >
          <div className={`
            flex items-center justify-center
            ${open ? 'w-6' : 'w-full'}
          `}>
            <Icon className="h-6 w-6 shrink-0" />
          </div>
          {open && (
            <span className={`ml-3 pr-3 pt-1 text-sm font-medium whitespace-nowrap ${isSelected ? 'text-blue-600' : 'text-gray-700'}`}>
              {item.text}
            </span>
          )}
        </div>
      </Link>
    );
  };

  return (
    <div className="flex h-screen flex-col">
      {/* Header */}
      <header className="bg-blue-600 border-b border-blue-700">
        <div className="flex h-16 items-center justify-between px-3">
          <div className="flex items-center">
            <button
              onClick={() => setOpen(!open)}
              className="p-2 rounded-md hover:bg-blue-500"
            >
              <Bars3Icon className="h-6 w-6 text-white" />
            </button>
            <Link href={session && currentOrganization?.id ? `/orgs/${currentOrganization.id}/dashboard` : session ? '/dashboard' : '/'} className={`${open ? 'ml-3' : 'ml-6'} text-xl font-semibold text-white`}>
              <span className="block sm:hidden">DocRouter.AI</span>
              <span className="hidden sm:block">Smart Document Router</span>
            </Link>
          </div>

          <div className="flex-1 flex justify-end">
            {session && <OrganizationSwitcher />}
          </div>

          <div className="flex items-center space-x-4">
            {isPDFViewer && pdfControls && (
              <PDFViewerControls key={forceUpdate} {...pdfControls} />
            )}
            {session ? (
              <UserMenu user={session?.user} />
            ) : (
              <AuthButton />
            )}
          </div>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside 
          className={`
            flex-shrink-0 
            transition-all duration-300 ease-in-out 
            bg-blue-50
            border-r border-gray-200
            ${open ? 'w-48' : 'w-16'}
          `}
        >
          <nav className="flex h-full flex-col overflow-hidden">
            {status === 'authenticated' && (
              <>
                <div className="py-1">
                  {fileMenuItems.map(renderMenuItem)}
                </div>
                {/* <hr className="border-gray-200" />
                <div className="py-1">
                  {modelMenuItems.map(renderMenuItem)}
                </div> */}
              </>
            )}
            <>
              <hr className="border-gray-200" />
              <div className="py-1">
                {systemMenuItems.map(renderMenuItem)}
              </div>
            </>
          </nav>
        </aside>

        {/* Main content */}
        <main className="flex-1 overflow-auto">
          {children}
        </main>
      </div>
      
      {/* Add the TourGuide component with a key to force remount */}
      {status === 'authenticated' && (
        <TourGuide key={`tour-${session?.user?.email}`} />
      )}
    </div>
  );
};

export default Layout;
