// ===== The Navigator popup — capture + settings =====
// Theme: 'system' leaves the attribute off so the prefers-color-scheme rule
// decides; an explicit choice pins it and wins over the OS.
function applyTheme(t) {
  if (t === 'light' || t === 'dark') document.documentElement.setAttribute('data-theme', t);
  else document.documentElement.removeAttribute('data-theme');
}

const $ = (id) => document.getElementById(id);
const VERSION = (chrome.runtime.getManifest && chrome.runtime.getManifest().version) || '';

// ---- URL / company detection (ported) ----
function hostMatches(url, ...domains) {
  let host;
  try { host = new URL(url).hostname.toLowerCase(); } catch { return false; }
  return domains.some(raw => {
    const d = (raw || '').toLowerCase().replace(/\/$/, '');
    return d && (host === d || host.endsWith('.' + d));
  });
}
const COMPANY_DOMAINS = {
  'microsoft.com': 'Microsoft', 'salesforce.com': 'Salesforce', 'servicenow.com': 'ServiceNow',
  'workday.com': 'Workday', 'paypal.com': 'PayPal', 'jpmorgan.com': 'JPMorgan Chase',
  'jpmorganchase.com': 'JPMorgan Chase', 'blackrock.com': 'BlackRock', 'addepar.com': 'Addepar',
  'oracle.com': 'Oracle', 'intuit.com': 'Intuit', 'google.com': 'Google', 'amazon.com': 'Amazon',
  'amazon.jobs': 'Amazon', 'stripe.com': 'Stripe', 'visa.com': 'Visa', 'mastercard.com': 'Mastercard',
  'uber.com': 'Uber', 'block.xyz': 'Block', 'plaid.com': 'Plaid', 'clearstreet.io': 'Clear Street',
  'simcorp.com': 'SimCorp', 'cisco.com': 'Cisco', 'ibm.com': 'IBM', 'meta.com': 'Meta',
  'metacareers.com': 'Meta', 'apple.com': 'Apple', 'databricks.com': 'Databricks', 'coinbase.com': 'Coinbase',
  'ubs.com': 'UBS', 'robinhood.com': 'Robinhood', 'affirm.com': 'Affirm', 'kraken.com': 'Kraken',
  'chime.com': 'Chime', 'ramp.com': 'Ramp', 'brex.com': 'Brex', 'rippling.com': 'Rippling',
  'greenhouse.io': '', 'lever.co': '', 'myworkdayjobs.com': '', 'taleo.net': '', 'icims.com': '',
  'eightfold.ai': '', 'linkedin.com': '', 'indeed.com': '', 'ziprecruiter.com': '',
};
function detectCompany(url) {
  try {
    const parsed = new URL(url);
    const hostname = parsed.hostname.toLowerCase();
    const pathParts = parsed.pathname.replace(/^\//, '').split('/').filter(Boolean);
    let detected = '';
    for (const [domain, company] of Object.entries(COMPANY_DOMAINS)) {
      if (hostname.includes(domain)) { detected = company; break; }
    }
    const titleCase = (s) => s.split(/[-_\s]+/).map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
    if (!detected) {
      for (const ats of ['eightfold.ai', 'myworkdayjobs.com', 'taleo.net', 'icims.com']) {
        if (hostname.endsWith(ats)) {
          const sub = hostname.replace(`.${ats}`, '').replace(/\./g, ' ').trim();
          if (sub && !['www', 'jobs', 'careers', 'apply'].includes(sub)) detected = titleCase(sub);
          break;
        }
      }
    }
    if (!detected) {
      for (const ats of ['greenhouse.io', 'lever.co', 'ashbyhq.com']) {
        if (hostname.endsWith(ats) && pathParts.length >= 1) {
          const slug = pathParts[0];
          if (slug && !['jobs', 'job', 'embed', 'api'].includes(slug)) detected = titleCase(slug);
          break;
        }
      }
    }
    if (!detected && hostMatches(url, 'rippling.com') && pathParts.length >= 1) {
      const slug = hostname === 'ats.rippling.com' || hostname.endsWith('.ats.rippling.com')
        ? pathParts[0] : (pathParts[0] === 'careers' && pathParts[1] ? pathParts[1] : '');
      if (slug) detected = titleCase(slug);
    }
    if (!detected && hostname === 'jobs.apple.com') detected = 'Apple';
    if (!detected && hostMatches(url, 'metacareers.com')) detected = 'Meta';
    if (!detected && hostMatches(url, 'google.com') && parsed.pathname.includes('/careers')) detected = 'Google';
    if (!detected) {
      const parts = hostname.split('.');
      const skip = ['www', 'jobs', 'careers', 'apply', 'boards', 'hire', 'recruiting', 'talent'];
      const tlds = ['com', 'org', 'net', 'co', 'io', 'ai', 'dev', 'xyz', 'us', 'uk', 'de', 'fr', 'ca', 'au', 'jobs'];
      const meaningful = parts.filter(p => !skip.includes(p) && !tlds.includes(p) && p.length > 1);
      if (meaningful.length) {
        const core = meaningful.length === 1 ? meaningful[0] : meaningful[meaningful.length - 1];
        detected = core.charAt(0).toUpperCase() + core.slice(1);
      }
    }
    return detected;
  } catch { return ''; }
}

// in-page extractors (executed in the tab)
function _extractTitleFn() {
  const skip = /^(careers|jobs|job search|open positions|work with|join)\b/i;
  const clean = (t) => t.trim().split('\n')[0].trim().substring(0, 200);
  const good = (t) => { t = (t || '').trim(); return t.length > 3 && !skip.test(t); };
  try {
    for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
      const d = JSON.parse(s.textContent);
      if (d['@type'] === 'JobPosting' && d.title) return clean(d.title);
    }
  } catch {}
  const sels = ['h1.job-title', 'h1.posting-headline', '.job-title h1', 'h1[data-job-title]',
    '.top-card-layout__title', 'h2[class*="position-title"]', '[class*="position-title"]', 'h1.t-24',
    '.jobsearch-JobInfoHeader-title', '.job-details h1', '.job-header h1', '.job-info h1',
    '[data-automation-id="jobPostingHeader"]'];
  for (const sel of sels) { const el = document.querySelector(sel); if (el && good(el.textContent)) return clean(el.textContent); }
  const og = document.querySelector('meta[property="og:title"]');
  if (og && good(og.content)) return clean(og.content);
  const h1 = document.querySelector('h1'); if (h1 && good(h1.textContent)) return clean(h1.textContent);
  const t = document.title.split(' - ')[0].split(' | ')[0].trim();
  return good(t) ? t : document.title;
}
function _extractDescFn() {
  const sels = ['[class*="jobs-description-content__text"]', '[class*="job-description"]', '[class*="jobDescription"]',
    '[class*="job_description"]', '[data-automation-id="jobPostingDescription"]', '.posting-page .content',
    '.job-details', '.description', 'article', '[role="article"]', 'main'];
  for (const sel of sels) { const el = document.querySelector(sel); if (el && el.innerText.trim().length > 100) return el.innerText.trim().substring(0, 15000); }
  for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
    try { const d = JSON.parse(s.textContent); if (d['@type'] === 'JobPosting' && d.description) { const div = document.createElement('div'); div.innerHTML = d.description; return div.innerText.trim().substring(0, 15000); } } catch {}
  }
  return '';
}

