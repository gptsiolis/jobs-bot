"use client";

import { useActionState, useMemo, useState } from "react";
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
import type { CompanyWatchlistRequest, JobRow, JobStatus } from "@/lib/types";

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
      <StatusAction jobId={job.job_id} status="new" title="Reopen">
        <RotateCcw size={16} />
      </StatusAction>
    </div>
  );
}

function atsLabel(request: CompanyWatchlistRequest) {
  const ats = request.ats_config?.ats;
  return typeof ats === "string" ? ats : request.status;
}

export function JobsDashboard({
  jobs,
  companyRequests
}: {
  jobs: JobRow[];
  companyRequests: CompanyWatchlistRequest[];
}) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("active");
  const [quality, setQuality] = useState("");
  const [sponsor, setSponsor] = useState("");
  const [source, setSource] = useState("");
  const [fit, setFit] = useState("");
  const [location, setLocation] = useState("");
  const [selectedId, setSelectedId] = useState(jobs[0]?.job_id || "");
  const [runState, runAction, runPending] = useActionState(triggerScraperRun, {
    ok: true,
    message: ""
  });
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
      const text = `${job.title} ${job.company} ${job.location_text} ${job.source}`.toLowerCase();
      return (
        activeMatch &&
        (!quality || job.quality_tier === quality) &&
        (!sponsor || job.sponsor_tier === sponsor) &&
        (!source || job.source === source) &&
        (!fit || job.fit_bucket === fit) &&
        (!location || job.location_text.includes(location)) &&
        (!q || text.includes(q))
      );
    });
  }, [jobs, query, status, quality, sponsor, source, fit, location]);

  const selected = filtered.find((job) => job.job_id === selectedId) || filtered[0] || null;

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
        <div className="control-panel">
          <h2>Scrapers</h2>
          <div className="button-row">
            <form action={runAction}>
              <input type="hidden" name="mode" value="watchlist" />
              <button className="primary-button" type="submit" disabled={runPending}>
                <Play size={15} />
                Watchlist
              </button>
            </form>
            <form action={runAction}>
              <input type="hidden" name="mode" value="discovery" />
              <button className="primary-button" type="submit" disabled={runPending}>
                <Play size={15} />
                Discovery
              </button>
            </form>
          </div>
          {runState.message ? (
            <span className={runState.ok ? "action-message" : "action-message is-error"}>
              {runState.message}
            </span>
          ) : null}
        </div>

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
            placeholder="Title, company, source"
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
          <span className="muted">Quality</span>
          <select value={quality} onChange={(event) => setQuality(event.target.value)}>
            <option value="">All</option>
            {unique(jobs.map((job) => job.quality_tier)).map((value) => (
              <option key={value} value={value}>
                {value}
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
        <label>
          <span className="muted">Source</span>
          <select value={source} onChange={(event) => setSource(event.target.value)}>
            <option value="">All</option>
            {unique(jobs.map((job) => job.source)).map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
      </section>

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
