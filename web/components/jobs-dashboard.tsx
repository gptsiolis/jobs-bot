"use client";

import { Fragment, useCallback, useEffect, useMemo, useState, useTransition } from "react";
import type { ReactNode } from "react";
import {
  Bookmark,
  CheckCircle2,
  ExternalLink,
  GripVertical,
  Linkedin,
  MessageSquareReply,
  RotateCcw,
  Search,
  XCircle
} from "lucide-react";
import {
  reorderJobs,
  setCompanyContactResponded,
  setCompanyMessaged,
  updateJobStatus
} from "@/app/actions";
import type { CompanyContact, JobRow, JobStatus } from "@/lib/types";
import { CompanyContacts } from "./company-contacts";

const roleFamilyMeta = [
  { value: "operations_strategy", label: "Operations · Strategy · Chief of Staff" },
  { value: "business_development", label: "Business Development · Sales" },
  { value: "early_career", label: "Early Career / New Grad" },
  { value: "other", label: "Other roles" }
];

const roleFamilyLabels: Record<string, string> = Object.fromEntries(
  roleFamilyMeta.map((family) => [family.value, family.label])
);

const knownRoleFamilies = new Set(["operations_strategy", "business_development", "early_career"]);
const opsTitleTerms = [
  "chief of staff", "business operations", "revenue operations", "operations", "strategy",
  "founder's associate", "founders associate", "founder associate", "special projects",
  "program associate", "program coordinator"
];
const bdTitleTerms = [
  "business development", "sales development", "account executive", "account manager",
  "sales associate", "sales representative", "partnership", "growth", "customer success",
  "investment analyst", "investment associate", "acquisitions", "asset management"
];
const earlyTitleTerms = [
  "new grad", "new graduate", "recent graduate", "early career", "entry level", "entry-level",
  "rotational", "graduate program", "analyst program", "associate program"
];

// Group jobs by role type. Prefer the server-assigned role_family; fall back to
// title keywords so jobs scraped before role_family existed still categorize.
function roleFamilyOf(job: JobRow): string {
  if (job.role_family && knownRoleFamilies.has(job.role_family)) return job.role_family;
  const title = job.title.toLowerCase();
  if (opsTitleTerms.some((term) => title.includes(term))) return "operations_strategy";
  if (bdTitleTerms.some((term) => title.includes(term))) return "business_development";
  if (earlyTitleTerms.some((term) => title.includes(term))) return "early_career";
  return "other";
}

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

function CompanyMessagedAction({ company, messaged }: { company: string; messaged: boolean }) {
  const title = messaged
    ? "Messaged on LinkedIn (whole company) — click to undo"
    : "Messaged on LinkedIn — moves every applied role at this company";
  return (
    <form action={setCompanyMessaged}>
      <input type="hidden" name="company" value={company} />
      <input type="hidden" name="messaged" value={messaged ? "false" : "true"} />
      <button
        className={messaged ? "status-button is-active" : "status-button"}
        type="submit"
        title={title}
        aria-label={title}
      >
        <Linkedin size={16} />
      </button>
    </form>
  );
}

function CompanyRespondedAction({ company, responded }: { company: string; responded: boolean }) {
  const title = responded
    ? "Contact responded (whole company) — click to undo"
    : "Mark the LinkedIn contact as responded";
  return (
    <form action={setCompanyContactResponded}>
      <input type="hidden" name="company" value={company} />
      <input type="hidden" name="responded" value={responded ? "false" : "true"} />
      <button
        className={responded ? "status-button is-responded" : "status-button"}
        type="submit"
        title={title}
        aria-label={title}
      >
        <MessageSquareReply size={16} />
      </button>
    </form>
  );
}

function JobActions({ job }: { job: JobRow }) {
  if (job.status === "applied" || job.status === "applied_messaged") {
    const messaged = job.status === "applied_messaged";
    return (
      <div className="status-actions">
        <CompanyMessagedAction company={job.company} messaged={messaged} />
        {messaged ? (
          <CompanyRespondedAction company={job.company} responded={job.contact_responded} />
        ) : null}
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
  onSelect,
  contacts
}: {
  jobs: JobRow[];
  status: JobStatus;
  selectedId: string;
  onSelect: (jobId: string) => void;
  contacts: CompanyContact[];
}) {
  const [order, setOrder] = useState<JobRow[]>(jobs);
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [overIndex, setOverIndex] = useState<number | null>(null);
  const [pending, startTransition] = useTransition();
  const showApplied = status === "applied" || status === "applied_messaged";
  const showContact = status === "applied_messaged";
  // reorder, #, score, role, company, location, sponsor, actions = 8, plus the
  // optional applied/contact columns. Used to span the inline contacts row.
  const columnCount = 8 + (showApplied ? 1 : 0) + (showContact ? 1 : 0);

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
              {showApplied ? <th>Applied</th> : null}
              {showContact ? <th>Contact</th> : null}
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {order.map((job, index) => {
              const showContacts =
                job.job_id === selectedId &&
                (job.status === "applied" || job.status === "applied_messaged");
              return (
              <Fragment key={job.job_id}>
              <tr
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
                {showApplied ? <td>{formatDate(job.applied_at)}</td> : null}
                {showContact ? (
                  <td>
                    <span className={job.contact_responded ? "pill fit-strong" : "pill"}>
                      {job.contact_responded ? "Responded" : "Awaiting"}
                    </span>
                  </td>
                ) : null}
                <td onClick={(event) => event.stopPropagation()}>
                  <JobActions job={job} />
                </td>
              </tr>
              {showContacts ? (
                <tr className="contacts-row">
                  <td colSpan={columnCount} onClick={(event) => event.stopPropagation()}>
                    <CompanyContacts
                      company={job.company}
                      contacts={contacts.filter((contact) => contact.company === job.company)}
                    />
                  </td>
                </tr>
              ) : null}
              </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function JobsDashboard({ jobs, contacts }: { jobs: JobRow[]; contacts: CompanyContact[] }) {
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
      const key = roleFamilyOf(job);
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
              contacts={contacts}
            />
          ) : null}
          {!reorderable &&
            roleFamilyMeta
              .filter((family) => grouped[family.value]?.length)
              .map((family) => (
              <div className="job-section" key={family.value}>
                <h2 className="section-title">
                  <span>{family.label}</span>
                  <span className="muted">{grouped[family.value].length}</span>
                </h2>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Score</th>
                        <th>Fit</th>
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
                      {grouped[family.value].map((job) => (
                        <tr
                          key={job.job_id}
                          className={job.job_id === selected?.job_id ? "is-selected" : ""}
                          onClick={() => setSelectedId(job.job_id)}
                        >
                          <td className="score">{job.applicability_score}</td>
                          <td>
                            <span className={`pill fit-pill fit-${job.fit_bucket}`}>
                              {job.fit_bucket}
                            </span>
                          </td>
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
                {selected.applied_at ? (
                  <>
                    <dt>Applied</dt>
                    <dd>{formatDate(selected.applied_at)}</dd>
                  </>
                ) : null}
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
                <dt>Role type</dt>
                <dd>{roleFamilyLabels[roleFamilyOf(selected)]}</dd>
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
