// extension/content_autofill_fill.js — structured application autofill (DOM layer).
// Loaded after lib/autofill_match.js (window.__autofillMatch available).
(function () {
  'use strict';

  // Inlined app mark (same asset as the in-field draft). Inlined rather than
  // chrome.runtime.getURL('icons/…') so it renders without a full reinstall to
  // register web_accessible_resources, and inside strict-CSP ATS pages.
  const NAV_ICON = 'data:image/png;base64,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';

  // Build a text signature for a control from every label source we can find.
  function labelText(el) {
    const parts = [];
    if (el.id) {
      const forLbl = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (forLbl) parts.push(forLbl.textContent);
    }
    if (el.getAttribute && el.getAttribute('aria-label')) parts.push(el.getAttribute('aria-label'));
    const alby = el.getAttribute && el.getAttribute('aria-labelledby');
    if (alby) alby.split(/\s+/).forEach(id => { const n = document.getElementById(id); if (n) parts.push(n.textContent); });
    const anc = el.closest && el.closest('label');
    if (anc) parts.push(anc.textContent);
    if (el.name) parts.push(el.name);
    if (el.id) parts.push(el.id);
    if (el.placeholder) parts.push(el.placeholder);
    const fs = el.closest && el.closest('fieldset');
    if (fs) { const lg = fs.querySelector('legend'); if (lg) parts.push(lg.textContent); }
    // Workday: the question sits in the enclosing formField-* container as a
    // label/legend, and the field's data-automation-id (gender/veteranStatus/
    // ethnicityDropdown/hispanicOrLatino) is itself a strong signal.
    const ff = el.closest && el.closest('[data-automation-id^="formField-"]');
    if (ff) {
      const lbl = ff.querySelector('label, legend');
      if (lbl) parts.push(lbl.textContent);
      parts.push(ff.getAttribute('data-automation-id') || '');
    }
    if (el.getAttribute && el.getAttribute('data-automation-id')) parts.push(el.getAttribute('data-automation-id'));
    // Ashby wraps each question in a [data-field-path] container with the question
    // text as a leading label/heading — a single-checkbox yes/no ("Are you
    // authorized to work…") otherwise contributes only its UUID path here, so the
    // matcher never sees the question. Pull the wrapper's question text + path.
    const dfp = el.closest && el.closest('[data-field-path]');
    if (dfp) {
      const q = dfp.querySelector('label:not([for]), legend, [class*="title" i], [class*="label" i], [class*="question" i], h1, h2, h3, h4');
      if (q && q.textContent) parts.push(q.textContent);
      parts.push(dfp.getAttribute('data-field-path') || '');
    }
    return parts.join(' ').replace(/\s+/g, ' ').trim();
  }

  // Returns [{el, kind, signature, optionEls?, optionTexts?}].
  // kind ∈ 'text' | 'textarea' | 'select' | 'radioGroup' | 'checkbox'.
  // The question text + path shared by a group of controls (a checkbox multi-select
  // or radio set). Ashby renders the group question as the wrapper's leading label.
  function containerSignature(container) {
    const parts = [];
    const q = container.querySelector('label:not([for]), legend, [class*="title" i], [class*="label" i], [class*="question" i], h1, h2, h3, h4');
    if (q && q.textContent) parts.push(q.textContent);
    if (container.getAttribute) parts.push(container.getAttribute('data-field-path') || '');
    return parts.join(' ').replace(/\s+/g, ' ').trim();
  }

  // Rendered and on the page: display:none, visibility:hidden, zero-size and off-screen
  // fields are all invisible to the user, so they are invisible to the filler too.
  function isVisible(el) {
    if (typeof el.checkVisibility === 'function' && !el.checkVisibility({ visibilityProperty: true, opacityProperty: true })) return false;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return false;
    return r.right > 0 && r.bottom > 0 && r.left < (document.documentElement.scrollWidth + 1) && r.top < (document.documentElement.scrollHeight + 1);
  }

  function discoverFields(root) {
    root = root || document;
    const out = [];
    const seenRadioNames = new Set();
    // Group checkboxes that share a question container ([data-field-path] or
    // fieldset) — an Ashby "select all that apply" (ethnicity, sexual orientation)
    // is N sibling checkboxes, not one boolean. A lone checkbox stays boolean.
    const cbGroups = new Map();
    root.querySelectorAll('input[type="checkbox"]').forEach(cb => {
      if (cb.disabled || cb.readOnly || !isVisible(cb)) return;
      const container = cb.closest('[data-field-path], fieldset') || cb;
      let g = cbGroups.get(container); if (!g) { g = []; cbGroups.set(container, g); } g.push(cb);
    });
    const emittedContainers = new Set();
    root.querySelectorAll('input, textarea, select').forEach(el => {
      if (el.disabled || el.readOnly) return;
      // a field the user cannot see is not a field to fill: an off-screen or display:none
      // form on a hostile page would otherwise collect the persona silently
      if (!isVisible(el)) return;
      const type = (el.type || '').toLowerCase();
      if (el.tagName === 'TEXTAREA') { out.push({ el, kind: 'textarea', signature: labelText(el) }); return; }
      if (el.tagName === 'SELECT') {
        const optionEls = Array.from(el.options);
        out.push({ el, kind: 'select', signature: labelText(el), optionEls, optionTexts: optionEls.map(o => o.textContent.trim()) });
        return;
      }
      if (['hidden', 'submit', 'button', 'file', 'password', 'image', 'reset'].includes(type)) return;
      if (type === 'checkbox') {
        const container = el.closest('[data-field-path], fieldset') || el;
        const g = cbGroups.get(container);
        if (g && g.length >= 2) {
          if (emittedContainers.has(container)) return;
          emittedContainers.add(container);
          out.push({ el: g[0], kind: 'checkboxGroup', signature: containerSignature(container),
                     optionEls: g, optionTexts: g.map(c => labelText(c) || c.value) });
          return;
        }
        out.push({ el, kind: 'checkbox', signature: labelText(el) });
        return;
      }
      if (type === 'radio') {
        if (!el.name || seenRadioNames.has(el.name)) return;
        seenRadioNames.add(el.name);
        const group = Array.from(root.querySelectorAll(`input[type="radio"][name="${CSS.escape(el.name)}"]`));
        // Group question: fieldset legend / heading label (Ashby uses a
        // question-title label, no <legend>), the data-field-path (Ashby EEO ids
        // like _systemfield_eeoc_gender), and the name — joined so the matcher
        // can find "gender"/"veteran"/etc. wherever the platform put it.
        const fs = el.closest('fieldset');
        let head = '';
        if (fs) { const lg = fs.querySelector('legend, [class*="question-title"], [class*="heading"]'); if (lg) head = lg.textContent || ''; }
        const pathWrap = el.closest('[data-field-path]');
        const fieldPath = pathWrap ? (pathWrap.getAttribute('data-field-path') || '') : '';
        const signature = (head + ' ' + fieldPath + ' ' + (el.name || '')).replace(/\s+/g, ' ').trim();
        out.push({ el, kind: 'radioGroup', signature, optionEls: group, optionTexts: group.map(r => labelText(r) || r.value) });
        return;
      }
      if (['text', 'email', 'tel', 'url', 'search', ''].includes(type)) {
        // A custom dropdown (react-select etc.) renders a text input that declares
        // itself a combobox; typing does nothing, so route it to the driver.
        const combo = window.__autofillCombobox;
        if (combo && combo.isComboWidget(el)) out.push({ el, kind: 'customDropdown', signature: labelText(el) });
        else out.push({ el, kind: 'text', signature: labelText(el) });
      }
    });
    // Supplementary: element-based comboboxes with no <input> (role=combobox on a
    // non-input). react-select uses an input (caught above); some libraries don't.
    const combo = window.__autofillCombobox;
    if (combo) {
      root.querySelectorAll(combo.COMBO_WIDGET).forEach(el => {
        const tag = el.tagName;
        if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return;
        if (out.some(f => f.el === el)) return;
        out.push({ el, kind: 'customDropdown', signature: labelText(el) });
      });
    }
    return out;
  }

  // Write a value through the native setter so React/Angular controlled inputs
  // notice it, then fire input+change.
  function setNativeValue(el, value) {
    let proto;
    if (el.tagName === 'TEXTAREA') proto = window.HTMLTextAreaElement.prototype;
    else if (el.tagName === 'SELECT') proto = window.HTMLSelectElement.prototype;
    else proto = window.HTMLInputElement.prototype;
    const desc = Object.getOwnPropertyDescriptor(proto, 'value');
    if (desc && desc.set) desc.set.call(el, value); else el.value = value;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function _isBlank(v) {
    return v === undefined || v === null || (typeof v === 'string' && v.trim() === '');
  }

  // fields: from discoverFields(). config: /api/autofill/config payload.
  // Returns [{el, field, key, action:'fill'|'flag', value?|checked?|optionIndex?, reason?}].
  function buildPlan(fields, config) {
    const M = window.__autofillMatch;
    const patterns = (config && config.field_patterns) || {};
    const syn = (config && config.option_synonyms) || {};
    const schema = (config && config.schema) || {};
    const answers = (config && config.answers) || {};
    // Split-phone: a separate country-code selector (its label mentions phone +
    // country/code) next to the number field means the number field wants the
    // national number, not the full "+.." one. Then fill phone with phone_national.
    const splitPhone = fields.some(f => {
      const s = M.normalizeLabel(f.signature || '');
      return (s.indexOf('phone') >= 0 && (s.indexOf('country') >= 0 || s.indexOf('code') >= 0)) || s.indexOf('dial code') >= 0;
    });
    const plan = [];
    const matched = new Set();
    fields.forEach(f => {
      const key = M.matchFieldKey(f.signature, patterns);
      if (!key) return; // unrecognized field — never touch it
      matched.add(f);
      let val = answers[key];
      if (key === 'phone' && splitPhone && typeof answers.phone_national === 'string') val = answers.phone_national;
      if (_isBlank(val)) { plan.push({ el: f.el, field: f, key, action: 'flag', reason: 'no-answer' }); return; }
      const spec = schema[key] || {};
      if (f.kind === 'text' || f.kind === 'textarea') {
        // Some forms render a yes/no or choice question as a plain text input
        // (e.g. "Are you over 18?"). Type the word rather than flagging: booleans
        // become Yes/No; an enum types its first option synonym (e.g. "Male").
        let tv = val;
        if (typeof tv === 'boolean') tv = tv ? 'Yes' : 'No';
        else if (spec.kind === 'enum') {
          const s = (syn[key] || {})[val];
          if (s && s.length) tv = s[0].replace(/\b\w/g, c => c.toUpperCase());
        }
        if (typeof tv === 'string') plan.push({ el: f.el, field: f, key, action: 'fill', value: tv });
        else plan.push({ el: f.el, field: f, key, action: 'flag', reason: 'type-mismatch' });
        return;
      }
      if (f.kind === 'checkbox') {
        if (typeof val === 'boolean') plan.push({ el: f.el, field: f, key, action: 'fill', checked: val });
        else plan.push({ el: f.el, field: f, key, action: 'flag', reason: 'type-mismatch' });
        return;
      }
      if (f.kind === 'checkboxGroup') {
        // Multi-select: check the option(s) matching the answer, leave the rest.
        const vals = Array.isArray(val) ? val : [val];
        const idx = [];
        vals.forEach(v => {
          const opt = (typeof v === 'boolean' || spec.kind === 'bool')
            ? M.boolToOption(!!v, f.optionTexts, syn._bool || {})
            : M.matchOption(v, f.optionTexts, syn[key] || {});
          if (opt && idx.indexOf(opt.index) < 0) idx.push(opt.index);
        });
        if (!idx.length) { plan.push({ el: f.el, field: f, key, action: 'flag', reason: 'no-option' }); return; }
        plan.push({ el: f.el, field: f, key, action: 'fill', checkIndices: idx });
        return;
      }
      if (f.kind === 'select' || f.kind === 'radioGroup') {
        let opt;
        if (typeof val === 'boolean' || spec.kind === 'bool') opt = M.boolToOption(!!val, f.optionTexts, syn._bool || {});
        else opt = M.matchOption(val, f.optionTexts, syn[key] || {});
        if (!opt) { plan.push({ el: f.el, field: f, key, action: 'flag', reason: 'no-option' }); return; }
        plan.push({ el: f.el, field: f, key, action: 'fill', optionIndex: opt.index });
        return;
      }
      if (f.kind === 'customDropdown') {
        // Options aren't in the DOM until the widget is opened, so defer option
        // matching to run time via a picker the combobox driver calls with the
        // live option texts.
        const pick = (optionTexts) => {
          let opt;
          if (typeof val === 'boolean' || spec.kind === 'bool') opt = M.boolToOption(!!val, optionTexts, syn._bool || {});
          else opt = M.matchOption(val, optionTexts, syn[key] || {});
          if (opt) return opt.index;
          // Fallback for free-text answers (country/city) with no enum synonyms:
          // pick the option whose text contains the answer.
          if (typeof val === 'string') {
            const nv = M.normalizeLabel(val);
            if (nv) { const i = optionTexts.findIndex(t => M.normalizeLabel(t).includes(nv)); if (i >= 0) return i; }
          }
          return null;
        };
        // Free-text fields (city/country/location) are searchable typeaheads whose
        // options render only after typing — type the answer to filter. Enum/bool
        // fields have short static lists, so never type (would filter to nothing).
        const searchText = (spec.kind === 'text' && typeof val === 'string') ? val : null;
        plan.push({ el: f.el, field: f, key, action: 'combobox', pick, searchText });
        return;
      }
    });

    // Decline-unknown-self-ID policy: for a diversity/self-ID question the persona
    // doesn't cover (pronouns, marital status, a company-specific identity Q),
    // select its "I prefer not to answer" / "decline to self-identify" option so
    // nothing is left blank. Gated on the setting; only fires on option fields that
    // both look demographic AND offer a decline option.
    if (config && config.decline_self_id) {
      const DEMO = /gender|identity|transgender|sexual|orientation|\brace\b|ethnic|ancestry|\bage\b|disab|veteran|pronoun|hispanic|latin|lgbt|national|religio|marital|neurodiver/i;
      const DECLINE = ['prefer not to answer', 'prefer not to say', 'decline to self', 'decline to answer',
                       'i decline', 'do not wish', "don't wish", 'choose not to'];
      const isDecline = (t) => { const n = M.normalizeLabel(t); return DECLINE.some(d => n.includes(M.normalizeLabel(d))); };
      fields.forEach(f => {
        if (matched.has(f)) return;
        if (f.kind !== 'radioGroup' && f.kind !== 'select' && f.kind !== 'checkboxGroup') return;
        const opts = f.optionTexts || [];
        const demographic = DEMO.test(f.signature || '') || opts.some(t => DEMO.test(t));
        if (!demographic) return;
        const di = opts.findIndex(isDecline);
        if (di < 0) return;
        if (f.kind === 'checkboxGroup') plan.push({ el: f.el, field: f, key: '_decline_self_id', action: 'fill', checkIndices: [di] });
        else plan.push({ el: f.el, field: f, key: '_decline_self_id', action: 'fill', optionIndex: di });
      });
    }
    return plan;
  }

  // The visible clickable label for a control. Ashby (and many React ATS) hide the
  // real <input type=radio/checkbox> and render a styled <label>; clicking the
  // hidden input sets .checked but doesn't drive the library's toggle, so we click
  // the label instead. Handles label[for=id] and an ancestor <label>.
  function labelFor(el) {
    if (el.id) { try { const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`); if (l) return l; } catch (e) { /* bad id */ } }
    return el.closest && el.closest('label');
  }
  function _setCheckedNative(el, want) {
    const desc = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'checked');
    if (desc && desc.set) desc.set.call(el, want); else el.checked = want;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }
  // Escalating strategy: click the label, then the input, then force checked — stop
  // as soon as the control reflects the desired state. Returns whether it stuck.
  function selectRadio(el) {
    const lbl = labelFor(el);
    if (!el.checked && lbl) lbl.click();
    if (!el.checked) try { el.click(); } catch (e) { /* ignore */ }
    if (!el.checked) _setCheckedNative(el, true);
    return !!el.checked;
  }
  function toggleCheckbox(el, want) {
    if (el.checked === want) return true;
    const lbl = labelFor(el);
    if (lbl) lbl.click();
    if (el.checked !== want) try { el.click(); } catch (e) { /* ignore */ }
    if (el.checked !== want) _setCheckedNative(el, want);
    return el.checked === want;
  }

  // Executes fills; returns {filled:[], flagged:[]}. Never submits. Radio/checkbox
  // writes are verified against the control's actual state so a fill that didn't
  // take (hidden input, custom widget) is flagged, not miscounted as filled.
  function applyPlan(plan) {
    const filled = [], flagged = [];
    const flag = (item, reason) => flagged.push({ el: item.el, field: item.field, key: item.key, action: 'flag', reason });
    plan.forEach(item => {
      if (item.action === 'flag') { flagged.push(item); return; }
      const f = item.field;
      try {
        if (f.kind === 'text' || f.kind === 'textarea') {
          setNativeValue(item.el, item.value);
        } else if (f.kind === 'checkbox') {
          if (!toggleCheckbox(item.el, item.checked)) { flag(item, 'fill-error'); return; }
        } else if (f.kind === 'checkboxGroup') {
          let allok = true;
          (item.checkIndices || []).forEach(i => { if (!toggleCheckbox(f.optionEls[i], true)) allok = false; });
          if (!allok) { flag(item, 'fill-error'); return; }
        } else if (f.kind === 'select') {
          setNativeValue(item.el, f.optionEls[item.optionIndex].value);
        } else if (f.kind === 'radioGroup') {
          if (!selectRadio(f.optionEls[item.optionIndex])) { flag(item, 'fill-error'); return; }
        }
        filled.push(item);
      } catch (e) {
        flag(item, 'fill-error');
      }
    });
    return { filled, flagged };
  }

  window.__autofillFill = { discoverFields, labelText, buildPlan, applyPlan, setNativeValue };

  if (window.__AUTOFILL_DEBUG) {
    // Manual-debug aid: dump discovered fields when the user sets the flag.
    console.table(discoverFields().map(f => ({ signature: f.signature, kind: f.kind })));
  }

  // --- structured autofill runner + floating button ---
  const STRUCTURED_TOGGLE_KEY = 'structuredAutofillEnabled';
  const STRUCTURED_TRIGGER_KEY = 'structuredAutofillTrigger';
  let _host = null;
  let _trigger = 'click';   // set from extension storage in initStructured
  let _els = null, _undoSnapshot = null, _started = false;

  function looksLikeApplication() {
    if (document.querySelector('input[type="file"]')) return true;
    return discoverFields().length >= 3;
  }

  // Faint blue tint on a filled field so the user sees what was touched.
  function tintField(el) {
    try {
      el.style.transition = 'background-color .4s ease';
      const prev = el.style.backgroundColor;
      el.style.backgroundColor = 'rgba(70,110,230,0.06)';
      setTimeout(() => { el.style.backgroundColor = prev; }, 4000);
    } catch (e) { /* ignore */ }
  }

  function getConfig() {
    return new Promise(resolve => {
      chrome.runtime.sendMessage({ type: 'autofill_config' }, resp => {
        resolve(resp && resp.config ? resp.config : null);
      });
    });
  }

  // Capture each field's prior value so a fill can be undone (a high-stakes write
  // into someone else's form). Native controls restore exactly; comboboxes best-effort.
  function snapshot(items) {
    return items.map(p => {
      const el = p.el, f = p.field, rec = { el, kind: f.kind };
      try {
        if (f.kind === 'text' || f.kind === 'textarea' || f.kind === 'select') rec.value = el.value;
        else if (f.kind === 'checkbox') rec.checked = el.checked;
        else if (f.kind === 'checkboxGroup') { rec.optionEls = f.optionEls || []; rec.states = rec.optionEls.map(c => c.checked); }
        else if (f.kind === 'radioGroup') rec.prevChecked = (f.optionEls || []).find(r => r.checked) || null;
        else if (f.kind === 'customDropdown') { rec.input = el.tagName === 'INPUT' ? el : (el.querySelector && el.querySelector('input')); rec.value = rec.input ? rec.input.value : ''; }
      } catch (e) { /* ignore */ }
      return rec;
    });
  }
  function undo(snap) {
    const sx = window.scrollX, sy = window.scrollY;  // pin viewport (clicks scroll off-screen controls into view)
    (snap || []).forEach(rec => {
      try {
        if (rec.kind === 'text' || rec.kind === 'textarea' || rec.kind === 'select') setNativeValue(rec.el, rec.value || '');
        else if (rec.kind === 'checkbox') { if (rec.el.checked !== rec.checked) rec.el.click(); }
        else if (rec.kind === 'checkboxGroup') { (rec.optionEls || []).forEach((c, i) => { if (c.checked !== rec.states[i]) toggleCheckbox(c, rec.states[i]); }); }
        else if (rec.kind === 'radioGroup') { if (rec.prevChecked) rec.prevChecked.click(); }
        else if (rec.kind === 'customDropdown' && rec.input) setNativeValue(rec.input, rec.value || '');
      } catch (e) { /* ignore */ }
    });
    if (window.scrollX !== sx || window.scrollY !== sy) window.scrollTo(sx, sy);
  }

  function fillablePlan(config) {
    return buildPlan(discoverFields(), config).filter(p => p.action === 'fill' || p.action === 'combobox' || p.action === 'flag');
  }
  function _fieldCount() {
    if (!_cfgCache) return 0;
    return fillablePlan(_cfgCache).filter(p => p.action === 'fill' || p.action === 'combobox').length;
  }

  async function runFill(onProgress) {
    const config = await ensureConfig();
    if (!config) return { filled: [], flagged: [], total: 0, error: 'no config' };
    const plan = fillablePlan(config);
    const fillable = plan.filter(p => p.action === 'fill' || p.action === 'combobox');
    _undoSnapshot = snapshot(fillable);
    const result = { filled: [], flagged: [], total: fillable.length };
    let done = 0;
    // Filling focuses/clicks controls that may be off-screen, and the browser
    // scrolls each into view — so the page visibly jumps around as it fills. Pin
    // the viewport: capture the scroll position up front and restore it after
    // every action (the scroll happens synchronously on click/focus, so restoring
    // right after cancels the jump). The user stays where they were.
    const sx = window.scrollX, sy = window.scrollY;
    const keepScroll = () => { if (window.scrollX !== sx || window.scrollY !== sy) window.scrollTo(sx, sy); };
    for (const item of plan) {
      if (item.action === 'flag') { result.flagged.push(item); continue; }
      if (item.action === 'combobox') {
        let ok = false;
        try { const combo = window.__autofillCombobox; ok = combo ? (await combo.fillCombobox(item.el, item.pick, item.searchText)) === 'filled' : false; } catch (e) { ok = false; }
        if (ok) { result.filled.push(item); tintField(item.el); } else result.flagged.push(item);
      } else {
        const r = applyPlan([item]);
        r.filled.forEach(x => { result.filled.push(x); tintField(x.el); });
        r.flagged.forEach(x => result.flagged.push(x));
      }
      keepScroll();
      done++; if (onProgress) onProgress(done, fillable.length);
      await new Promise(res => setTimeout(res, 90));
      keepScroll();
    }
    return result;
  }

  const PILL_CSS = `
    .row { display:flex; align-items:center; gap:8px; }
    .undo { display:none; align-items:center; font:600 12.5px "Helvetica Neue",Helvetica,Arial,sans-serif; color:#57534C; background:#fff; border:1px solid #E4E1DB; border-radius:999px; padding:8px 13px; cursor:pointer; box-shadow:0 2px 8px rgba(26,25,23,0.10); }
    .pill { display:flex; align-items:center; gap:8px; font:600 13.5px "Helvetica Neue",Helvetica,Arial,sans-serif; color:#fff; border:none; border-radius:999px; padding:10px 16px 10px 11px; cursor:pointer; background:oklch(0.52 0.15 255); box-shadow:0 2px 6px rgba(26,25,23,0.12),0 8px 22px rgba(37,64,143,0.22); }
    .pill:hover { background:oklch(0.46 0.15 255); }
    .pill.filling { background:oklch(0.62 0.09 255); cursor:default; }
    .pill.done { background:oklch(0.52 0.13 150); }
    .mark { width:22px; height:22px; border-radius:999px; box-shadow:0 0 0 1.5px rgba(255,255,255,0.28); display:block; }
    .spin { width:14px; height:14px; border-radius:999px; border:2px solid rgba(255,255,255,.4); border-top-color:#fff; animation:afspin .7s linear infinite; display:none; }
    @keyframes afspin { to { transform:rotate(360deg); } }
    .ck { width:11px; height:7px; border-left:2px solid #fff; border-bottom:2px solid #fff; transform:rotate(-45deg); margin:0 3px -2px; display:none; }
    .count { font-family:'SF Mono',ui-monospace,Menlo,monospace; font-size:10.5px; color:rgba(255,255,255,0.6); }
    .pill.filling .count { color:rgba(255,255,255,0.75); }
    .pill.filling .mark, .pill.done .mark { display:none; }
    .pill.filling .spin { display:block; }
    .pill.done .ck { display:inline-block; }
  `;

  function mountButton(initialDone) {
    if (!_host) {
      _host = document.createElement('div');
      _host.style.cssText = 'position:fixed;bottom:16px;right:16px;z-index:2147483647;';
      const shadow = _host.attachShadow({ mode: 'open' });
      const style = document.createElement('style'); style.textContent = PILL_CSS;
      const row = document.createElement('div'); row.className = 'row';
      row.innerHTML =
        '<button class="undo" id="af-undo">Undo</button>' +
        '<button class="pill idle" id="af-pill">' +
        '<img class="mark" src="' + NAV_ICON + '" alt="">' +
        '<span class="spin"></span><span class="ck"></span>' +
        '<span class="label" id="af-label">Fill form</span>' +
        '<span class="count" id="af-count"></span></button>';
      shadow.append(style, row);
      _els = { pill: shadow.getElementById('af-pill'), label: shadow.getElementById('af-label'), count: shadow.getElementById('af-count'), undo: shadow.getElementById('af-undo') };
      _els.pill.addEventListener('click', onFillClick);
      _els.undo.addEventListener('click', onUndoClick);
      document.documentElement.appendChild(_host);
      _setState('idle');
    }
    if (initialDone) _setState('done', initialDone);
  }

  function _setState(s, data) {
    if (!_els) return;
    _els.pill.className = 'pill ' + s;
    _els.undo.style.display = 'none';
    if (s === 'idle') { _els.label.textContent = 'Fill form'; _els.count.textContent = String(_fieldCount()); _els.pill.disabled = false; }
    else if (s === 'filling') { _els.label.textContent = 'Filling…'; _els.count.textContent = data ? (data.done + '/' + data.total) : ''; _els.pill.disabled = true; }
    else if (s === 'done') {
      const f = data.filled, t = data.total;
      _els.label.textContent = (f < t) ? (f + ' of ' + t + ' fields filled') : (f + ' fields filled');
      _els.count.textContent = ''; _els.pill.disabled = false; _els.undo.style.display = 'flex';
    }
  }

  async function onFillClick() {
    if (_els && _els.pill.disabled) return;
    _setState('filling', { done: 0, total: _fieldCount() });
    const r = await runFill((done, total) => _setState('filling', { done, total }));
    _setState('done', { filled: r.filled.length, total: r.total });
  }
  function onUndoClick() { undo(_undoSnapshot); _setState('idle'); }

  async function autoFill() {
    const r = await runFill();
    mountButton({ filled: r.filled.length, total: r.total });
  }

  let _cfgCache; let _cfgDone = false;
  function ensureConfig() {
    if (_cfgDone) return Promise.resolve(_cfgCache);
    return getConfig().then(c => { _cfgCache = c; _cfgDone = true; return c; });
  }

  async function tryMount() {
    if (_started) return true;                      // already acting in this frame
    if (!looksLikeApplication()) return false;      // no fillable form in this frame yet
    const config = await ensureConfig();
    if (!config) return false;
    // Only act in a frame that has at least one fillable matched field — avoids
    // duplicate buttons across iframes / unrelated frames (all_frames:true).
    const hasFillable = buildPlan(discoverFields(), config).some(p => p.action === 'fill' || p.action === 'combobox');
    if (!hasFillable) return false;
    _started = true;
    // 'auto' fills on load then shows the button in its done/Undo state; 'click'
    // shows the idle button and fills on click. ('off' never reaches here.)
    if (_trigger === 'auto') autoFill(); else mountButton();
    return true;
  }

  function initStructured() {
    chrome.storage.sync.get([STRUCTURED_TOGGLE_KEY, STRUCTURED_TRIGGER_KEY], (cfg) => {
      if (!cfg[STRUCTURED_TOGGLE_KEY]) return;     // feature off
      _trigger = cfg[STRUCTURED_TRIGGER_KEY] === 'auto' ? 'auto' : 'click';
      tryMount();
      if (_host) return;
      // SPA application forms (Oracle/Workday/Ashby) render after page load, so a
      // one-shot check finds nothing. Re-check on DOM changes until the button
      // mounts, then stop. Bounded (60s cap) so it can't observe forever.
      let done = false;
      const obs = new MutationObserver(() => {
        if (done) return;
        clearTimeout(obs._t);
        obs._t = setTimeout(async () => {
          if (done) return;
          if (await tryMount()) { done = true; obs.disconnect(); }
        }, 600);
      });
      try { obs.observe(document.documentElement, { childList: true, subtree: true }); } catch (e) { /* ignore */ }
      setTimeout(() => { done = true; try { obs.disconnect(); } catch (e) { /* ignore */ } }, 60000);
    });
  }

  if (document.readyState === 'loading') window.addEventListener('DOMContentLoaded', initStructured);
  else initStructured();

  // React to the popup toggling the mode (Off / On click / Auto) without needing
  // a page reload: mount the button when enabled, remove it when turned Off.
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== 'sync') return;
    if (!changes[STRUCTURED_TOGGLE_KEY] && !changes[STRUCTURED_TRIGGER_KEY]) return;
    chrome.storage.sync.get([STRUCTURED_TOGGLE_KEY, STRUCTURED_TRIGGER_KEY], (cfg) => {
      _trigger = cfg[STRUCTURED_TRIGGER_KEY] === 'auto' ? 'auto' : 'click';
      if (!cfg[STRUCTURED_TOGGLE_KEY]) { if (_host) { _host.remove(); _host = null; } _els = null; _started = false; return; }
      tryMount();
    });
  });
})();
