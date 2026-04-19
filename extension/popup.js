// Hostname-safe URL matching helper. Avoids "substring of URL" pitfalls where
// e.g. "evil-rippling.com" would match a naive `hostname.includes('rippling.com')`.
function hostMatches(url, ...domains) {
  let host
  try { host = new URL(url).hostname.toLowerCase() } catch { return false }
  return domains.some(raw => {
    const d = (raw || '').toLowerCase().replace(/\/$/, '')
    return d && (host === d || host.endsWith('.' + d))
  })
}

// Known company domains for auto-detection
const COMPANY_DOMAINS = {
  'microsoft.com': 'Microsoft', 'salesforce.com': 'Salesforce',
  'servicenow.com': 'ServiceNow', 'workday.com': 'Workday',
  'paypal.com': 'PayPal', 'jpmorgan.com': 'JPMorgan Chase',
  'jpmorganchase.com': 'JPMorgan Chase', 'blackrock.com': 'BlackRock',
  'addepar.com': 'Addepar', 'oracle.com': 'Oracle',
  'intuit.com': 'Intuit', 'google.com': 'Google',
  'amazon.com': 'Amazon', 'amazon.jobs': 'Amazon',
  'stripe.com': 'Stripe', 'visa.com': 'Visa',
  'mastercard.com': 'Mastercard', 'uber.com': 'Uber',
  'block.xyz': 'Block', 'plaid.com': 'Plaid',
  'clearstreet.io': 'Clear Street', 'simcorp.com': 'SimCorp',
  'cisco.com': 'Cisco', 'ibm.com': 'IBM',
  'meta.com': 'Meta', 'metacareers.com': 'Meta',
  'apple.com': 'Apple', 'databricks.com': 'Databricks',
  'coinbase.com': 'Coinbase', 'ubs.com': 'UBS',
  'robinhood.com': 'Robinhood', 'affirm.com': 'Affirm',
  'kraken.com': 'Kraken', 'chime.com': 'Chime',
  'ramp.com': 'Ramp', 'brex.com': 'Brex',
  'rippling.com': 'Rippling',
  // ATS domains
  'greenhouse.io': '', 'lever.co': '', 'myworkdayjobs.com': '',
  'taleo.net': '', 'icims.com': '', 'eightfold.ai': '',
  // Job boards
  'linkedin.com': '', 'indeed.com': '', 'ziprecruiter.com': '',
};

