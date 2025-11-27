import { DocRouterOrg } from '../../src';
import { getTestDatabase, getBaseUrl, createTestFixtures } from '../setup/jest-setup';

describe('Prompts Integration Tests', () => {
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

  test('create/list/get/update/delete prompt', async () => {
    const created = await client.createPrompt({ prompt: { name: 'Prompt A', content: 'Extract fields' } as any });
    expect(created).toBeDefined();
    // Backend returns prompt_revid/prompt_id
    const promptRevId = (created as any).prompt_revid || (created as any).id;
    expect(promptRevId).toBeDefined();

    const listed = await client.listPrompts({ limit: 5 });
    expect(Array.isArray(listed.prompts)).toBe(true);

    const fetched = await client.getPrompt({ promptRevId });
    expect((fetched as any).name || (fetched as any).prompt_name || fetched).toBeDefined();

    const updated = await client.updatePrompt({ 
      promptId: (created as any).prompt_id || (created as any).id, 
      prompt: { 
        name: 'Prompt A', 
        content: 'Extract fields v2' 
      } as any 
    });
    expect((updated as any).content).toBe('Extract fields v2');

    await client.deletePrompt({ promptId: (created as any).prompt_id || (created as any).id });
    await expect(client.getPrompt({ promptRevId })).rejects.toThrow();
  });

  test('list prompts supports skip, limit, and nameSearch', async () => {
    // create two prompts
    const a = await client.createPrompt({ prompt: { name: 'Alpha Prompt', content: 'A' } as any });
    const b = await client.createPrompt({ prompt: { name: 'Beta Prompt', content: 'B' } as any });

    const listedLimited = await client.listPrompts({ limit: 1 });
    expect(Array.isArray(listedLimited.prompts)).toBe(true);
    expect(listedLimited.prompts.length).toBeLessThanOrEqual(1);

    const listedSkip = await client.listPrompts({ skip: 1, limit: 10 });
    expect(listedSkip.skip).toBe(1);

    const searchAlpha = await client.listPrompts({ nameSearch: 'Alpha' });
    expect(searchAlpha.prompts.find(p => (p as any).name?.includes('Alpha'))).toBeDefined();

    // cleanup
    await client.deletePrompt({ promptId: (a as any).prompt_id });
    await client.deletePrompt({ promptId: (b as any).prompt_id });
  });

  test('update only name does not change content', async () => {
    const created = await client.createPrompt({ prompt: { name: 'Name Only', content: 'original' } as any });
    const updatedNameOnly = await client.updatePrompt({
      promptId: (created as any).prompt_id,
      prompt: { name: 'Name Only Renamed', content: 'original' } as any
    });
    expect((updatedNameOnly as any).name).toBe('Name Only Renamed');
    expect((updatedNameOnly as any).content).toBe('original');
    await client.deletePrompt({ promptId: (created as any).prompt_id });
  });
});


