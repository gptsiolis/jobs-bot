"use client";

import { useActionState, useCallback, useEffect, useMemo, useState, useTransition } from "react";
import type { ReactNode } from "react";
import {
  Bookmark,
  CheckCircle2,
  ExternalLink,
  GripVertical,
  Linkedin,
  Play,
  RotateCcw,
  Search,
  XCircle
} from "lucide-react";
import { reorderJobs, triggerScraperRun, updateJobStatus } from "@/app/actions";
import type { JobRow, JobRun, JobStatus } from "@/lib/types";

const fitOrder = ["strong", "possible", "unknown", "reject"];
const statusLabels: Record<JobStatus, string> = {
  new: "New",
  saved: "Saved",
  applied: "Applied",
  applied_messaged: "Applied · Messaged",
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
  { value: "applied_messaged", label: "Applied · Messaged" },
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
  active,
  children
}: {
  jobId: string;
  status: JobStatus;
  title: string;
  active?: boolean;
  children: ReactNode;
}) {
  return (
    <form action={updateJobStatus}>
      <input type="hidden" name="job_id" value={jobId} />
      <input type="hidden" name="status" value={status} />
      <button
        className={active ? "status-button is-active" : "status-button"}
        type="submit"
        title={title}
        aria-label={title}
      >
        {children}
      </button>
    </form>
  );
}