document.addEventListener('DOMContentLoaded', async () => {
  const mainPage = document.getElementById('mainPage');
  const settingsPage = document.getElementById('settingsPage');

  // Load settings
  const settings = await chrome.storage.sync.get(['serverUrl', 'apiKey']);
  document.getElementById('serverUrl').value = settings.serverUrl || 'http://localhost';
  document.getElementById('apiKey').value = settings.apiKey || '';

  // Pre-fill from current tab
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab) {
    document.getElementById('url').value = tab.url || '';

    // Auto-detect company from URL — 3 layers
    try {
      const parsed = new URL(tab.url);
      const hostname = parsed.hostname.toLowerCase();
      const pathParts = parsed.pathname.replace(/^\//, '').split('/').filter(Boolean);
      let detected = '';

      // Layer 1: hardcoded domain map
      for (const [domain, company] of Object.entries(COMPANY_DOMAINS)) {
        if (hostname.includes(domain)) {
          detected = company;
          break;
        }
      }

      // Layer 2: ATS URL pattern detection
      if (!detected) {
        const titleCase = (s) => s.split(/[-_\s]+/).map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');

        // Subdomain-based: {company}.eightfold.ai, {company}.myworkdayjobs.com, {company}.taleo.net, {company}.icims.com
        const subdomainAts = ['eightfold.ai', 'myworkdayjobs.com', 'taleo.net', 'icims.com'];
        for (const ats of subdomainAts) {
          if (hostname.endsWith(ats)) {
            const sub = hostname.replace(`.${ats}`, '').replace(/\./g, ' ').trim();
            if (sub && !['www', 'jobs', 'careers', 'apply'].includes(sub)) {
              detected = titleCase(sub);
            }
            break;
          }
        }

        // Path-based: boards.greenhouse.io/{company}, jobs.lever.co/{company}, jobs.ashbyhq.com/{company}
        if (!detected) {
          const pathAts = {
            'greenhouse.io': true,    // boards.greenhouse.io/{company} or job-boards.greenhouse.io/{company}
            'lever.co': true,         // jobs.lever.co/{company}
            'ashbyhq.com': true,      // jobs.ashbyhq.com/{company}
          };
          for (const [ats] of Object.entries(pathAts)) {
            if (hostname.endsWith(ats) && pathParts.length >= 1) {
              const slug = pathParts[0];
              if (slug && !['jobs', 'job', 'embed', 'api'].includes(slug)) {
                detected = titleCase(slug);
              }
              break;
            }
          }
        }

        // Rippling: ats.rippling.com/{company} or rippling.com/careers/{company}
        if (!detected && hostMatches(tab.url, 'rippling.com') && pathParts.length >= 1) {
          const slug = hostname === 'ats.rippling.com' || hostname.endsWith('.ats.rippling.com')
            ? pathParts[0]
            : (pathParts[0] === 'careers' && pathParts[1] ? pathParts[1] : '');
          if (slug) detected = titleCase(slug);
        }

        // Apple: jobs.apple.com
        if (!detected && hostname === 'jobs.apple.com') detected = 'Apple';

        // Meta: metacareers.com
        if (!detected && hostMatches(tab.url, 'metacareers.com')) detected = 'Meta';

        // Google: google.com/about/careers
        if (!detected && hostMatches(tab.url, 'google.com') && parsed.pathname.includes('/careers')) detected = 'Google';
      }

      // Layer 3: fallback — extract from core domain
      if (!detected) {
        const parts = hostname.split('.');
        // Strip common prefixes: www, jobs, careers, apply, boards, hire
        const skip = ['www', 'jobs', 'careers', 'apply', 'boards', 'hire', 'recruiting', 'talent'];
        // Strip TLDs: com, org, net, co, io, ai, etc. and country codes
        const tlds = ['com', 'org', 'net', 'co', 'io', 'ai', 'dev', 'xyz', 'us', 'uk', 'de', 'fr', 'ca', 'au', 'jobs'];
        const meaningful = parts.filter(p => !skip.includes(p) && !tlds.includes(p) && p.length > 1);
        if (meaningful.length > 0) {
          // Take the most likely company part (usually the main domain)
          const core = meaningful.length === 1 ? meaningful[0] : meaningful[meaningful.length - 1];
          detected = core.charAt(0).toUpperCase() + core.slice(1);
        }
      }

      if (detected) {
        document.getElementById('company').value = detected;
      }
    } catch (e) {}

    // Try to extract title from page
    try {
      const [result] = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: async () => {
          const log = [];
          const skipPatterns = /^(careers|jobs|job search|open positions|work with|join)\b/i;

          function cleanTitle(text) {
            return text.trim().split('\n')[0].trim().substring(0, 200);
          }

          function isGoodTitle(text) {
            const t = text.trim();
            return t.length > 3 && !skipPatterns.test(t);
          }

          // 1. Try JSON-LD schema first
          try {
            const ldScripts = document.querySelectorAll('script[type="application/ld+json"]');
            log.push(`[1] JSON-LD scripts found: ${ldScripts.length}`);
            for (const s of ldScripts) {
              const data = JSON.parse(s.textContent);
              log.push(`[1] JSON-LD @type=${data['@type']}, title=${data.title || 'N/A'}`);
              if (data['@type'] === 'JobPosting' && data.title) {
                log.push(`[1] MATCH: ${data.title}`);
                return cleanTitle(data.title);
              }
            }
          } catch (e) {
            log.push(`[1] JSON-LD error: ${e.message}`);
          }

          const selectors = [
            'h1.job-title', 'h1.posting-headline', '.job-title h1',
            'h1[data-job-title]', '.top-card-layout__title',
            'h2[class*="position-title"]', '[class*="position-title"]',
            'h1.t-24', '.jobsearch-JobInfoHeader-title',
            '.job-details h1', '.job-header h1', '.job-info h1',
            '[data-automation-id="jobPostingHeader"]',
          ];

          // 2. Try CSS selectors immediately
          for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (el) {
              log.push(`[2] Selector "${sel}" => "${el.textContent.trim().substring(0, 80)}" good=${isGoodTitle(el.textContent)}`);
              if (isGoodTitle(el.textContent)) {
                return cleanTitle(el.textContent);
              }
            }
          }
          log.push('[2] No CSS selector matched');

          // 3. Try meta tags
          const ogTitle = document.querySelector('meta[property="og:title"]');
          log.push(`[3] og:title = ${ogTitle ? ogTitle.content : 'NOT FOUND'}`);
          if (ogTitle && isGoodTitle(ogTitle.content)) {
            return cleanTitle(ogTitle.content);
          }

          // 4. Wait up to 3s for dynamic content
          for (let i = 0; i < 6; i++) {
            await new Promise(r => setTimeout(r, 500));
            for (const sel of selectors) {
              const el = document.querySelector(sel);
              if (el && isGoodTitle(el.textContent)) {
                log.push(`[4] After ${(i+1)*500}ms, selector "${sel}" => "${el.textContent.trim().substring(0, 80)}"`);
                return cleanTitle(el.textContent);
              }
            }
          }
          log.push('[4] No match after 3s wait');

          // 5. Try generic h1
          const h1 = document.querySelector('h1');
          log.push(`[5] h1 = "${h1 ? h1.textContent.trim().substring(0, 80) : 'NOT FOUND'}" good=${h1 ? isGoodTitle(h1.textContent) : false}`);
          if (h1 && isGoodTitle(h1.textContent)) {
            return cleanTitle(h1.textContent);
          }

          // 6. Fallback to document.title
          const title = document.title.split(' - ')[0].split(' | ')[0].trim();
          log.push(`[6] document.title = "${document.title}", cleaned = "${title}", good=${isGoodTitle(title)}`);
          if (isGoodTitle(title)) return title;
          return document.title;
        },
      });
      if (result && result.result) {
        document.getElementById('title').value = result.result;
      }
    } catch (e) {
      // If scripting fails, use page title
      if (tab.title) {
        document.getElementById('title').value = tab.title.split(' - ')[0].split(' | ')[0].trim();
      }
    }
  }

  // Save application
  document.getElementById('saveBtn').addEventListener('click', async () => {
    const btn = document.getElementById('saveBtn');
    const status = document.getElementById('status');

    const title = document.getElementById('title').value.trim();
    const company = document.getElementById('company').value.trim();
    const url = document.getElementById('url').value.trim();

    if (!title || !company || !url) {
      status.textContent = 'Please fill in title, company, and URL';
      status.className = 'status error';
      return;
    }

    const serverUrl = (await chrome.storage.sync.get('serverUrl')).serverUrl || 'http://localhost';
    const apiKey = (await chrome.storage.sync.get('apiKey')).apiKey || '';

    btn.disabled = true;
    btn.textContent = 'Saving...';

    try {
      const resp = await fetch(`${serverUrl}/api/applications`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-API-Key': apiKey },
        body: JSON.stringify({ title, company, url }),
      });

      if (resp.ok) {
        const data = await resp.json();
        status.textContent = `Application logged for ${data.company}`;
        status.className = 'status success';
        btn.textContent = 'Saved!';
      } else {
        const err = await resp.text();
        status.textContent = `Error: ${err}`;
        status.className = 'status error';
        btn.disabled = false;
        btn.textContent = 'Save Application';
      }
    } catch (e) {
      status.textContent = `Connection failed: ${e.message}. Check Settings.`;
      status.className = 'status error';
      btn.disabled = false;
      btn.textContent = 'Save Application';
    }
  });

  // Save to Job Feed (no application)
  document.getElementById('saveJobBtn').addEventListener('click', async () => {
    const btn = document.getElementById('saveJobBtn');
    const status = document.getElementById('status');

    const title = document.getElementById('title').value.trim();
    const company = document.getElementById('company').value.trim();
    const url = document.getElementById('url').value.trim();

    if (!title || !company || !url) {
      status.textContent = 'Please fill in title, company, and URL';
      status.className = 'status error';
      return;
    }

    const serverUrl = (await chrome.storage.sync.get('serverUrl')).serverUrl || 'http://localhost';
    const apiKey = (await chrome.storage.sync.get('apiKey')).apiKey || '';

    btn.disabled = true;
    btn.textContent = 'Extracting...';

    // Try to extract job description from the current page
    let description = '';
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tab) {
        const [result] = await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          func: () => {
            // Try common job description selectors
            const selectors = [
              '[class*="jobs-description-content__text"]', '[class*="job-description"]',
              '[class*="jobDescription"]', '[class*="job_description"]',
              '[data-automation-id="jobPostingDescription"]',
              '.posting-page .content', '.job-details', '.description',
              'article', '[role="article"]', 'main',
            ];
            for (const sel of selectors) {
              const el = document.querySelector(sel);
              if (el && el.innerText.trim().length > 100) {
                return el.innerText.trim().substring(0, 15000);
              }
            }
            // Fallback: try JSON-LD
            const ldScripts = document.querySelectorAll('script[type="application/ld+json"]');
            for (const s of ldScripts) {
              try {
                const data = JSON.parse(s.textContent);
                if (data['@type'] === 'JobPosting' && data.description) {
                  const div = document.createElement('div');
                  div.innerHTML = data.description;
                  return div.innerText.trim().substring(0, 15000);
                }
              } catch {}
            }
            return '';
          },
        });
        if (result && result.result) description = result.result;
      }
    } catch {}

    btn.textContent = 'Saving...';

    try {
      const resp = await fetch(`${serverUrl}/api/jobs/save-from-extension`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-API-Key': apiKey },
        body: JSON.stringify({ title, company, url, description }),
      });

      if (resp.ok) {
        const data = await resp.json();
        status.textContent = `${data.new ? 'Saved' : 'Already exists'}: ${data.title} at ${data.company}`;
        status.className = 'status success';
        btn.textContent = 'Saved!';
      } else {
        const err = await resp.text();
        status.textContent = `Error: ${err}`;
        status.className = 'status error';
        btn.disabled = false;
        btn.textContent = 'Save to Job Feed';
      }
    } catch (e) {
      status.textContent = `Connection failed: ${e.message}. Check Settings.`;
      status.className = 'status error';
      btn.disabled = false;
      btn.textContent = 'Save to Job Feed';
    }
  });

  // Settings navigation
  document.getElementById('settingsBtn').addEventListener('click', () => {
    mainPage.className = 'main-page';
    settingsPage.className = 'settings-page active';
  });

  document.getElementById('backBtn').addEventListener('click', () => {
    settingsPage.className = 'settings-page';
    mainPage.className = 'main-page active';
  });

  // Save settings
  document.getElementById('saveSettingsBtn').addEventListener('click', async () => {
    const serverUrl = document.getElementById('serverUrl').value.trim();
    const apiKey = document.getElementById('apiKey').value.trim();
    const settingsStatus = document.getElementById('settingsStatus');

    await chrome.storage.sync.set({ serverUrl, apiKey });
    settingsStatus.textContent = 'Settings saved!';
    settingsStatus.className = 'status success';

    setTimeout(() => {
      settingsPage.className = 'settings-page';
      mainPage.className = 'main-page active';
    }, 800);
  });
});

