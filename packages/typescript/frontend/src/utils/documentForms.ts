import type { Form } from '@docrouter/sdk';
import type { DocRouterOrgApi } from '@/utils/api';

export async function loadDocumentMatchingForms(
  api: DocRouterOrgApi,
  documentId: string,
  options?: { limit?: number },
): Promise<{ tagIds: string[]; forms: Form[]; totalCount: number; documentName: string | null }> {
  const doc = await api.getDocument({
    documentId,
    fileType: 'original',
    includeContent: false,
  });
  const tagIds = doc.tag_ids ?? [];
  const documentName = doc.document_name ?? null;
  if (tagIds.length === 0) {
    return { tagIds, forms: [], totalCount: 0, documentName };
  }
  const limit = options?.limit ?? 100;
  const formsRes = await api.listForms({
    tag_ids: tagIds.join(','),
    limit,
  });
  const forms = formsRes.forms ?? [];
  const totalCount = formsRes.total_count ?? forms.length;
  return { tagIds, forms, totalCount, documentName };
}

export function documentHasMatchingForms(totalCount: number, forms: Form[]): boolean {
  return totalCount > 0 || forms.length > 0;
}
