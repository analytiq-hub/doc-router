import {
  clearHiddenFieldsToDefaults,
  mergeParameterDefaults,
} from '../../src/flow-parameter-merge';

describe('clearHiddenFieldsToDefaults', () => {
  it('evaluates visibility from original params so reset order does not break chained show_when', () => {
    /** `early` is hidden first and cleared — `late` must still see original `early` when deciding visibility. */
    const parameterSchema = {
      type: 'object',
      properties: {
        early: {
          type: 'string',
          default: '',
          'x-ui-show-when': { field: 'root', equals: 0 },
        },
        late: {
          type: 'string',
          default: '',
          'x-ui-show-when': { field: 'early', equals: 'X' },
        },
        root: { type: 'integer', default: 0 },
      },
    };

    const params = { root: 1, early: 'X', late: 'keep-me' };

    const cleared = clearHiddenFieldsToDefaults(parameterSchema, mergeParameterDefaults(parameterSchema, params));

    expect(cleared.root).toBe(1);
    expect(cleared.early).toBe('');
    expect(cleared.late).toBe('keep-me');
  });
});
