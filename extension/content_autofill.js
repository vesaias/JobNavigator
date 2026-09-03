// extension/content_autofill.js
// In-field AI draft (design section C, overlay revision).
//
// Per the handoff's C2 "overlay, never inject" rule: the draft is NEVER written
// into the host page's textarea while generating. Each field gets a shadow-DOM
// overlay (appended to document.body, positioned over the field box) that draws
// the blue border and renders the streaming draft itself. The real field is left
// untouched until the user clicks Insert. Every field is independent — its own
// affordance, overlay, stream and length override; two can generate at once.
(() => {
  // Presence marker so the dashboard can tell the extension is installed/enabled
  // (its declarativeNetRequest rules strip X-Frame-Options/CSP so postings embed).
  // Set unconditionally, independent of the Autofill toggle.
  try { document.documentElement.setAttribute('data-jn-ext', chrome.runtime.getManifest().version || '1'); } catch (_) {}

  const NAV_ICON = 'data:image/png;base64,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';

  // ── page context extraction ─────────────────────────────────────────────────
  const isAnswerField = (el) => {
    if (!el || el.readOnly || el.disabled) return false;
    if (el.getAttribute && (el.getAttribute('role') === 'combobox' ||
        el.getAttribute('aria-autocomplete') ||
        el.getAttribute('aria-haspopup') === 'listbox')) return false;
    if (el.tagName === 'TEXTAREA' || el.isContentEditable) return true;
    // A long free-text input whose label reads as a question (design C heuristic).
    if (el.tagName === 'INPUT' && (el.type || 'text').toLowerCase() === 'text') {
      const noLimit = !(el.maxLength > 0) || el.maxLength > 200;
      const q = questionFor(el).trim();
      return noLimit && q.endsWith('?');
    }
    return false;
  };

  function questionFor(el) {
    if (el.id) {
      const lab = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (lab) return lab.innerText.trim();
    }
    const ariaId = el.getAttribute && el.getAttribute('aria-labelledby');
    if (ariaId) { const n = document.getElementById(ariaId); if (n) return n.innerText.trim(); }
    if (el.getAttribute && el.getAttribute('aria-label')) return el.getAttribute('aria-label').trim();
    if (el.placeholder) return el.placeholder.trim();
    let p = el.closest('label') || el.parentElement;
    for (let i = 0; p && i < 4; i++, p = p.parentElement) {
      const t = (p.innerText || '').trim();
      if (t && t.length < 300) return t.split('\n')[0].trim();
    }
    return '';
  }

  function pageCompany() {
    for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
      try {
        const j = JSON.parse(s.textContent);
        const o = Array.isArray(j) ? j.find(x => x['@type'] === 'JobPosting') : j;
        if (o && o.hiringOrganization && o.hiringOrganization.name) return o.hiringOrganization.name;
      } catch {}
    }
    const og = document.querySelector('meta[property="og:site_name"]');
    return (og && og.content) || location.hostname.replace(/^www\./, '');
  }

  function pagePosition() {
    for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
      try {
        const j = JSON.parse(s.textContent);
        const o = Array.isArray(j) ? j.find(x => x['@type'] === 'JobPosting') : j;
        if (o && o.title) return o.title;
      } catch {}
    }
    const og = document.querySelector('meta[property="og:title"]');
    return (og && og.content) || document.title;
  }

  const fieldMaxOf = (el) => (el.maxLength && el.maxLength > 0 ? el.maxLength : null);
  const fieldKey = (el) => el.id || el.name || (questionFor(el) ? 'q:' + questionFor(el) : 'af-field');

  function writeToField(el, value) {
    if (el.isContentEditable) {
      el.textContent = value;
      el.dispatchEvent(new Event('input', { bubbles: true }));
    } else {
      const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
      setter.call(el, value);
      el.dispatchEvent(new Event('input', { bubbles: true }));
    }
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }
  const fieldHasContent = (el) => (el.isContentEditable ? el.textContent : el.value).trim().length > 0;

  // Safety net: if a provider ignores the plain-prose instruction and wraps the
  // answer in a ```json fence or a {"answer": "..."} object, unwrap it on done.
  function unwrapAnswer(t) {
    if (!t) return t;
    let s = t.trim();
    const fence = s.match(/^```(?:json)?\s*([\s\S]*?)\s*```$/i);
    if (fence) s = fence[1].trim();
    if (s.startsWith('{')) {
      try { const o = JSON.parse(s); if (o && typeof o.answer === 'string') return o.answer.trim(); } catch (e) { /* not JSON */ }
    }
    return s;
  }

  // ── state ───────────────────────────────────────────────────────────────────
  let enabled = false;
  let DEFAULT_LEN = 250;
  const affs = new Map();       // fieldKey -> { host, node, lbl, el }
  const sessions = new Map();   // fieldKey -> draft session (multiple concurrent)

  chrome.storage.sync.get(['autofillEnabled', 'autofillDefaultLength'], (cfg) => {
    enabled = !!cfg.autofillEnabled;
    DEFAULT_LEN = parseInt(cfg.autofillDefaultLength, 10) || 250;
  });
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== 'sync') return;
    if (changes.autofillDefaultLength) DEFAULT_LEN = parseInt(changes.autofillDefaultLength.newValue, 10) || 250;
    if (changes.autofillEnabled) {
      enabled = !!changes.autofillEnabled.newValue;
      if (!enabled) {
        for (const k of [...sessions.keys()]) teardownSession(k);
        for (const k of [...affs.keys()]) removeAff(k);
      }
    }
  });

  // ── resting affordance ───────────────────────────────────────────────────────
  const AFF_CSS = `
    .rail{position:relative;width:230px;height:26px;pointer-events:none;
          display:flex;justify-content:flex-end;align-items:center}
    .btn{pointer-events:auto;box-sizing:border-box;height:26px;max-width:26px;
         display:flex;flex-direction:row-reverse;align-items:center;overflow:hidden;
         white-space:nowrap;border:1px solid #E4E1DB;background:#fff;border-radius:999px;
         padding:0;cursor:pointer;
         transition:max-width .22s cubic-bezier(.2,.8,.3,1),border-color .2s,box-shadow .2s}
    .btn:hover,.btn:focus-visible{max-width:220px;border-color:oklch(0.82 0.06 255);
         box-shadow:0 2px 10px rgba(37,64,143,0.14);outline:none}
    .icon{width:18px;height:18px;margin:3px;flex:0 0 auto}
    .lbl{font:600 12.5px/1 "Helvetica Neue",Helvetica,Arial,sans-serif;
         color:oklch(0.42 0.14 255);padding:0 6px 0 10px;flex:0 0 auto}`;

  function positionAff(w) {
    const r = w.el.getBoundingClientRect();
    w.host.style.top = `${window.scrollY + r.bottom - 26 - 9}px`;
    w.host.style.left = `${window.scrollX + r.right - 9 - 230}px`;
  }

  function affFor(el) {
    const key = fieldKey(el);
    let w = affs.get(key);
    if (!w) {
      const host = document.createElement('div');
      host.style.cssText = 'position:absolute;z-index:2147483646;width:230px;height:26px;pointer-events:none;';
      const root = host.attachShadow({ mode: 'open' });
      root.innerHTML = `<style>${AFF_CSS}</style>
        <div class="rail">
          <button class="btn" role="button" aria-label="Draft with Navigator">
            <img class="icon" src="${NAV_ICON}" alt="">
            <span class="lbl">Draft with Navigator</span>
          </button>
        </div>`;
      const btn = root.querySelector('.btn');
      btn.addEventListener('mousedown', (ev) => {
        ev.preventDefault(); ev.stopPropagation();
        const cur = affs.get(key);
        if (cur) startDraft(cur.el);
      });
      // The affordance overlays the field's corner, so moving the pointer onto it
      // fires the field's mouseout → the 200ms cleanup would remove it (the field
      // isn't :hover and, unfocused, isn't the activeElement) → it remounts on the
      // next mouseover → a 5Hz blink. Track hover on the affordance itself so
      // cleanup keeps it while the pointer is over it.
      btn.addEventListener('mouseenter', () => { const c = affs.get(key); if (c) c.hovering = true; });
      btn.addEventListener('mouseleave', () => { const c = affs.get(key); if (c) c.hovering = false; });
      document.body.appendChild(host);
      w = { host, node: root.querySelector('.rail'), lbl: root.querySelector('.lbl'), el, key, hovering: false };
      affs.set(key, w);
    }
    w.el = el;
    // "Redraft" once the field already holds content the user owns (design C4).
    w.lbl.textContent = fieldHasContent(el) ? 'Redraft' : 'Draft with Navigator';
    positionAff(w);
    return w;
  }
  function showAff(el) { affFor(el).host.style.display = ''; }
  function removeAff(key) {
    const w = affs.get(key);
    if (w) { w.host.remove(); affs.delete(key); }
  }

  // ── draft overlay (renders the draft itself; host field untouched til Insert) ─
  const OVER_CSS = `
    :host{all:initial}
    *{box-sizing:border-box}
    .fieldbox{position:relative;background:#fff;border:2px solid oklch(0.52 0.15 255);
              overflow:hidden;font:14px "Helvetica Neue",Helvetica,Arial,sans-serif}
    /* Loader lives inside the field box so its overflow:hidden + border-radius clip
       it to the rounded top corners (a host-level bar pokes past the radius). */
    .prog{position:absolute;top:0;left:0;right:0;height:2px;background:oklch(0.94 0.02 255);
          overflow:hidden;z-index:6}
    .prog .run{position:absolute;top:0;height:100%;width:38%;left:-38%;
               background:oklch(0.52 0.15 255);animation:navslide 1.15s ease-in-out infinite}
    .scroll{position:absolute;inset:0;overflow-y:auto;padding:8px 10px}
    .txt{color:#57534C;white-space:pre-wrap;word-break:break-word;margin:0}
    .txt.done{color:#1A1917;animation:navrise .22s ease}
    .caret{display:inline-block;width:1.5px;height:1.05em;background:oklch(0.52 0.15 255);
           vertical-align:text-bottom;margin-left:1px;animation:navblink 1s step-end infinite}
    .skel{padding:12px 10px}
    .skbar{height:9px;border-radius:3px;margin-bottom:9px;
           background:linear-gradient(90deg,rgba(150,150,150,0.14),rgba(150,150,150,0.30) 40%,rgba(150,150,150,0.14) 80%);
           background-size:320px 100%;animation:navshimmer 1.3s linear infinite}
    .bar{background:#FAF9F7;border:1px solid #ECE9E3;border-top:none;border-radius:0 0 7px 7px;
         padding:8px 10px;font:13px "Helvetica Neue",Helvetica,Arial,sans-serif;color:#1A1917}
    .row{display:flex;align-items:center;gap:8px}
    .row2{margin-top:8px;padding-top:8px;border-top:1px solid #ECE9E3}
    button{font:600 12.5px "Helvetica Neue",Helvetica,Arial,sans-serif;border-radius:6px;
           padding:6px 12px;cursor:pointer;border:1px solid #E4E1DB;background:#fff;color:#57534C}
    button:hover{background:#F7F5F1}
    button.primary{background:oklch(0.52 0.15 255);border-color:oklch(0.52 0.15 255);color:#fff}
    button.primary:hover{background:oklch(0.46 0.15 255)}
    button.icon-btn{padding:6px 9px}
    .spin{width:13px;height:13px;border:2px solid #CFCAC2;border-top-color:oklch(0.52 0.15 255);
          border-radius:50%;display:inline-block;animation:navspin .7s linear infinite}
    .drafting{color:#57534C;font-weight:600}
    .err{color:oklch(0.5 0.18 25);font-weight:600}
    .spacer{flex:1 1 auto}
    .count{font:11px ui-monospace,"SF Mono",Menlo,monospace;color:#8A857C}
    .count.over{color:oklch(0.55 0.18 25)}
    .seg{display:inline-flex;background:#F2F0EC;border-radius:6px;padding:2px}
    .seg > *{font:600 11.5px "Helvetica Neue",Helvetica,Arial,sans-serif;border:1px solid transparent;
             background:transparent;color:#57534C;border-radius:5px;padding:4px 9px;cursor:pointer}
    .seg > .on{background:#fff;border-color:oklch(0.82 0.06 255);color:oklch(0.42 0.14 255)}
    .seg input{width:66px;background:transparent;color:#57534C;text-align:center;outline:none;
               font:600 11.5px "Helvetica Neue",Helvetica,Arial,sans-serif;
               -webkit-appearance:none;-moz-appearance:textfield;appearance:none}
    .seg input::-webkit-outer-spin-button,.seg input::-webkit-inner-spin-button{-webkit-appearance:none;margin:0}
    .seg input::placeholder{color:#8A857C}
    .lenlbl{font:11px ui-monospace,"SF Mono",Menlo,monospace;color:#8A857C;margin-right:2px}
    .refine{display:flex;flex-direction:column;gap:8px;margin-top:8px;padding-top:9px;border-top:1px solid #ECE9E3}
    .askpill{display:inline-flex;align-items:center;gap:6px;align-self:flex-start;
             background:oklch(0.97 0.015 255);border:1px solid oklch(0.92 0.03 255);
             color:oklch(0.42 0.14 255);border-radius:999px;padding:3px 5px 3px 10px;
             font:600 11.5px "Helvetica Neue",Helvetica,Arial,sans-serif}
    .askpill .x{width:15px;height:15px;display:inline-flex;align-items:center;justify-content:center;
                border:none;background:transparent;color:oklch(0.42 0.14 255);cursor:pointer;
                border-radius:999px;font-size:13px;line-height:1;padding:0}
    .askpill .x:hover{background:oklch(0.92 0.03 255)}
    .refine .ask{display:flex;gap:8px;align-items:center}
    .refine .askin{flex:1 1 auto;box-sizing:border-box;border:1px solid #E4E1DB;background:#FDFDFC;
                   border-radius:6px;padding:6px 9px;outline:none;color:#1A1917;
                   font:13px "Helvetica Neue",Helvetica,Arial,sans-serif}
    .refine .askin:focus{border-color:oklch(0.82 0.06 255);background:#fff}
    .refine .askin::placeholder{color:#A8A29A}
    .refine .redraft{border:1px solid #E4E1DB;background:#fff;color:#A8A29A;cursor:default}
    .refine .redraft.on{background:oklch(0.52 0.15 255);border-color:oklch(0.52 0.15 255);color:#fff;cursor:pointer}
    .refine .redraft.on:hover{background:oklch(0.46 0.15 255)}
    .twists{display:flex;gap:6px;flex-wrap:wrap}
    .twist{font:600 11.5px "Helvetica Neue",Helvetica,Arial,sans-serif;border:1px solid #E4E1DB;
           background:#fff;color:#57534C;border-radius:999px;padding:4px 11px;cursor:pointer}
    .twist:hover{background:#F7F5F1;border-color:oklch(0.82 0.06 255)}
    .hidden{display:none}
    @keyframes navspin{to{transform:rotate(360deg)}}
    @keyframes navslide{0%{left:-38%}100%{left:100%}}
    @keyframes navshimmer{0%{background-position:-320px 0}100%{background-position:320px 0}}
    @keyframes navblink{50%{opacity:0}}
    @keyframes navrise{from{opacity:.4;transform:translateY(2px)}to{opacity:1;transform:none}}`;

  // Push the page's following content down by the bar's height (see startDraft).
  function reserveSpace(s) {
    try {
      const bar = s.root.querySelector('.bar');
      const h = bar ? bar.getBoundingClientRect().height : 0;
      const need = Math.max(0, h + (s.barGap || 0) - (s.gapBelow || 0) + 8);  // shortfall (+ carded bar gap) + an 8px breathing gap below the bar
      const next = `${s.baseMargin + need}px`;
      if (s.el.style.marginBottom !== next) {
        s.el.style.marginBottom = next;
        // Growing/shrinking this field's margin shifts every field below it, but
        // their ResizeObserver won't fire (their size didn't change) and no
        // scroll/resize event fires — so re-anchor every open overlay to follow.
        for (const s2 of sessions.values()) if (s2 !== s) positionOverlay(s2);
      }
    } catch (e) { /* ignore */ }
  }

  // True when the host already frames the field — its own border, an outline
  // (Greenhouse wraps the textarea in an `.input-wrapper` with a 1px outline), or a
  // box-shadow — on the field itself or a snug wrapper. There my blue border nests
  // inside that frame as a redundant second one, so I drop it and let the loader +
  // text carry the active state.
  // Returns the host element that frames the field — the field itself or a snug
  // wrapper carrying a solid outline (Greenhouse's `.input-wrapper`) or an ancestor
  // border — or null. When it's a wrapper taller than the field, the overlay sizes
  // to IT (not the textarea) so the action bar sits below the whole frame instead
  // of painting over the wrapper's lower padding + bottom border.
  function hostFrameEl(el) {
    try {
      const fr = el.getBoundingClientRect();
      const notTransparent = (c) => c && !/rgba?\(0,\s*0,\s*0,\s*0\)|transparent/.test(c);
      let n = el;
      for (let i = 0; n && i < 6; i++, n = n.parentElement) {
        const nr = n.getBoundingClientRect();
        // Snug to the field (a frame, not a wide page section or a tall card).
        if (!((nr.width - fr.width) < 120 && nr.height < fr.height * 2.5)) continue;
        // Only an ANCESTOR frame counts (Greenhouse's `.input-wrapper` outline).
        // The FIELD's own outline/border is skipped: a focus outline (Ashby adds a
        // 4px one on :focus) is transient and would make the look depend on whether
        // the user clicked in first; the field's own border sits under my overlay
        // which replaces it. My overlay draws the blue border in both cases.
        if (i > 0) {
          const cs = getComputedStyle(n);
          const ow = parseFloat(cs.outlineWidth) || 0;
          if (ow >= 1 && cs.outlineStyle !== 'none' && cs.outlineStyle !== 'auto' && notTransparent(cs.outlineColor)) return n;
          const bw = parseFloat(cs.borderTopWidth) || 0;
          if (bw >= 1 && notTransparent(cs.borderTopColor)) return n;
        }
      }
    } catch (e) { /* ignore */ }
    return null;
  }

  // Mirror the host field's own colours so the draft reads as native — a dark
  // careers page (e.g. cursor.com) has dark inputs where ink-on-white would be
  // invisible. The caret and the light action bar stay as the extension's chrome.
  function themeOverlay(s) {
    try {
      const cs = getComputedStyle(s.el);
      const bg = cs.backgroundColor;
      const fg = cs.color;
      if (bg && !/^rgba?\(0,\s*0,\s*0,\s*0\)$|transparent/.test(bg)) s.fieldbox.style.background = bg;
      if (fg) s.txt.style.color = fg;   // inline wins over the .txt / .txt.done rules
      // Soften where the host already frames the field: no injected border on the
      // field OR the action bar below it — just loader + text inside the host's own
      // frame (avoids a double frame, e.g. Greenhouse's outline).
      if (s.carded) {
        s.fieldbox.style.border = 'none';
        const bar = s.root.querySelector('.bar');
        if (bar) bar.style.border = 'none';
        // The frame's outline sits at (frame bottom + outline width), which can be
        // below the field's own bottom. Start the bar past it so it doesn't cover
        // the lower outline. Widen the reserve by the same amount (barGap).
        const ow = parseFloat(getComputedStyle(s.frame).outlineWidth) || 1;
        const fr = s.frame.getBoundingClientRect(), er = s.el.getBoundingClientRect();
        s.barGap = Math.max(0, Math.round(fr.bottom - er.bottom) + ow + 2);
        s.fieldbox.style.marginBottom = `${s.barGap}px`;
      }
    } catch (e) { /* ignore */ }
  }

  function positionOverlay(s) {
    const r = s.el.getBoundingClientRect();   // size to the field itself (not a wrapper
                                              // — Greenhouse tucks the label in the wrapper)
    const top = Math.round(window.scrollY + r.top), left = Math.round(window.scrollX + r.left);
    const w = Math.round(r.width), h = Math.round(r.height);
    // Skip redundant writes — re-anchoring fires on every scroll/resize tick, and
    // rewriting identical values thrashes layout (a source of visible jitter).
    if (s._pos && s._pos.top === top && s._pos.left === left && s._pos.w === w && s._pos.h === h) return;
    s._pos = { top, left, w, h };
    s.host.style.top = `${top}px`;
    s.host.style.left = `${left}px`;
    s.host.style.width = `${w}px`;
    s.fieldbox.style.height = `${h}px`;
    const cs = getComputedStyle(s.el);
    // Round the TOP corners to the field's radius; square the BOTTOM so the field
    // box meets the action bar flush (no notch at the rounded corner).
    const rad = parseFloat(cs.borderTopLeftRadius) > 0 ? cs.borderTopLeftRadius : '7px';
    s.fieldbox.style.borderRadius = `${rad} ${rad} 0 0`;
    s.txt.style.fontSize = cs.fontSize;
    s.txt.style.lineHeight = cs.lineHeight === 'normal' ? '1.45' : cs.lineHeight;
  }

  function startDraft(el) {
    const key = fieldKey(el);
    if (sessions.has(key)) teardownSession(key);   // re-draft replaces
    removeAff(key);                                // hide the resting affordance

    const host = document.createElement('div');
    host.style.cssText = 'position:absolute;z-index:2147483647;';
    const root = host.attachShadow({ mode: 'open' });
    root.innerHTML = `<style>${OVER_CSS}</style>
      <div class="fieldbox">
        <div class="prog"><span class="run"></span></div>
        <div class="scroll">
          <div class="skel"><div class="skbar"></div><div class="skbar"></div><div class="skbar" style="width:62%"></div></div>
          <p class="txt hidden"><span class="chars"></span><span class="caret"></span></p>
        </div>
      </div>
      <div class="bar">
        <div class="row" id="mainRow"></div>
        <div class="refine hidden" id="refineRow"></div>
        <div class="row row2 hidden" id="overflow">
          <button id="copy">Copy</button>
          <button id="savebank">Save to bank</button>
          <span class="spacer"></span>
          <span class="lenlbl">Length</span>
          <span class="seg" id="seg">
            <button data-len="120">120</button>
            <button data-len="250">250</button>
            <button data-len="500">500</button>
            <input id="customLen" type="number" min="40" max="4000" placeholder="custom">
          </span>
        </div>
      </div>`;
    document.body.appendChild(host);

    const fieldMax = fieldMaxOf(el);
    const frame = hostFrameEl(el);
    const s = {
      el, key, host, root,
      frame: frame || el,          // geometry anchor: the framed wrapper, else the field
      carded: !!frame,             // host already frames the field (drop my borders)
      fieldbox: root.querySelector('.fieldbox'),
      scrollEl: root.querySelector('.scroll'),
      prog: root.querySelector('.prog'),
      skel: root.querySelector('.skel'),
      txt: root.querySelector('.txt'),
      chars: root.querySelector('.chars'),
      len: fieldMax || DEFAULT_LEN,
      fieldMax,                    // R2-H-12: the field's own hard ceiling, if it has one
      acc: '', prevAcc: '', port: null, streaming: false, inserting: false,
      instructions: [],   // ordered refinement history; UI shows only the last as a pill
      ctx: { question: questionFor(el), company: pageCompany(), position: pagePosition() },
    };
    sessions.set(key, s);
    // Reserve room below the field so the overlay's bar doesn't cover the next
    // field — push the host page's following content down by the bar's height via
    // the field's own margin (restored on teardown). Deliberate override of C2's
    // "never push page content": in practice the overlap reads worse than a shift.
    s.prevMargin = el.style.marginBottom;
    s.baseMargin = parseFloat(getComputedStyle(el).marginBottom) || 0;
    // When my overlay draws its own blue border, suppress the field's own focus
    // outline/box-shadow so it doesn't double up (Ashby adds a 4px focus outline).
    // On carded pages the host frame IS the indicator, so leave it be.
    if (!s.carded) {
      s.prevOutline = el.style.outline; s.prevShadow = el.style.boxShadow;
      el.style.outline = 'none'; el.style.boxShadow = 'none';
    }
    // Space already below the field inside its wrapper (padding + margin). The bar
    // can sit in that space for free — only the shortfall needs reserving, else the
    // wrapper padding stacks below the bar as a visible dead gap.
    s.gapBelow = (() => {
      const par = el.parentElement;
      return par ? Math.max(0, Math.round(par.getBoundingClientRect().bottom - el.getBoundingClientRect().bottom)) : 0;
    })();
    positionOverlay(s);
    themeOverlay(s);

    // Re-anchor on scroll/resize (global) + resize of the field.
    try { s.ro = new ResizeObserver(() => positionOverlay(s)); s.ro.observe(el); } catch { s.ro = null; }
    // The user typing into the real field wins: close the draft, keep their text.
    s.onInput = () => { if (!s.inserting) teardownSession(key, { reveal: true }); };
    el.addEventListener('input', s.onInput);

    ensureBodyObserver();  // catch async layout shifts (a field auto-growing on Insert)
    wireOverflow(s);
    beginStream(s);
  }

  // A page-level layout watch: an inserted field auto-grows a frame LATER (React
  // re-render), and margins released on teardown reflow the page — both move other
  // open overlays' fields without firing their own ResizeObserver. Watch the body
  // size and re-anchor every open overlay when it changes.
  let _bodyRO = null;
  function ensureBodyObserver() {
    if (_bodyRO) return;
    try {
      _bodyRO = new ResizeObserver(() => { for (const s of sessions.values()) positionOverlay(s); });
      _bodyRO.observe(document.body);
    } catch (e) { _bodyRO = null; }
  }
  function maybeStopBodyObserver() {
    if (_bodyRO && sessions.size === 0) { try { _bodyRO.disconnect(); } catch (e) { /* ignore */ } _bodyRO = null; }
  }

  function wireOverflow(s) {
    const root = s.root;
    root.getElementById('copy').onclick = () => navigator.clipboard.writeText(s.acc);
    const saveBtn = root.getElementById('savebank');
    saveBtn.onclick = async () => {
      const resp = await chrome.runtime.sendMessage({ type: 'autofill_save', question: s.ctx.question, answer: s.acc });
      saveBtn.textContent = (resp && resp.count !== undefined && !resp.error) ? 'Saved ✓' : 'Save failed';
      setTimeout(() => { saveBtn.textContent = 'Save to bank'; }, 1800);
    };
    const seg = root.getElementById('seg');
    const custom = root.getElementById('customLen');
    const markLen = () => {
      seg.querySelectorAll('button').forEach(b => b.classList.toggle('on', !custom.value && +b.dataset.len === s.len));
      custom.classList.toggle('on', !!custom.value);
    };
    // Changing length only re-scales the counter denominator; regeneration stays
    // explicit (the Regenerate button) — a length tap never re-drafts on its own.
    seg.querySelectorAll('button').forEach(b => {
      b.onclick = () => { custom.value = ''; s.len = +b.dataset.len; markLen(); updateCount(s); };
    });
    custom.onchange = () => { const v = parseInt(custom.value, 10); if (v > 0) { s.len = v; markLen(); updateCount(s); } };
    markLen();
  }

  // R2-H-12: max_chars is a hint to the model, not a contract — a 300-char ask
  // came back at 346. Cut the text we write to the field (the browser would
  // silently truncate an <input>, and would not truncate a contenteditable at
  // all), and say so in the counter. Trim back to a word boundary when one is
  // close, so the cut doesn't land mid-word.
  //
  // R3-B-04: the cap used to apply only when the field declared a maxLength —
  // which the usual Greenhouse/Lever/Ashby <textarea> does not — so the length
  // the user picked was ignored on exactly the fields it was picked for (600 ->
  // 714 chars, inserted whole). The ceiling is now the picked length, tightened
  // by the field's own hard limit when it has one. /answer applies the same trim
  // server-side; this is what enforces it on the streamed path.
  const capOf = (s) => (s.fieldMax ? Math.min(s.fieldMax, s.len) : s.len);
  const capForField = (s) => {
    const hard = capOf(s);
    if (!hard || s.acc.length <= hard) return s.acc;
    const cut = s.acc.slice(0, hard);
    const sp = cut.lastIndexOf(' ');
    return (sp > hard - 20 ? cut.slice(0, sp) : cut).replace(/[\s,;:]+$/, '');
  };
  const countLabel = (s) => {
    const base = `${s.acc.length}/${s.len}`;
    return s.acc.length > capOf(s) ? `${base} · trimmed to ${capForField(s).length}` : base;
  };

  const TWISTS = [
    ['More confident', 'Make it more confident and assertive'],
    ['More specific', 'Be more specific with concrete detail'],
    ['Less formal', 'Make it less formal and more conversational'],
  ];

  function renderDrafting(s) {
    s.root.getElementById('refineRow').classList.add('hidden');
    s.root.getElementById('mainRow').innerHTML =
      `<span class="spin"></span><span class="drafting">Drafting…</span>
       <span class="spacer"></span><button id="stop">Stop</button>`;
    s.root.getElementById('stop').onclick = () => stopStream(s);
    reserveSpace(s);
  }
  function renderDone(s) {
    s.prog.classList.add('hidden');
    s.txt.classList.add('done');
    const caret = s.txt.querySelector('.caret'); if (caret) caret.remove();
    const over = s.acc.length > s.len;
    s.root.getElementById('mainRow').innerHTML = `
      <button class="primary" id="insert">Insert</button>
      <button id="regen">Regenerate</button>
      <button class="icon-btn" id="more">···</button>
      <span class="spacer"></span>
      <span class="count ${over ? 'over' : ''}" id="count" title="${s.fieldMax ? 'This field accepts ' + s.fieldMax + ' characters' : ''}">${countLabel(s)}</span>`;
    s.root.getElementById('insert').onclick = () => insertDraft(s);
    s.root.getElementById('regen').onclick = () => beginStream(s);
    s.root.getElementById('more').onclick = () => s.root.getElementById('overflow').classList.toggle('hidden');
    renderRefine(s);
  }

  // The C5 refinement row: an active-ask pill (last instruction, removable), a free
  // instruction field + Redraft button, and the quick-twist chips. Shown only on a
  // finished draft; the full instruction history is what gets sent, the pill shows
  // only the latest.
  function renderRefine(s) {
    const row = s.root.getElementById('refineRow');
    row.classList.remove('hidden');
    const active = s.instructions[s.instructions.length - 1];
    const esc = (t) => t.replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
    row.innerHTML = `
      ${active ? `<span class="askpill">Asked for: ${esc(active)}<button class="x" id="clearAsk" aria-label="Clear">×</button></span>` : ''}
      <div class="ask">
        <input class="askin" id="askin" type="text" placeholder="Ask for a change — e.g. add a specific example">
        <button class="redraft" id="redraft">Redraft</button>
      </div>
      <div class="twists">${TWISTS.map((t, i) => `<button class="twist" data-i="${i}">${t[0]}</button>`).join('')}</div>`;

    const input = row.querySelector('#askin');
    const btn = row.querySelector('#redraft');
    const sync = () => btn.classList.toggle('on', input.value.trim().length > 0);
    input.addEventListener('input', sync);
    const submit = () => { const t = input.value.trim(); if (t) applyInstruction(s, t); };
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); submit(); } });
    btn.onclick = () => { if (input.value.trim()) submit(); };
    row.querySelectorAll('.twist').forEach(b => { b.onclick = () => applyInstruction(s, TWISTS[+b.dataset.i][1]); });
    const clear = row.querySelector('#clearAsk');
    if (clear) clear.onclick = () => { s.instructions.pop(); renderRefine(s); };  // no re-run (C5)
    reserveSpace(s);
  }
  function applyInstruction(s, text) {
    s.instructions.push(text);   // history compounds; pill shows the latest
    beginStream(s);              // re-draft in place, honoring the full history
  }
  // Re-scale the counter to the current length without regenerating (used when the
  // user changes the length override in the done state).
  function updateCount(s) {
    const c = s.root.getElementById('count');
    if (!c) return;
    c.textContent = countLabel(s);
    c.classList.toggle('over', s.acc.length > s.len);
  }

  function beginStream(s) {
    try { if (s.port) s.port.disconnect(); } catch {}
    s.prevAcc = s.acc;   // kept so a failed refinement can restore the last good draft
    s.acc = ''; s.streaming = true;
    s.prog.classList.remove('hidden');
    s.skel.classList.remove('hidden');
    s.txt.classList.add('hidden');
    s.txt.classList.remove('done');
    if (!s.txt.querySelector('.caret')) s.txt.insertAdjacentHTML('beforeend', '<span class="caret"></span>');
    s.chars.textContent = '';
    renderDrafting(s);

    const port = chrome.runtime.connect({ name: 'autofill_stream' });
    s.port = port;
    let settled = false, first = true;
    port.onMessage.addListener((m) => {
      if (sessions.get(s.key) !== s) return;
      if (m.type === 'delta') {
        if (first) { first = false; s.skel.classList.add('hidden'); s.txt.classList.remove('hidden'); }
        s.acc += m.delta;
        s.chars.textContent = s.acc;
        s.fieldbox.querySelector('.scroll').scrollTop = s.fieldbox.querySelector('.scroll').scrollHeight;
      } else if (m.type === 'done') {
        if (settled) return; settled = true; s.streaming = false;
        if (first) { s.skel.classList.add('hidden'); s.txt.classList.remove('hidden'); }
        const clean = unwrapAnswer(s.acc);
        if (clean !== s.acc) { s.acc = clean; s.chars.textContent = s.acc; }
        renderDone(s);
      } else if (m.type === 'error') {
        if (settled) return; settled = true; s.streaming = false; onStreamError(s, m.error);
      }
    });
    port.onDisconnect.addListener(() => {
      if (settled || sessions.get(s.key) !== s) return; settled = true; s.streaming = false;
      if (s.acc) renderDone(s); else onStreamError(s, 'connection lost');
    });
    port.postMessage({ type: 'start', question: s.ctx.question, company: s.ctx.company,
      position: s.ctx.position, max_chars: s.len, refinements: s.instructions.slice() });
  }
  function stopStream(s) {
    // Design C6: Stop discards the draft entirely and returns to resting.
    teardownSession(s.key, { reveal: true });
  }
  function onStreamError(s, err) {
    s.prog.classList.add('hidden'); s.skel.classList.add('hidden');
    // A failed refinement must not blank the previous draft (C5). If we had a prior
    // draft, restore it and show the done UI with an inline notice; the failed
    // instruction is rolled back so the pill/history reflect the surviving answer.
    if (s.prevAcc) {
      if (s.instructions.length) s.instructions.pop();
      s.acc = s.prevAcc;
      s.chars.textContent = s.acc;
      s.txt.classList.remove('hidden');
      renderDone(s);
      const row = s.root.getElementById('mainRow');
      const note = document.createElement('span');
      note.className = 'err'; note.style.marginLeft = '8px'; note.textContent = "Couldn't refine — kept your draft";
      row.appendChild(note);
      setTimeout(() => { try { note.remove(); } catch {} }, 3000);
      return;
    }
    s.root.getElementById('mainRow').innerHTML =
      `<span class="err">Couldn't reach the model — ${err || 'try again'}</span>
       <span class="spacer"></span><button id="retry">Try again</button>
       <button id="cancel">Dismiss</button>`;
    s.root.getElementById('retry').onclick = () => beginStream(s);
    s.root.getElementById('cancel').onclick = () => teardownSession(s.key, { reveal: true });
  }
  function insertDraft(s) {
    s.inserting = true;                 // guard our own input event from closing the draft
    writeToField(s.el, capForField(s));   // R2-H-12 / R3-B-04: never write past the picked length or the field's maxLength
    teardownSession(s.key, { reveal: true });   // affordance returns as "Redraft"
  }

  function teardownSession(key, opts) {
    const s = sessions.get(key);
    if (!s) return;
    sessions.delete(key);
    try { if (s.port) s.port.disconnect(); } catch {}
    try { if (s.ro) s.ro.disconnect(); } catch {}
    try { s.el.removeEventListener('input', s.onInput); } catch {}
    try { s.el.style.marginBottom = s.prevMargin; } catch (e) { /* ignore */ }  // release reserved space
    try { if (s.prevOutline !== undefined) { s.el.style.outline = s.prevOutline; s.el.style.boxShadow = s.prevShadow; } } catch (e) { /* ignore */ }
    s.host.remove();
    if (opts && opts.reveal && enabled &&
        (document.activeElement === s.el || s.el.matches(':hover'))) showAff(s.el);
    // Tearing down releases this field's reserved margin (and Insert may grow the
    // field), shifting every field below it — re-anchor the still-open overlays so
    // they follow instead of detaching from their fields. (The body observer also
    // catches the field's async grow a frame later.)
    for (const s2 of sessions.values()) positionOverlay(s2);
    maybeStopBodyObserver();
  }

  // ── wiring ───────────────────────────────────────────────────────────────────
  function eligibleTarget(t) { return t && t.matches && isAnswerField(t) ? t : null; }

  document.addEventListener('focusin', (e) => {
    if (!enabled) return;
    const el = eligibleTarget(e.target);
    if (el && !sessions.has(fieldKey(el))) showAff(el);
  }, true);
  document.addEventListener('mouseover', (e) => {
    if (!enabled) return;
    const el = eligibleTarget(e.target);
    if (el && !sessions.has(fieldKey(el))) showAff(el);
  }, true);
  const scheduleAffCleanup = () => setTimeout(() => {
    const active = document.activeElement;
    for (const [key, w] of affs) {
      if (sessions.has(key)) continue;
      const hot = active === w.el || (w.el.matches && w.el.matches(':hover')) ||
                  w.host.contains(active) || w.hovering;
      if (!hot) removeAff(key);
    }
  }, 200);
  document.addEventListener('focusout', () => { if (enabled) scheduleAffCleanup(); }, true);
  document.addEventListener('mouseout', () => { if (enabled) scheduleAffCleanup(); }, true);

  window.addEventListener('scroll', () => {
    for (const w of affs.values()) positionAff(w);
    for (const s of sessions.values()) positionOverlay(s);
  }, true);
  window.addEventListener('resize', () => {
    for (const w of affs.values()) positionAff(w);
    for (const s of sessions.values()) positionOverlay(s);
  }, true);
})();
