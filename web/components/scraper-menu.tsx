"use client";

import { useActionState, useCallback, useEffect, useRef, useState } from "react";
import { Play, X } from "lucide-react";
import { triggerScraperRun } from "@/app/actions";
import type { JobRun } from "@/lib/types";

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

export function ScraperMenu({ initialRun }: { initialRun: JobRun | null }) {
  const [open, setOpen] = useState(false);
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
  const containerRef = useRef<HTMLDivElement>(null);

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

  useEffect(() => {
    if (!open) return;
    function handlePointer(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", handlePointer);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handlePointer);
      document.removeEventListener("keydown", handleKey);
    };
  }, [open]);

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
  const triggerState = isActive ? "run-state is-running" : "run-state is-" + (run?.status || "idle");

  return (
    <div className="header-menu scraper-menu" ref={containerRef}>
      <button
        type="button"
        className={open ? "text-button header-menu-trigger is-open" : "text-button header-menu-trigger"}
        onClick={() => setOpen((value) => !value)}
        aria-haspopup="dialog"
        aria-expanded={open}
      >
        <Play size={15} />
        Scraper
        <span className={triggerState}>{statusLabel}</span>
      </button>
      {open ? (
        <div className="header-popover scraper-popover" role="dialog" aria-label="Scraper">
          <div className="header-popover-head">
            <h2>Scraper</h2>
            <button
              type="button"
              className="icon-button"
              onClick={() => setOpen(false)}
              aria-label="Close scraper"
            >
              <X size={15} />
            </button>
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
      ) : null}
    </div>
  );
}
