// Datos 2026 demo runner: drives the real DocRouter UI from steps.yaml.
//
//   node run-demo.ts                 # live, visible browser window
//   node run-demo.ts --record        # headless, records out/demo-<ts>.webm + timeline
//   node run-demo.ts --loop          # live, reset + run forever (booth mode)
//   node run-demo.ts --from 12       # start at step 12 (debugging; skips earlier steps)
//   node run-demo.ts --only 12-15    # run a range of steps
//
// Run `python reset.py` before each pass (--loop does it for you).

import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import puppeteer from 'puppeteer';
import type { Browser, ElementHandle, Page } from 'puppeteer';
import yaml from 'js-yaml';
import { OVERLAY_JS } from './overlay.ts';
import { titleCardHtml, FIT_TITLE_JS } from './title-card.ts';
import type { TitleCard } from './title-card.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, '../../..');

// ---------------------------------------------------------------- config

type Action = Record<string, any>;
type Step = { part: string; caption: string; actions: Action[]; hold?: number };
type Doc = { config: any; steps: Step[] };

const doc = yaml.load(fs.readFileSync(path.join(HERE, 'steps.yaml'), 'utf8')) as Doc;
const cfg = doc.config;
const ins = cfg.insurance;

const args = process.argv.slice(2);
const flag = (name: string) => args.includes(`--${name}`);
const opt = (name: string) => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 ? args[i + 1] : undefined;
};
const RECORD = flag('record');
const LOOP = flag('loop');
const SHOTS = flag('shots');   // screenshot after every step into out/
const HEADLESS = RECORD || flag('headless');
const range = (() => {
  if (opt('only')) {
    const [a, b] = opt('only')!.split('-').map(Number);
    return [a, b ?? a];
  }
  return [Number(opt('from') ?? 0), Infinity];
})();

