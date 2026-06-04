"use client";

import { useActionState, useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  Bookmark,
  CheckCircle2,
  ExternalLink,
  Play,
  Plus,
  RotateCcw,
  Search,
  XCircle
} from "lucide-react";
import {
  addCompanyWatchlistRequest,
  triggerScraperRun,
  updateJobStatus
} from "@/app/actions";
import type { CompanyWatchlistRequest, JobRow, JobRun, JobStatus } from "@/lib/types";

const fitOrder = ["strong", "possible", "unknown", "reject"];
const statusLabels: Record<JobStatus, string> = {
  new: "New",
  saved: "Saved",
  applied: "Applied",
  next_round: "Next Round",
  rejected: "Rejected",
  dismissed: "Dismissed",
  archived: "Archived"
};

const phaseTabs = [
  { value: "active", label: "All jobs" },
  { value: "new", label: "New" },
  { value: "saved", label: "Saved" },
  { value: "applied", label: "Applied" },
  { value: "next_round", label: "Next Round" },
  { value: "rejected", label: "Rejected" },
];

function unique(values: string[]) {
  return Array.from(new Set(values.filter(Boolean))).sort((a, b) => a.localeCompare(b));
}

function formatDate(value: string | null) {
  if (!value) return "";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit"
  }).format(new Date(value));
}

function StatusAction({
  jobId,
  status,
  title,
  children
}: {
  jobId: string;
  status: JobStatus;
  title: string;
  children: ReactNode;
}) {
  return (
    <form action={updateJobStatus}>
      <input type="hidden" name="job_id" value={jobId} />
      <input type="hidden" name="status" value={status} />
      <button className="status-button" type="submit" title={title} aria-label={title}>
        {children}
      </button>
    </form>
  );
}

function JobActions({ job }: { job: JobRow }) {
  if (job.status === "applied") {
    return (
      <div className="status-actions">
        <StatusAction jobId={job.job_id} status="next_round" title="Moved to next round">
          <CheckCircle2 size={16} />
        </StatusAction>
        <StatusAction jobId={job.job_id} status="rejected" title="Rejected">
          <XCircle size={16} />
        </StatusAction>
      </div>
    );
  }

  if (job.status === "next_round" || job.status === "rejected") {
    return (
      <div className="status-actions">
        <StatusAction jobId={job.job_id} status="applied" title="Back to applied">
          <RotateCcw size={16} />
        </StatusAction>
      </div>
    );
  }

  return (
    <div className="status-actions">
      <StatusAction jobId={job.job_id} status="saved" title="Save">
        <Bookmark size={16} />
      </StatusAction>
      <StatusAction jobId={job.job_id} status="applied" title="Applied">
        <CheckCircle2 size={16} />
      </StatusAction>
      <StatusAction jobId={job.job_id} status="dismissed" title="Dismiss">
        <XCircle size={16} />
      </StatusAction>
    </div>
  );
}

function atsLabel(request: CompanyWatchlistRequest) {
  const ats = request.ats_config?.ats;
  return typeof ats === "string" ? ats : request.status;
}

type RunStatusResponse = {
  run: JobRun | null;
  estimate_seconds: number | null;
  generated_at: string;
};

const fallbackEstimateSeconds: Record<string, number> = {
  watchlist: 12 * 60,
  discovery: 18 * 60,
  job_search: 20 * 60,
  source_expansion: 3 * 60,
  all: 38 * 60
};

function formatDuration(seconds: number | null) {
  if (seconds === null || !Number.isFinite(seconds)) return "--";
  const safe = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(safe / 60);
  const remainder = safe % 60;
  if (minutes >= 60) {
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return String(hours) + "h " + String(mins) + "m";
  }
  return String(minutes) + "m " + remainder.toString().padStart(2, "0") + "s";
}

function formatMode(value: string) {
  if (value === "all") return "All scrapers";
  return value.replaceAll("_", " ");
}

function runElapsedSeconds(run: JobRun | null, now: number) {
  if (!run?.started_at) return null;
  const started = new Date(run.started_at).getTime();
  const finished = run.finished_at ? new Date(run.finished_at).getTime() : now;
  if (!Number.isFinite(started) || !Number.isFinite(finished) || finished < started) {
    return null;
  }
  return Math.round((finished - started) / 1000);
}

function sourceSummary(run: JobRun | null) {
  const counts = run?.counts_by_source || {};
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 3);
  if (!entries.length) return "No source counts yet";
  return entries.map(([source, count]) => source + ": " + String(count)).join(" | ");
}

