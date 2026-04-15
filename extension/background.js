// Background service worker for JobNavigator Chrome Extension
// Handles context menu and background operations

function setupFrameRules() {
  chrome.declarativeNetRequest.updateSessionRules({
    removeRuleIds: [1, 2]
  }, () => {
    chrome.declarativeNetRequest.updateSessionRules({
    addRules: [
    {
      id: 1,
      priority: 1,
      action: {
        type: chrome.declarativeNetRequest.RuleActionType.MODIFY_HEADERS,
        responseHeaders: [
          { header: "x-frame-options", operation: chrome.declarativeNetRequest.HeaderOperation.REMOVE },
          { header: "content-security-policy", operation: chrome.declarativeNetRequest.HeaderOperation.REMOVE }
        ]
      },
      condition: {
        urlFilter: "*",
        resourceTypes: [
          chrome.declarativeNetRequest.ResourceType.MAIN_FRAME,
          chrome.declarativeNetRequest.ResourceType.SUB_FRAME
        ]
      }
    },
    {
      id: 2,
      priority: 1,
      action: {
        type: chrome.declarativeNetRequest.RuleActionType.MODIFY_HEADERS,
        requestHeaders: [
          { header: "sec-fetch-dest", operation: chrome.declarativeNetRequest.HeaderOperation.SET, value: "document" },
          { header: "sec-fetch-site", operation: chrome.declarativeNetRequest.HeaderOperation.SET, value: "none" }
        ]
      },
      condition: {
        urlFilter: "*",
        resourceTypes: [
          chrome.declarativeNetRequest.ResourceType.SUB_FRAME
        ]
      }
    }
    ]
    }, () => {
      if (chrome.runtime.lastError) {
        console.error('Failed to add rules:', chrome.runtime.lastError);
      } else {
        console.log('Frame header rules installed');
      }
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
});