// --- LinkedIn Capture UI ---

const linkedinToggle = document.getElementById('linkedin-toggle');
const linkedinCount = document.getElementById('linkedin-count');
const linkedinSend = document.getElementById('linkedin-send');
const linkedinClear = document.getElementById('linkedin-clear');
const linkedinStatus = document.getElementById('linkedin-status');

function showLinkedinStatus(msg, isError) {
  linkedinStatus.textContent = msg;
  linkedinStatus.style.color = isError ? '#dc2626' : '#16a34a';
  linkedinStatus.style.display = 'block';
  setTimeout(() => { linkedinStatus.style.display = 'none'; }, 4000);
}

function updateLinkedinCount(count) {
  linkedinCount.textContent = `${count} job${count !== 1 ? 's' : ''} captured`;
  linkedinSend.disabled = count === 0;
  linkedinClear.disabled = count === 0;
}

// Load toggle state
chrome.storage.sync.get('linkedinCapture', (data) => {
  linkedinToggle.checked = !!data.linkedinCapture;
});

// Get current count from background
chrome.runtime.sendMessage({ type: 'linkedin_get_count' }, (resp) => {
  if (resp && resp.count !== undefined) {
    updateLinkedinCount(resp.count);
  }
});

// Toggle handler
linkedinToggle.addEventListener('change', () => {
  chrome.storage.sync.set({ linkedinCapture: linkedinToggle.checked });
});

