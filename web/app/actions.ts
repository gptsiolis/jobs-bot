"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { createSupabaseServerClient } from "@/lib/supabase/server";
import type { JobStatus } from "@/lib/types";

const allowedStatuses: JobStatus[] = [
  "new",
  "saved",
  "applied",
  "next_round",
  "rejected",
  "dismissed",
  "archived"
];

type ActionState = {
  ok: boolean;
  message: string;
};

function normalizeCompanyName(value: string) {
  return value
    .toLowerCase()
    .replace(/[\.,&']/g, " ")
    .replace(/\b(inc|llc|corp|corporation|co|ltd|the)\b/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

async function requireUser() {
  const supabase = await createSupabaseServerClient();
  const { data: user } = await supabase.auth.getUser();
  if (!user.user) {
    redirect("/login");
  }
  return supabase;
}

export async function updateJobStatus(formData: FormData) {
  const jobId = String(formData.get("job_id") || "");
  const status = String(formData.get("status") || "") as JobStatus;

  if (!jobId || !allowedStatuses.includes(status)) {
    throw new Error("Invalid job status update");
  }

  const supabase = await requireUser();

  const { error } = await supabase
    .from("jobs")
    .update({ status })
    .eq("job_id", jobId);

  if (error) {
    throw new Error(error.message);
  }

  revalidatePath("/");
}

export async function triggerScraperRun(
  _previousState: ActionState,
  formData: FormData
): Promise<ActionState> {
  await requireUser();

  const mode = String(formData.get("mode") || "");
  if (!["all"].includes(mode)) {
    return { ok: false, message: "Choose the combined scraper run." };
  }

  const token = process.env.GITHUB_ACTIONS_TOKEN;
  const repository = process.env.GITHUB_REPOSITORY || "gptsiolis/jobs-bot";
  const ref = process.env.GITHUB_ACTIONS_REF || "master";
  if (!token) {
    return {
      ok: false,
      message: "Missing GITHUB_ACTIONS_TOKEN in Vercel."
    };
  }

  const response = await fetch(
    `https://api.github.com/repos/${repository}/actions/workflows/scrape.yml/dispatches`,
    {
      method: "POST",
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2022-11-28"
      },
      body: JSON.stringify({ ref, inputs: { mode } }),
      cache: "no-store"
    }
  );

  if (!response.ok) {
    const detail = await response.text();
    return {
      ok: false,
      message: `GitHub rejected the run request (${response.status}): ${detail.slice(0, 140)}`
    };
  }

  revalidatePath("/");
  return { ok: true, message: "Scraper run started." };
}

export async function addCompanyWatchlistRequest(
  _previousState: ActionState,
  formData: FormData
): Promise<ActionState> {
  const companyName = String(formData.get("company_name") || "").trim();
  const normalizedName = normalizeCompanyName(companyName);
  if (!companyName || !normalizedName) {
    return { ok: false, message: "Enter a company name." };
  }

  const supabase = await requireUser();
  const { data: existing, error: existingError } = await supabase
    .from("company_watchlist_requests")
    .select("id,status")
    .eq("normalized_name", normalizedName)
    .maybeSingle();

  if (existingError) {
    return { ok: false, message: existingError.message };
  }
  if (existing) {
    return { ok: true, message: `${companyName} is already ${existing.status}.` };
  }

  const { error } = await supabase.from("company_watchlist_requests").insert({
    company_name: companyName,
    normalized_name: normalizedName,
    status: "pending"
  });

  if (error) {
    return { ok: false, message: error.message };
  }

  revalidatePath("/");
  return { ok: true, message: `${companyName} added.` };
}

export async function signOut() {
  const supabase = await createSupabaseServerClient();
  await supabase.auth.signOut();
  redirect("/login");
}