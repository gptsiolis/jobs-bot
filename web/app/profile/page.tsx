import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { ProfileForm } from "@/components/profile-form";
import { createSupabaseServerClient } from "@/lib/supabase/server";
import type { ApplicantProfile } from "@/lib/types";

export default async function ProfilePage() {
  const supabase = await createSupabaseServerClient();
  const { data: auth } = await supabase.auth.getUser();
  if (!auth.user) {
    redirect("/login");
  }

  const { data: profile } = await supabase
    .from("applicant_profile")
    .select(
      "full_name,email,phone,location,linkedin_url,github_url,portfolio_url,years_experience,work_authorized,requires_sponsorship,willing_to_relocate,earliest_start,salary_expectation,minimum_salary,standard_answers,resume_path,resume_filename,updated_at"
    )
    .eq("created_by", auth.user.id)
    .maybeSingle();

  return (
    <div className="page">
      <header className="topbar">
        <div className="brand">
          <h1>Your profile</h1>
          <span>{auth.user.email}</span>
        </div>
        <div className="topbar-actions">
          <Link className="text-button" href="/">
            <ArrowLeft size={15} /> Back to jobs
          </Link>
        </div>
      </header>
      <main className="main main-narrow">
        <ProfileForm
          profile={(profile as ApplicantProfile) ?? null}
          fallbackEmail={auth.user.email ?? ""}
        />
      </main>
    </div>
  );
}
