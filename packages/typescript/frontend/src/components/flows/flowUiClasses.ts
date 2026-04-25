/** Shared Tailwind classes for form controls in the flow editor. */
export const flowLabelClass = 'mb-1 block text-xs font-medium text-gray-600';
export const flowInputClass =
  'w-full rounded-md border border-gray-300 bg-white px-2.5 py-1.5 text-sm text-gray-900 shadow-sm placeholder:text-gray-400 read-only:cursor-not-allowed read-only:bg-gray-100 focus:border-violet-600 focus:outline-none focus:ring-2 focus:ring-violet-500/20';
export const flowSelectClass = flowInputClass + ' cursor-pointer';
export const flowNameBreadcrumbInputClass =
  'min-w-[10rem] max-w-xl flex-1 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-semibold text-gray-900 shadow-sm read-only:cursor-default read-only:border-transparent read-only:bg-transparent focus:border-violet-600 focus:outline-none focus:ring-2 focus:ring-violet-500/25';

/** Shared shell: inline name styling (used by read + input + measuring span). */
const flowInlineNameShell =
  'box-border inline-block min-h-[38px] max-w-[min(100%,42rem)] whitespace-nowrap rounded-md px-3 py-1.5 align-middle text-sm font-semibold text-gray-900';

/** Plain title (no border); width follows text up to max-w. */
export const flowInlineNameReadClass = `${flowInlineNameShell} cursor-default overflow-hidden text-ellipsis border border-transparent`;

/** Bordered field; width is set from a hidden measuring span in the component. */
export const flowInlineNameInputClass = `${flowInlineNameShell} border border-gray-300 bg-white shadow-sm focus:border-violet-600 focus:outline-none focus:ring-2 focus:ring-violet-500/25`;

/** Hidden measuring span for inline-name inputs (same font + padding, no border/shadow). */
export const flowInlineNameMeasureClass =
  `${flowInlineNameShell} border border-transparent shadow-none px-3 py-1.5`;
