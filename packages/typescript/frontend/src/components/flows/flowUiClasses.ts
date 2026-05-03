/** Shared Tailwind classes for form controls in the flow editor. */
export const flowLabelClass = 'mb-1 block text-xs font-medium text-gray-600';
export const flowInputClass =
  'w-full rounded-md border border-gray-300 bg-white px-2.5 py-1.5 text-sm text-gray-900 shadow-sm placeholder:text-gray-400 read-only:cursor-not-allowed read-only:bg-gray-100 focus:border-violet-600 focus:outline-none focus:ring-2 focus:ring-violet-500/20';
export const flowSelectClass = flowInputClass + ' cursor-pointer';
export const flowNameBreadcrumbInputClass =
  'min-w-[10rem] max-w-xl flex-1 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-semibold text-gray-900 shadow-sm read-only:cursor-default read-only:border-transparent read-only:bg-transparent focus:border-violet-600 focus:outline-none focus:ring-2 focus:ring-violet-500/25';

/** Shared shell: inline name styling (used by read + input + measuring span). */
const flowInlineNameShell =
  'box-border inline-block min-h-0 max-w-[min(100%,42rem)] whitespace-nowrap rounded-md px-2.5 py-0.5 align-middle text-sm font-semibold text-gray-900';

/** Plain title (no border); width follows text up to max-w. */
export const flowInlineNameReadClass = `${flowInlineNameShell} cursor-default overflow-hidden text-ellipsis border border-transparent`;

/** Bordered field; width is set from a hidden measuring span in the component. */
export const flowInlineNameInputClass = `${flowInlineNameShell} border border-gray-300 bg-white shadow-sm focus:border-violet-600 focus:outline-none focus:ring-2 focus:ring-violet-500/25`;

/** Hidden measuring span for inline-name inputs (same font + padding, no border/shadow). */
export const flowInlineNameMeasureClass = `${flowInlineNameShell} border border-transparent shadow-none px-2.5 py-0.5`;

/** Matches executions workspace title strip — keeps editor toolbar one row visually aligned (42px). */
export const FLOW_WORKSPACE_HEADER_HEIGHT_CLASS = 'h-[2.625rem]';

/** Toolbar collapsed title + executions header title — plain text inset (no chip padding); lives under outer `px-3`. */
export const FLOW_WORKSPACE_TITLE_READ_CLASS =
  'min-w-0 max-w-[min(100%,42rem)] truncate text-sm font-semibold text-gray-900';

/**
 * Use on React Flow `Panel` rows pinned to `top` under the flow workspace header. The centered
 * Editor/Executions tab straddle (`FlowWorkspaceTabStraddle`) hangs ~half its height into the canvas;
 * this top padding keeps status text from sitting under the pill.
 */
export const FLOW_RF_PANEL_CLEAR_BELOW_WORKSPACE_TABS = '!pt-7';

/** Headless UI switch track (shared by node settings + schema-driven parameters). */
export const flowSwitchTrackClass =
  'group relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent bg-gray-200 transition-colors data-[checked]:bg-gray-400 focus:outline-none focus:ring-2 focus:ring-gray-300 focus:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-60';

export const flowSwitchThumbClass =
  'inline-block h-3.5 w-3.5 translate-x-0.5 rounded-full bg-white shadow transition group-data-[checked]:translate-x-4';
