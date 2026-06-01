"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { createSupabaseBrowserClient } from "@/lib/supabase/browser";

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);
    const form = new FormData(event.currentTarget);
    const supabase = createSupabaseBrowserClient();
    const { error: signInError } = await supabase.auth.signInWithPassword({
      email: String(form.get("email") || ""),
      password: String(form.get("password") || "")
    });
    setLoading(false);
    if (signInError) {
      setError(signInError.message);
      return;
    }
    router.replace("/");
    router.refresh();
  }

  return (
    <main className="login-shell">
      <section className="login">
        <h1>Jobs Bot</h1>
        <form onSubmit={submit}>
          <input name="email" type="email" autoComplete="email" placeholder="Email" required />
          <input
            name="password"
            type="password"
            autoComplete="current-password"
            placeholder="Password"
            required
          />
          {error ? <div className="error">{error}</div> : null}
          <button className="primary-button" type="submit" disabled={loading}>
            {loading ? "Signing in" : "Sign in"}
          </button>
        </form>
      </section>
    </main>
  );
}
