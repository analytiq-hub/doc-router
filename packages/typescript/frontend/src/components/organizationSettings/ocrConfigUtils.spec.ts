/** @vitest-environment node */
import { describe, expect, it } from 'vitest'

import { cloneOcrConfig, isOcrMode, normalizeOcrConfig } from './ocrConfigUtils'

describe('ocrConfigUtils', () => {
  it('normalizes partial OCR config with defaults', () => {
    const normalized = normalizeOcrConfig({
      mode: 'llm',
      textract: { feature_types: ['TABLES'] },
      llm: { provider: 'openai', model: 'gpt-4o' },
    })
    expect(normalized.mode).toBe('llm')
    expect(normalized.textract.feature_types).toEqual(['TABLES'])
    expect(normalized.llm).toEqual({ provider: 'openai', model: 'gpt-4o' })
    expect(normalized.mistral).toEqual({})
  })

  it('clones without sharing nested arrays', () => {
    const original = normalizeOcrConfig({
      mode: 'textract',
      textract: { feature_types: ['FORMS'] },
    })
    const copy = cloneOcrConfig(original)
    copy.textract.feature_types.push('TABLES')
    expect(original.textract.feature_types).toEqual(['FORMS'])
  })

  it('recognizes OCR engine ids', () => {
    expect(isOcrMode('textract')).toBe(true)
    expect(isOcrMode('unknown')).toBe(false)
  })
})