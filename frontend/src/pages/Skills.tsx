import { useState } from "react";
import type { FormEvent } from "react";
import { request } from "../api";
import { errorText } from "../errors";
import type { SkillsResponse } from "../types";
import { useLoad } from "../useLoad";

export default function Skills() {
  const { data, error, loading, reload } = useLoad("skills", () => request<SkillsResponse>("/skills"));
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  async function addSkills(names: string[]) {
    setBusy(true);
    setMessage(null);
    setFormError(null);
    try {
      const out = await request<{ added: string[]; already_existed: string[] }>("/skills", {
        method: "POST",
        json: { names },
      });
      setMessage(out.added.length ? `Added ${out.added.length} skill(s).` : "Those skills were already in your list.");
      setText("");
      reload();
    } catch (err) {
      setFormError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function removeSkill(id: string) {
    setBusy(true);
    setMessage(null);
    setFormError(null);
    try {
      await request(`/skills/${id}`, { method: "DELETE" });
      reload();
    } catch (err) {
      setFormError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    const names = text
      .split(/[,\n]/)
      .map((s) => s.trim())
      .filter(Boolean);
    if (names.length > 0) void addSkills(names);
  }

  return (
    <>
      <h1>Skills</h1>
      <p className="muted">
        Applicants are matched against the skills listed here. A skill counts when the exact word or phrase appears in
        the job description and in the resume.
      </p>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {loading && !data && <p className="muted">Loading...</p>}

      {data && (
        <>
          <div className="card">
            <h2>{data.using_defaults ? "Built-in skills (in use)" : `Your skills (${data.custom.length})`}</h2>
            {data.using_defaults ? (
              <>
                <p className="muted small">
                  Your company has no skills of its own yet, so these {data.defaults.length} built-in skills are used.
                  As soon as you add one skill, the built-in list is replaced by yours. Copy it first if you want to
                  keep it.
                </p>
                <div className="chips">
                  {data.defaults.map((s) => (
                    <span key={s} className="chip">
                      {s}
                    </span>
                  ))}
                </div>
                <div className="actions">
                  <button className="ghost" disabled={busy} onClick={() => void addSkills(data.defaults)}>
                    Copy the built-in skills into my list
                  </button>
                </div>
              </>
            ) : (
              <div className="chips">
                {data.custom.map((s) => (
                  <span key={s.id} className="chip">
                    {s.name}
                    <button
                      className="chip-btn"
                      aria-label={`Remove ${s.name}`}
                      disabled={busy}
                      onClick={() => void removeSkill(s.id)}
                    >
                      &times;
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

          <div className="card">
            <h2>Add skills</h2>
            <form onSubmit={onSubmit}>
              <label>
                Skill names, separated by commas or new lines
                <textarea
                  rows={3}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="python, fastapi, postgresql"
                />
              </label>
              {formError && (
                <p className="error" role="alert">
                  {formError}
                </p>
              )}
              {message && <p className="success">{message}</p>}
              <button type="submit" disabled={busy || text.trim() === ""}>
                Add skills
              </button>
            </form>
            <p className="muted small">
              Changes apply to new applications. To update existing applicants, open the job and choose Re-score all.
            </p>
          </div>
        </>
      )}
    </>
  );
}
