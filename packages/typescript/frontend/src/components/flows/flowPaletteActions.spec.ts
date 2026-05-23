import { describe, expect, it } from 'vitest';
import type { FlowNodeType } from '@docrouter/sdk';
import {
  nodeTypeHasPaletteActions,
  paletteActionGroupsForNodeType,
  paletteActionsForNodeType,
} from './flowPaletteActions';

const googleDriveLikeSchema = {
  type: 'object',
  properties: {
    resource: {
      type: 'string',
      enum: ['file', 'fileFolder', 'folder', 'drive'],
      'x-ui-enum-names': ['File', 'File/Folder', 'Folder', 'Shared Drive'],
    },
    operation: {
      type: 'string',
      'x-ui-enum-by': {
        field: 'resource',
        variants: {
          drive: {
            enum: ['create', 'deleteDrive', 'get', 'list', 'update'],
            'x-ui-enum-names': ['Create', 'Delete', 'Get', 'Get Many', 'Update'],
          },
          file: {
            enum: ['copy', 'download', 'upload'],
            'x-ui-enum-names': ['Copy', 'Download', 'Upload'],
          },
          fileFolder: {
            enum: ['search'],
            'x-ui-enum-names': ['Search'],
          },
          folder: {
            enum: ['create', 'share'],
            'x-ui-enum-names': ['Create', 'Share'],
          },
        },
      },
    },
  },
};

function googleDriveNodeType(): FlowNodeType {
  return {
    key: 'flows.google_drive',
    label: 'Google Drive',
    description: 'Access data on Google Drive (experimental).',
    category: 'input',
    palette_group: 'app',
    is_trigger: false,
    min_inputs: 1,
    max_inputs: 1,
    outputs: 1,
    output_labels: ['main'],
    parameter_schema: googleDriveLikeSchema,
    experimental: true,
  };
}

describe('flowPaletteActions', () => {
  it('builds grouped actions for resource/operation schema', () => {
    const nt = googleDriveNodeType();
    expect(nodeTypeHasPaletteActions(nt)).toBe(true);
    const groups = paletteActionGroupsForNodeType(nt);
    expect(groups.map((g) => g.label)).toEqual([
      'FILE ACTIONS',
      'FILE/FOLDER ACTIONS',
      'FOLDER ACTIONS',
      'SHARED DRIVE ACTIONS',
    ]);
    expect(paletteActionsForNodeType(nt)).toHaveLength(11);
    const download = paletteActionsForNodeType(nt).find((a) => a.key === 'file:download');
    expect(download?.label).toBe('Download file');
    expect(download?.parameters).toEqual({ resource: 'file', operation: 'download' });
    const search = paletteActionsForNodeType(nt).find((a) => a.key === 'fileFolder:search');
    expect(search?.label).toBe('Search files and folders');
  });

  it('returns empty for nodes without resource/operation drill-in', () => {
    const nt: FlowNodeType = {
      key: 'flows.http_request',
      label: 'HTTP Request',
      description: '',
      category: 'core',
      is_trigger: false,
      min_inputs: 1,
      max_inputs: 1,
      outputs: 1,
      output_labels: ['main'],
      parameter_schema: { type: 'object', properties: { url: { type: 'string' } } },
    };
    expect(paletteActionsForNodeType(nt)).toEqual([]);
    expect(nodeTypeHasPaletteActions(nt)).toBe(false);
  });

  it('returns empty when only one action exists', () => {
    const nt: FlowNodeType = {
      ...googleDriveNodeType(),
      parameter_schema: {
        type: 'object',
        properties: {
          resource: { type: 'string', enum: ['file'], 'x-ui-enum-names': ['File'] },
          operation: {
            type: 'string',
            'x-ui-enum-by': {
              field: 'resource',
              variants: {
                file: { enum: ['download'], 'x-ui-enum-names': ['Download'] },
              },
            },
          },
        },
      },
    };
    expect(paletteActionsForNodeType(nt)).toEqual([]);
  });
});
