import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { expect } from 'vitest'

export function expectHubTable(
  container: HTMLElement,
  ariaLabel: string,
  headers: string[],
  rowText: string,
) {
  const scope = within(container)
  expect(scope.getByRole('table', { name: ariaLabel })).toBeInTheDocument()
  for (const header of headers) {
    expect(scope.getAllByRole('columnheader', { name: header })[0]).toBeInTheDocument()
  }
  expect(scope.getByText(rowText)).toBeInTheDocument()
  expect(scope.queryByText('No rows')).not.toBeInTheDocument()
}

export function openRowActionsMenu(container: HTMLElement, actionForLabel: string) {
  const scope = within(container)
  fireEvent.click(scope.getAllByRole('button', { name: `Actions for ${actionForLabel}` })[0])
}

export function latestOpenMenu() {
  const menus = screen.queryAllByRole('menu')
  expect(menus.length).toBeGreaterThan(0)
  return menus[menus.length - 1]!
}

export async function expectRowActionMenu(
  container: HTMLElement,
  actionForLabel: string,
  menuItems: string[],
) {
  openRowActionsMenu(container, actionForLabel)
  await waitFor(() => {
    expect(latestOpenMenu()).toBeVisible()
  })
  const menu = latestOpenMenu()
  for (const item of menuItems) {
    expect(within(menu).getByRole('menuitem', { name: item })).toBeInTheDocument()
  }
}