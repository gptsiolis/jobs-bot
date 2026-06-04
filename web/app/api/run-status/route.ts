import { NextResponse } from "next/server";
import { createSupabaseServerClient } from "@/lib/supabase/server";

const fallbackEstimateSeconds: Record<string, number> = {
  watchlist: 12 * 60,
  discovery: 40 * 60,
  job_search: 15 * 60,
  source_expansion: 3 * 60,
  all: 65 * 60
};

type RunRow = {
  id: string;
  mode: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  total_found: number;
  total_written: number;
  total_new: number;
  counts_by_source?: Record<string, number> | null;
  failures?: unknown[] | null;
  error?: string | null;
};

type EstimatedRun = RunRow & { estimate_seconds: number };

function durationSeconds(run: Pick<RunRow, "started_at" | "finished_at">) {
  if (!run.started_at || !run.finished_at) return null;
  const started = new Date(run.started_at).getTime();
  const finished = new Date(run.finished_at).getTime();
  if (!Number.isFinite(started) || !Number.isFinite(finished) || finished <= started) {
    return null;
  }
  return Math.round((finished - started) / 1000);
}

function elapsedSeconds(run: Pick<RunRow, "started_at">, now = Date.now()) {
  const started = new Date(run.started_at).getTime();
  if (!Number.isFinite(started) || now < started) return 0;
  return Math.round((now - started) / 1000);
}

function median(values: number[]) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  if (sorted.length % 2) return sorted[middle];
  return Math.round((sorted[middle - 1] + sorted[middle]) / 2);
}

function estimateForMode(mode: string, runs: RunRow[]) {
  const durations = runs
    .filter((run) => run.mode === mode && run.status !== "running")
    .map((run) => durationSeconds(run))
    .filter((value): value is number => typeof value === "number" && value > 0);
  return median(durations) || fallbackEstimateSeconds[mode] || fallbackEstimateSeconds.all;
}

function staleAdjustedRun(run: RunRow, allRuns: RunRow[]): EstimatedRun {
  const estimate = estimateForMode(run.mode, allRuns);
  const staleLimit = Math.max(estimate * 1.75, 90 * 60);
  if (run.status === "running" && elapsedSeconds(run) > staleLimit) {
    return {
      ...run,
      status: "cancelled",
      finished_at: run.finished_at || new Date().toISOString(),
      error: run.error || "Run appears stale after exceeding the expected runtime.",
      estimate_seconds: estimate
    };
  }
  return { ...run, estimate_seconds: estimate };
}

export async function GET() {
  const supabase = await createSupabaseServerClient();
  const { data: auth } = await supabase.auth.getUser();

  if (!auth.user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { data: rawRuns, error } = await supabase
    .from("job_runs")
    .select("id,mode,status,started_at,finished_at,total_found,total_written,total_new,counts_by_source,failures,error")
    .order("started_at", { ascending: false })
    .limit(12);

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  const runs = (rawRuns || []) as RunRow[];
  if (!runs.length) {
    return NextResponse.json(
      { run: null, active_runs: [], estimate_seconds: null, generated_at: new Date().toISOString() },
      { headers: { "Cache-Control": "no-store" } }
    );
  }

  const adjusted = runs.map((run) => staleAdjustedRun(run, runs));
  const activeRuns = adjusted.filter((run) => run.status === "running");
  const primary = activeRuns[0] || adjusted[0];

  return NextResponse.json(
    {
      run: primary,
      active_runs: activeRuns,
      estimate_seconds: primary.estimate_seconds,
      generated_at: new Date().toISOString()
    },
    { headers: { "Cache-Control": "no-store" } }
  );
}
