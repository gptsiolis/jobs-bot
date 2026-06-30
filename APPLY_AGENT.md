# Autonomous apply agent

Submits applications you've **approved** on the dashboard by driving a real,
logged-in Chrome profile with Playwright. Auto-submits the clean structured ATS
(Greenhouse / Lever / Ashby); fills + flags everything else for a quick manual
finish. Runs locally — your machine must be on when it runs.

## One-time setup

1. **Install the browser** Playwright uses (local):
   ```
   python -m playwright install chromium
   ```
2. **Apply the migration** (adds submit tracking + the `applications` bucket):
   ```
   python scripts/apply_migration.py supabase/migrations/015_application_submit.sql
   ```
3. **Log into the agent's Chrome profile once** (saves your sessions so the agent
   isn't blocked by logins):
   ```
   python apply_agent.py --login
   ```
   A Chrome window opens on a dedicated profile (`~/.jobs-bot/apply-profile`, or
   `APPLY_PROFILE_DIR`). Sign into LinkedIn / Google / any ATS accounts, then press
   Enter in the terminal to save and close.
4. **(Recommended) Add a location + postal code** to your `/profile`. Many forms
   require location; for remote roles it's harmless and it raises the auto-submit
   rate (otherwise those jobs get flagged instead of submitted).

## Running

- Manually:  `python apply_agent.py`  (drafts anything queued, then submits approved)
- Test without submitting:  `python apply_agent.py --dry-run`
- Headless:  set `APPLY_HEADLESS=1`

## Nightly schedule (Windows Task Scheduler)

```
schtasks /Create /SC DAILY /TN "JobsBot Apply Agent" ^
  /TR "C:\Users\tsiol\jobs-bot\scripts\run_apply_agent.bat" /ST 02:00
```

Output is appended to `apply_agent.log`. Delete the task with
`schtasks /Delete /TN "JobsBot Apply Agent"`.

## What it will and won't do

- **Auto-submits:** Greenhouse, Lever, Ashby (when all required fields map and the
  resume attaches).
- **Fills + flags (no submit):** Workday and other gated/messy ATS, anything with a
  captcha or login wall, or any form missing a required field it can't fill
  truthfully (it never invents a location/postal code). Flagged drafts show on the
  dashboard with the reason and a "finish manually" link.
