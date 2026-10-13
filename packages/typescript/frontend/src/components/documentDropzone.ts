import type { CSSProperties } from 'react';

/**
 * Hide the file input without `display: none`.
 * Chromium and Safari skip the change event on a `display: none` file input,
 * so a chosen document never reaches onDrop and the upload step stays disabled.
 */
export const dropzoneInputStyle: CSSProperties = {
  border: 0,
  display: 'block',
  height: 0,
  margin: 0,
  opacity: 0,
  overflow: 'hidden',
  padding: 0,
  width: 0,
};

type PickerEvent = {
  type?: string;
  dataTransfer?: { files?: ArrayLike<File> | null } | null;
  target?: { files?: ArrayLike<File> | null } | null;
};

/**
 * Read chosen files synchronously from a drop or a file-input change.
 *
 * react-dropzone's default reader (`file-selector`) calls `webkitGetAsEntry()`
 * and then awaits. Current Chromium clears the DataTransfer after that, so
 * `getAsFile()` is null, onDrop runs with an empty list, and nothing is shown.
 * `dataTransfer.files` is still populated on the drop event itself.
 *
 * Drag-hover events (`dragenter` / `dragover`) must not read the payload.
 */
export function filesFromPickerEvent(event: unknown): File[] {
  if (!event || typeof event !== 'object' || Array.isArray(event)) return [];
  const picker = event as PickerEvent;
  if (picker.type && picker.type !== 'drop' && picker.type !== 'change') return [];

  const dropped = picker.dataTransfer?.files;
  if (dropped && dropped.length > 0) {
    return Array.from(dropped);
  }
  const chosen = picker.target?.files;
  if (chosen && chosen.length > 0) {
    return Array.from(chosen);
  }
  return [];
}

/** Works on http:// hosts that are not a secure context (`crypto.randomUUID` throws there). */
export function newUploadRowId(): string {
  try {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      return crypto.randomUUID();
    }
  } catch {
    // Insecure context: randomUUID exists in the type but is not callable.
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
