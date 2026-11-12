import InfoTooltip from '@/components/InfoTooltip'

export function DocumentUploadInfoTooltip() {
  return (
    <InfoTooltip
      title="Document Upload"
      content={
        <>
          <p className="mb-2">Upload documents to be processed by AI prompts. Supported file formats:</p>
          <ul className="mb-2 list-inside list-disc space-y-1">
            <li>
              <strong>PDF files</strong> (.pdf)
            </li>
            <li>
              <strong>Word documents</strong> (.doc, .docx)
            </li>
            <li>
              <strong>Excel files</strong> (.xls, .xlsx)
            </li>
            <li>
              <strong>CSV files</strong> (.csv)
            </li>
            <li>
              <strong>Text files</strong> (.txt, .md)
            </li>
            <li>
              <strong>Image files</strong> (.jpg, .jpeg, .png, .gif, .webp, .bmp, .tiff, .tif)
            </li>
          </ul>
          <p className="mb-2">
            <strong>Note:</strong> Select appropriate tags for your documents to control which prompts are run. Images
            will be processed using OCR to extract text.
          </p>
        </>
      }
    />
  )
}
