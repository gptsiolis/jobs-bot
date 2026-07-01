"""Autonomous apply agent (Phase 4).

Takes drafts the user has APPROVED on the dashboard and submits them by driving a
real, logged-in Chrome profile with Playwright — no interactive Claude session.
It reads each form's actual fields, maps the approved profile/answers onto them
with one Claude call, uploads the resume itself, and:

  * auto-submits the clean structured ATS (Greenhouse / Lever / Ashby), then flips
    the job to 'applied' and saves a confirmation screenshot;
  * for anything gated/messy, or if a required field can't be filled, or on a
    captcha/login wall — it fills what it can and FLAGS the draft for a quick
    manual finish (never submits junk).

Usage:
    python apply_agent.py --login   # one-time: sign into LinkedIn/Google/ATS
    python apply_agent.py           # draft queued + submit approved
    python apply_agent.py --dry-run # fill but never click submit (test)

Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, ANTHROPIC_API_KEY.
Optional: APPLY_PROFILE_DIR (persistent Chrome profile dir),
          ANTHROPIC_DRAFT_MODEL (default claude-sonnet-4-6),
          APPLY_HEADLESS=1 to run headless.
"""

import json
import os
import re
import sys
import tempfile

import requests

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass

from storage import SupabaseJobStore
import apply_engine

ANTHROPIC_ENDPOINT = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-4-6"

# ATS whose hosted forms are structured enough to auto-submit confidently.
CLEAN_ATS = {"greenhouse", "lever", "ashby"}
CLEAN_DOMAINS = ("greenhouse.io", "lever.co", "ashbyhq.com")


def _profile_dir():
    return os.getenv("APPLY_PROFILE_DIR") or os.path.join(
        os.path.expanduser("~"), ".jobs-bot", "apply-profile"
    )


def _model():
    return os.getenv("ANTHROPIC_DRAFT_MODEL") or os.getenv("ANTHROPIC_MODEL") or DEFAULT_MODEL


def _headless():
    return os.getenv("APPLY_HEADLESS", "").lower() in {"1", "true", "yes"}


def is_clean_ats(draft):
    ats = (draft.get("ats") or (draft.get("jobs") or {}).get("ats") or "").lower()
    if ats in CLEAN_ATS:
        return True
    url = (draft.get("apply_url") or (draft.get("jobs") or {}).get("apply_url") or "").lower()
    return any(dom in url for dom in CLEAN_DOMAINS)


# --- DOM extraction ---------------------------------------------------------

# Tag every fillable field with data-apply-idx and return a compact descriptor
# list (index, label, type, required, select options) for the LLM to map.
_EXTRACT_JS = r"""
() => {
  const out = [];
  let i = 0;
  for (const el of document.querySelectorAll('input, select, textarea')) {
    const tag = el.tagName.toLowerCase();
    const type = (el.getAttribute('type') || tag).toLowerCase();
    if (['hidden', 'submit', 'button', 'reset', 'image'].includes(type)) continue;
    // Radios/checkboxes are often custom-styled (real input visually hidden) but
    // still functional — keep them; only skip other invisible fields.
    if (el.offsetParent === null && !['file', 'radio', 'checkbox'].includes(type)) continue;
    el.setAttribute('data-apply-idx', String(i));
    let label = el.getAttribute('aria-label') || '';
    if (!label && el.id) {
      const l = document.querySelector('label[for="' + CSS.escape(el.id) + '"]');
      if (l) label = l.innerText;
    }
    if (!label) { const l = el.closest('label'); if (l) label = l.innerText; }
    if (!label) label = el.getAttribute('placeholder') || el.getAttribute('name') || '';
    let options = null;
    if (tag === 'select') options = Array.from(el.options).map(o => o.text.trim()).filter(Boolean);
    const required = el.required || el.getAttribute('aria-required') === 'true';
    const autocomplete = el.getAttribute('role') === 'combobox' ||
      !!el.getAttribute('aria-autocomplete') || el.getAttribute('aria-haspopup') === 'listbox';
    out.push({ idx: i, tag, type, autocomplete,
      label: (label || '').replace(/\s+/g, ' ').trim().slice(0, 160), required, options });
    i++;
  }
  return out;
}
"""


def extract_fields(page):
    try:
        return page.evaluate(_EXTRACT_JS) or []
    except Exception:
        return []


