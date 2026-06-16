"use client";

import { useActionState, useEffect, useRef, useState } from "react";
import { Building2, Plus, X } from "lucide-react";
import { addCompanyWatchlistRequest } from "@/app/actions";
import type { CompanyWatchlistRequest } from "@/lib/types";

function atsLabel(request: CompanyWatchlistRequest) {
  const ats = request.ats_config?.ats;
  return typeof ats === "string" ? ats : request.status;
}

export function CompanyWatchlistMenu({
  companyRequests
}: {
  companyRequests: CompanyWatchlistRequest[];
}) {
  const [open, setOpen] = useState(false);
  const [companyState, companyAction, companyPending] = useActionState(
    addCompanyWatchlistRequest,
    { ok: true, message: "" }
  );
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

  return (
    <div className="watchlist-menu" ref={containerRef}>
      <button
        type="button"
        className={open ? "text-button watchlist-trigger is-open" : "text-button watchlist-trigger"}
        onClick={() => setOpen((value) => !value)}
        aria-haspopup="dialog"
        aria-expanded={open}
      >
        <Building2 size={15} />
        Watchlist
        {companyRequests.length ? (
          <span className="watchlist-count">{companyRequests.length}</span>
        ) : null}
      </button>
      {open ? (
        <div className="watchlist-popover" role="dialog" aria-label="Company watchlist">
          <div className="watchlist-popover-head">
            <h2>Company Watchlist</h2>
            <button
              type="button"
              className="icon-button"
              onClick={() => setOpen(false)}
              aria-label="Close watchlist"
            >
              <X size={15} />
            </button>
          </div>
          <form action={companyAction} className="inline-form">
            <input name="company_name" placeholder="Company name" autoFocus />
            <button className="primary-button" type="submit" disabled={companyPending}>
              <Plus size={15} />
              Add
            </button>
          </form>
          {companyState.message ? (
            <span className={companyState.ok ? "action-message" : "action-message is-error"}>
              {companyState.message}
            </span>
          ) : null}
          {companyRequests.length ? (
            <div className="request-list">
              {companyRequests.map((request) => (
                <div className="request-row" key={request.id}>
                  <strong>{request.company_name}</strong>
                  <span className="pill">{atsLabel(request)}</span>
                  {request.last_error ? <span className="muted">{request.last_error}</span> : null}
                </div>
              ))}
            </div>
          ) : (
            <p className="muted watchlist-empty">
              No companies tracked yet. Add one to scrape its roles.
            </p>
          )}
        </div>
      ) : null}
    </div>
  );
}
