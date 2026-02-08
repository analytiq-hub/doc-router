/**
 * Check if OCR is supported for a file based on its extension.
 * Matches the backend logic in packages/python/analytiq_data/common/doc.py
 * 
 * @param fileName - The file name (with extension)
 * @returns true if OCR is supported, false otherwise
 */
export function isOCRSupported(fileName: string | null | undefined): boolean {
  if (!fileName) return false;
  
  const lastDotIndex = fileName.lastIndexOf('.');
  if (lastDotIndex === -1) return false;
  
  const ext = fileName.substring(lastDotIndex).toLowerCase();
  
  // OCR not supported for structured data files and text files
  const skipExtensions = ['.csv', '.xls', '.xlsx', '.txt', '.md'];
  return !skipExtensions.includes(ext);
}

/**
 * Check if an error is a 404 "OCR ... not found" from the API (OCR not run yet or still processing).
 * Use this to avoid logging these as console errors and to show a user-friendly message.
 */
export function isOcrNotReadyError(err: unknown): boolean {
  const apiErr = err as Error & { status?: number };
  return (
    apiErr?.status === 404 &&
    typeof apiErr?.message === 'string' &&
    /OCR .* not found/i.test(apiErr.message)
  );
}