def reveal_form(page):
    """Some career pages gate the form behind an 'Apply' button — click it."""
    for sel in ('a:has-text("Apply")', 'button:has-text("Apply")',
                'a:has-text("Apply now")', 'button:has-text("Apply now")'):
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click()
                page.wait_for_timeout(1500)
                return
        except Exception:
            continue


def detect_block(page):
    """Heuristics for things we must not push through: captcha or a login wall."""
    try:
        if page.query_selector('iframe[src*="recaptcha"], iframe[src*="hcaptcha"], '
                               'iframe[title*="captcha" i]'):
            return "captcha"
        title = (page.title() or "").lower()
        if "just a moment" in title or "attention required" in title:
            return "cloudflare challenge"
        # A password field with no resume upload usually means a login wall.
        if page.query_selector('input[type=password]') and not page.query_selector('input[type=file]'):
            return "login required"
    except Exception:
        pass
    return None


# --- LLM field mapping ------------------------------------------------------


def map_fields(fields, draft, job):
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("Missing ANTHROPIC_API_KEY.")

    fv = draft.get("field_values") or {}
    answers = draft.get("drafted_answers") or []
    payload_fields = [
        {k: f[k] for k in ("idx", "type", "label", "required", "options") if f.get(k) is not None}
        for f in fields
    ]
    system = (
        "You map a job application form's fields to a candidate's data. You are "
        "given the form fields (with idx, type, label, required, and select "
        "options) and the candidate's known values plus pre-drafted answers. "
        "Return JSON only:\n"
        '{"fills": [{"idx": int, "value": string}], "resume_idx": int|null, '
        '"missing_required": [string]}.\n'
        "Rules:\n"
        "- For a file input meant for the resume/CV, set resume_idx to its idx "
        "(do NOT put it in fills).\n"
        "- For a <select>, value MUST be one of its exact option texts.\n"
        "- For checkboxes (e.g. consent/agree), value \"true\".\n"
        "- Map work authorization / sponsorship from the booleans "
        "(work_authorized true -> Yes, requires_sponsorship true -> Yes).\n"
        "- Use the pre-drafted answers for matching free-text questions; for a "
        "new free-text question, write a short honest answer from the candidate "
        "data — never invent facts.\n"
        "- NEVER invent a location, city, or postal code. If a REQUIRED field has "
        "no truthful value in the data (e.g. location/postal code when location "
        "is blank), put its label in missing_required and do not fill it.\n"
        "- Only include fields you can fill truthfully in fills."
    )
    user = json.dumps({
        "job": {"title": job.get("title", ""), "company": job.get("company", "")},
        "form_fields": payload_fields,
        "candidate_values": fv,
        "drafted_answers": answers,
    })

    resp = requests.post(
        ANTHROPIC_ENDPOINT,
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={"model": _model(), "max_tokens": 1500, "system": system,
              "messages": [{"role": "user", "content": user}]},
        timeout=90,
    )
    resp.raise_for_status()
    text = "".join(
        b.get("text", "") for b in resp.json().get("content", []) if b.get("type") == "text"
    ).strip()
    text = re.sub(r"^```(?:json)?|```$", "", text.strip()).strip()
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return {"fills": [], "resume_idx": None, "missing_required": ["<unparseable mapping>"]}
    data.setdefault("fills", [])
    data.setdefault("resume_idx", None)
    data.setdefault("missing_required", [])
    return data


# --- Filling ----------------------------------------------------------------


def fill_form(page, fields, mapping, resume_path):
    by_idx = {f["idx"]: f for f in fields}
    for fill in mapping.get("fills", []):
        idx = fill.get("idx")
        value = fill.get("value")
        field = by_idx.get(idx)
        if field is None or value is None:
            continue
        loc = page.locator(f'[data-apply-idx="{idx}"]')
        try:
            if field["tag"] == "select":
                try:
                    loc.select_option(label=str(value))
                except Exception:
                    loc.select_option(str(value))
            elif field["type"] in ("checkbox", "radio"):
                if str(value).lower() in ("true", "yes", "1", "on"):
                    _check_maybe_hidden(page, loc, idx)
            elif field.get("autocomplete"):
                _fill_autocomplete(page, loc, str(value))
            else:
                loc.fill(str(value))
        except Exception:
            continue

    resume_idx = mapping.get("resume_idx")
    attached = False
    if resume_idx is not None and resume_path:
        try:
            page.locator(f'[data-apply-idx="{resume_idx}"]').set_input_files(resume_path)
            attached = True
        except Exception:
            attached = False
    return attached


