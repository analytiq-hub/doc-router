import { DocRouterOrg } from '../../src';
import { getTestDatabase, getBaseUrl, createTestFixtures } from '../setup/jest-setup';

describe('Tags Integration Tests', () => {
  let testFixtures: any;
  let client: DocRouterOrg;

  beforeEach(async () => {
    const testDb = getTestDatabase();
    const baseUrl = getBaseUrl();
    testFixtures = await createTestFixtures(testDb, baseUrl);

    client = new DocRouterOrg({
      baseURL: baseUrl,
      orgToken: testFixtures.member.token,
      organizationId: testFixtures.org_id
    });
  });

  test('create/get/list/update/delete tag', async () => {
    const created = await client.createTag({
      tag: { name: 'Integration Tag', color: '#123456' }
    });
    expect(created).toBeDefined();
    expect(created.id).toBeDefined();

    const fetched = await client.getTag({ tagId: created.id });
    expect(fetched.name).toBe('Integration Tag');

    const listed = await client.listTags({ limit: 5 });
    expect(Array.isArray(listed.tags)).toBe(true);

    const updated = await client.updateTag({ tagId: created.id, tag: { name: 'Updated Tag' } });
    expect(updated.name).toBe('Updated Tag');

    await client.deleteTag({ tagId: created.id });
    await expect(client.getTag({ tagId: created.id })).rejects.toThrow();
  });

  test('list tags supports skip, limit, and nameSearch', async () => {
    const t1 = await client.createTag({ tag: { name: 'Alpha Tag', color: '#111111' } });
    const t2 = await client.createTag({ tag: { name: 'Beta Tag', color: '#222222' } });

    const limited = await client.listTags({ limit: 1 });
    expect(Array.isArray(limited.tags)).toBe(true);
    expect(limited.tags.length).toBeLessThanOrEqual(1);

    const skipped = await client.listTags({ skip: 1, limit: 10 });
    expect(skipped.skip).toBe(1);

    const search = await client.listTags({ nameSearch: 'Alpha' });
    expect(search.tags.find(t => t.name.includes('Alpha'))).toBeDefined();

    await client.deleteTag({ tagId: t1.id });
    await client.deleteTag({ tagId: t2.id });
  });
});


