// Background service worker for JobNavigator Chrome Extension
// Handles context menu and background operations

// The Job Feed previews postings in an iframe, which most career sites refuse
// (X-Frame-Options / CSP frame-ancestors). These rules lift that for frames the
// dashboard itself opens and nothing else: sub_frame only, and only when the
// request's initiator is the dashboard's host (serverUrl). A top-level page, or
// a frame opened by any other site, keeps its headers.
function dashboardHost(serverUrl) {
  try { return new URL(serverUrl || 'http://localhost').hostname.toLowerCase() } catch { return 'localhost' }
}

function setupFrameRules() {
  chrome.storage.sync.get(['serverUrl'], (settings) => {
    const host = dashboardHost(settings.serverUrl);
    const DNR = chrome.declarativeNetRequest;
    const condition = {
      urlFilter: "*",
      resourceTypes: [DNR.ResourceType.SUB_FRAME],
      initiatorDomains: [host],
    };
    chrome.declarativeNetRequest.updateSessionRules({ removeRuleIds: [1, 2] }, () => {
      chrome.declarativeNetRequest.updateSessionRules({
        addRules: [
          {
            id: 1,
            priority: 1,
            action: {
              type: DNR.RuleActionType.MODIFY_HEADERS,
              responseHeaders: [
                { header: "x-frame-options", operation: DNR.HeaderOperation.REMOVE },
                { header: "content-security-policy", operation: DNR.HeaderOperation.REMOVE }
              ]
            },
            condition,
          },
          {
            id: 2,
            priority: 1,
            action: {
              type: DNR.RuleActionType.MODIFY_HEADERS,
              requestHeaders: [
                { header: "sec-fetch-dest", operation: DNR.HeaderOperation.SET, value: "document" },
                { header: "sec-fetch-site", operation: DNR.HeaderOperation.SET, value: "none" }
              ]
            },
            condition,
          }
        ]
      }, () => {
        if (chrome.runtime.lastError) {
          console.error('Failed to add rules:', chrome.runtime.lastError);
        } else {
          console.log('Frame header rules installed for frames opened by', host);
        }
      });
    });
  });
}

chrome.runtime.onInstalled.addListener(() => {
  console.log('JobNavigator extension installed');
  setupFrameRules();
});

chrome.runtime.onStartup.addListener(() => {
  setupFrameRules();
});

// The rules are scoped to the dashboard's host, so they follow the server URL.
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === 'sync' && changes.serverUrl) setupFrameRules();
});

// Also run immediately in case service worker restarts
setupFrameRules();

// --- LinkedIn Capture ---

const capturedIds = new Set();

// Restore from session storage on service worker restart
chrome.storage.session.get('linkedinCapturedIds', (data) => {
  if (data.linkedinCapturedIds) {
    for (const id of data.linkedinCapturedIds) capturedIds.add(id);
    updateBadge();
  }
});

function updateBadge() {
  const count = capturedIds.size;
  chrome.action.setBadgeText({ text: count > 0 ? String(count) : '' });
  chrome.action.setBadgeBackgroundColor({ color: '#3B82F6' });
}

