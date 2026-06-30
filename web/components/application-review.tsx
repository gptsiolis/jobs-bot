"use client";

import { CheckCircle2, ExternalLink, FileText, Send, XCircle } from "lucide-react";
import { approveDraft, removeDraft } from "@/app/actions";
import type { ApplicationDraft } from "@/lib/types";

// The auto-apply review surface. Drafts the engine has prepared
// (needs_review) show editable answers with Approve/Dismiss. Approved drafts
// wait for the local browser runner to submit them. Skipped drafts (e.g. below
// the salary floor) and failures are surfaced compactly.
export function ApplicationReview({ drafts }: { drafts: ApplicationDraft[] }) {
  if (!drafts.length) {
    return null;
  }

  const review = drafts.filter((d) => d.status === "needs_review");
  const approved = drafts.filter((d) => d.status === "approved");
  const submitted = drafts.filter((d) => d.status === "submitted");
  const queued = drafts.filter((d) => d.status === "queued" || d.status === "drafting");
  const skipped = drafts.filter((d) => d.status === "skipped" || d.status === "failed");

  return (
    <section className="application-review">
      <div className="status-suggestions-head">
        <Send size={16} />
        <span>Auto-apply</span>
        <span className="muted">
          {review.length} to review · {approved.length} ready · {queued.length} queued
        </span>
      </div>

      {queued.length ? (
        <p className="profile-hint">
          {queued.length} job{queued.length > 1 ? "s" : ""} queued. Run{" "}
          <code>python apply_engine.py</code> locally to draft the answers.
        </p>
      ) : null}

      {review.map((d) => {
        const answers = d.drafted_answers || [];
        return (
          <form key={d.id} action={approveDraft} className="draft-card">
            <input type="hidden" name="id" value={d.id} />
            <input type="hidden" name="answer_count" value={answers.length} />
            <div className="draft-head">
              <div>
                <strong>{d.jobs?.title || d.job_id}</strong>
                {d.jobs?.company ? <span className="muted"> — {d.jobs.company}</span> : null}
                {d.ats ? <span className="pill draft-ats">{d.ats}</span> : null}
              </div>
              {d.apply_url ? (
                <a className="text-button" href={d.apply_url} target="_blank" rel="noreferrer">
                  <ExternalLink size={14} /> Form
                </a>
              ) : null}
            </div>

            <div className="draft-answers">
              {answers.map((qa, i) => (
                <label key={i} className="draft-answer">
                  <span className="draft-question">{qa.question}</span>
                  <input type="hidden" name={`question_${i}`} value={qa.question} />
                  <textarea name={`answer_${i}`} defaultValue={qa.answer} rows={3} />
                </label>
              ))}
              {answers.length === 0 ? (
                <p className="profile-hint">No drafted answers — this form may be field-only.</p>
              ) : null}
            </div>

            <div className="draft-actions">
              <button className="primary-button" type="submit">
                <CheckCircle2 size={15} /> Approve
              </button>
              <button className="status-button" type="submit" formAction={removeDraft} title="Dismiss">
                <XCircle size={15} />
              </button>
            </div>
          </form>
        );
      })}

      {approved.length ? (
        <ul className="draft-mini-list">
          {approved.map((d) => (
            <li key={d.id} className="draft-mini is-approved">
              <CheckCircle2 size={14} />
              <span>{d.jobs?.company || ""} — {d.jobs?.title || d.job_id}</span>
              <span className="muted">approved · awaiting submit</span>
            </li>
          ))}
        </ul>
      ) : null}

      {submitted.length ? (
        <ul className="draft-mini-list">
          {submitted.map((d) => (
            <li key={d.id} className="draft-mini">
              <FileText size={14} />
              <span>{d.jobs?.company || ""} — {d.jobs?.title || d.job_id}</span>
              <span className="muted">submitted</span>
            </li>
          ))}
        </ul>
      ) : null}

      {skipped.length ? (
        <ul className="draft-mini-list">
          {skipped.map((d) => (
            <li key={d.id} className="draft-mini is-skipped">
              <XCircle size={14} />
              <span>{d.jobs?.company || ""} — {d.jobs?.title || d.job_id}</span>
              <span className="muted">{d.skip_reason || d.error || "skipped"}</span>
              <form action={removeDraft}>
                <input type="hidden" name="id" value={d.id} />
                <button className="text-button" type="submit">clear</button>
              </form>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
