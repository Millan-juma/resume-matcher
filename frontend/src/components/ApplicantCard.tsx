import { useState } from "react";
import { request } from "../api";
import { errorText } from "../errors";
import type { Applicant, Explanation, Stage } from "../types";

const STAGES: Stage[] = ["applied", "interview", "rejected", "hired"];

function failureText(code: string | null | undefined): string {
  if (code === "NoReadableText") return "No readable text could be extracted from this resume.";
  return code ? `Scoring failed (${code}).` : "Scoring failed.";
}

type Props = { applicant: Applicant; rank: number; onChanged: () => void };

export default function ApplicantCard({ applicant: a, rank, onChanged }: Props) {
  const [stageBusy, setStageBusy] = useState(false);
  const [explaining, setExplaining] = useState(false);
  const [explanation, setExplanation] = useState<Explanation | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function changeStage(stage: Stage) {
    setError(null);
    setStageBusy(true);
    try {
      await request<Applicant>(`/jobs/applications/${a.id}/stage`, { method: "PATCH", json: { stage } });
      onChanged();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setStageBusy(false);
    }
  }

  async function explain() {
    setError(null);
    setExplaining(true);
    try {
      setExplanation(await request<Explanation>(`/applications/${a.id}/explain`, { method: "POST" }));
    } catch (err) {
      setError(errorText(err));
    } finally {
      setExplaining(false);
    }
  }

  const bd = a.score_breakdown;
  return (
    <div className="card">
      <div className="spread">
        <div className="row">
          <span className="score">{a.score === null ? "-" : a.score.toFixed(1)}</span>
          <div>
            <strong>Applicant #{rank}</strong>
            <div className="muted small">ID {a.id.slice(0, 8)}</div>
          </div>
        </div>
        <label className="inline">
          <span className="muted small">Stage</span>
          <select value={a.stage} disabled={stageBusy} onChange={(e) => void changeStage(e.target.value as Stage)}>
            {STAGES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
      </div>

      {a.scoring_status === "pending" && <p className="muted small">Scoring in progress...</p>}
      {a.scoring_status === "failed" && <p className="error small">{failureText(a.scoring_error)}</p>}

      {bd && (
        <div className="chips">
          {bd.matched_skills.map((s) => (
            <span key={`m-${s}`} className="chip ok">
              + {s}
            </span>
          ))}
          {bd.missing_skills.map((s) => (
            <span key={`x-${s}`} className="chip bad">
              - {s}
            </span>
          ))}
        </div>
      )}

      <div className="actions">
        <button className="ghost" disabled={explaining || a.scoring_status !== "done"} onClick={() => void explain()}>
          {explaining ? "Explaining..." : "Explain this match"}
        </button>
      </div>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {explanation && (
        <div className="explain">
          <p>{explanation.summary}</p>
          <strong>Strengths</strong>
          <ul className="tight">
            {explanation.strengths.map((t, i) => (
              <li key={`s${i}-${t}`}>{t}</li>
            ))}
          </ul>
          <strong>Gaps</strong>
          <ul className="tight">
            {explanation.gaps.map((t, i) => (
              <li key={`g${i}-${t}`}>{t}</li>
            ))}
          </ul>
          <strong>Suggestions</strong>
          <ul className="tight">
            {explanation.suggestions.map((t, i) => (
              <li key={`u${i}-${t}`}>{t}</li>
            ))}
          </ul>
          <p className="muted small">
            {explanation.note} Source: {explanation.provider}
            {explanation.cached ? " (cached)" : ""}
          </p>
        </div>
      )}
    </div>
  );
}
