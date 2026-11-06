import { useState } from "react";
import { useAuth } from "../auth-context";

export default function Home() {
  const { user } = useAuth();
  const [copied, setCopied] = useState(false);
  if (!user) return null;

  const isStaff = user.role !== "candidate";
  const joinLink = `${window.location.origin}/join/${user.org_id}`;

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(joinLink);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard blocked: the link is visible to copy by hand
    }
  }

  return (
    <>
      <h1>Welcome</h1>
      <p className="muted">
        Signed in as {user.email} ({user.role}).
      </p>
      {isStaff ? (
        <div className="card">
          <h2>Candidate sign-up link</h2>
          <p className="muted small">Share this link so candidates can register under your company.</p>
          <div className="row">
            <input readOnly value={joinLink} onFocus={(e) => e.currentTarget.select()} />
            <button onClick={() => void copyLink()}>{copied ? "Copied" : "Copy"}</button>
          </div>
        </div>
      ) : (
        <div className="card">
          <p className="muted">Open jobs and your applications appear here in the next step.</p>
        </div>
      )}
    </>
  );
}
