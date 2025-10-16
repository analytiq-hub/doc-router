import { 
  ViewSidebar, 
  PictureAsPdf,
  ViewSidebarOutlined,
  PictureAsPdfOutlined 
} from '@mui/icons-material';

interface PDFViewerControlsProps {
  showLeftPanel: boolean;
  setShowLeftPanel: React.Dispatch<React.SetStateAction<boolean>>;
  showPdfPanel: boolean;
  setShowPdfPanel: React.Dispatch<React.SetStateAction<boolean>>;
  sidebarMode?: 'extraction' | 'forms';
}

const PDFViewerControls: React.FC<PDFViewerControlsProps> = ({
  showLeftPanel,
  setShowLeftPanel,
  showPdfPanel,
  setShowPdfPanel,
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
            ? 'bg-blue-100 text-blue-700 hover:bg-blue-200' 
            : 'text-blue-200 hover:bg-blue-500 hover:text-white'
          }
        `}
        title={showLeftPanel ? `Hide ${sidebarMode === 'extraction' ? 'Extraction' : 'Forms'} Panel` : `Show ${sidebarMode === 'extraction' ? 'Extraction' : 'Forms'} Panel`}
      >
        {showLeftPanel ? (
          <ViewSidebar className="w-4 h-4" />
        ) : (
          <ViewSidebarOutlined className="w-4 h-4" />
        )}
      </button>
      
      <button
        onClick={() => setShowPdfPanel(prev => !prev)}
        className={`
          flex items-center justify-center
          w-8 h-[31px]
          rounded
          transition-colors duration-150
          ${showPdfPanel 
            ? 'bg-blue-100 text-blue-700 hover:bg-blue-200' 
            : 'text-blue-200 hover:bg-blue-500 hover:text-white'
          }
        `}
        title={showPdfPanel ? "Hide PDF Panel" : "Show PDF Panel"}
      >
        {showPdfPanel ? (
          <PictureAsPdf className="w-4 h-4" />
        ) : (
          <PictureAsPdfOutlined className="w-4 h-4" />
        )}
      </button>
    </div>
  );
};

export default PDFViewerControls; 