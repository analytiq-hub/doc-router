import { FileText, PanelRight } from 'lucide-react';
import type { DocSidebarTab } from '@/utils/docPageUrl';

interface PDFViewerControlsProps {
  showRightPanel: boolean;
  setShowRightPanel: React.Dispatch<React.SetStateAction<boolean>>;
  showPdfPanel: boolean;
  setShowPdfPanel: React.Dispatch<React.SetStateAction<boolean>>;
  isSmallScreen?: boolean;
  rightPanelTab?: DocSidebarTab;
}

const TAB_TITLE: Record<DocSidebarTab, string> = {
  extraction: 'Extraction',
  flows: 'Flows',
  forms: 'Forms',
  text: 'Text',
  info: 'Info',
  chat: 'Chat',
};

const PDFViewerControls: React.FC<PDFViewerControlsProps> = ({
  showRightPanel,
  setShowRightPanel,
  showPdfPanel,
  setShowPdfPanel,
  isSmallScreen = false,
  rightPanelTab = 'extraction',
}) => {
  const panelLabel = TAB_TITLE[rightPanelTab] ?? 'Panel';

  return (
    <div className="flex items-center gap-1">
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
        title={showPdfPanel ? 'Hide PDF' : 'Show PDF'}
      >
        <FileText className={`h-4 w-4 ${showPdfPanel ? '' : 'opacity-50'}`} aria-hidden />
      </button>

      {!isSmallScreen && (
        <button
          onClick={() => setShowRightPanel((prev) => !prev)}
          className={`
            flex items-center justify-center
            w-8 h-[31px]
            rounded
            transition-colors duration-150
            ${showRightPanel
              ? 'bg-brand-foreground/15 text-brand-foreground hover:bg-brand-foreground/25'
              : 'text-brand-foreground/70 hover:bg-brand-foreground/15 hover:text-brand-foreground'
            }
          `}
          title={
            showRightPanel
              ? `Hide ${panelLabel} panel`
              : `Show document panel (${panelLabel})`
          }
        >
          <PanelRight className={`h-4 w-4 ${showRightPanel ? '' : 'opacity-50'}`} aria-hidden />
        </button>
      )}
    </div>
  );
};

export default PDFViewerControls;
