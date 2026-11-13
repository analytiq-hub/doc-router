import type { JsonValue } from '@docrouter/sdk';

export function resultContainerPaths(value: JsonValue, path = ''): string[] {
  if (Array.isArray(value)) {
    return [
      path,
      ...value.flatMap((item, index) =>
        item !== null && typeof item === 'object'
          ? resultContainerPaths(item, `${path}[${index}]`)
          : [],
      ),
    ];
  }
  if (value !== null && typeof value === 'object') {
    return [
      path,
      ...Object.entries(value).flatMap(([key, child]) =>
        child !== null && typeof child === 'object'
          ? resultContainerPaths(child, path ? `${path}.${key}` : key)
          : [],
      ),
    ];
  }
  return [];
}

/** Keep short, shallow values readable; collapse structures that would dominate a narrow panel. */
export function resultContainerStartsCollapsed(value: JsonValue, level: number): boolean {
  if (level === 0) return false;
  if (Array.isArray(value)) {
    const hasStructuredItems = value.some((item) => item !== null && typeof item === 'object');
    return hasStructuredItems || value.length > 3;
  }
  if (value !== null && typeof value === 'object') {
    return level > 1 || Object.keys(value).length > 4;
  }
  return false;
}

type Leaf = string | number | boolean | null;

const isLeafValue = (value: JsonValue | undefined): value is Leaf =>
  value === null || typeof value !== 'object';

const isBlank = (value: JsonValue | undefined) => value === null || value === undefined || value === '';

/** Numbers, and strings that read as amounts: "40.00", "$1,200", "(15.5)", "12%". */
const looksNumeric = (value: JsonValue) =>
  typeof value === 'number' ||
  (typeof value === 'string' && /^[-+(]?\s?[$€£¥]?\s?\d[\d,.]*\s?%?\)?$/.test(value.trim()));

const oneLine = (value: Leaf) => String(value).replace(/\s+/g, ' ').trim();

/**
 * One-line stand-in for an object inside a list: its first text field, plus its last
 * numeric field (usually the amount) when there is one.
 */
export function resultItemSummary(item: { [key: string]: JsonValue }): {
  title: string | null;
  value: string | null;
} {
  const leaves = Object.entries(item).filter(
    (entry): entry is [string, Leaf] => isLeafValue(entry[1]) && !isBlank(entry[1]),
  );
  const titleEntry =
    leaves.find(([, value]) => typeof value === 'string' && !looksNumeric(value)) ?? leaves[0];
  const valueEntry = [...leaves]
    .reverse()
    .find(([key, value]) => key !== titleEntry?.[0] && looksNumeric(value));
  return {
    title: titleEntry ? oneLine(titleEntry[1]) : null,
    value: valueEntry ? oneLine(valueEntry[1]) : null,
  };
}

/** Text for a table cell or summary: leaves as written, containers as a count. */
export function resultCellText(value: JsonValue | undefined): string {
  if (isBlank(value)) return '—';
  if (isLeafValue(value)) return String(value);
  if (Array.isArray(value)) return value.length === 1 ? '1 item' : `${value.length} items`;
  const count = Object.keys(value as object).length;
  return count === 1 ? '1 field' : `${count} fields`;
}

type PathStep = string | number;

/** Split a path written the way the result tree builds them: `a.b[2].c` → a, b, 2, c. */
function parseResultPath(path: string): PathStep[] {
  if (!path) return [];
  return path.split('.').flatMap((part): PathStep[] => {
    const match = /^(.*?)((?:\[\d+\])*)$/.exec(part);
    if (!match) return [part];
    return [
      ...(match[1] ? [match[1]] : []),
      ...[...match[2].matchAll(/\[(\d+)\]/g)].map((m) => Number(m[1])),
    ];
  });
}

function child(node: JsonValue | undefined, step: PathStep): JsonValue | undefined {
  if (node === null || node === undefined || typeof node !== 'object') return undefined;
  if (Array.isArray(node)) return typeof step === 'number' ? node[step] : undefined;
  return typeof step === 'string' ? node[step] : undefined;
}

export function resultValueAtPath(root: JsonValue, path: string): JsonValue | undefined {
  return parseResultPath(path).reduce<JsonValue | undefined>(child, root);
}

/** Replace the value at `path` in place. False when the path does not lead to an existing slot. */
export function setResultValueAtPath(root: JsonValue, path: string, value: JsonValue): boolean {
  const steps = parseResultPath(path);
  const last = steps.pop();
  if (last === undefined) return false;
  const parent = steps.reduce<JsonValue | undefined>(child, root);
  if (parent === null || parent === undefined || typeof parent !== 'object') return false;
  if (Array.isArray(parent)) {
    if (typeof last !== 'number' || last >= parent.length) return false;
    parent[last] = value;
    return true;
  }
  if (typeof last !== 'string') return false;
  parent[last] = value;
  return true;
}

