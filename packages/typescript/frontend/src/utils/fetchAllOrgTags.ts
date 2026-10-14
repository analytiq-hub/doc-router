import { DocRouterOrgApi } from '@/utils/api';
import type { Tag } from '@docrouter/sdk';

const PAGE_SIZE = 100;

/** Load all org tags (API limit is 100 per request). */
export async function fetchAllOrgTags(api: DocRouterOrgApi): Promise<Tag[]> {
  const tags: Tag[] = [];
  for (let skip = 0; ; skip += PAGE_SIZE) {
    const page = await api.listTags({ skip, limit: PAGE_SIZE });
    tags.push(...page.tags);
    if (page.tags.length < PAGE_SIZE) break;
  }
  return tags;
}
