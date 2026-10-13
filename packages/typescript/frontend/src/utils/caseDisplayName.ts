/** Human-readable case title; falls back to the stable Case ID when no name is set. */
export function caseDisplayName(caseRow: {
  case_id: string;
  display_name?: string | null;
}): string {
  const trimmed = caseRow.display_name?.trim();
  return trimmed || caseRow.case_id;
}
