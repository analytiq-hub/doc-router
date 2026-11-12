'use client';

import { Download, MoreVertical, RefreshCw, FileText } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

const iconBtnClass =
  'cursor-pointer rounded-full p-1 transition-colors hover:bg-black/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';

type PdfPanelMoreMenuProps = {
  onDownload: () => void;
  onReload?: () => void;
  reloadLabel?: string;
  onRunInfo?: () => void;
};

/** Kebab menu for PDF extraction / flows side panel rows. */
export function PdfPanelMoreMenu({
  onDownload,
  onReload,
  reloadLabel = 'Reload',
  onRunInfo,
}: PdfPanelMoreMenuProps) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <button
            type="button"
            onClick={(e) => e.stopPropagation()}
            className={iconBtnClass}
            title="More actions"
          />
        }
      >
        <MoreVertical className="size-4 text-muted-foreground" aria-hidden />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-36" onClick={(e) => e.stopPropagation()}>
        <DropdownMenuItem
          onClick={() => {
            onDownload();
          }}
        >
          <Download />
          Download
        </DropdownMenuItem>
        {onReload ? (
          <DropdownMenuItem
            onClick={() => {
              onReload();
            }}
          >
            <RefreshCw />
            {reloadLabel}
          </DropdownMenuItem>
        ) : null}
        {onRunInfo ? (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={() => {
                onRunInfo();
              }}
            >
              <FileText />
              Run Info
            </DropdownMenuItem>
          </>
        ) : null}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export { iconBtnClass };

/** Spinning refresh control (same affordance as before). */
export function PdfPanelReloadButton({
  running,
  onReload,
  title,
}: {
  running: boolean;
  onReload: () => void;
  title: string;
}) {
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        onReload();
      }}
      className={iconBtnClass}
      title={title}
      disabled={running}
    >
      {running ? (
        <div
          className="size-4 animate-spin rounded-full border-2 border-primary/60 border-t-transparent"
          aria-hidden
        />
      ) : (
        <RefreshCw className="size-4 text-muted-foreground" aria-hidden />
      )}
    </button>
  );
}