// Send button
linkedinSend.addEventListener('click', () => {
  linkedinSend.disabled = true;
  linkedinSend.textContent = 'Sending...';

  chrome.runtime.sendMessage({ type: 'linkedin_send' }, (resp) => {
    linkedinSend.textContent = 'Send to JobNavigator';
    if (resp && resp.error) {
      showLinkedinStatus(resp.error, true);
      linkedinSend.disabled = false;
    } else if (resp) {
      // Show detailed count: new vs already imported
      let msg;
      if (resp.new !== undefined) {
        if (resp.already_imported > 0) {
          msg = `Processing ${resp.new} new job${resp.new !== 1 ? 's' : ''} (${resp.already_imported} already imported)`;
        } else {
          msg = `Processing ${resp.new} new job${resp.new !== 1 ? 's' : ''}`;
        }
      } else {
        msg = resp.message || `Sent ${resp.accepted} jobs for processing`;
      }
      showLinkedinStatus(msg, false);
      updateLinkedinCount(0);
    }
  });
});

// Clear button
linkedinClear.addEventListener('click', () => {
  chrome.runtime.sendMessage({ type: 'linkedin_clear' }, () => {
    updateLinkedinCount(0);
  });
});

// Listen for count updates while popup is open
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === 'linkedin_count_update') {
    updateLinkedinCount(msg.count);
  }
});
