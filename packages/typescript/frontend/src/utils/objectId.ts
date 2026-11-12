/** MongoDB ObjectId string (same format as document ids). */
export function isObjectIdString(value: string | null | undefined): boolean {
  if (!value) return false;
  return /^[0-9a-f]{24}$/i.test(value.trim());
}