/** Remove the list item at `path` (which must end in an index) in place. */
export function removeResultItemAtPath(root: JsonValue, path: string): boolean {
  const steps = parseResultPath(path);
  const last = steps.pop();
  const parent = steps.reduce<JsonValue | undefined>(child, root);
  if (typeof last !== 'number' || !Array.isArray(parent) || last >= parent.length) return false;
  parent.splice(last, 1);
  return true;
}

/** An empty value with the same shape as `sample`, for a newly added list item. */
export function blankResultValue(sample: JsonValue): JsonValue {
  if (typeof sample === 'string') return '';
  if (typeof sample === 'number') return 0;
  if (typeof sample === 'boolean') return false;
  if (sample === null) return null;
  if (Array.isArray(sample)) return [];
  return Object.fromEntries(Object.entries(sample).map(([key, value]) => [key, blankResultValue(value)]));
}

/**
 * A sample item for the list at `path`: its own first item, or, when it is empty, the first
 * item of the same list under a sibling (`jobs[1].projects` borrows from `jobs[0].projects`).
 */
export function resultListSample(root: JsonValue, path: string): JsonValue | undefined {
  const own = resultValueAtPath(root, path);
  if (Array.isArray(own) && own.length > 0) return own[0];
  const search = (node: JsonValue | undefined, steps: PathStep[]): JsonValue | undefined => {
    if (steps.length === 0) return Array.isArray(node) && node.length > 0 ? node[0] : undefined;
    const [step, ...rest] = steps;
    if (typeof step === 'number' && Array.isArray(node)) {
      for (const item of node) {
        const found = search(item, rest);
        if (found !== undefined) return found;
      }
      return undefined;
    }
    return search(child(node, step), rest);
  };
  return search(root, parseResultPath(path));
}

/** Keep a corrected value in the type it had: numbers stay numbers, booleans stay booleans. */
export function coerceEditedValue(original: JsonValue | undefined, text: string): JsonValue {
  const trimmed = text.trim();
  if (typeof original === 'number' && trimmed !== '' && Number.isFinite(Number(trimmed))) {
    return Number(trimmed);
  }
  if (typeof original === 'boolean' && /^(true|false)$/i.test(trimmed)) {
    return trimmed.toLowerCase() === 'true';
  }
  if (original === null && trimmed === '') return null;
  return text;
}

export type ResultCollapsibleNode = { path: string; defaultOpen: boolean };

const isObjectValue = (value: JsonValue | undefined): value is { [key: string]: JsonValue } =>
  value !== null && typeof value === 'object' && !Array.isArray(value);

/**
 * Every disclosure the results panel draws for `payload`, with whether it starts open. Mirrors the
 * sidebar's layout: top-level fields are level 1, a lone top-level object shows its fields
 * directly, and objects inside lists are summary rows that start closed.
 */
export function resultCollapsibleNodes(payload: { [key: string]: JsonValue }): ResultCollapsibleNode[] {
  const nodes: ResultCollapsibleNode[] = [];

  const fields = (value: { [key: string]: JsonValue }, path: string, level: number) => {
    for (const [key, child] of Object.entries(value)) {
      entry(child, path ? `${path}.${key}` : key, level + 1);
    }
  };

  const entry = (value: JsonValue, path: string, level: number) => {
    if (Array.isArray(value)) {
      if (value.length === 0) return;
      nodes.push({ path, defaultOpen: !resultContainerStartsCollapsed(value, level) });
      value.forEach((item, index) => {
        const itemPath = `${path}[${index}]`;
        if (Array.isArray(item)) {
          entry(item, itemPath, level + 1);
        } else if (isObjectValue(item) && Object.keys(item).length > 0) {
          nodes.push({ path: itemPath, defaultOpen: false });
          fields(item, itemPath, level + 1);
        }
      });
    } else if (isObjectValue(value) && Object.keys(value).length > 0) {
      nodes.push({ path, defaultOpen: !resultContainerStartsCollapsed(value, level) });
      fields(value, path, level);
    }
  };

  const entries = Object.entries(payload);
  if (entries.length === 1) {
    const [key, value] = entries[0];
    if (isObjectValue(value) && Object.keys(value).length > 0) fields(value, key, 0);
    else entry(value, key, 0);
  } else {
    fields(payload, '', 0);
  }
  return nodes;
}