// ---- state ----
const state = {
  screen: 'capture', url: '', host: '', path: '',
  send: 'idle', applied: 'idle', lastError: '',
  li: false, af: false, atsMode: 'off', len: 250, captured: 0,
  theme: 'system',
  liInfo: false, afInfo: false, charsOpen: false, urlOpen: false,
  serverUrl: 'http://localhost', apiKey: '',
};
let _sendT, _saveT;

async function cfg() {
  const s = await chrome.storage.sync.get(['serverUrl', 'apiKey']);
  state.serverUrl = s.serverUrl || 'http://localhost';
  state.apiKey = s.apiKey || '';
  return { serverUrl: state.serverUrl, apiKey: state.apiKey };
}

// ---- render ----
function render() {
  const cap = state.screen === 'capture';
  $('hdrCapture').classList.toggle('hide', !cap);
  $('hdrSettings').classList.toggle('hide', cap);
  $('screenCapture').classList.toggle('hide', !cap);
  $('screenSettings').classList.toggle('hide', cap);

  // source
  $('srcHost').textContent = state.host;
  $('srcPath').textContent = state.path;
  const detected = !!($('title').value.trim() && $('company').value.trim());
  $('chipDetected').classList.toggle('hide', !detected);
  $('chipNot').classList.toggle('hide', detected);

  // send states
  $('btnSend').classList.toggle('hide', state.send !== 'idle');
  $('btnSending').classList.toggle('hide', state.send !== 'sending');
  $('btnSent').classList.toggle('hide', state.send !== 'sent');
  $('btnRetry').classList.toggle('hide', state.send !== 'error');

  // applied button
  const ab = $('btnApplied');
  ab.classList.remove('saved', 'err-btn');
  if (state.applied === 'saving') ab.innerHTML = '<div class="spin" style="border-color:rgba(0,0,0,.18); border-top-color:#57534C"></div>';
  else if (state.applied === 'saved') { ab.classList.add('saved'); ab.innerHTML = '<div class="check-sm"></div>Saved'; }
  else if (state.applied === 'exists') { ab.classList.add('saved'); ab.innerHTML = '<div class="check-sm"></div>Already logged'; }
  else if (state.applied === 'error') { ab.classList.add('err-btn'); ab.innerHTML = 'Retry'; }
  else ab.innerHTML = 'Save as applied';

  // error card (send or applied) — text depends on which action failed
  const showErr = state.send === 'error' || state.applied === 'error';
  $('errCard').classList.toggle('hide', !showErr);
  if (showErr) $('errHd').textContent = state.lastError === 'applied' ? "Couldn't reach the Application Board" : "Couldn't reach the Job Feed";

  // captured strip + LinkedIn count
  $('capturedStrip').classList.toggle('hide', state.captured <= 0);
  $('capturedCount').textContent = String(state.captured);
  $('liCount').classList.toggle('hide', state.captured > 0);
  $('liCount').textContent = `${state.captured} jobs`;

  // toggles
  $('liToggle').dataset.on = String(state.li);
  $('afToggle').dataset.on = String(state.af);
  $('liInfoCard').classList.toggle('hide', !state.liInfo);
  $('afInfoCard').classList.toggle('hide', !state.afInfo);

  // chars
  $('lenChip').textContent = `${state.len} chars`;
  $('charsPanel').style.display = state.charsOpen ? 'flex' : 'none';
  document.querySelectorAll('.preset').forEach(p => p.classList.toggle('active', Number(p.dataset.len) === state.len));

  // ats segmented
  document.querySelectorAll('.seg-opt[data-mode]').forEach(o => o.classList.toggle('active', o.dataset.mode === state.atsMode));
  document.querySelectorAll('[data-theme-opt]').forEach(o => o.classList.toggle('active', o.dataset.themeOpt === state.theme));

  // url sheet
  $('urlSheet').classList.toggle('hide', !state.urlOpen);
}

