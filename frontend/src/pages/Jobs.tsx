import { useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { request } from "../api";
import { useAuth } from "../auth-context";
import { errorText } from "../errors";
import type { Job } from "../types";
import { useLoad } from "../useLoad";

export default function Jobs() {
  const { user } = useAuth();
  const { data: jobs, error, loading, reload } = useLoad("jobs", () => request<Job[]>("/jobs"));
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const joinLink = user ? `${window.location.origin}/join/${user.org_id}` : "";

  async function createJob(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    setBusy(true);
    try {
      await request<Job>("/jobs", {
        method: "POST",
        json: { title: title.trim(), description: description.trim() },
      });
      setTitle("");
      setDescription("");
      reload();
    } catch (err) {
      setFormError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(joinLink);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard blocked: the link is visible to copy by hand
    }
  }

  if (!user) return null;

  return (
    <>
      <h1>Jobs</h1>

      <div className="card">
        <h2>Post a job</h2>
        <form onSubmit={(e) => void createJob(e)}>
          <label>
            Title
            <input value={title} onChange={(e) => setTitle(e.target.value)} required minLength={2} maxLength={200} />
          </label>
          <label>
            Description
            <textarea
              rows={5}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              required
              minLength={20}
              placeholder="Describe the role and name the skills you need. Applicants are matched against them."
            />
          </label>
          {formError && (
            <p className="error" role="alert">
              {formError}
            </p>
          )}
          <button type="submit" disabled={busy}>
            {busy ? "Posting..." : "Post job"}
          </button>
        </form>
      </div>

      <div className="card">
        <h2>Your jobs</h2>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        {loading && !jobs && <p className="muted">Loading...</p>}
        {jobs && jobs.length === 0 && <p className="muted">No jobs yet. Post your first one above.</p>}
        {jobs?.map((j) => (
          <div key={j.id} className="list-row">
            <strong>{j.title}</strong>
            <Link to={`/jobs/${j.id}`}>View applicants</Link>
          </div>
        ))}
      </div>

      <div className="card">
        <h2>Candidate sign-up link</h2>
        <p className="muted small">Share this link so candidates can register under your company.</p>
        <div className="row">
          <input readOnly value={joinLink} onFocus={(e) => e.currentTarget.select()} />
          <button onClick={() => void copyLink()}>{copied ? "Copied" : "Copy"}</button>
        </div>
      </div>
    </>
  );
}
