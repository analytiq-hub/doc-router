import type { OrgOcrConfig } from '@docrouter/sdk';

export const FALLBACK_TEXTRACT_FEATURES = ['LAYOUT', 'TABLES', 'FORMS', 'SIGNATURES'] as const;

export const FALLBACK_OCR_MODES = ['textract', 'mistral', 'mistral_vertex', 'llm', 'pymupdf'] as const;

export type OcrMode = (typeof FALLBACK_OCR_MODES)[number];

export const OCR_MODE_LABELS: Record<OcrMode, string> = {
  textract: 'AWS Textract',
  mistral: 'Mistral OCR',
  mistral_vertex: 'Mistral OCR (Vertex AI)',
  llm: 'LLM OCR',
  pymupdf: 'PyMuPDF (embedded text)',
};

export function isOcrMode(s: string): s is OcrMode {
  return (FALLBACK_OCR_MODES as readonly string[]).includes(s);
}

export function normalizeOcrConfig(raw: OrgOcrConfig): OrgOcrConfig {
  return {
    mode: raw.mode ?? 'textract',
    textract: {
      feature_types:
        raw.textract?.feature_types !== undefined && Array.isArray(raw.textract.feature_types)
          ? [...raw.textract.feature_types]
          : [],
    },
    mistral: raw.mistral ?? {},
    mistral_vertex: raw.mistral_vertex ?? {},
    pymupdf: raw.pymupdf ?? {},
    llm: {
      provider: raw.llm?.provider ?? null,
      model: raw.llm?.model ?? null,
    },
  };
}

export const cloneOcrConfig = (c: OrgOcrConfig): OrgOcrConfig =>
  normalizeOcrConfig(JSON.parse(JSON.stringify(c)) as OrgOcrConfig);