import { useState } from "react";
import type { FormEvent } from "react";
import { request } from "../api";
import { useAuth } from "../auth-context";
import { errorText } from "../errors";
import type { StaffMember } from "../types";
import { useLoad } from "../useLoad";

export default function Team() {
  const { user } = useAuth();
  const { data, error, loading, reload } = useLoad("staff", () => request<StaffMember[]>("/users/staff"));
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"recruiter" | "admin">("recruiter");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  async function addMember(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMessage(null);
    setFormError(null);
    try {
      await request<StaffMember>("/users/staff", { method: "POST", json: { email: email.trim(), password, role } });
      setMessage(`Added ${email.trim()}. Share the password with them securely. There is no invite email yet.`);
      setEmail("");
      setPassword("");
      reload();
    } catch (err) {
      setFormError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function toggle(m: StaffMember) {
    if (m.is_active && !confirm(`Deactivate ${m.email}? They lose access immediately.`)) return;
    setBusy(true);
    setMessage(null);
    setFormError(null);
    try {
      await request(`/users/${m.id}/${m.is_active ? "deactivate" : "reactivate"}`, { method: "POST" });
      reload();
    } catch (err) {
      setFormError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>Team</h1>

      <div className="card">
        <h2>Add a team member</h2>
        <form onSubmit={(e) => void addMember(e)}>
          <label>
            Email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label>
            Temporary password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              autoComplete="new-password"
            />
          </label>
          <label>
            Role
            <select value={role} onChange={(e) => setRole(e.target.value as "recruiter" | "admin")}>
              <option value="recruiter">Recruiter</option>
              <option value="admin">Admin</option>
            </select>
          </label>
          {formError && (
            <p className="error" role="alert">
              {formError}
            </p>
          )}
          {message && <p className="success">{message}</p>}
          <button type="submit" disabled={busy}>
            Add member
          </button>
        </form>
      </div>

      <div className="card">
        <h2>Members</h2>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        {loading && !data && <p className="muted">Loading...</p>}
        {data?.map((m) => (
          <div key={m.id} className="list-row">
            <div>
              <strong>{m.email}</strong>{" "}
              <span className="badge">{m.role}</span>{" "}
              {!m.is_active && <span className="badge">deactivated</span>}
            </div>
            {m.id !== user?.id && (
              <button className={m.is_active ? "danger" : "ghost"} disabled={busy} onClick={() => void toggle(m)}>
                {m.is_active ? "Deactivate" : "Reactivate"}
              </button>
            )}
          </div>
        ))}
      </div>
    </>
  );
}
