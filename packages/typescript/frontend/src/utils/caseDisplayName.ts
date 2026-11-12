/** Human-readable case title; falls back to the stable Case ID when no name is set. */
export function caseDisplayName(caseRow: {
  case_id: string;
  name?: string | null;
}): string {
  const trimmed = caseRow.name?.trim();
  return trimmed || caseRow.case_id;
}
