"use client";

import { useActionState, useEffect, useState } from "react";
import { ExternalLink, MessageSquareReply, Plus, X } from "lucide-react";
import {
  addCompanyContact,
  removeCompanyContact,
  setContactResponded
} from "@/app/actions";
import type { CompanyContact } from "@/lib/types";

// Best-guess a person's name from a LinkedIn profile URL. The /in/<slug> is
// usually "first-last" with an optional alphanumeric hash suffix LinkedIn adds
// to disambiguate. We strip the hash (any token containing a digit) and
// title-case the rest. Returns "" for custom handles like /in/jsmith where the
// guess would be unreliable, so we don't overwrite with junk.
function nameFromLinkedinUrl(url: string): string {
  const match = url.match(/linkedin\.com\/in\/([^/?#]+)/i);
  if (!match) return "";
  const slug = decodeURIComponent(match[1]);
  const words = slug
    .split("-")
    .filter((word) => word && !/\d/.test(word));
  if (words.length < 2) return "";
  return words
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
}

export function CompanyContacts({
  company,
  contacts
}: {
  company: string;
  contacts: CompanyContact[];
}) {
  const [state, action, pending] = useActionState(addCompanyContact, { ok: true, message: "" });
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  // Once the user types in the name field, stop auto-filling it from the URL.
  const [nameEdited, setNameEdited] = useState(false);

  // Clear the inputs once an add succeeds so the next person can be pasted in.
  useEffect(() => {
    if (state.ok && state.message) {
      setName("");
      setUrl("");
      setNameEdited(false);
    }
  }, [state]);

  const handleUrlChange = (value: string) => {
    setUrl(value);
    if (!nameEdited) {
      setName(nameFromLinkedinUrl(value));
    }
  };

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

      <form action={action} className="contacts-add">
        <input type="hidden" name="company" value={company} />
        <input
          name="contact_name"
          placeholder="Name (auto-filled from URL)"
          autoComplete="off"
          value={name}
          onChange={(event) => {
            setName(event.target.value);
            setNameEdited(true);
          }}
        />
        <div className="contacts-add-row">
          <input
            name="linkedin_url"
            placeholder="LinkedIn profile URL"
            autoComplete="off"
            value={url}
            onChange={(event) => handleUrlChange(event.target.value)}
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