function JobActions({ job }: { job: JobRow }) {
  if (job.status === "applied" || job.status === "applied_messaged") {
    const messaged = job.status === "applied_messaged";
    return (
      <div className="status-actions">
        <StatusAction
          jobId={job.job_id}
          status={messaged ? "applied" : "applied_messaged"}
          title={messaged ? "Messaged a contact — click to undo" : "Mark as messaged a contact"}
          active={messaged}
        >
          <Linkedin size={16} />
        </StatusAction>
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

const reorderableStatuses = new Set(["saved", "applied", "applied_messaged"]);

function byManualRank(a: JobRow, b: JobRow) {
  const ar = a.manual_rank;
  const br = b.manual_rank;
  if (ar !== null && br !== null && ar !== br) return ar - br;
  if (ar !== null && br === null) return -1;
  if (ar === null && br !== null) return 1;
  if (a.applicability_score !== b.applicability_score) {
    return b.applicability_score - a.applicability_score;
  }
  return (b.last_seen_at || "").localeCompare(a.last_seen_at || "");
}

function ReorderableJobList({
  jobs,
  status,
  selectedId,
  onSelect
}: {
  jobs: JobRow[];
  status: JobStatus;
  selectedId: string;
  onSelect: (jobId: string) => void;
}) {
  const [order, setOrder] = useState<JobRow[]>(jobs);
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [overIndex, setOverIndex] = useState<number | null>(null);
  const [pending, startTransition] = useTransition();

  // Resync when the server sends a new list (revalidation, filtering, tab switch).
  useEffect(() => {
    setOrder(jobs);
  }, [jobs]);

  const persist = useCallback(
    (next: JobRow[]) => {
      startTransition(async () => {
        await reorderJobs(status, next.map((job) => job.job_id));
      });
    },
    [status]
  );

  const moveTo = useCallback(
    (from: number, to: number) => {
      if (from === to || from < 0 || to < 0) return;
      setOrder((current) => {
        if (from >= current.length || to >= current.length) return current;
        const next = [...current];
        const [moved] = next.splice(from, 1);
        next.splice(to, 0, moved);
        persist(next);
        return next;
      });
    },
    [persist]
  );

  const handleDrop = (targetIndex: number) => {
    if (dragIndex !== null) moveTo(dragIndex, targetIndex);
    setDragIndex(null);
    setOverIndex(null);
  };

  if (!order.length) return null;

  return (
    <div className={pending ? "job-section reorder-list is-saving" : "job-section reorder-list"}>
      <h2 className="section-title">
        <span>Priority order</span>
        <span className="muted">drag to rank &middot; {order.length}</span>
      </h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th aria-label="Reorder" />
              <th>#</th>
              <th>Score</th>
              <th>Role</th>
              <th>Company</th>
              <th>Location</th>
              <th>Sponsor</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {order.map((job, index) => (
              <tr
                key={job.job_id}
                draggable
                onDragStart={(event) => {
                  setDragIndex(index);
                  event.dataTransfer.effectAllowed = "move";
                }}
                onDragOver={(event) => {
                  event.preventDefault();
                  event.dataTransfer.dropEffect = "move";
                  if (overIndex !== index) setOverIndex(index);
                }}
                onDrop={(event) => {
                  event.preventDefault();
                  handleDrop(index);
                }}
                onDragEnd={() => {
                  setDragIndex(null);
                  setOverIndex(null);
                }}
                className={[
                  job.job_id === selectedId ? "is-selected" : "",
                  index === dragIndex ? "is-dragging" : "",
                  index === overIndex && dragIndex !== null && dragIndex !== index ? "is-drop-target" : ""
                ]
                  .filter(Boolean)
                  .join(" ")}
                onClick={() => onSelect(job.job_id)}
              >
                <td className="drag-handle" aria-hidden="true">
                  <GripVertical size={16} />
                </td>
                <td className="score">{index + 1}</td>
                <td className="score">{job.applicability_score}</td>
                <td>
                  {job.apply_url ? (
                    <a
                      className="title-button"
                      href={job.apply_url}
                      target="_blank"
                      rel="noreferrer"
                      draggable={false}
                      onClick={(event) => {
                        event.stopPropagation();
                        onSelect(job.job_id);
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
                        onSelect(job.job_id);
                      }}
                    >
                      {job.title}
                    </button>
                  )}
                </td>
                <td>{job.company}</td>
                <td>{job.location_text}</td>
                <td>{job.sponsor_tier.replaceAll("_", " ")}</td>
                <td onClick={(event) => event.stopPropagation()}>
                  <JobActions job={job} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

type EstimatedRun = JobRun & { estimate_seconds?: number | null };

type RunStatusResponse = {
  run: EstimatedRun | null;
  active_runs?: EstimatedRun[];
  estimate_seconds: number | null;
  generated_at: string;
};

const fallbackEstimateSeconds: Record<string, number> = {
  watchlist: 12 * 60,
  discovery: 40 * 60,
  job_search: 15 * 60,
  source_expansion: 3 * 60,
  all: 65 * 60
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
  const activeRuns = snapshot.active_runs || [];
  const startedAtMs = run?.started_at ? new Date(run.started_at).getTime() : 0;
  const isRunning = activeRuns.length > 0 || run?.status === "running";
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
    if (runState.ok && runState.message === "Scraper runs started.") {
      setQueuedAt(Date.now());
      void loadStatus();
    }
  }, [loadStatus, runState.message, runState.ok]);

  useEffect(() => {
    if (queuedAt && run && Number.isFinite(startedAtMs) && startedAtMs >= queuedAt - 30000) {
      setQueuedAt(null);
    }
  }, [queuedAt, run, startedAtMs]);

  const activeEstimates = activeRuns.map((activeRun) => activeRun.estimate_seconds || fallbackEstimateSeconds[activeRun.mode] || fallbackEstimateSeconds.all);
  const activeElapsed = activeRuns.map((activeRun) => runElapsedSeconds(activeRun, now) || 0);
  const activeRemaining = activeRuns.map((activeRun, index) => Math.max(0, activeEstimates[index] - activeElapsed[index]));
  const estimate = activeRuns.length
    ? Math.max(...activeEstimates)
    : snapshot.estimate_seconds || (run ? fallbackEstimateSeconds[run.mode] : null) || null;
  const elapsed = isQueued
    ? Math.round((now - (queuedAt || now)) / 1000)
    : activeRuns.length
      ? Math.max(...activeElapsed)
      : runElapsedSeconds(run, now);
  const remaining = activeRuns.length
    ? Math.max(...activeRemaining)
    : isRunning && estimate && elapsed !== null
      ? Math.max(0, estimate - elapsed)
      : null;
  const progress = isQueued
    ? 4
    : activeRuns.length
      ? Math.min(96, Math.max(6, Math.round(activeRuns.reduce((sum, activeRun, index) => {
          return sum + Math.min(1, activeElapsed[index] / activeEstimates[index]);
        }, 0) / activeRuns.length * 100)))
      : isRunning && estimate && elapsed !== null
        ? Math.min(96, Math.max(6, Math.round((elapsed / estimate) * 100)))
        : run
          ? 100
          : 0;
  const statusLabel = isQueued ? "Queued" : isRunning ? "Running" : run ? run.status : "Idle";
  const modeLabel = isQueued
    ? "All scrapers"
    : activeRuns.length > 1
      ? String(activeRuns.length) + " scraper runs"
      : activeRuns.length === 1
        ? formatMode(activeRuns[0].mode)
        : run
          ? formatMode(run.mode)
          : "No runs yet";
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
      <p className="run-source-summary">
        {activeRuns.length
          ? activeRuns.map((activeRun) => formatMode(activeRun.mode)).join(" running | ") + " running"
          : sourceSummary(run)}
      </p>
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
  latestRun
}: {
  jobs: JobRow[];
  latestRun: JobRun | null;
}) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("active");
  const [sponsor, setSponsor] = useState("");
  const [fit, setFit] = useState("");
  const [location, setLocation] = useState("");
  const [showHidden, setShowHidden] = useState(false);
  const [selectedId, setSelectedId] = useState(jobs[0]?.job_id || "");

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

  const reorderable = reorderableStatuses.has(status);
  const bucketJobs = useMemo(
    () => (reorderable ? [...filtered].sort(byManualRank) : []),
    [filtered, reorderable]
  );

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
          {reorderable && bucketJobs.length ? (
            <ReorderableJobList
              jobs={bucketJobs}
              status={status as JobStatus}
              selectedId={selected?.job_id || ""}
              onSelect={setSelectedId}
            />
          ) : null}
          {!reorderable &&
            fitOrder
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
