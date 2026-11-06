import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { request } from "../api";
import ApplicantCard from "../components/ApplicantCard";
import { errorText } from "../errors";
import type { Applicant, Job } from "../types";
import { useLoad } from "../useLoad";

const PAGE_LIMIT = 200;

export default function JobDetail() {
  const { jobId = "" } = useParams();
  const job = useLoad(`job:${jobId}`, () => request<Job>(`/jobs/${jobId}`));
  const apps = useLoad(`apps:${jobId}`, () =>
    request<Applicant[]>(`/jobs/${jobId}/applications?limit=${PAGE_LIMIT}`),
  );
  const [message, setMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const list = apps.data;
  const pending = list?.some((a) => a.scoring_status === "pending") ?? false;
  const reloadApps = apps.reload;

  // While anything is still being scored, check again every 3 seconds (for up to 2 minutes).
  useEffect(() => {
    if (!pending) return undefined;
    let ticks = 0;
    const timer = setInterval(() => {
      ticks += 1;
      if (ticks > 40) clearInterval(timer);
      else reloadApps();
    }, 3000);
    return () => clearInterval(timer);
  }, [pending, reloadApps]);

  async function rescore(onlyUnfinished: boolean) {
    setBusy(true);
    setMessage(null);
    setActionError(null);
    try {
      const out = await request<{ queued: number }>(
        `/jobs/${jobId}/rescore?only_unfinished=${onlyUnfinished}`,
        { method: "POST" },
      );
      setMessage(out.queued === 0 ? "Nothing to re-score." : `Queued ${out.queued} application(s) for scoring.`);
      reloadApps();
    } catch (err) {
      setActionError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <p>
        <Link to="/">&larr; All jobs</Link>
      </p>

      {job.error && (
        <p className="error" role="alert">
          {job.error}
        </p>
      )}
      {job.data && (
        <div className="card">
          <h1>{job.data.title}</h1>
          <details>
            <summary>Job description</summary>
            <p className="pre">{job.data.description}</p>
          </details>
        </div>
      )}

      <div className="spread">
        <h2>Applicants</h2>
        <div className="actions">
          <button className="ghost" onClick={apps.reload}>
            Refresh
          </button>
          <button className="ghost" disabled={busy} onClick={() => void rescore(true)}>
            Retry unfinished
          </button>
          <button className="ghost" disabled={busy} onClick={() => void rescore(false)}>
            Re-score all
          </button>
        </div>
      </div>
      <p className="muted small">
        Scores rank applicants against each other. They are decision support, not a verdict or a percentage.
      </p>

      {message && <p className="success">{message}</p>}
      {actionError && (
        <p className="error" role="alert">
          {actionError}
        </p>
      )}
      {apps.error && (
        <p className="error" role="alert">
          {apps.error}
        </p>
      )}
      {apps.loading && !list && <p className="muted">Loading...</p>}
      {list && list.length === 0 && <p className="muted">No applicants yet.</p>}
      {pending && (
        <p className="muted small">
          Some applicants are still being scored. If this takes more than a minute, check that the worker is running.
        </p>
      )}

      {list?.map((a, i) => (
        <ApplicantCard key={a.id} applicant={a} rank={i + 1} onChanged={reloadApps} />
      ))}

      {list && list.length >= PAGE_LIMIT && (
        <p className="muted small">Showing the top {PAGE_LIMIT} applicants by score.</p>
      )}
    </>
  );
}
