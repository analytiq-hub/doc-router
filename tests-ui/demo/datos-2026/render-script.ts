// Print the presenter script (the captions in steps.yaml) as Markdown.
//   node render-script.ts > script.md

import fs from 'node:fs';
import yaml from 'js-yaml';

const doc = yaml.load(fs.readFileSync(new URL('steps.yaml', import.meta.url), 'utf8')) as {
  steps: { part: string; caption: string; actions: Record<string, unknown>[] }[];
};

const screen = (actions: Record<string, unknown>[]) =>
  actions
    .map((a) => {
      const [k, v] = Object.entries(a)[0];
      if (k === 'goto') return `open ${v}`;
      if (k === 'click') return `click ${(v as any).text ?? (v as any).selector ?? 'button'}`;
      if (k === 'type') return `type "${(v as any).text}"`;
      if (k === 'open_node') return `open node "${v}"`;
      if (k === 'output_view') return `${v} view`;
      if (k === 'title_card') return `title card: ${(v as any).heading}`;
      if (k === 'goto_api_docs') return 'Swagger /docs';
      if (k === 'upload') return 'upload FNOL copy';
      if (k === 'wait_agent') return 'agent works (~80s live)';
      if (k === 'wait_extraction') return 'extraction runs (~30s live)';
      return null;
    })
    .filter(Boolean)
    .join(' → ');

let out = '# DocRouter demo: presenter script\n\nGenerated from `steps.yaml`. Edit the captions there, not here.\n';
let last = '';
for (const [i, s] of doc.steps.entries()) {
  if (s.part !== last) out += `\n## ${s.part}\n\n`;
  last = s.part;
  const sc = screen(s.actions ?? []);
  out += `${i}. ${s.caption}${sc ? `\n   _Screen: ${sc}_` : ''}\n`;
}
process.stdout.write(out);