# After filling, re-read the form and return the labels of any REQUIRED field
# that is still empty — catches custom widgets (autocomplete, styled radios) that
# our fill couldn't populate, so we flag instead of submitting an incomplete form.
_VERIFY_JS = r"""
() => {
  const empties = [];
  const seenRadio = {};
  for (const el of document.querySelectorAll('[data-apply-idx]')) {
    const required = el.required || el.getAttribute('aria-required') === 'true';
    if (!required) continue;
    const tag = el.tagName.toLowerCase();
    const type = (el.getAttribute('type') || tag).toLowerCase();
    let label = el.getAttribute('aria-label') ||
      (el.labels && el.labels[0] && el.labels[0].innerText) || el.name || '';
    label = (label || '').replace(/\s+/g, ' ').trim().slice(0, 80);
    if (type === 'radio') {
      const name = el.name; if (!name) continue;
      if (seenRadio[name]) continue; seenRadio[name] = true;
      if (!document.querySelector('input[type=radio][name="' + CSS.escape(name) + '"]:checked'))
        empties.push(label || 'a required choice');
    } else if (type === 'checkbox') {
      if (!el.checked) empties.push(label || 'a required checkbox');
    } else if (type === 'file') {
      if (!el.files || el.files.length === 0) empties.push(label || 'a required file');
    } else if (!el.value || !el.value.trim()) {
      empties.push(label || 'a required field');
    }
  }
  return empties;
}
"""


def verify_required(page):
    try:
        return page.evaluate(_VERIFY_JS) or []
    except Exception:
        return []


def unstuck_fills(page, fields, mapping):
    """Return labels of text/select/autocomplete values we tried to fill but that
    didn't actually land (the field is still empty) — the custom-widget blind
    spot that a required-attribute check misses."""
    by_idx = {f["idx"]: f for f in fields}
    check = [fl["idx"] for fl in mapping.get("fills", [])
             if by_idx.get(fl.get("idx")) and by_idx[fl["idx"]]["type"] not in ("checkbox", "radio", "file")]
    if not check:
        return []
    try:
        vals = page.evaluate(
            """(idxs) => { const r = {};
                for (const idx of idxs) { const el = document.querySelector('[data-apply-idx="'+idx+'"]');
                  if (el) r[idx] = (el.value || '').trim(); } return r; }""",
            check,
        ) or {}
    except Exception:
        return []
    out = []
    for idx in check:
        if not vals.get(str(idx)) and not vals.get(idx):
            out.append(by_idx[idx].get("label") or f"field {idx}")
    return out


def _fill_autocomplete(page, loc, value):
    """Type into an autocomplete/combobox field and pick the first suggestion —
    typing alone doesn't register a value in Google-Places-style widgets."""
    loc.click()
    try:
        loc.fill("")
    except Exception:
        pass
    loc.type(value, delay=60)
    page.wait_for_timeout(1500)
    for sel in ('[role=option]', 'li[role=option]', 'ul[role=listbox] li',
                '.pac-item', '[class*="option"]'):
        try:
            opt = page.query_selector(sel)
            if opt and opt.is_visible():
                opt.click()
                page.wait_for_timeout(300)
                return
        except Exception:
            continue
    # Fallback: keyboard-select the first suggestion.
    try:
        loc.press("ArrowDown")
        loc.press("Enter")
    except Exception:
        pass


def _check_maybe_hidden(page, loc, idx):
    """Check a radio/checkbox; if the real input is visually hidden (custom UI),
    click its label instead."""
    try:
        loc.check(timeout=2000)
        return
    except Exception:
        pass
    try:
        page.evaluate(
            """(idx) => {
                const el = document.querySelector('[data-apply-idx="' + idx + '"]');
                if (!el) return;
                let lbl = el.id ? document.querySelector('label[for="' + CSS.escape(el.id) + '"]') : null;
                if (!lbl) lbl = el.closest('label');
                (lbl || el).click();
            }""",
            str(idx),
        )
    except Exception:
        pass


def find_submit(page):
    for sel in ('button[type=submit]', 'input[type=submit]',
                'button:has-text("Submit application")', 'button:has-text("Submit")',
                'button:has-text("Submit Application")'):
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                return el
        except Exception:
            continue
    return None


# --- Per-draft processing ---------------------------------------------------