// ---- actions ----
async function doSend() {
  if (state.send === 'sending') return;
  const title = $('title').value.trim(), company = $('company').value.trim(), url = state.url.trim();
  if (!title || !company || !url) return;
  state.send = 'sending'; render();
  let description = '';
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab) { const [r] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: _extractDescFn }); if (r && r.result) description = r.result; }
  } catch {}
  try {
    const resp = await fetch(`${state.serverUrl}/api/jobs/save-from-extension`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'X-API-Key': state.apiKey },
      body: JSON.stringify({ title, company, url, description }),
    });
    if (!resp.ok) throw new Error(String(resp.status));
    state.send = 'sent'; render();
    clearTimeout(_sendT); _sendT = setTimeout(() => { state.send = 'idle'; render(); }, 1800);
  } catch { state.send = 'error'; state.lastError = 'send'; render(); }
}
async function doApplied() {
  if (state.applied === 'saving') return;
  const title = $('title').value.trim(), company = $('company').value.trim(), url = state.url.trim();
  if (!title || !company || !url) return;
  state.applied = 'saving'; render();
  try {
    const resp = await fetch(`${state.serverUrl}/api/applications`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'X-API-Key': state.apiKey },
      body: JSON.stringify({ title, company, url }),
    });
    if (resp.status === 409) { state.applied = 'exists'; render(); clearTimeout(_saveT); _saveT = setTimeout(() => { state.applied = 'idle'; render(); }, 2200); return; }   // already logged for this posting
    if (!resp.ok) throw new Error(String(resp.status));
    state.applied = 'saved'; render();
    clearTimeout(_saveT); _saveT = setTimeout(() => { state.applied = 'idle'; render(); }, 1800);
  } catch { state.applied = 'error'; state.lastError = 'applied'; render(); }
}

