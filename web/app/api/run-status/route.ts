import { NextResponse } from "next/server";
import { createSupabaseServerClient } from "@/lib/supabase/server";

const fallbackEstimateSeconds: Record<string, number> = {
  watchlist: 12 * 60,
  discovery: 18 * 60,
  job_search: 20 * 60,
  source_expansion: 3 * 60,
  all: 38 * 60
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

function durationSeconds(run: Pick<RunRow, "started_at" | "finished_at">) {
  if (!run.started_at || !run.finished_at) return null;
  const started = new Date(run.started_at).getTime();
  const finished = new Date(run.finished_at).getTime();
  if (!Number.isFinite(started) || !Number.isFinite(finished) || finished <= started) {
    return null;
  }
  return Math.round((finished - started) / 1000);
}

function median(values: number[]) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  if (sorted.length % 2) return sorted[middle];
  return Math.round((sorted[middle - 1] + sorted[middle]) / 2);
}

export async function GET() {
  const supabase = await createSupabaseServerClient();
  const { data: auth } = await supabase.auth.getUser();

  if (!auth.user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { data: latest, error: latestError } = await supabase
    .from("job_runs")
    .select("id,mode,status,started_at,finished_at,total_found,total_written,total_new,counts_by_source,failures,error")
    .order("started_at", { ascending: false })
    .limit(1)
    .maybeSingle<RunRow>();

  if (latestError) {
    return NextResponse.json({ error: latestError.message }, { status: 500 });
  }

  if (!latest) {
    return NextResponse.json(
      { run: null, estimate_seconds: null, generated_at: new Date().toISOString() },
      { headers: { "Cache-Control": "no-store" } }
    );
  }

  const { data: history } = await supabase
    .from("job_runs")
    .select("started_at,finished_at")
    .eq("mode", latest.mode)
    .neq("status", "running")
    .not("finished_at", "is", null)
    .order("started_at", { ascending: false })
    .limit(8);

  const durations = (history || [])
    .map((run) => durationSeconds(run))
    .filter((value): value is number => typeof value === "number" && value > 0);
  const estimate = median(durations) || fallbackEstimateSeconds[latest.mode] || fallbackEstimateSeconds.all;

  return NextResponse.json(
    { run: latest, estimate_seconds: estimate, generated_at: new Date().toISOString() },
    { headers: { "Cache-Control": "no-store" } }
  );
}
