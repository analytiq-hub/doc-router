import { describe, expect, it } from 'vitest';

import {
  blankResultValue,
  coerceEditedValue,
  removeResultItemAtPath,
  resultCellText,
  resultCollapsibleNodes,
  resultContainerPaths,
  resultContainerStartsCollapsed,
  resultItemSummary,
  resultListSample,
  resultValueAtPath,
  setResultValueAtPath,
} from './resultTree';

describe('result tree', () => {
  it('keeps shallow scalar groups open and collapses large or deep structures', () => {
    expect(resultContainerStartsCollapsed({ city: 'Seattle', state: 'WA' }, 1)).toBe(false);
    expect(
      resultContainerStartsCollapsed(
        { one: 1, two: 2, three: 3, four: 4, five: 5 },
        1,
      ),
    ).toBe(true);
    expect(resultContainerStartsCollapsed([{ company: 'A' }], 1)).toBe(true);
    expect(resultContainerStartsCollapsed(['C', 'Python', 'CUDA'], 1)).toBe(false);
    expect(resultContainerStartsCollapsed(['C', 'Python', 'CUDA', 'ROS'], 1)).toBe(true);
  });

  it('collects nested object and array paths for expand-all controls', () => {
    expect(
      resultContainerPaths({
        work_experience: [
          { company: 'A', projects: [{ name: 'Navigation' }] },
          { company: 'B', projects: [] },
        ],
      }),
    ).toEqual([
      '',
      'work_experience',
      'work_experience[0]',
      'work_experience[0].projects',
      'work_experience[0].projects[0]',
      'work_experience[1]',
      'work_experience[1].projects',
    ]);
  });

  it('summarizes a list item by its first text field and last amount', () => {
    expect(
      resultItemSummary({ sku: 'A-1', description: 'Widget A', qty: 2, amount: '$40.00' }),
    ).toEqual({ title: 'A-1', value: '$40.00' });
    expect(resultItemSummary({ qty: 2, description: 'Widget\n A', notes: null })).toEqual({
      title: 'Widget A',
      value: '2',
    });
    expect(resultItemSummary({ company: 'Acme', projects: [{ name: 'Nav' }] })).toEqual({
      title: 'Acme',
      value: null,
    });
    expect(resultItemSummary({ total: 12 })).toEqual({ title: '12', value: null });
    expect(resultItemSummary({ notes: '', tags: [] })).toEqual({ title: null, value: null });
  });

  it('describes cells and resolves tree paths', () => {
    const root = { vendor: { name: 'Acme' }, items: [{ tags: ['a', 'b'] }, { tags: [] }] };
    expect(resultCellText(null)).toBe('—');
    expect(resultCellText(0)).toBe('0');
    expect(resultCellText(['a'])).toBe('1 item');
    expect(resultCellText({ a: 1, b: 2 })).toBe('2 fields');
    expect(resultValueAtPath(root, '')).toBe(root);
    expect(resultValueAtPath(root, 'vendor.name')).toBe('Acme');
    expect(resultValueAtPath(root, 'items[0].tags[1]')).toBe('b');
    expect(resultValueAtPath(root, 'items[5].tags')).toBeUndefined();
    expect(resultValueAtPath(root, 'vendor.name.first')).toBeUndefined();
  });

  it('edits and removes values inside nested lists', () => {
    const root = {
      jobs: [
        { company: 'A', projects: [{ name: 'Nav' }, { name: 'Map' }] },
        { company: 'B', projects: [] },
      ],
    };
    expect(setResultValueAtPath(root, 'jobs[0].projects[1].name', 'Maps')).toBe(true);
    expect(root.jobs[0].projects[1].name).toBe('Maps');
    expect(setResultValueAtPath(root, 'jobs[4].company', 'X')).toBe(false);
    expect(setResultValueAtPath(root, 'jobs[9]', 'X')).toBe(false);

    expect(removeResultItemAtPath(root, 'jobs[0].projects[0]')).toBe(true);
    expect(root.jobs).toHaveLength(2);
    expect(root.jobs[0].projects).toEqual([{ name: 'Maps' }]);
    expect(removeResultItemAtPath(root, 'jobs[0].company')).toBe(false);
  });

  it('builds a blank item from the list itself or from a sibling list', () => {
    const root = {
      jobs: [
        { company: 'A', projects: [{ name: 'Nav', hours: 3, tags: ['x'] }] },
        { company: 'B', projects: [] },
      ],
      skills: [],
    };
    expect(resultListSample(root, 'jobs')).toBe(root.jobs[0]);
    expect(resultListSample(root, 'jobs[1].projects')).toBe(root.jobs[0].projects[0]);
    expect(resultListSample(root, 'skills')).toBeUndefined();
    expect(blankResultValue(root.jobs[0])).toEqual({ company: '', projects: [] });
    expect(blankResultValue(root.jobs[0].projects[0])).toEqual({ name: '', hours: 0, tags: [] });
  });

  it('keeps the original type when a value is corrected', () => {
    expect(coerceEditedValue(40, ' 42.5 ')).toBe(42.5);
    expect(coerceEditedValue(40, 'n/a')).toBe('n/a');
    expect(coerceEditedValue(true, 'False')).toBe(false);
    expect(coerceEditedValue('02139', '02140')).toBe('02140');
    expect(coerceEditedValue(null, '')).toBeNull();
    expect(coerceEditedValue(null, '7')).toBe('7');
  });

  it('lists the disclosures the panel draws, with their starting state', () => {
    expect(
      resultCollapsibleNodes({
        name: 'Kim',
        languages: ['en', 'es'],
        address: { city: 'Seattle' },
        jobs: [{ company: 'A', projects: [{ name: 'Nav' }] }, {}],
        empty: [],
      }),
    ).toEqual([
      { path: 'languages', defaultOpen: true },
      { path: 'address', defaultOpen: true },
      { path: 'jobs', defaultOpen: false },
      { path: 'jobs[0]', defaultOpen: false },
      { path: 'jobs[0].projects', defaultOpen: false },
      { path: 'jobs[0].projects[0]', defaultOpen: false },
    ]);
    // A lone object shows its fields directly; a lone list is itself a group.
    expect(resultCollapsibleNodes({ cv: { name: 'Kim', tags: ['a'] } })).toEqual([
      { path: 'cv.tags', defaultOpen: true },
    ]);
    expect(resultCollapsibleNodes({ items: [{ sku: 'A' }] })).toEqual([
      { path: 'items', defaultOpen: true },
      { path: 'items[0]', defaultOpen: false },
    ]);
    expect(resultCollapsibleNodes({ name: 'Kim' })).toEqual([]);
  });
});
