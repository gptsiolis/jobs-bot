"use client";

import { useActionState } from "react";
import { FileText } from "lucide-react";
import { saveProfile } from "@/app/actions";
import type { ApplicantProfile } from "@/lib/types";

// Maps a tri-state boolean (yes / no / unanswered) to the <select> value the
// saveProfile action expects.
function triValue(value: boolean | null | undefined) {
  if (value === true) return "yes";
  if (value === false) return "no";
  return "";
}

export function ProfileForm({
  profile,
  fallbackEmail
}: {
  profile: ApplicantProfile | null;
  fallbackEmail: string;
}) {
  const [state, action, pending] = useActionState(saveProfile, { ok: true, message: "" });
  const p = profile;

  return (
    <form className="profile-form" action={action}>
      <p className="profile-hint">
        These answers are reused to fill out job applications. Fill in what you can — you can
        always update it later.
      </p>

      <fieldset className="profile-fieldset">
        <legend>Basics</legend>
        <label>
          Full name
          <input name="full_name" defaultValue={p?.full_name ?? ""} placeholder="George Tsiolis" />
        </label>
        <label>
          Email
          <input
            name="email"
            type="email"
            defaultValue={p?.email || fallbackEmail}
            placeholder="you@example.com"
          />
        </label>
        <label>
          Phone
          <input name="phone" defaultValue={p?.phone ?? ""} placeholder="+1 555 123 4567" />
        </label>
        <label>
          Location
          <input name="location" defaultValue={p?.location ?? ""} placeholder="New York, NY" />
        </label>
        <label>
          LinkedIn URL
          <input
            name="linkedin_url"
            defaultValue={p?.linkedin_url ?? ""}
            placeholder="https://linkedin.com/in/…"
          />
        </label>
        <label>
          GitHub URL
          <input
            name="github_url"
            defaultValue={p?.github_url ?? ""}
            placeholder="https://github.com/…"
          />
        </label>
        <label>
          Portfolio / website
          <input
            name="portfolio_url"
            defaultValue={p?.portfolio_url ?? ""}
            placeholder="https://…"
          />
        </label>
        <label>
          Years of experience
          <input
            name="years_experience"
            defaultValue={p?.years_experience ?? ""}
            placeholder="e.g. 2"
          />
        </label>
      </fieldset>

      <fieldset className="profile-fieldset">
        <legend>Work authorization & logistics</legend>
        <label>
          Authorized to work in the US?
          <select name="work_authorized" defaultValue={triValue(p?.work_authorized)}>
            <option value="">No answer</option>
            <option value="yes">Yes</option>
            <option value="no">No</option>
          </select>
        </label>
        <label>
          Require visa sponsorship?
          <select name="requires_sponsorship" defaultValue={triValue(p?.requires_sponsorship)}>
            <option value="">No answer</option>
            <option value="yes">Yes</option>
            <option value="no">No</option>
          </select>
        </label>
        <label>
          Willing to relocate?
          <select name="willing_to_relocate" defaultValue={triValue(p?.willing_to_relocate)}>
            <option value="">No answer</option>
            <option value="yes">Yes</option>
            <option value="no">No</option>
          </select>
        </label>
        <label>
          Earliest start date
          <input
            name="earliest_start"
            defaultValue={p?.earliest_start ?? ""}
            placeholder="e.g. Immediately / 2 weeks"
          />
        </label>
        <label>
          Salary expectation <span className="profile-sub">(what to put on forms, optional)</span>
          <input
            name="salary_expectation"
            defaultValue={p?.salary_expectation ?? ""}
            placeholder="e.g. $80,000"
          />
        </label>
        <label>
          Minimum salary <span className="profile-sub">(won&apos;t apply to jobs below this)</span>
          <input
            name="minimum_salary"
            inputMode="numeric"
            defaultValue={p?.minimum_salary != null ? String(p.minimum_salary) : ""}
            placeholder="e.g. 75000"
          />
        </label>
      </fieldset>

      <fieldset className="profile-fieldset">
        <legend>Resume</legend>
        {p?.resume_filename ? (
          <p className="profile-resume-current">
            <FileText size={15} /> Current: <strong>{p.resume_filename}</strong>
          </p>
        ) : (
          <p className="profile-hint">No resume uploaded yet.</p>
        )}
        <label>
          Upload resume (PDF){p?.resume_filename ? " — replaces current" : ""}
          <input name="resume" type="file" accept=".pdf,.doc,.docx" />
        </label>
      </fieldset>

      <div className="profile-actions">
        <button className="primary-button" type="submit" disabled={pending}>
          {pending ? "Saving…" : "Save profile"}
        </button>
        {state.message ? (
          <span className={state.ok ? "profile-msg is-ok" : "profile-msg is-error"}>
            {state.message}
          </span>
        ) : null}
      </div>
    </form>
  );
}
