import { Bolt, Check, Crop, Download, FileText } from 'lucide-react';
import {
  DropdownMenuCheckboxItem,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu';
import { isOCRSupported } from '@/utils/ocr-utils';
import { cn } from 'cn';

type Props = {
  fileName: string;
  showBoundingBoxes: boolean;
  ocrPanelOpen: boolean;
  onToggleBoundingBoxes: () => void;
  onOpenOcrOutput: () => void;
  onDownloadOcrJson: () => void;
  onRerunOcr: () => void;
};

export function DocRouterMenuExtras({
  fileName,
  showBoundingBoxes,
  ocrPanelOpen,
  onToggleBoundingBoxes,
  onOpenOcrOutput,
  onDownloadOcrJson,
  onRerunOcr,
}: Props) {
  const ocrOk = isOCRSupported(fileName);
  return (
    <>
      <DropdownMenuSeparator />
      <DropdownMenuGroup>
        <DropdownMenuCheckboxItem
          closeOnClick
          checked={showBoundingBoxes}
          disabled={!ocrOk}
          onCheckedChange={onToggleBoundingBoxes}
        >
          <Crop className={cn('mr-2 size-4')} />
          Bounding boxes
          {showBoundingBoxes ? <Check className="ml-auto size-4" /> : null}
        </DropdownMenuCheckboxItem>
        <DropdownMenuItem disabled={!ocrOk} onClick={onOpenOcrOutput}>
          <FileText className="mr-2 size-4" />
          Show OCR output
          {ocrPanelOpen ? <Check className="ml-auto size-4" /> : null}
        </DropdownMenuItem>
        <DropdownMenuItem disabled={!ocrOk} onClick={() => void onDownloadOcrJson()}>
          <Download className="mr-2 size-4" />
          Download OCR JSON
        </DropdownMenuItem>
        <DropdownMenuItem disabled={!ocrOk} onClick={() => void onRerunOcr()}>
          <Bolt className="mr-2 size-4" />
          Rerun OCR
        </DropdownMenuItem>
      </DropdownMenuGroup>
    </>
  );
}
