import { describe, expect, it } from 'vitest';
import type { NodeChange } from 'reactflow';
import {
  shouldPushUndoForEdgeChanges,
  shouldPushUndoForNodeChanges,
  isFlowEditorUndoKey,
} from './flowGraphUndo';

describe('shouldPushUndoForNodeChanges', () => {
  it('ignores selection-only changes', () => {
    const changes: NodeChange[] = [{ type: 'select', id: 'a', selected: true }];
    expect(shouldPushUndoForNodeChanges(changes, false)).toBe(false);
  });

  it('suppresses all changes while a drag session is active', () => {
    const duringDrag: NodeChange[] = [
      { type: 'position', id: 'a', position: { x: 3, y: 4 }, dragging: true },
    ];
    expect(shouldPushUndoForNodeChanges(duringDrag, true)).toBe(false);
    expect(shouldPushUndoForNodeChanges([{ type: 'remove', id: 'a' }], true)).toBe(false);
  });

  it('does not push in-flight drag position frames', () => {
    const frame: NodeChange[] = [{ type: 'position', id: 'a', position: { x: 3, y: 4 }, dragging: true }];
    expect(shouldPushUndoForNodeChanges(frame, false)).toBe(false);
  });

  it('pushes keyboard nudge position changes', () => {
    const nudge: NodeChange[] = [{ type: 'position', id: 'a', position: { x: 3, y: 4 }, dragging: false }];
    expect(shouldPushUndoForNodeChanges(nudge, false)).toBe(true);
  });

  it('ignores drag-end marker without position', () => {
    const end: NodeChange[] = [{ type: 'position', id: 'a', dragging: false }];
    expect(shouldPushUndoForNodeChanges(end, false)).toBe(false);
  });

  it('pushes for remove changes', () => {
    const changes: NodeChange[] = [{ type: 'remove', id: 'a' }];
    expect(shouldPushUndoForNodeChanges(changes, false)).toBe(true);
  });
});

describe('shouldPushUndoForEdgeChanges', () => {
  it('ignores selection-only changes', () => {
    expect(shouldPushUndoForEdgeChanges([{ type: 'select', id: 'e1', selected: true }])).toBe(false);
  });

  it('pushes for remove changes', () => {
    expect(shouldPushUndoForEdgeChanges([{ type: 'remove', id: 'e1' }])).toBe(true);
  });
});

describe('isFlowEditorUndoKey', () => {
  it('detects Cmd/Ctrl+Z without shift', () => {
    expect(
      isFlowEditorUndoKey({ metaKey: true, ctrlKey: false, key: 'z', shiftKey: false } as KeyboardEvent),
    ).toBe(true);
    expect(
      isFlowEditorUndoKey({ metaKey: false, ctrlKey: true, key: 'z', shiftKey: false } as KeyboardEvent),
    ).toBe(true);
    expect(
      isFlowEditorUndoKey({ metaKey: true, ctrlKey: false, key: 'z', shiftKey: true } as KeyboardEvent),
    ).toBe(false);
  });
});
