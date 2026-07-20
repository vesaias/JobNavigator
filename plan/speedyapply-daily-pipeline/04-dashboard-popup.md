# Subproblem 4: Show the ready-to-apply popup

## 1. Goal
Display an in-app modal listing prepared applications and provide direct application, resume PDF, and resume editor links.

## 2. Why this step exists
The user needs a concise daily handoff: which companies to apply to, where the form is, and which tailored resume to use.

## 3. Files involved
- `frontend/src/components/ApplyQueueModal.jsx` - new modal with queue polling, links, progress/error states, and acknowledgement.
- `frontend/src/App.jsx` - mount the global modal after authentication.
- `frontend/src/components/Settings.jsx` - expose SpeedyApply feeds, schedule, timezone, age cap, run cap, resume selection, enabled state, and manual trigger.
- `frontend/src/api.js` - reuse the authenticated Axios client without changing its contract.

## 4. Exact changes
- Fetch unseen ready items after app startup and poll periodically so resumes completed after page load appear.
- Show company, title, location, source feed, application form link, PDF link, and resume editor link.
- Open application forms in a new tab; do not attempt form submission.
- Acknowledge items when the user closes or confirms the modal so the same batch does not reopen indefinitely.
- Add a SpeedyApply settings card with clear defaults and a manual “Run now” button.
- Explain that the backend must remain running and that employer forms, CAPTCHAs, and final submission remain manual.

## 5. Out of scope
- Do not automate browser form completion or CAPTCHA handling.
- Do not add OS-native notifications that require platform-specific services.

## 6. Done condition
New ready items open one clear modal, all paths are clickable, and acknowledged items do not appear in the unseen query.

## 7. Verification
- Run `npm run build` in `frontend/`.
- With a seeded ready queue item, load the dashboard, open each link, close the modal, and confirm it stays closed after refresh.

## 8. Expected output
A global ready-to-apply modal and editable SpeedyApply automation settings.

## 9. Notes for the next step
Documentation can describe the complete daily handoff and its manual boundary.

## 10. Risks or ambiguity
Browsers can block unsolicited OS notifications, so the implementation intentionally uses a reliable in-app modal.
