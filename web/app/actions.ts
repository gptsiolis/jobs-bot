"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { createSupabaseServerClient } from "@/lib/supabase/server";
import type { JobStatus } from "@/lib/types";

const allowedStatuses: JobStatus[] = [
  "new",
  "saved",
  "applied",
  "applied_messaged",
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

// A single LinkedIn message covers a whole company, so messaging is tracked
// per company: toggling it moves every applied role at that company into (or
// out of) the applied_messaged bucket together.
export async function setCompanyMessaged(formData: FormData) {
  const company = String(formData.get("company") || "");
  const messaged = String(formData.get("messaged") || "") === "true";

  if (!company) {
    throw new Error("Invalid company message update");
  }

  const supabase = await requireUser();

  const update = messaged
    ? { status: "applied_messaged" as JobStatus }
    : { status: "applied" as JobStatus, contact_responded: false };
  const fromStatus: JobStatus = messaged ? "applied" : "applied_messaged";

  const { error } = await supabase
    .from("jobs")
    .update(update)
    .eq("company", company)
    .eq("status", fromStatus);

  if (error) {
    throw new Error(error.message);
  }

  revalidatePath("/");
}

export async function setCompanyContactResponded(formData: FormData) {
  const company = String(formData.get("company") || "");
  const responded = String(formData.get("responded") || "") === "true";

  if (!company) {
    throw new Error("Invalid contact response update");
  }

  const supabase = await requireUser();

  const { error } = await supabase
    .from("jobs")
    .update({ contact_responded: responded })
    .eq("company", company)
    .eq("status", "applied_messaged");

  if (error) {
    throw new Error(error.message);
  }

  revalidatePath("/");
}

// Normalize a LinkedIn profile URL: trim, drop tracking query/hash, ensure a
// scheme so the stored value is always a clickable link.
function normalizeLinkedinUrl(value: string) {
  let url = value.trim();
  if (!url) return "";
  url = url.replace(/[?#].*$/, "").replace(/\/+$/, "");
  if (!/^https?:\/\//i.test(url)) {
    url = "https://" + url.replace(/^\/+/, "");
  }
  return url;
}

export async function addCompanyContact(
  _previousState: ActionState,
  formData: FormData
): Promise<ActionState> {
  const company = String(formData.get("company") || "").trim();
  const contactName = String(formData.get("contact_name") || "").trim();
  const linkedinUrl = normalizeLinkedinUrl(String(formData.get("linkedin_url") || ""));

  if (!company) {
    return { ok: false, message: "Missing company." };
  }
  if (!linkedinUrl) {
    return { ok: false, message: "Paste the person's LinkedIn URL." };
  }
  if (!/linkedin\.com/i.test(linkedinUrl)) {
    return { ok: false, message: "That doesn't look like a LinkedIn URL." };
  }

  const supabase = await requireUser();
  const { error } = await supabase.from("company_contacts").insert({
    company,
    contact_name: contactName || null,
    linkedin_url: linkedinUrl
  });

  if (error) {
    if (error.code === "23505") {
      return { ok: true, message: "That person is already on the list." };
    }
    return { ok: false, message: error.message };
  }

  revalidatePath("/");
  return { ok: true, message: `Added ${contactName || "contact"}.` };
}

export async function setContactResponded(formData: FormData) {
  const id = String(formData.get("id") || "");
  const company = String(formData.get("company") || "");
  const responded = String(formData.get("responded") || "") === "true";
  if (!id) {
    throw new Error("Invalid contact");
  }

  const supabase = await requireUser();
  const { error } = await supabase
    .from("company_contacts")
    .update({ responded })
    .eq("id", id);

  if (error) {
    throw new Error(error.message);
  }

  // Bubble the reply up to the job: marking a person as replied flips the
  // company's applied_messaged roles from "Awaiting" to "Responded". When
  // un-marking, only fall back to "Awaiting" if no one else at the company has
  // replied either.
  if (company) {
    let jobResponded = responded;
    if (!responded) {
      const { data: others } = await supabase
        .from("company_contacts")
        .select("id")
        .eq("company", company)
        .eq("responded", true)
        .limit(1);
      jobResponded = Boolean(others && others.length);
    }

    const { error: jobError } = await supabase
      .from("jobs")
      .update({ contact_responded: jobResponded })
      .eq("company", company)
      .eq("status", "applied_messaged");

    if (jobError) {
      throw new Error(jobError.message);
    }
  }

  revalidatePath("/");
}

export async function removeCompanyContact(formData: FormData) {
  const id = String(formData.get("id") || "");
  if (!id) {
    throw new Error("Invalid contact");
  }

  const supabase = await requireUser();
  const { error } = await supabase.from("company_contacts").delete().eq("id", id);

  if (error) {
    throw new Error(error.message);
  }

  revalidatePath("/");
}

const reorderableStatuses: JobStatus[] = ["saved", "applied", "applied_messaged"];

export async function reorderJobs(status: JobStatus, orderedIds: string[]) {
  if (!reorderableStatuses.includes(status)) {
    throw new Error("Reordering is only supported for saved and applied jobs");
  }
  if (!Array.isArray(orderedIds) || orderedIds.length === 0) {
    return;
  }

  const supabase = await requireUser();
  const payload = orderedIds.map((jobId, index) => ({
    job_id: String(jobId),
    manual_rank: index
  }));

  const { error } = await supabase.rpc("reorder_jobs", { payload });
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

  const modes = mode === "all" ? ["watchlist", "discovery", "job_search"] : [mode];
  const dispatchUrl = "https://api.github.com/repos/" + repository + "/actions/workflows/scrape.yml/dispatches";

  for (const scraperMode of modes) {
    const response = await fetch(dispatchUrl, {
      method: "POST",
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: "Bearer " + token,
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2022-11-28"
      },
      body: JSON.stringify({ ref, inputs: { mode: scraperMode } }),
      cache: "no-store"
    });

    if (!response.ok) {
      const detail = await response.text();
      return {
        ok: false,
        message: "GitHub rejected " + scraperMode + " (" + String(response.status) + "): " + detail.slice(0, 140)
      };
    }
  }

  revalidatePath("/");
  return { ok: true, message: "Scraper runs started." };
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

const roleFamilies = ["operations_strategy", "business_development", "early_career"];

export async function addRolePreference(
  _previousState: ActionState,
  formData: FormData
): Promise<ActionState> {
  const keyword = String(formData.get("keyword") || "").trim().toLowerCase();
  const family = String(formData.get("family") || "");

  if (!keyword) {
    return { ok: false, message: "Enter a title or keyword." };
  }
  if (!roleFamilies.includes(family)) {
    return { ok: false, message: "Pick a category." };
  }

  const supabase = await requireUser();
  const { error } = await supabase.from("role_preferences").insert({ keyword, family });

  if (error) {
    if (error.code === "23505") {
      return { ok: true, message: `"${keyword}" is already in the list.` };
    }
    return { ok: false, message: error.message };
  }

  revalidatePath("/");
  return { ok: true, message: `Added "${keyword}".` };
}

export async function removeRolePreference(formData: FormData) {
  const id = String(formData.get("id") || "");
  if (!id) {
    throw new Error("Invalid role preference");
  }

  const supabase = await requireUser();
  const { error } = await supabase.from("role_preferences").delete().eq("id", id);

  if (error) {
    throw new Error(error.message);
  }

  revalidatePath("/");
}

export async function signOut() {
  const supabase = await createSupabaseServerClient();
  await supabase.auth.signOut();
  redirect("/login");
}