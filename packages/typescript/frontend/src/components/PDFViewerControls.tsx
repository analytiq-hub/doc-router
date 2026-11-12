import { FileText, MessageSquare, PanelLeft } from 'lucide-react';

interface PDFViewerControlsProps {
  showLeftPanel: boolean;
  setShowLeftPanel: React.Dispatch<React.SetStateAction<boolean>>;
  showPdfPanel: boolean;
  setShowPdfPanel: React.Dispatch<React.SetStateAction<boolean>>;
  showChatPanel?: boolean;
  setShowChatPanel?: React.Dispatch<React.SetStateAction<boolean>>;
  isSmallScreen?: boolean;
  sidebarMode?: 'extraction' | 'forms';
}

const PDFViewerControls: React.FC<PDFViewerControlsProps> = ({
  showLeftPanel,
  setShowLeftPanel,
  showPdfPanel,
  setShowPdfPanel,
  showChatPanel = true,
  setShowChatPanel = () => {},
  isSmallScreen = false,
  sidebarMode = 'extraction',
}) => {
  return (
    <div className="flex items-center gap-1">
      <button
        onClick={() => setShowLeftPanel((prev: boolean) => !prev)}
        className={`
          flex items-center justify-center
          w-8 h-[31px]
          rounded
          transition-colors duration-150
          ${showLeftPanel
            ? 'bg-brand-foreground/15 text-brand-foreground hover:bg-brand-foreground/25'
            : 'text-brand-foreground/70 hover:bg-brand-foreground/15 hover:text-brand-foreground'
          }
        `}
        title={
          showLeftPanel
            ? `Hide ${sidebarMode === 'extraction' ? 'Extraction' : 'Forms'} Panel`
            : `Show ${sidebarMode === 'extraction' ? 'Extraction' : 'Forms'} Panel`
        }
      >
        <PanelLeft className={`h-4 w-4 ${showLeftPanel ? '' : 'opacity-50'}`} aria-hidden />
      </button>

      <button
        onClick={() => setShowPdfPanel((prev) => !prev)}
        className={`
          flex items-center justify-center
          w-8 h-[31px]
          rounded
          transition-colors duration-150
          ${showPdfPanel
            ? 'bg-brand-foreground/15 text-brand-foreground hover:bg-brand-foreground/25'
            : 'text-brand-foreground/70 hover:bg-brand-foreground/15 hover:text-brand-foreground'
          }
        `}
        title={showPdfPanel ? 'Hide PDF Panel' : 'Show PDF Panel'}
      >
        <FileText className={`h-4 w-4 ${showPdfPanel ? '' : 'opacity-50'}`} aria-hidden />
      </button>

      {!isSmallScreen && (
        <button
          onClick={() => setShowChatPanel((prev) => !prev)}
          className={`
            flex items-center justify-center
            w-8 h-[31px]
            rounded
            transition-colors duration-150
            ${showChatPanel
              ? 'bg-brand-foreground/15 text-brand-foreground hover:bg-brand-foreground/25'
              : 'text-brand-foreground/70 hover:bg-brand-foreground/15 hover:text-brand-foreground'
            }
          `}
          title={showChatPanel ? 'Hide Chat Panel' : 'Show Chat Panel'}
        >
          <MessageSquare className={`h-4 w-4 ${showChatPanel ? '' : 'opacity-50'}`} aria-hidden />
        </button>
      )}
    </div>
  );
};

export default PDFViewerControls;
