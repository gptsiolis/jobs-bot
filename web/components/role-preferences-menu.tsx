"use client";

import { useActionState, useEffect, useRef, useState } from "react";
import { Plus, SlidersHorizontal, X } from "lucide-react";
import { addRolePreference, removeRolePreference } from "@/app/actions";
import type { RolePreference } from "@/lib/types";

const families: { value: RolePreference["family"]; label: string; hint: string }[] = [
  {
    value: "operations_strategy",
    label: "Operations · Strategy · Chief of Staff",
    hint: "Top priority — surfaced first"
  },
  { value: "business_development", label: "Business Development · Sales", hint: "Secondary" },
  { value: "early_career", label: "Early Career / New Grad", hint: "Signals, function-agnostic" }
];

export function RolePreferencesMenu({ preferences }: { preferences: RolePreference[] }) {
  const [open, setOpen] = useState(false);
  const [state, action, pending] = useActionState(addRolePreference, { ok: true, message: "" });
  const containerRef = useRef<HTMLDivElement>(null);

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

  const byFamily = (family: RolePreference["family"]) =>
    preferences
      .filter((pref) => pref.family === family)
      .sort((a, b) => a.keyword.localeCompare(b.keyword));

  return (
    <div className="header-menu" ref={containerRef}>
      <button
        type="button"
        className={open ? "text-button header-menu-trigger is-open" : "text-button header-menu-trigger"}
        onClick={() => setOpen((value) => !value)}
        aria-haspopup="dialog"
        aria-expanded={open}
      >
        <SlidersHorizontal size={15} />
        Preferences
      </button>
      {open ? (
        <div className="header-popover pref-popover" role="dialog" aria-label="Role preferences">
          <div className="header-popover-head">
            <h2>Role preferences</h2>
            <button
              type="button"
              className="icon-button"
              onClick={() => setOpen(false)}
              aria-label="Close preferences"
            >
              <X size={15} />
            </button>
          </div>
          <p className="muted pref-intro">
            Titles the scrapers search for and prioritize. Changes apply on the next scraper run.
          </p>
          <form action={action} className="pref-add">
            <select name="family" defaultValue="operations_strategy">
              {families.map((family) => (
                <option key={family.value} value={family.value}>
                  {family.label}
                </option>
              ))}
            </select>
            <div className="pref-add-row">
              <input name="keyword" placeholder="Add a title or keyword" />
              <button className="primary-button" type="submit" disabled={pending}>
                <Plus size={15} />
                Add
              </button>
            </div>
          </form>
          {state.message ? (
            <span className={state.ok ? "action-message" : "action-message is-error"}>
              {state.message}
            </span>
          ) : null}
          {families.map((family) => {
            const items = byFamily(family.value);
            return (
              <div className="pref-section" key={family.value}>
                <h3>
                  {family.label} <span className="muted">· {items.length}</span>
                </h3>
                {items.length ? (
                  <div className="pref-chips">
                    {items.map((pref) => (
                      <span className="pref-chip" key={pref.id}>
                        {pref.keyword}
                        <form action={removeRolePreference}>
                          <input type="hidden" name="id" value={pref.id} />
                          <button
                            className="pref-chip-remove"
                            type="submit"
                            aria-label={`Remove ${pref.keyword}`}
                            title={`Remove ${pref.keyword}`}
                          >
                            <X size={12} />
                          </button>
                        </form>
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="muted pref-empty">None yet.</p>
                )}
              </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
