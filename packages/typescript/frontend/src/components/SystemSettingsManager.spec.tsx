/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { SystemSettings } from '@docrouter/sdk'

import SystemSettingsManager from './SystemSettingsManager'

const BASE: SystemSettings = {
  textract_max_concurrent: 32,
  llm_max_concurrent_by_model: {},
  n_ocr_workers: 4,
  n_llm_workers: 4,
  n_kb_index_workers: 4,
  n_webhook_workers: 4,
  n_flow_run_workers: 4,
}

const getSystemSettings = vi.fn<() => Promise<SystemSettings>>()
const updateSystemSettings = vi.fn<(patch: unknown) => Promise<SystemSettings>>()

vi.mock('@/utils/api', () => ({
  DocRouterAccountApi: class {
    getSystemSettings = getSystemSettings
    updateSystemSettings = updateSystemSettings
  },
  getApiErrorMsg: (err: unknown) => (err instanceof Error ? err.message : 'Error'),
}))

describe('SystemSettingsManager', () => {
  beforeEach(() => {
    getSystemSettings.mockReset()
    updateSystemSettings.mockReset()
    getSystemSettings.mockResolvedValue({ ...BASE })
    updateSystemSettings.mockImplementation(async (patch) => ({ ...BASE, ...patch }))
  })

  afterEach(() => {
    cleanup()
  })

  it('keeps Save disabled on Rate limits until Textract concurrency changes', async () => {
    render(<SystemSettingsManager section="limits" />)
    const save = await screen.findByRole('button', { name: 'Save' })
    expect(save).toBeDisabled()

    const input = await screen.findByLabelText('Max concurrent Textract jobs')
    fireEvent.change(input, { target: { value: '40' } })
    await waitFor(() => expect(save).toBeEnabled())

    fireEvent.click(save)
    await waitFor(() =>
      expect(updateSystemSettings).toHaveBeenCalledWith({ textract_max_concurrent: 40 }),
    )
    await waitFor(() => expect(save).toBeDisabled())
  })

  it('saves only queue worker counts on the Queues section', async () => {
    render(<SystemSettingsManager section="queues" />)
    await screen.findByLabelText('OCR queue workers')

    const save = screen.getByRole('button', { name: 'Save' })
    expect(save).toBeDisabled()

    const ocrWorkers = screen.getByLabelText('OCR queue workers')
    fireEvent.change(ocrWorkers, { target: { value: '6' } })
    await waitFor(() => expect(save).toBeEnabled())

    fireEvent.click(save)
    await waitFor(() =>
      expect(updateSystemSettings).toHaveBeenCalledWith({
        n_ocr_workers: 6,
        n_llm_workers: 4,
        n_kb_index_workers: 4,
        n_webhook_workers: 4,
        n_flow_run_workers: 4,
      }),
    )
  })

  it('shows Textract-only copy on limits, not LLM table', async () => {
    render(<SystemSettingsManager section="limits" />)
    await screen.findByText('OCR (Textract)')
    expect(screen.getByText(/LLM models table/i)).toBeInTheDocument()
    expect(screen.queryByLabelText(/LLM model/i)).not.toBeInTheDocument()
  })

  it('shows worker count fields on queues, not Textract', async () => {
    render(<SystemSettingsManager section="queues" />)
    await screen.findByText('Queue worker counts')
    expect(screen.getByLabelText('Flow run queue workers')).toBeInTheDocument()
    expect(screen.queryByLabelText('Max concurrent Textract jobs')).not.toBeInTheDocument()
  })
})