async function checkConnection() {
  $('connDot').classList.remove('bad'); $('connTx').textContent = 'Checking…';
  try {
    const resp = await fetch(`${$('serverUrl').value.trim() || state.serverUrl}/api/autofill/config`,
      { headers: { 'X-API-Key': $('apiKey').value.trim() || state.apiKey } });
    if (resp.status === 401) { $('connDot').classList.add('bad'); $('connTx').textContent = 'API key rejected'; }
    else if (resp.ok) { $('connDot').classList.remove('bad'); $('connTx').textContent = `Connected · v${VERSION}`; }
    else { $('connDot').classList.add('bad'); $('connTx').textContent = `Server error ${resp.status}`; }
  } catch { $('connDot').classList.add('bad'); $('connTx').textContent = 'Cannot reach server'; }
}

// ---- init ----
document.addEventListener('DOMContentLoaded', async () => {
  await cfg();
  $('serverUrl').value = state.serverUrl;
  $('apiKey').value = state.apiKey;

  // storage-backed feature state
  const st = await chrome.storage.sync.get(['linkedinCapture', 'autofillEnabled', 'autofillDefaultLength', 'structuredAutofillEnabled', 'structuredAutofillTrigger', 'theme']);
  state.li = !!st.linkedinCapture;
  state.af = !!st.autofillEnabled;
  state.len = Number(st.autofillDefaultLength) > 0 ? Number(st.autofillDefaultLength) : 250;
  state.atsMode = !st.structuredAutofillEnabled ? 'off' : (st.structuredAutofillTrigger === 'auto' ? 'auto' : 'click');
  state.theme = ['light', 'dark', 'system'].includes(st.theme) ? st.theme : 'system';
  applyTheme(state.theme);
  $('lenCustom').value = String(state.len);

  // captured count
  chrome.runtime.sendMessage({ type: 'linkedin_get_count' }, (resp) => { if (resp && resp.count !== undefined) { state.captured = resp.count; render(); } });

  // current tab → source + parse
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab) {
    state.url = tab.url || '';
    try { const u = new URL(state.url); state.host = u.hostname.replace(/^www\./, ''); state.path = (u.pathname + u.search).slice(0, 40); } catch { state.host = state.url.slice(0, 40); }
    if (tab.favIconUrl) { $('favicon').src = tab.favIconUrl; } else { $('favicon').style.background = '#DCE7F3'; }
    const co = detectCompany(state.url); if (co) $('company').value = co;
    render();
    try {
      const [r] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: _extractTitleFn });
      if (r && r.result) $('title').value = r.result;
    } catch { if (tab.title) $('title').value = tab.title.split(' - ')[0].split(' | ')[0].trim(); }
  }
  render();

  // header nav
  $('toSettings').onclick = () => { state.screen = 'settings'; render(); checkConnection(); };
  $('hdrSettings').onclick = () => { state.screen = 'capture'; render(); };

  // capture actions
  $('btnSend').onclick = doSend;
  $('btnRetry').onclick = doSend;
  $('btnApplied').onclick = doApplied;
  $('title').oninput = render;
  $('company').oninput = render;

  // edit url sheet
  $('btnEditUrl').onclick = () => { $('urlText').value = state.url; state.urlOpen = true; render(); };
  $('urlCancel').onclick = () => { state.urlOpen = false; render(); };
  $('urlSheet').onclick = (e) => { if (e.target === $('urlSheet')) { state.urlOpen = false; render(); } };
  $('urlUpdate').onclick = () => {
    state.url = $('urlText').value.trim();
    try { const u = new URL(state.url); state.host = u.hostname.replace(/^www\./, ''); state.path = (u.pathname + u.search).slice(0, 40); } catch {}
    state.urlOpen = false; render();
  };

  // captured strip → send LinkedIn
  $('capturedStrip').onclick = () => {
    chrome.runtime.sendMessage({ type: 'linkedin_send' }, (resp) => { if (resp && !resp.error) { state.captured = 0; render(); } });
  };

  // footer: LinkedIn
  $('liToggle').onclick = () => { state.li = !state.li; chrome.storage.sync.set({ linkedinCapture: state.li }); render(); };
  $('liInfo').onclick = () => { state.liInfo = !state.liInfo; render(); };
  $('liClear').onclick = () => { chrome.runtime.sendMessage({ type: 'linkedin_clear' }, () => { state.captured = 0; render(); }); };

  // footer: AI-drafted
  $('afToggle').onclick = () => { state.af = !state.af; chrome.storage.sync.set({ autofillEnabled: state.af }); render(); };
  $('afInfo').onclick = () => { state.afInfo = !state.afInfo; render(); };
  $('lenChip').onclick = () => { state.charsOpen = !state.charsOpen; render(); };
  document.querySelectorAll('.preset').forEach(p => p.onclick = () => {
    state.len = Number(p.dataset.len); $('lenCustom').value = String(state.len);
    chrome.storage.sync.set({ autofillDefaultLength: state.len }); render();
  });
  $('lenCustom').onchange = () => {
    const n = parseInt($('lenCustom').value, 10);
    if (n > 0) { state.len = n; chrome.storage.sync.set({ autofillDefaultLength: n }); render(); }
  };

  // footer: Fill ATS forms segmented
  document.querySelectorAll('[data-theme-opt]').forEach(o => o.onclick = () => {
    state.theme = o.dataset.themeOpt;
    chrome.storage.sync.set({ theme: state.theme });
    applyTheme(state.theme);
    render();
  });
  document.querySelectorAll('.seg-opt[data-mode]').forEach(o => o.onclick = () => {
    state.atsMode = o.dataset.mode;
    if (state.atsMode === 'off') chrome.storage.sync.set({ structuredAutofillEnabled: false });
    else chrome.storage.sync.set({ structuredAutofillEnabled: true, structuredAutofillTrigger: state.atsMode });
    render();
  });

  // settings
  $('showKey').onclick = () => {
    const on = $('apiKey').type === 'password';
    $('apiKey').type = on ? 'text' : 'password'; $('showKey').textContent = on ? 'Hide' : 'Show';
  };
  $('apiKey').onchange = checkConnection;
  $('serverUrl').onchange = checkConnection;
  $('saveSettings').onclick = async () => {
    state.serverUrl = $('serverUrl').value.trim(); state.apiKey = $('apiKey').value.trim();
    await chrome.storage.sync.set({ serverUrl: state.serverUrl, apiKey: state.apiKey });
    await checkConnection();
    state.screen = 'capture'; render();
  };

  render();
});

// live LinkedIn count updates
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === 'linkedin_count_update') { state.captured = msg.count; render(); }
});
