// Caption bar, part chip, fake cursor and highlight boxes, injected into every page the
// demo shows. Shared by run-demo.ts and render-cards.ts.

/** Overlay (caption bar, part chip, fake cursor, highlight boxes) injected into every page. */
export const OVERLAY_JS = `
(() => {
  if (window.__demo) return;
  const css = \`
    #__demo_cap{position:fixed;box-sizing:border-box;left:50%;bottom:28px;transform:translateX(-50%);max-width:1400px;width:calc(100% - 160px);
      background:rgba(15,23,42,.92);color:#fff;font:500 25px/1.4 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
      padding:18px 28px 20px;border-radius:14px;box-shadow:0 10px 30px rgba(0,0,0,.35);z-index:2147483646;pointer-events:none;
      transition:opacity .25s}
    #__demo_cap .part{display:inline-block;font:700 13px/1 -apple-system,sans-serif;letter-spacing:.08em;text-transform:uppercase;
      color:#93c5fd;margin-bottom:8px}
    #__demo_cap .fast{float:right;font:600 13px/1 -apple-system,sans-serif;color:#fde68a;display:none}
    #__demo_cap.compress .fast{display:inline}
    #__demo_cursor{position:fixed;width:22px;height:22px;margin:-11px 0 0 -11px;border-radius:50%;
      background:rgba(37,99,235,.35);border:2px solid #1d4ed8;z-index:2147483647;pointer-events:none;
      transition:left .45s cubic-bezier(.2,.7,.2,1),top .45s cubic-bezier(.2,.7,.2,1),transform .12s}
    #__demo_cursor.down{transform:scale(.7);background:rgba(37,99,235,.6)}
    .__demo_hl{position:fixed;border:4px solid #f59e0b;border-radius:10px;box-shadow:0 0 0 6px rgba(245,158,11,.25);
      z-index:2147483645;pointer-events:none;animation:__demo_pulse 1.2s ease-in-out infinite}
    @keyframes __demo_pulse{50%{box-shadow:0 0 0 12px rgba(245,158,11,.12)}}\`;
  const mount = () => {
    if (document.getElementById('__demo_style')) return;
    const st = document.createElement('style'); st.id = '__demo_style'; st.textContent = css;
    (document.head || document.documentElement).appendChild(st);
    const cap = document.createElement('div'); cap.id = '__demo_cap'; cap.style.opacity = '0';
    cap.innerHTML = '<span class="fast">sped up</span><div class="part"></div><div class="txt"></div>';
    document.documentElement.appendChild(cap);
    const cur = document.createElement('div'); cur.id = '__demo_cursor';
    cur.style.left = (window.__demoCursor?.x ?? innerWidth / 2) + 'px'; cur.style.top = (window.__demoCursor?.y ?? innerHeight / 2) + 'px';
    document.documentElement.appendChild(cur);
    let s = null;
    try { s = sessionStorage.getItem('__demo_caption'); } catch {}
    if (s) window.__demo.caption(JSON.parse(s));
  };
  window.__demo = {
    caption(c) {
      try { sessionStorage.setItem('__demo_caption', JSON.stringify(c)); } catch {}
      const el = document.getElementById('__demo_cap'); if (!el) return;
      el.querySelector('.part').textContent = c.part || '';
      el.querySelector('.txt').textContent = c.text || '';
      el.classList.toggle('compress', !!c.compress);
      el.style.opacity = c.text ? '1' : '0';
    },
    cursor(x, y, down) {
      const el = document.getElementById('__demo_cursor'); if (!el) return;
      el.style.left = x + 'px'; el.style.top = y + 'px'; el.classList.toggle('down', !!down);
    },
    highlight(rects, ms) {
      for (const r of rects) {
        const d = document.createElement('div'); d.className = '__demo_hl';
        Object.assign(d.style, { left: r.x - 6 + 'px', top: r.y - 6 + 'px', width: r.w + 12 + 'px', height: r.h + 12 + 'px' });
        document.documentElement.appendChild(d); setTimeout(() => d.remove(), ms);
      }
    },
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount); else mount();
})();`;
