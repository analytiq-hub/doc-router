/**
 * Tailwind primitives for flows workspace dropdown menus (compact sans, ~13px, light border / soft shadow).
 */

export const flowWorkspaceDropdownSurfaceClass =
  'rounded-md border border-gray-200 bg-white py-1 shadow-[0_4px_14px_rgba(15,23,42,0.08)]';

const flowSans13 = 'font-sans text-[13px] font-normal leading-snug antialiased';

/** Use with `<MenuItems portal anchor="bottom end" />` — includes z-index and gap spacing */
export const flowWorkspaceMenuPanelClass = `z-[280] mt-1 min-w-[11rem] ${flowWorkspaceDropdownSurfaceClass} outline-none`;

/** Toolbar / modal header ⋮ triggers */
export const flowWorkspaceMenuTriggerIconBtnClass =
  'inline-flex shrink-0 items-center justify-center rounded-md p-1.5 text-gray-600 transition hover:bg-gray-100 data-[hover]:bg-gray-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/50';

/** React Flow node toolbar ⋮ trigger (28×28 target) */
export const flowWorkspaceMenuTriggerCompactClass =
  'inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-gray-600 transition hover:bg-gray-100 data-[hover]:bg-gray-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/50';

export const flowWorkspaceDropdownItemClass =
  `${flowSans13} flex w-full cursor-pointer items-center gap-2 border-0 px-[14px] py-2.5 text-left text-gray-600 hover:bg-gray-100`;

export const flowWorkspaceDropdownItemSimpleClass =
  `${flowSans13} block w-full cursor-pointer border-0 px-[14px] py-2.5 text-left text-gray-600 hover:bg-gray-100`;

export const flowWorkspaceDropdownItemDestructiveClass =
  `${flowSans13} flex w-full cursor-pointer items-center gap-2 border-0 px-[14px] py-2.5 text-left text-red-600 hover:bg-red-50`;

export const flowWorkspaceDropdownItemMutedClass =
  `${flowSans13} px-[14px] py-2.5 text-left text-gray-400`;

export const flowWorkspaceDropdownDividerClass = 'my-1 border-0 border-t border-gray-200';
