"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { createSupabaseServerClient } from "@/lib/supabase/server";
import type { JobStatus } from "@/lib/types";

const allowedStatuses: JobStatus[] = ["new", "saved", "applied", "dismissed", "archived"];

export async function updateJobStatus(formData: FormData) {
  const jobId = String(formData.get("job_id") || "");
  const status = String(formData.get("status") || "") as JobStatus;

  if (!jobId || !allowedStatuses.includes(status)) {
    throw new Error("Invalid job status update");
  }

  const supabase = await createSupabaseServerClient();
  const { data: user } = await supabase.auth.getUser();
  if (!user.user) {
    redirect("/login");
  }

  const { error } = await supabase
    .from("jobs")
    .update({ status })
    .eq("job_id", jobId);

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
