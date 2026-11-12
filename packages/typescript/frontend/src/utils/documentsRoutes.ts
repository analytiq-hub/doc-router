export function docsListPath(organizationId: string, caseId?: string) {
  if (!caseId) return `/orgs/${organizationId}/docs`
  const query = new URLSearchParams({ case_id: caseId })
  return `/orgs/${organizationId}/docs?${query.toString()}`
}

export function docsUploadPath(organizationId: string, caseId?: string) {
  const query = new URLSearchParams({ tab: 'upload' })
  if (caseId) query.set('case_id', caseId)
  return `/orgs/${organizationId}/docs?${query.toString()}`
}
