"use client";

import { useActionState, useEffect, useRef } from "react";
import { ExternalLink, MessageSquareReply, Plus, X } from "lucide-react";
import {
  addCompanyContact,
  removeCompanyContact,
  setContactResponded
} from "@/app/actions";
import type { CompanyContact } from "@/lib/types";

export function CompanyContacts({
  company,
  contacts
}: {
  company: string;
  contacts: CompanyContact[];
}) {
  const [state, action, pending] = useActionState(addCompanyContact, { ok: true, message: "" });
  const formRef = useRef<HTMLFormElement>(null);

  // Clear the inputs once an add succeeds so the next person can be pasted in.
  useEffect(() => {
    if (state.ok && state.message) {
      formRef.current?.reset();
    }
  }, [state]);

  return (
    <div className="contacts">
      <h3 className="contacts-title">
        People messaged
        <span className="muted"> · {contacts.length}</span>
      </h3>
      <p className="muted contacts-hint">
        Track who you&apos;ve reached out to on LinkedIn. If they don&apos;t reply, add the
        next person you try.
      </p>

      <form ref={formRef} action={action} className="contacts-add">
        <input type="hidden" name="company" value={company} />
        <input name="contact_name" placeholder="Name (optional)" autoComplete="off" />
        <div className="contacts-add-row">
          <input
            name="linkedin_url"
            placeholder="LinkedIn profile URL"
            autoComplete="off"
          />
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

      {contacts.length ? (
        <ul className="contacts-list">
          {contacts.map((contact) => (
            <li key={contact.id} className={contact.responded ? "contact is-responded" : "contact"}>
              <a
                className="contact-link"
                href={contact.linkedin_url}
                target="_blank"
                rel="noreferrer"
              >
                {contact.contact_name || contact.linkedin_url}
                <ExternalLink size={13} />
              </a>
              {contact.responded ? <span className="pill fit-strong">Replied</span> : null}
              <div className="contact-actions">
                <form action={setContactResponded}>
                  <input type="hidden" name="id" value={contact.id} />
                  <input type="hidden" name="responded" value={contact.responded ? "false" : "true"} />
                  <button
                    className={contact.responded ? "icon-button is-responded" : "icon-button"}
                    type="submit"
                    title={contact.responded ? "Mark as no reply yet" : "Mark as replied"}
                    aria-label={contact.responded ? "Mark as no reply yet" : "Mark as replied"}
                  >
                    <MessageSquareReply size={14} />
                  </button>
                </form>
                <form action={removeCompanyContact}>
                  <input type="hidden" name="id" value={contact.id} />
                  <button
                    className="icon-button"
                    type="submit"
                    title="Remove contact"
                    aria-label="Remove contact"
                  >
                    <X size={14} />
                  </button>
                </form>
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