def process_draft(page, store, draft, profile, resume_path, dry_run=False):
    job = draft.get("jobs") or {}
    label = f"{job.get('company', '?')} — {job.get('title', '?')}"
    draft_id = draft["id"]
    uid = (profile.get("resume_path") or "x/").split("/")[0]

    def flag(reason):
        shot = _screenshot(page, store, uid, draft_id)
        store.update_draft(draft_id, {"status": "needs_review", "flag_reason": reason,
                                      "confirmation_path": shot})
        print(f"[flag] {label} :: {reason}")

    store.update_draft(draft_id, {"status": "submitting"})
    page.goto(draft.get("apply_url"), wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(1500)

    blocked = detect_block(page)
    if blocked:
        return flag(blocked)

    fields = extract_fields(page)
    if len(fields) < 2:
        reveal_form(page)
        fields = extract_fields(page)
    if len(fields) < 2:
        return flag("no application form found on page")

    # Use the LATEST profile for the structured fields (so profile edits like
    # name/location/postal apply without re-drafting); keep the approved essay
    # answers from the draft.
    live_draft = {**draft, "field_values": apply_engine.map_profile_fields(profile)}
    mapping = map_fields(fields, live_draft, job)
    attached = fill_form(page, fields, mapping, resume_path)
    needs_resume = any(f["type"] == "file" and f.get("required") for f in fields)

    # Trust nothing: (a) required fields must hold a value, and (b) every value
    # we *attempted* to fill must actually have landed (custom autocomplete
    # widgets silently drop typed text). Either failing → flag, don't submit.
    empties = verify_required(page)
    unstuck = unstuck_fills(page, fields, mapping)
    missing = list(dict.fromkeys((mapping.get("missing_required") or []) + empties + unstuck))
    if missing:
        return flag("could not fill: " + ", ".join(missing[:6]))
    if needs_resume and not attached:
        return flag("resume upload failed")
    if not is_clean_ats(draft):
        return flag("filled; needs manual submit (non-auto-submit ATS)")
    if dry_run:
        return flag("dry-run: filled, not submitted")

    submit = find_submit(page)
    if not submit:
        return flag("filled; submit button not found")

    submit.click()
    page.wait_for_timeout(4000)
    shot = _screenshot(page, store, uid, draft_id)
    store.update_draft(draft_id, {"status": "submitted", "submitted_at": _now(),
                                  "confirmation_path": shot, "flag_reason": None})
    store.set_job_status(draft["job_id"], "applied")
    store.log_job_note_event(draft["job_id"], "apply_agent_submit", None, "applied",
                             json.dumps({"source": "apply_agent", "company": job.get("company")}))
    print(f"[submitted] {label}")


def _now():
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def _screenshot(page, store, uid, draft_id):
    try:
        png = page.screenshot(full_page=True)
        return store.upload_application_screenshot(f"{uid}/{draft_id}.png", png)
    except Exception as exc:
        print(f"[screenshot] skipped: {exc}")
        return None


# --- Modes ------------------------------------------------------------------


def login_mode():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(_profile_dir(), headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://www.linkedin.com/login")
        print("A Chrome window opened using the agent's profile.")
        print("Log into LinkedIn / Google / any ATS accounts you need.")
        input("When done, press Enter here to save the session and close... ")
        ctx.close()


def run(dry_run=False):
    from playwright.sync_api import sync_playwright

    store = SupabaseJobStore()
    profile = store.get_applicant_profile()
    if not profile:
        print("[Apply] No profile — fill it in first.")
        return
    # Draft anything still queued, then submit everything approved.
    apply_engine.process_queue(dry_run=False)

    drafts = store.list_drafts_by_status("approved")
    if not drafts:
        print("[Apply] Nothing approved to submit.")
        return

    resume_path = None
    if profile.get("resume_path"):
        raw = store.download_resume(profile["resume_path"])
        # Keep the real filename so recruiters see e.g. George_Tsiolis_Resume.pdf,
        # not a temp name — set_input_files uploads under the file's basename.
        fname = profile.get("resume_filename") or "resume.pdf"
        resume_path = os.path.join(tempfile.mkdtemp(), fname)
        with open(resume_path, "wb") as fh:
            fh.write(raw)

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(_profile_dir(), headless=_headless())
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        for draft in drafts:
            try:
                process_draft(page, store, draft, profile, resume_path, dry_run=dry_run)
            except Exception as exc:
                store.update_draft(draft["id"], {"status": "failed", "error": str(exc)[:500]})
                print(f"[error] {draft.get('job_id')} :: {exc}")
        ctx.close()


def main():
    if "--login" in sys.argv:
        login_mode()
        return
    run(dry_run="--dry-run" in sys.argv)


if __name__ == "__main__":
    main()