function ScraperPanel({ initialRun }: { initialRun: JobRun | null }) {
  const [runState, runAction, runPending] = useActionState(triggerScraperRun, {
    ok: true,
    message: ""
  });
  const [snapshot, setSnapshot] = useState<RunStatusResponse>({
    run: initialRun,
    estimate_seconds: initialRun ? fallbackEstimateSeconds[initialRun.mode] || fallbackEstimateSeconds.all : null,
    generated_at: new Date().toISOString()
  });
  const [queuedAt, setQueuedAt] = useState<number | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [statusError, setStatusError] = useState("");

  const loadStatus = useCallback(async () => {
    try {
      const response = await fetch("/api/run-status", { cache: "no-store" });
      if (!response.ok) throw new Error("Status request failed (" + String(response.status) + ")");
      const data = (await response.json()) as RunStatusResponse;
      setSnapshot(data);
      setStatusError("");
    } catch (error) {
      setStatusError(error instanceof Error ? error.message : "Could not load run status");
    }
  }, []);

  const run = snapshot.run;
  const startedAtMs = run?.started_at ? new Date(run.started_at).getTime() : 0;
  const isRunning = run?.status === "running";
  const isQueued = Boolean(
    queuedAt && !isRunning && (!run || !Number.isFinite(startedAtMs) || startedAtMs < queuedAt - 5000)
  );
  const isActive = isRunning || isQueued || runPending;

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    void loadStatus();
    const timer = window.setInterval(() => void loadStatus(), isActive ? 5000 : 20000);
    return () => window.clearInterval(timer);
  }, [isActive, loadStatus]);

  useEffect(() => {
    if (runState.ok && runState.message === "Scraper run started.") {
      setQueuedAt(Date.now());
      void loadStatus();
    }
  }, [loadStatus, runState.message, runState.ok]);

  useEffect(() => {
    if (queuedAt && run && Number.isFinite(startedAtMs) && startedAtMs >= queuedAt - 30000) {
      setQueuedAt(null);
    }
  }, [queuedAt, run, startedAtMs]);

  const estimate = snapshot.estimate_seconds || (run ? fallbackEstimateSeconds[run.mode] : null) || null;
  const elapsed = isQueued ? Math.round((now - (queuedAt || now)) / 1000) : runElapsedSeconds(run, now);
  const remaining = isRunning && estimate && elapsed !== null ? Math.max(0, estimate - elapsed) : null;
  const progress = isQueued
    ? 4
    : isRunning && estimate && elapsed !== null
      ? Math.min(96, Math.max(6, Math.round((elapsed / estimate) * 100)))
      : run
        ? 100
        : 0;
  const statusLabel = isQueued ? "Queued" : isRunning ? "Running" : run ? run.status : "Idle";
  const modeLabel = isQueued ? "All scrapers" : run ? formatMode(run.mode) : "No runs yet";
  const buttonDisabled = runPending || isQueued || isRunning;

  return (
    <div className={isActive ? "control-panel scraper-panel is-active" : "control-panel scraper-panel"}>
      <div className="panel-heading">
        <h2>Scraper</h2>
        <span className={isActive ? "run-state is-running" : "run-state is-" + (run?.status || "idle")}>
          {statusLabel}
        </span>
      </div>
      <form action={runAction}>
        <input type="hidden" name="mode" value="all" />
        <button className="primary-button wide-button" type="submit" disabled={buttonDisabled}>
          <Play size={15} />
          {buttonDisabled ? "Scraper Running" : "Run All Scrapers"}
        </button>
      </form>
      <div className="run-progress" aria-label="Scraper progress">
        <span style={{ width: String(progress) + "%" }} />
      </div>
      <div className="run-status-grid">
        <span>
          <strong>{modeLabel}</strong>
          <small>Mode</small>
        </span>
        <span>
          <strong>{formatDuration(elapsed)}</strong>
          <small>{isQueued ? "Queued for" : "Elapsed"}</small>
        </span>
        <span>
          <strong>{remaining === null ? (isRunning ? "Calculating" : "--") : formatDuration(remaining)}</strong>
          <small>Approx left</small>
        </span>
      </div>
      {run && run.status !== "running" ? (
        <div className="run-result">
          <strong>{run.total_new} new</strong>
          <span>{run.total_written} written | {run.total_found} matched</span>
        </div>
      ) : null}
      <p className="run-source-summary">{sourceSummary(run)}</p>
      {runState.message ? (
        <span className={runState.ok ? "action-message" : "action-message is-error"}>
          {runState.message}
        </span>
      ) : null}
      {statusError ? <span className="action-message is-error">{statusError}</span> : null}
    </div>
  );
}