function loadEnv(): Record<string, string> {
  const out: Record<string, string> = {};
  for (const f of [path.join(REPO, '.env'), path.join(HERE, '.env')]) {
    if (!fs.existsSync(f)) continue;
    for (const line of fs.readFileSync(f, 'utf8').split('\n')) {
      const m = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$/);
      if (m) out[m[1]] = m[2].replace(/^["']|["']$/g, '');
    }
  }
  return { ...out, ...Object.fromEntries(Object.entries(process.env).filter(([k]) => k.startsWith('DEMO_'))) } as Record<string, string>;
}
const env = loadEnv();
if (!env.DEMO_EMAIL || !env.DEMO_PASSWORD) throw new Error(`DEMO_EMAIL / DEMO_PASSWORD missing; see ${path.join(HERE, '.env')}`);

const vars: Record<string, string> = {
  ins: ins.org_id,
  test: cfg.test.org_id,
  flow: cfg.test.surgery_flow_id,
  home_case: ins.home_claim_case_id,
  home_fnol: ins.home_fnol_doc_id,
};
const fill = (s: string) => s.replace(/\{(\w+)\}/g, (_, k) => {
  if (!(k in vars)) throw new Error(`Unknown template variable {${k}}`);
  return vars[k];
});

// ---------------------------------------------------------------- helpers

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const log = (...a: unknown[]) => console.log(new Date().toISOString().slice(11, 19), ...a);

function resolveChrome(): string | undefined {
  const candidates = [
    process.env.PUPPETEER_EXECUTABLE_PATH,
    (() => { try { return puppeteer.executablePath(); } catch { return undefined; } })(),
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
  ];
  return candidates.find((p): p is string => typeof p === 'string' && fs.existsSync(p));
}



// ---------------------------------------------------------------- the runner

class Demo {
  page!: Page;
  browser!: Browser;
  caption = { part: '', text: '', compress: false };
  cursor = { x: 960, y: 540 };
  t0 = 0;
  timeline: { step: number; part: string; caption: string; start: number; end: number; waits: [number, number][] }[] = [];
  currentWaits: [number, number][] = [];
  uploadedDocId = '';

  now() { return (Date.now() - this.t0) / 1000; }

  async launch() {
    this.browser = await puppeteer.launch({
      executablePath: resolveChrome(),
      headless: HEADLESS,
      defaultViewport: HEADLESS ? cfg.viewport : null,
      args: [
        `--window-size=${cfg.viewport.width},${cfg.viewport.height}`,
        ...(HEADLESS ? [] : ['--start-fullscreen', '--disable-infobars']),
        '--no-default-browser-check',
      ],
      ignoreDefaultArgs: ['--enable-automation'],
    });
    this.page = (await this.browser.pages())[0] ?? (await this.browser.newPage());
    this.page.setDefaultTimeout(20000);
    await this.page.evaluateOnNewDocument(OVERLAY_JS);
  }

  async login() {
    const p = this.page;
    await p.goto(`${cfg.base_url}/auth/signin`, { waitUntil: 'networkidle0' });
    await p.type('#email', env.DEMO_EMAIL);
    await p.type('#password', env.DEMO_PASSWORD);
    await Promise.all([p.waitForNavigation({ waitUntil: 'networkidle0' }), p.click('button[type=submit]')]);
    if (p.url().includes('/auth/signin')) throw new Error('Login failed; run `python reset.py --setup`');
    vars.kb = await this.lookupKbId();
  }

  /** Call the API from the page, using the browser session cookie. */
  async api(pathname: string, init: RequestInit = {}): Promise<any> {
    return this.page.evaluate(async (url: string, i: RequestInit) => {
      const r = await fetch(url, { ...i, credentials: 'include', headers: { 'Content-Type': 'application/json' } });
      if (!r.ok) throw new Error(`${r.status} ${url}`);
      return r.json();
    }, `${cfg.api_url}${pathname}`, init as any);
  }

  async lookupKbId() {
    const r = await this.api(`/v0/orgs/${ins.org_id}/knowledge-bases`);
    const kb = r.knowledge_bases.find((k: any) => k.name === ins.kb.name);
    if (!kb) throw new Error(`Knowledge base '${ins.kb.name}' missing; run \`python reset.py --setup\``);
    return kb.kb_id;
  }

  async setCaption(c: Partial<typeof this.caption>) {
    Object.assign(this.caption, c);
    await this.page.evaluate((cap) => (window as any).__demo?.caption(cap), this.caption).catch(() => {});
  }

  /** Mark a slow wait: shown as "sped up" while recording, and logged for postprocess. */
  async compressed<T>(fn: () => Promise<T>): Promise<T> {
    const start = this.now();
    if (RECORD) await this.setCaption({ compress: true });
    try {
      return await fn();
    } finally {
      if (RECORD) await this.setCaption({ compress: false });
      this.currentWaits.push([start, this.now()]);
    }
  }

  // ------------------------------------------------ element finding

  async findByText(selector: string, text: string, opts: { exact?: boolean; all?: boolean; timeout?: number } = {}): Promise<ElementHandle<Element>[]> {
    const exact = opts.exact ?? true;
    const deadline = Date.now() + (opts.timeout ?? 20) * 1000;
    while (Date.now() < deadline) {
      const handles = await this.page.$$(selector);
      const hits: ElementHandle<Element>[] = [];
      for (const h of handles) {
        const ok = await h.evaluate((el, t, ex) => {
          const e = el as HTMLElement;
          if (!e.offsetParent && getComputedStyle(e).position !== 'fixed') return false;
          const s = (e.innerText || e.textContent || '').trim();
          return ex ? s === t : s.includes(t);
        }, text, exact);
        if (ok) hits.push(h);
        if (ok && !opts.all) return hits;
      }
      if (hits.length) return hits;
      await sleep(250);
    }
    throw new Error(`No visible ${selector} with text "${text}"`);
  }

  async resolve(a: Action): Promise<ElementHandle<Element>> {
    if (a.xpath) return (await this.page.waitForSelector(`xpath/${a.xpath}`, { visible: true }))!;
    if (a.text) {
      const sel = a.selector ? fill(a.selector) : 'a,button,[role=tab],[role=menuitem],label,span,div';
      // Prefer the innermost match so a click lands on the label, not its container.
      const hits = await this.findByText(sel, a.text, { exact: a.exact ?? true, all: true, timeout: a.timeout });
      return a.first ? hits[0] : hits[hits.length - 1];
    }
    return (await this.page.waitForSelector(fill(a.selector), { visible: true }))!;
  }

  async moveCursorTo(el: ElementHandle<Element>) {
    await el.evaluate((e) => e.scrollIntoView({ block: 'center', behavior: 'instant' as ScrollBehavior }));
    const box = await el.boundingBox();
    if (!box) return null;
    const x = box.x + box.width / 2, y = box.y + box.height / 2;
    this.cursor = { x, y };
    await this.page.evaluate((x, y) => { (window as any).__demoCursor = { x, y }; (window as any).__demo?.cursor(x, y, false); }, x, y);
    await sleep(500);
    return { x, y };
  }

  async click(el: ElementHandle<Element>) {
    const pt = await this.moveCursorTo(el);
    await this.page.evaluate((x, y) => (window as any).__demo?.cursor(x, y, true), this.cursor.x, this.cursor.y);
    if (pt) await this.page.mouse.click(pt.x, pt.y); else await el.click();
    await this.page.evaluate((x, y) => (window as any).__demo?.cursor(x, y, false), this.cursor.x, this.cursor.y);
    await sleep(400);
  }

  async highlight(els: ElementHandle<Element>[], ms: number, row = false) {
    const rects = [];
    // Bring the (last) target into view inside whatever pane scrolls it.
    await els[els.length - 1]?.evaluate((e) => e.scrollIntoView({ block: 'center', behavior: 'smooth' }));
    await sleep(700);
    for (const el of els) {
      const target = row ? ((await el.evaluateHandle((e) => (e as HTMLElement).closest('[role=treeitem],tr,li,[class*="row"]') ?? e.parentElement ?? e)) as ElementHandle<Element>) : el;
      const b = await target.boundingBox();
      if (b && b.width > 0) rects.push({ x: b.x, y: b.y, w: b.width, h: b.height });
    }
    if (rects.length) await this.page.evaluate((r, m) => (window as any).__demo?.highlight(r, m), rects, ms);
    await sleep(Math.min(ms, 2500));
    if (SHOTS) await this.page.screenshot({ path: path.join(HERE, "out", `hl-${Date.now()}.png`) });
  }

  async goto(url: string) {
    await this.page.goto(url, { waitUntil: 'networkidle0', timeout: 60000 });
    await this.setCaption({});
  }

  // ------------------------------------------------ actions

  async run(a: Action) {
    const [name, arg] = Object.entries(a)[0] as [string, any];
    const p = this.page;
    switch (name) {
      case 'goto':
        return this.goto(cfg.base_url + fill(arg));
      case 'reload':
        await p.reload({ waitUntil: 'networkidle0' });
        return this.setCaption({});
      case 'pause':
        return sleep(Number(arg) * 1000);
      case 'click':
        return this.click(await this.resolve(arg));
      case 'type': {
        const el = await this.resolve({ selector: arg.selector });
        await this.click(el);
        await el.type(arg.text, { delay: arg.delay ?? 28 });
        return sleep(400);
      }
      case 'press':
        await p.keyboard.press(arg);
        return sleep(300);
      case 'wait_for': {
        const timeout = (arg.timeout ?? 20) * 1000;
        const fn = async () => {
          if (!arg.text) return p.waitForSelector(fill(arg.selector), { visible: true, timeout });
          // `fail_text` ends the wait early (e.g. a flow run that errored) instead of timing out.
          const h = await p.waitForFunction((t: string, f: string | null) => {
            const body = document.body.innerText;
            return body.includes(t) ? 'ok' : f && body.includes(f) ? 'fail' : false;
          }, { timeout }, arg.text, arg.fail_text ?? null);
          if ((await h.jsonValue()) === 'fail') throw new Error(`Saw "${arg.fail_text}" while waiting for "${arg.text}"`);
        };
        return timeout > 20000 ? this.compressed(fn) : fn();
      }
      case 'highlight': {
        const els = arg.text
          ? await this.findByText(arg.selector ?? '*', arg.text, { exact: !arg.contains, all: !!arg.all })
          : [await this.resolve({ selector: arg.selector })];
        // For text matches, keep the innermost elements only.
        const inner = arg.text ? await this.innermost(els) : els;
        return this.highlight(arg.all ? inner : inner.slice(-1), arg.ms ?? 2500, !!arg.row);
      }
      case 'scroll_to_bottom':
        return p.evaluate(() => document.querySelectorAll('*').forEach((e) => {
          const el = e as HTMLElement;
          if (el.scrollHeight > el.clientHeight + 20 && /(auto|scroll)/.test(getComputedStyle(el).overflowY)) el.scrollTop = el.scrollHeight;
        }));
      case 'upload': {
        const input = (await p.$('input[type=file]')) as ElementHandle<HTMLInputElement>;
        await input.uploadFile(path.join(HERE, arg.file));
        return sleep(1200);
      }
      case 'title_card':
        return this.titleCard(arg);
      case 'goto_api_docs':
        await this.goto(`${cfg.api_url}/docs`);
        await p.waitForSelector('.swagger-ui .opblock-tag', { timeout: 30000 }).catch(() => {});
        await sleep(1500);
        return this.scrollTo('#operations-tag-documents');
      case 'scroll_to':
        return this.scrollTo(arg);
      case 'preapprove_agent_tools':
        return p.evaluate((o: string, d: string, t: string[]) => {
          localStorage.setItem(`agent-auto-approved-tools-${o}-${d}`, JSON.stringify(t));
        }, ins.org_id, ins.home_fnol_doc_id, ins.agent_preapproved_tools);
      case 'wait_agent':
        return this.compressed(() => this.waitAgent((arg.timeout ?? 240) * 1000));
      case 'expand_extraction': {
        // The collapsed result row shows a one-line preview ("claim_number: … · policy_number: …").
        await sleep(800);
        const previews = await this.findByText('[role=tabpanel] *', 'claim_number:', { exact: false, all: true });
        const inner = await this.innermost(previews);
        await this.click(inner[0]);
        return sleep(1500);
      }
      case 'click_agent_tag': {
        const tags = (await this.api(`/v0/orgs/${ins.org_id}/tags?limit=100`)).tags as { name: string }[];
        const agentTag = tags.find((t) => !ins.baseline_tags.includes(t.name));
        if (!agentTag) throw new Error('No agent-created tag found; did Part 2 run?');
        vars.agent_tag = agentTag.name;
        return this.click(await this.resolve({ selector: 'label, span', text: agentTag.name }));
      }
      case 'open_uploaded_doc': {
        const deadline = Date.now() + (arg.timeout ?? 60) * 1000;
        while (Date.now() < deadline) {
          const r = await this.api(`/v0/orgs/${ins.org_id}/documents?limit=50&name_search=${encodeURIComponent(ins.upload_file_name)}`);
          const d = r.documents.find((x: any) => x.document_name === ins.upload_file_name);
          if (d) { this.uploadedDocId = d.id; break; }
          await sleep(1000);
        }
        if (!this.uploadedDocId) throw new Error('Uploaded document not found');
        return this.goto(`${cfg.base_url}/orgs/${ins.org_id}/docs/${this.uploadedDocId}`);
      }
      case 'wait_extraction':
        return this.compressed(async () => {
          const deadline = Date.now() + (arg.timeout ?? 180) * 1000;
          while (Date.now() < deadline) {
            const txt = await p.evaluate(() => (document.querySelector('[role=tabpanel]') as HTMLElement | null)?.innerText ?? '');
            if (/claim_number/i.test(txt) && !/Not run yet|Running|Processing|Loading/i.test(txt)) return;
            await sleep(4000);
            await p.reload({ waitUntil: 'networkidle0' });
            await this.setCaption({});
          }
          throw new Error('Extraction on the uploaded document did not finish');
        });
      case 'select_kb_model': {
        await p.waitForSelector('select');
        await p.select('select', ins.kb.chat_model);
        return sleep(500);
      }
      case 'wait_gone': {
        // Wait until no visible element matches (e.g. the chat's Cancel button while it answers).
        return this.compressed(async () => {
          await sleep(1500);
          const deadline = Date.now() + (arg.timeout ?? 90) * 1000;
          while (Date.now() < deadline) {
            const still = await p.evaluate((sel: string, t: string) => [...document.querySelectorAll(sel)]
              .some((e) => (e as HTMLElement).offsetParent !== null && (e as HTMLElement).innerText.trim() === t), arg.selector, arg.text);
            if (!still) return;
            await sleep(500);
          }
          throw new Error(`"${arg.text}" still visible after ${arg.timeout ?? 90}s`);
        });
      }
      case 'wait_stable':
        return this.compressed(() => this.waitStable((arg.timeout ?? 90) * 1000, (arg.quiet ?? 4) * 1000));
      case 'open_node': {
        const node = await this.findByText('.react-flow__node', arg, { exact: false });
        await this.moveCursorTo(node[0]);
        await node[0].evaluate((e) => e.dispatchEvent(new MouseEvent('dblclick', { bubbles: true, cancelable: true })));
        await p.waitForSelector('[role=dialog]', { visible: true });
        return sleep(1200);
      }
      case 'close_panel': {
        const btn = await p.$('[role=dialog] button[aria-label="Close"], [role=dialog] button[title="Close"]');
        if (btn) await this.click(btn); else await p.keyboard.press('Escape');
        return sleep(600);
      }
      case 'output_view': {
        // The OUTPUT pane is the right-most set of Schema/Table/JSON/Binary toggles in the panel.
        const btns = await this.findByText('[role=dialog] button', arg, { exact: true, all: true });
        return this.click(btns[btns.length - 1]);
      }
      case 'toggle_output_row': {
        const rows = await this.findByText('[role=dialog] *', arg, { exact: true, all: true });
        const inner = await this.innermost(rows);
        return this.click(inner[inner.length - 1]);
      }
      default:
        throw new Error(`Unknown action '${name}'`);
    }
  }

  async scrollTo(selector: string) {
    await this.page.evaluate((s: string) => document.querySelector(s)?.scrollIntoView({ block: 'start', behavior: 'smooth' }), selector);
    return sleep(1500);
  }

  async innermost(els: ElementHandle<Element>[]) {
    if (els.length < 2) return els;
    const keepIdx: number[] = await this.page.evaluate(
      (...nodes: Element[]) => nodes.map((n, i) => (nodes.some((o) => o !== n && n.contains(o)) ? -1 : i)).filter((i) => i >= 0),
      ...els,
    );
    return keepIdx.length ? keepIdx.map((i) => els[i]) : els;
  }

  async waitAgent(timeout: number) {
    const p = this.page;
    await p.waitForSelector('button[title="Stop"]', { timeout: 15000 }).catch(() => {});
    const deadline = Date.now() + timeout;
    while (Date.now() < deadline) {
      // Approve any tool the config did not pre-approve, so the run never stalls.
      const approve = await p.$('xpath///button[normalize-space(.)="Approve"]');
      if (approve) { log('  approving an extra tool call'); await this.click(approve); }
      if (!(await p.$('button[title="Stop"]'))) return;
      await sleep(1000);
    }
    throw new Error('Agent did not finish in time');
  }

  async waitStable(timeout: number, quiet: number) {
    const deadline = Date.now() + timeout;
    await sleep(2000);
    let last = '', since = Date.now();
    while (Date.now() < deadline) {
      const txt = await this.page.evaluate(() => (document.querySelector('main') ?? document.body).textContent ?? '');
      if (txt !== last) { last = txt; since = Date.now(); }
      else if (Date.now() - since >= quiet) return;
      await sleep(500);
    }
  }

  /**
   * Full-screen title card in the series design (same background, fonts and layout as the
   * video poster, see docrouter.github.io/_brand/demo-poster). The caption bar is drawn on top.
   */
  async titleCard(arg: TitleCard) {
    await this.page.goto('about:blank');
    await this.page.setContent(titleCardHtml(arg));
    await this.page.evaluate(() => document.fonts.ready);
    await this.page.evaluate(FIT_TITLE_JS);
    // setContent replaced the document, so mount the overlay again.
    await this.page.evaluate(() => { delete (window as any).__demo; });
    await this.page.evaluate(OVERLAY_JS);
    await this.page.evaluate(() => { const c = document.getElementById('__demo_cursor'); if (c) c.style.display = 'none'; });
    await this.setCaption({});
  }

  // ------------------------------------------------ main loop

  async runSteps() {
    for (const [i, step] of doc.steps.entries()) {
      if (i < range[0] || i > range[1]) continue;
      const start = this.now();
      this.currentWaits = [];
      log(`step ${i} [${step.part}] ${step.caption.slice(0, 70)}…`);
      await this.setCaption({ part: step.part, text: step.caption });
      for (const a of step.actions ?? []) {
        try {
          await this.run(a);
        } catch (e) {
          log(`  FAILED ${JSON.stringify(a)}: ${(e as Error).message}`);
          await this.page.screenshot({ path: path.join(HERE, 'out', `fail-step${i}.png`) }).catch(() => {});
          throw e;
        }
      }
      // Keep the caption up long enough to read, not counting compressed waits.
      const waited = this.currentWaits.reduce((s, [a, b]) => s + (b - a), 0);
      const minRead = step.caption.split(/\s+/).length / (cfg.reading_words_per_second ?? 3);
      const shown = this.now() - start - waited;
      await sleep(Math.max((step.hold ?? 0), minRead - shown, 0) * 1000);
      if (SHOTS) await this.page.screenshot({ path: path.join(HERE, 'out', `step-${String(i).padStart(2, '0')}.png`) });
      this.timeline.push({ step: i, part: step.part, caption: step.caption, start, end: this.now(), waits: this.currentWaits });
    }
  }
}

function reset() {
  log('reset.py');
  const py = fs.existsSync(path.join(REPO, '.venv/bin/python')) ? path.join(REPO, '.venv/bin/python') : 'python3';
  const r = spawnSync(py, [path.join(HERE, 'reset.py')], { stdio: 'inherit', cwd: REPO });
  if (r.status !== 0) throw new Error('reset.py failed');
}

async function once(record: boolean) {
  const demo = new Demo();
  await demo.launch();
  fs.mkdirSync(path.join(HERE, 'out'), { recursive: true });
  const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
  try {
    await demo.login();
    let recorder: Awaited<ReturnType<Page['screencast']>> | undefined;
    if (record) {
      await demo.page.goto('about:blank');
      recorder = await demo.page.screencast({ path: path.join(HERE, 'out', `demo-${stamp}.webm`) as `${string}.webm`, fps: 30, quality: 20 });
    }
    demo.t0 = Date.now();
    await demo.runSteps();
    await recorder?.stop();
    const tl = path.join(HERE, 'out', `demo-${stamp}.timeline.json`);
    fs.writeFileSync(tl, JSON.stringify({ compress_speed: cfg.compress_speed, steps: demo.timeline }, null, 1));
    log(`done in ${demo.now().toFixed(0)}s${record ? ` -> out/demo-${stamp}.webm (+ timeline); run: node postprocess.ts out/demo-${stamp}.webm` : ''}`);
  } finally {
    await demo.browser.close();
  }
}

if (LOOP) {
  for (;;) {
    try { reset(); await once(false); } catch (e) { log(`run failed: ${(e as Error).message}; retrying in 10s`); }
    await sleep(10000);
  }
} else {
  await once(RECORD);
}
