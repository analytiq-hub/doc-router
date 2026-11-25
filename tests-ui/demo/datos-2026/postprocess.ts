// Turn a raw recording into the booth MP4: waits marked in the timeline (agent thinking,
// extraction, flow run) are sped up by `compress_speed`; everything else plays at 1x.
//
//   node postprocess.ts out/demo-<stamp>.webm            # -> out/demo-<stamp>.mp4
//   node postprocess.ts out/demo-<stamp>.webm --speed 8

import fs from 'node:fs';
import { spawnSync } from 'node:child_process';

const [input, ...rest] = process.argv.slice(2);
if (!input || !input.endsWith('.webm')) {
  console.error('usage: node postprocess.ts out/demo-<stamp>.webm [--speed N]');
  process.exit(1);
}
const tlPath = input.replace(/\.webm$/, '.timeline.json');
const tl = JSON.parse(fs.readFileSync(tlPath, 'utf8')) as {
  compress_speed: number;
  steps: { waits: [number, number][] }[];
};
const si = rest.indexOf('--speed');
const speed = si >= 0 ? Number(rest[si + 1]) : tl.compress_speed || 6;

// Build [start, end, speed] segments that cover the whole video.
const waits = tl.steps.flatMap((s) => s.waits).filter(([a, b]) => b - a > 1.5).sort((x, y) => x[0] - y[0]);
const probe = spawnSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', input], { encoding: 'utf8' });
const duration = Number(probe.stdout.trim()) || Infinity;
const segs: [number, number, number][] = [];
let t = 0;
for (const [a, b] of waits) {
  // Keep the first and last half second of each wait at normal speed so transitions read.
  const s = Math.max(a + 0.5, t), e = Math.min(b - 0.5, duration);
  if (e - s < 1) continue;
  if (s > t) segs.push([t, s, 1]);
  segs.push([s, e, speed]);
  t = e;
}
segs.push([t, duration, 1]);

const filters = segs.map(([a, b, sp], i) =>
  `[0:v]trim=start=${a.toFixed(3)}${Number.isFinite(b) ? `:end=${b.toFixed(3)}` : ''},setpts=(PTS-STARTPTS)/${sp}[v${i}]`);
const graph = `${filters.join(';')};${segs.map((_, i) => `[v${i}]`).join('')}concat=n=${segs.length}:v=1:a=0[out]`;
const output = input.replace(/\.webm$/, '.mp4');

console.log(`${waits.length} waits sped up ${speed}x; ${segs.length} segments -> ${output}`);
const r = spawnSync('ffmpeg', ['-y', '-i', input, '-filter_complex', graph, '-map', '[out]',
  '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-pix_fmt', 'yuv420p', '-r', '30', '-movflags', '+faststart', output],
{ stdio: 'inherit' });
process.exit(r.status ?? 1);
