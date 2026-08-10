"use client";

import { CheckCircle2, Mail, XCircle } from "lucide-react";
import { applyStatusSuggestion, dismissStatusSuggestion } from "@/app/actions";
import type { StatusSuggestion } from "@/lib/types";

const statusLabels: Record<string, string> = {
  next_round: "Next Round",
  rejected: "Rejected"
};

const actionLabels: Record<string, string> = {
  next_round: "Move to Next Round",
  rejected: "Mark Rejected"
};

function suggestionChainKey(suggestion: StatusSuggestion) {
  return [
    suggestion.job_id,
    suggestion.gmail_thread_id || suggestion.gmail_message_id || suggestion.id
  ].join(":");
}

// Suggested status changes the email agent surfaced but did not auto-apply
// (lower confidence). The UI collapses repeated messages from the same Gmail
// thread/job so a recruiter chain only creates one visible review item.
export function StatusSuggestions({ suggestions }: { suggestions: StatusSuggestion[] }) {
  const seenSuggestions = new Set<string>();
  const visibleSuggestions = suggestions.filter((suggestion) => {
    const key = suggestionChainKey(suggestion);
    if (seenSuggestions.has(key)) return false;
    seenSuggestions.add(key);
    return true;
  });

  if (!visibleSuggestions.length) {
    return null;
  }

  return (
    <section className="status-suggestions">
      <div className="status-suggestions-head">
        <Mail size={16} />
        <span>Suggested updates from your inbox</span>
        <span className="muted">{visibleSuggestions.length}</span>
      </div>
      <ul className="status-suggestions-list">
        {visibleSuggestions.map((s) => {
          const company = s.jobs?.company || "";
          const title = s.jobs?.title || s.job_id;
          const pct = Math.round((s.confidence || 0) * 100);
          const actionLabel = actionLabels[s.suggested_status] || `Mark ${statusLabels[s.suggested_status] || s.suggested_status}`;
          return (
            <li key={s.id} className="status-suggestion">
              <div className="status-suggestion-main">
                <div className="status-suggestion-job">
                  <strong>{title}</strong>
                  {company ? <span className="muted"> — {company}</span> : null}
                </div>
                <div className="status-suggestion-meta">
                  <span className={`pill pill-${s.suggested_status}`}>
                    {statusLabels[s.suggested_status] || s.suggested_status}
                  </span>
                  <span className="muted">{pct}% confident</span>
                  {s.email_subject ? (
                    <span className="muted status-suggestion-subject" title={s.email_subject}>
                      “{s.email_subject}”
                    </span>
                  ) : null}
                </div>
                {s.evidence ? <p className="status-suggestion-evidence">{s.evidence}</p> : null}
              </div>
              <div className="status-suggestion-actions">
                <form action={applyStatusSuggestion}>
                  <input type="hidden" name="id" value={s.id} />
                  <input type="hidden" name="job_id" value={s.job_id} />
                  <input type="hidden" name="suggested_status" value={s.suggested_status} />
                  <button className="status-button" type="submit" title={actionLabel}>
                    <CheckCircle2 size={16} />
                    <span>{actionLabel}</span>
                  </button>
                </form>
                <form action={dismissStatusSuggestion}>
                  <input type="hidden" name="id" value={s.id} />
                  <button className="status-button" type="submit" title="Dismiss">
                    <XCircle size={16} />
                  </button>
                </form>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
