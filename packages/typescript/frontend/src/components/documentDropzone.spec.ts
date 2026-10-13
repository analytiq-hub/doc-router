import { describe, expect, it } from 'vitest';
import { filesFromPickerEvent } from './documentDropzone';

function pdf(name = 'invoice.pdf'): File {
  return new File(['%PDF'], name, { type: 'application/pdf' });
}

describe('filesFromPickerEvent', () => {
  it('reads files from a drop without touching DataTransferItem', () => {
    const file = pdf();
    const chosen = filesFromPickerEvent({
      type: 'drop',
      dataTransfer: { files: [file] },
    });
    expect(chosen).toEqual([file]);
  });

  it('does not read the payload during drag hover', () => {
    const file = pdf();
    expect(
      filesFromPickerEvent({
        type: 'dragenter',
        dataTransfer: { files: [file] },
      })
    ).toEqual([]);
  });

  it('reads files from a file-input change event', () => {
    const file = pdf('scan.png');
    const chosen = filesFromPickerEvent({
      type: 'change',
      target: { files: [file] },
    });
    expect(chosen).toEqual([file]);
  });

  it('returns nothing when the dialog is cancelled', () => {
    expect(filesFromPickerEvent({ type: 'change', target: { files: [] } })).toEqual([]);
    expect(filesFromPickerEvent(null)).toEqual([]);
  });
});
