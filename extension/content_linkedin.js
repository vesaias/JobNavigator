// LinkedIn Collection Page Capture
// Runs on: linkedin.com/jobs/collections/*
// Passively captures job IDs from card links as the user scrolls.
// Backend handles all scraping via Playwright.

(() => {
  const capturedIds = new Set();
  let observer = null;
  let enabled = false;

  function scan() {
    let added = 0;
    document.querySelectorAll('a[href*="/jobs/view/"]').forEach(link => {
      const match = link.href.match(/\/jobs\/view\/(\d+)/);
      if (!match) return;
      const jobId = match[1];
      if (capturedIds.has(jobId)) return;
      capturedIds.add(jobId);
      added++;
    });
    if (added > 0) {
      chrome.runtime.sendMessage({
        type: 'linkedin_ids',
        ids: Array.from(capturedIds),
      });
    }
  }

  function startCapturing() {
    if (observer) return;
    scan();

    const target = document.querySelector('[class*="jobs-search-results"]')
      || document.querySelector('main')
      || document.body;

    observer = new MutationObserver(() => scan());
    observer.observe(target, { childList: true, subtree: true });
  }

  function stopCapturing() {
    if (observer) {
      observer.disconnect();
      observer = null;
    }
  }

  function checkEnabled() {
    chrome.storage.sync.get('linkedinCapture', (data) => {
      const shouldBeEnabled = !!data.linkedinCapture;
      if (shouldBeEnabled && !enabled) {
        enabled = true;
        startCapturing();
      } else if (!shouldBeEnabled && enabled) {
        enabled = false;
        stopCapturing();
      }
    });
  }

  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === 'sync' && changes.linkedinCapture) {
      checkEnabled();
    }
  });

  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.type === 'linkedin_clear_ids') {
      capturedIds.clear();
      sendResponse({ ok: true });
    }
  });

  checkEnabled();
})();