function backupToSession() {
  chrome.storage.session.set({ linkedinCapturedIds: Array.from(capturedIds) });
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  // Content script pushes captured IDs
  if (msg.type === 'linkedin_ids') {
    for (const id of msg.ids) capturedIds.add(id);
    updateBadge();
    backupToSession();
    sendResponse({ count: capturedIds.size });
    return;
  }

  // Popup requests count
  if (msg.type === 'linkedin_get_count') {
    sendResponse({ count: capturedIds.size });
    return;
  }

  // Popup triggers send to backend
  if (msg.type === 'linkedin_send') {
    const ids = Array.from(capturedIds);
    if (ids.length === 0) {
      sendResponse({ error: 'No jobs to send' });
      return;
    }

    chrome.storage.sync.get(['serverUrl', 'apiKey'], async (settings) => {
      const serverUrl = settings.serverUrl || 'http://localhost';
      const apiKey = settings.apiKey || '';

      try {
        const headers = { 'Content-Type': 'application/json' };
        if (apiKey) headers['X-API-Key'] = apiKey;

        const resp = await fetch(`${serverUrl}/api/jobs/linkedin-import`, {
          method: 'POST',
          headers,
          body: JSON.stringify({ linkedin_ids: ids }),
        });

        if (!resp.ok) {
          sendResponse({ error: `Server error: ${resp.status}` });
          return;
        }

        const result = await resp.json();
        capturedIds.clear();
        updateBadge();
        backupToSession();
        sendResponse(result);
      } catch (e) {
        sendResponse({ error: e.message });
      }
    });

    return true; // Async response
  }

  // Popup triggers clear
  if (msg.type === 'linkedin_clear') {
    capturedIds.clear();
    updateBadge();
    backupToSession();
    sendResponse({ ok: true });
    return;
  }

  // --- Application Autofill ---

  // Content script requests a generated answer for a focused application field
  if (msg.type === 'autofill_generate') {
    chrome.storage.sync.get(['serverUrl', 'apiKey'], async (settings) => {
      const serverUrl = settings.serverUrl || 'http://localhost';
      const apiKey = settings.apiKey || '';

      try {
        const headers = { 'Content-Type': 'application/json' };
        if (apiKey) headers['X-API-Key'] = apiKey;

        const resp = await fetch(`${serverUrl}/api/autofill/answer`, {
          method: 'POST',
          headers,
          body: JSON.stringify({
            question: msg.question,
            company: msg.company,
            position: msg.position,
            max_chars: msg.max_chars,
          }),
        });

        if (!resp.ok) {
          sendResponse({ error: `Server error: ${resp.status}` });
          return;
        }

        const result = await resp.json();
        sendResponse(result);
      } catch (e) {
        sendResponse({ error: e.message });
      }
    });

    return true; // Async response
  }

  // Content script saves an edited/approved answer to the persona Q&A bank
  if (msg.type === 'autofill_save') {
    chrome.storage.sync.get(['serverUrl', 'apiKey'], async (settings) => {
      const serverUrl = settings.serverUrl || 'http://localhost';
      const apiKey = settings.apiKey || '';

      try {
        const headers = { 'Content-Type': 'application/json' };
        if (apiKey) headers['X-API-Key'] = apiKey;

        const resp = await fetch(`${serverUrl}/api/persona/qa-bank`, {
          method: 'POST',
          headers,
          body: JSON.stringify({
            question: msg.question,
            answer: msg.answer,
          }),
        });

        if (!resp.ok) {
          sendResponse({ error: `Server error: ${resp.status}` });
          return;
        }

        const result = await resp.json();
        sendResponse(result);
      } catch (e) {
        sendResponse({ error: e.message });
      }
    });

    return true; // Async response
  }

  // Content script requests the structured-autofill config (answers + dictionaries)
  if (msg.type === 'autofill_config') {
    chrome.storage.sync.get(['serverUrl', 'apiKey'], async (settings) => {
      const serverUrl = settings.serverUrl || 'http://localhost';
      const apiKey = settings.apiKey || '';
      try {
        const headers = {};
        if (apiKey) headers['X-API-Key'] = apiKey;
        const resp = await fetch(`${serverUrl}/api/autofill/config`, { headers });
        if (!resp.ok) {
          sendResponse({ error: `Server error: ${resp.status}` });
          return;
        }
        sendResponse({ config: await resp.json() });
      } catch (e) {
        sendResponse({ error: e.message });
      }
    });
    return true; // Async response
  }
});

// --- Application Autofill: streaming draft relay (SSE over a long-lived port) ---
// The content script can't stream cross-origin easily, so it opens a port named
// 'autofill_stream', posts {question, company, position, max_chars}, and we relay
// the backend SSE endpoint back as {delta} / {done} / {error} port messages.
chrome.runtime.onConnect.addListener((port) => {
  if (port.name !== 'autofill_stream') return;

  let aborter = null;
  port.onDisconnect.addListener(() => { if (aborter) aborter.abort(); });

  port.onMessage.addListener((req) => {
    if (!req || req.type !== 'start') return;
    chrome.storage.sync.get(['serverUrl', 'apiKey'], async (settings) => {
      const serverUrl = settings.serverUrl || 'http://localhost';
      const apiKey = settings.apiKey || '';
      aborter = new AbortController();
      const post = (m) => { try { port.postMessage(m); } catch (_) {} };
      try {
        const headers = { 'Content-Type': 'application/json' };
        if (apiKey) headers['X-API-Key'] = apiKey;
        const resp = await fetch(`${serverUrl}/api/autofill/answer/stream`, {
          method: 'POST',
          headers,
          body: JSON.stringify({
            question: req.question,
            company: req.company,
            position: req.position,
            max_chars: req.max_chars,
            refinements: req.refinements || [],
          }),
          signal: aborter.signal,
        });
        if (!resp.ok || !resp.body) {
          post({ type: 'error', error: `Server error: ${resp.status}` });
          return;
        }
        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buf = '';
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          // SSE frames are separated by a blank line
          let idx;
          while ((idx = buf.indexOf('\n\n')) !== -1) {
            const frame = buf.slice(0, idx);
            buf = buf.slice(idx + 2);
            const line = frame.split('\n').find((l) => l.startsWith('data:'));
            if (!line) continue;
            const data = line.slice(5).trim();
            if (data === '[DONE]') { post({ type: 'done' }); continue; }
            try {
              const obj = JSON.parse(data);
              if (obj.delta) post({ type: 'delta', delta: obj.delta });
              else if (obj.error) post({ type: 'error', error: obj.error });
            } catch (_) { /* ignore malformed frame */ }
          }
        }
        post({ type: 'done' });
      } catch (e) {
        if (e.name !== 'AbortError') post({ type: 'error', error: e.message });
      }
    });
  });
});