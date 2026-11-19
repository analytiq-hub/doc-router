// Where the user was, so Settings can open where they left it and send them back where they came from.
// Kept per browser; storage that cannot be used just forgets.

const LAST_APP = 'lastAppPath'
const LAST_SETTINGS = 'lastSettingsPath'

/** Settings addresses that only forward elsewhere. They are never a place to come back to. */
const FORWARDING = [
  /^\/settings\/user\/developer\/?$/,
  /^\/settings\/account\/development\/?$/,
  /^\/settings\/organizations\/[^/]+\/webhooks\/?$/,
]

function read(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function write(key: string, value: string): void {
  try {
    localStorage.setItem(key, value)
  } catch {
    // private window or blocked storage: nothing is remembered
  }
}

function pathOnly(value: string): string {
  return value.split('?')[0] ?? value
}

function isSettingsPath(pathname: string): boolean {
  return pathname.startsWith('/settings/') && !FORWARDING.some((pattern) => pattern.test(pathname))
}

function isAppPath(pathname: string): boolean {
  return pathname.startsWith('/orgs/')
}

/** Remembers the page as the last app page (an organization's page) or the last settings page. */
export function rememberPath(pathname: string, search = ''): void {
  if (isSettingsPath(pathname)) write(LAST_SETTINGS, pathname + search)
  else if (isAppPath(pathname)) write(LAST_APP, pathname + search)
}

/** Forgets what was remembered: on sign-out, so the next person on this browser starts clean. */
export function forgetNavigation(): void {
  try {
    localStorage.removeItem(LAST_APP)
    localStorage.removeItem(LAST_SETTINGS)
  } catch {
    // storage that cannot be used has nothing to forget
  }
}

export function lastAppPath(): string | null {
  const value = read(LAST_APP)
  if (!value || !isAppPath(pathOnly(value)) || pathOnly(value).startsWith('//')) return null
  return value
}

export function lastSettingsPath(): string | null {
  const value = read(LAST_SETTINGS)
  if (!value || !isSettingsPath(pathOnly(value)) || pathOnly(value).startsWith('//')) return null
  return value
}
