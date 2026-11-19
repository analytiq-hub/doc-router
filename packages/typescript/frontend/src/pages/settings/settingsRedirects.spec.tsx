/** @vitest-environment jsdom */
import { render, waitFor } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import DevelopmentWorkerSettingsRedirect from './development-worker-settings'

describe('settings redirects', () => {
  it('sends legacy worker-settings to Queues', async () => {
    const router = createMemoryRouter(
      [
        {
          path: '/settings/account/development/worker-settings',
          element: <DevelopmentWorkerSettingsRedirect />,
        },
        { path: '/settings/account/queues', element: <div>Queues page</div> },
      ],
      { initialEntries: ['/settings/account/development/worker-settings'] },
    )
    render(<RouterProvider router={router} />)
    await waitFor(() => expect(router.state.location.pathname).toBe('/settings/account/queues'))
  })
})