export function JobsDashboard({
  jobs,
  companyRequests,
  latestRun
}: {
  jobs: JobRow[];
  companyRequests: CompanyWatchlistRequest[];
  latestRun: JobRun | null;
}) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("active");
  const [sponsor, setSponsor] = useState("");
  const [fit, setFit] = useState("");
  const [location, setLocation] = useState("");
  const [showHidden, setShowHidden] = useState(false);
  const [selectedId, setSelectedId] = useState(jobs[0]?.job_id || "");
  const [companyState, companyAction, companyPending] = useActionState(
    addCompanyWatchlistRequest,
    { ok: true, message: "" }
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return jobs.filter((job) => {
      const activeMatch =
        status === "active"
          ? job.status === "new" || job.status === "saved"
          : !status || job.status === status;
      const text = `${job.title} ${job.company} ${job.location_text}`.toLowerCase();
      const visibilityMatch = showHidden || job.visibility !== "hidden" || job.status !== "new";
      return (
        visibilityMatch &&
        activeMatch &&
        (!sponsor || job.sponsor_tier === sponsor) &&
        (!fit || job.fit_bucket === fit) &&
        (!location || job.location_text.includes(location)) &&
        (!q || text.includes(q))
      );
    });
  }, [jobs, query, status, sponsor, fit, location, showHidden]);

  const selected = filtered.find((job) => job.job_id === selectedId) || filtered[0] || null;
  const hiddenCount = jobs.filter((job) => job.visibility === "hidden" && job.status === "new").length;

  const grouped = useMemo(() => {
    return filtered.reduce<Record<string, JobRow[]>>((acc, job) => {
      const key = job.fit_bucket || "unknown";
      acc[key] = acc[key] || [];
      acc[key].push(job);
      return acc;
    }, {});
  }, [filtered]);

  const locations = unique(
    jobs.flatMap((job) =>
      job.location_text
        .split(",")
        .map((part) => part.replace("(Remote)", "").trim())
        .filter(Boolean)
    )
  );

  return (
    <>
      <section className="controls-grid">
        <ScraperPanel initialRun={latestRun} />

        <div className="control-panel">
          <h2>Company Watchlist</h2>
          <form action={companyAction} className="inline-form">
            <input name="company_name" placeholder="Company name" />
            <button className="primary-button" type="submit" disabled={companyPending}>
              <Plus size={15} />
              Add
            </button>
          </form>
          {companyState.message ? (
            <span className={companyState.ok ? "action-message" : "action-message is-error"}>
              {companyState.message}
            </span>
          ) : null}
          {companyRequests.length ? (
            <div className="request-list">
              {companyRequests.map((request) => (
                <div className="request-row" key={request.id}>
                  <strong>{request.company_name}</strong>
                  <span className="pill">{atsLabel(request)}</span>
                  {request.last_error ? <span className="muted">{request.last_error}</span> : null}
                </div>
              ))}
            </div>
          ) : null}
        </div>
      </section>

      <nav className="phase-tabs" aria-label="Job phases">
        {phaseTabs.map((tab) => {
          const count = jobs.filter((job) => {
            if (tab.value === "active") {
              return job.status === "new" || job.status === "saved";
            }
            return job.status === tab.value;
          }).length;
          return (
            <button
              key={tab.value}
              className={status === tab.value ? "phase-tab is-active" : "phase-tab"}
              type="button"
              onClick={() => setStatus(tab.value)}
            >
              <span>{tab.label}</span>
              <strong>{count}</strong>
            </button>
          );
        })}
      </nav>

      <section className="filters">
        <label>
          <span className="muted">Search</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Title or company"
          />
        </label>
        <label>
          <span className="muted">Fit</span>
          <select value={fit} onChange={(event) => setFit(event.target.value)}>
            <option value="">All</option>
            {unique(jobs.map((job) => job.fit_bucket)).map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="muted">Sponsor</span>
          <select value={sponsor} onChange={(event) => setSponsor(event.target.value)}>
            <option value="">All</option>
            {unique(jobs.map((job) => job.sponsor_tier)).map((value) => (
              <option key={value} value={value}>
                {value.replaceAll("_", " ")}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="muted">Location</span>
          <select value={location} onChange={(event) => setLocation(event.target.value)}>
            <option value="">All</option>
            {locations.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
      </section>

      <div className="visibility-toggle">
        <label>
          <input
            type="checkbox"
            checked={showHidden}
            onChange={(event) => setShowHidden(event.target.checked)}
          />
          <span>Show lower-ranked candidates</span>
        </label>
        <span className="muted">{hiddenCount} hidden new jobs</span>
      </div>

      <div className="content-grid">
        <section>
          {fitOrder
            .filter((bucket) => grouped[bucket]?.length)
            .map((bucket) => (
              <div className="job-section" key={bucket}>
                <h2 className="section-title">
                  <span>{bucket}</span>
                  <span className="muted">{grouped[bucket].length}</span>
                </h2>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Score</th>
                        <th>Role</th>
                        <th>Company</th>
                        <th>Location</th>
                        <th>Status</th>
                        <th>Sponsor</th>
                        <th>Seen</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {grouped[bucket].map((job) => (
                        <tr
                          key={job.job_id}
                          className={job.job_id === selected?.job_id ? "is-selected" : ""}
                          onClick={() => setSelectedId(job.job_id)}
                        >
                          <td className="score">{job.applicability_score}</td>
                          <td>
                            {job.apply_url ? (
                              <a
                                className="title-button"
                                href={job.apply_url}
                                target="_blank"
                                rel="noreferrer"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  setSelectedId(job.job_id);
                                }}
                              >
                                {job.title}
                              </a>
                            ) : (
                              <button
                                className="title-button"
                                type="button"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  setSelectedId(job.job_id);
                                }}
                              >
                                {job.title}
                              </button>
                            )}
                          </td>
                          <td>{job.company}</td>
                          <td>{job.location_text}</td>
                          <td>
                            <span className="pill">{statusLabels[job.status]}</span>
                          </td>
                          <td>{job.sponsor_tier.replaceAll("_", " ")}</td>
                          <td>{formatDate(job.last_seen_at)}</td>
                          <td onClick={(event) => event.stopPropagation()}>
                            <JobActions job={job} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          {!filtered.length ? (
            <div className="metric">
              <Search size={18} />
              <span className="muted">No jobs match the current filters.</span>
            </div>
          ) : null}
        </section>

        <aside className="detail">
          {selected ? (
            <>
              <h2>{selected.title}</h2>
              <div className="muted">{selected.company}</div>
              <dl>
                <dt>Score</dt>
                <dd>{selected.applicability_score}</dd>
                <dt>Status</dt>
                <dd>{statusLabels[selected.status]}</dd>
                <dt>Location</dt>
                <dd>{selected.location_text}</dd>
                <dt>Source</dt>
                <dd>{selected.source}</dd>
                <dt>Fit</dt>
                <dd>{selected.fit_reasons.join(", ") || selected.fit_bucket}</dd>
                <dt>Sponsor</dt>
                <dd>
                  {selected.sponsor_tier.replaceAll("_", " ")}
                  {selected.sponsor_reasons.length
                    ? `, ${selected.sponsor_reasons.join(", ")}`
                    : ""}
                </dd>
                <dt>Quality</dt>
                <dd>{selected.quality_tier}</dd>
                {selected.role_family ? (
                  <>
                    <dt>Role family</dt>
                    <dd>{selected.role_family}</dd>
                  </>
                ) : null}
                {selected.ai_fit_score !== null ? (
                  <>
                    <dt>AI fit</dt>
                    <dd>{selected.ai_fit_score}</dd>
                  </>
                ) : null}
                <dt>First seen</dt>
                <dd>{formatDate(selected.first_seen_at)}</dd>
                <dt>Last seen</dt>
                <dd>{formatDate(selected.last_seen_at)}</dd>
              </dl>
              {selected.apply_url ? (
                <a className="primary-button" href={selected.apply_url} target="_blank" rel="noreferrer">
                  Apply <ExternalLink size={15} />
                </a>
              ) : null}
              {selected.ai_summary ? (
                <p className="excerpt">{selected.ai_summary}</p>
              ) : null}
              {selected.ai_reject_reasons.length ? (
                <p className="excerpt">Watchouts: {selected.ai_reject_reasons.join(", ")}</p>
              ) : null}
              {selected.description_excerpt ? (
                <p className="excerpt">{selected.description_excerpt}</p>
              ) : null}
            </>
          ) : (
            <span className="muted">No job selected.</span>
          )}
        </aside>
      </div>
    </>
  );
}
