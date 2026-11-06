import { useState } from "react";
import type { FormEvent } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { ApiError } from "../api";
import { useAuth } from "../auth-context";

type Mode = "login" | "org" | "candidate";

export default function AuthPage({ joinMode = false }: { joinMode?: boolean }) {
  const { orgId: orgIdFromLink } = useParams();
  const { user, loading, signIn, signUpOrg, signUpCandidate } = useAuth();
  const [mode, setMode] = useState<Mode>(joinMode ? "candidate" : "login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [orgName, setOrgName] = useState("");
  const [orgIdInput, setOrgIdInput] = useState(orgIdFromLink ?? "");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (loading) return <p className="muted center">Loading…</p>;
  if (user) return <Navigate to="/" replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "login") await signIn(email, password);
      else if (mode === "org") await signUpOrg(orgName.trim(), email, password);
      else await signUpCandidate(orgIdInput.trim(), email, password);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
    } finally {
      setBusy(false);
    }
  }

  const title = mode === "login" ? "Sign in" : mode === "org" ? "Register your company" : "Create a candidate account";

  return (
    <div className="card narrow">
      {!joinMode && (
        <div className="tabs" role="tablist">
          <button type="button" className={mode === "login" ? "tab active" : "tab"} onClick={() => setMode("login")}>
            Sign in
          </button>
          <button type="button" className={mode === "org" ? "tab active" : "tab"} onClick={() => setMode("org")}>
            Company
          </button>
          <button
            type="button"
            className={mode === "candidate" ? "tab active" : "tab"}
            onClick={() => setMode("candidate")}
          >
            Candidate
          </button>
        </div>
      )}
      <h1>{title}</h1>
      <form onSubmit={(e) => void onSubmit(e)}>
        {mode === "org" && (
          <label>
            Company name
            <input value={orgName} onChange={(e) => setOrgName(e.target.value)} required minLength={2} maxLength={200} />
          </label>
        )}
        {mode === "candidate" && (
          <label>
            Company ID
            <input
              value={orgIdInput}
              onChange={(e) => setOrgIdInput(e.target.value)}
              required
              readOnly={Boolean(orgIdFromLink)}
              placeholder="Ask the company for its sign-up link"
            />
          </label>
        )}
        <label>
          Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={mode === "login" ? undefined : 8}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
          />
        </label>
        {mode !== "login" && <p className="muted small">Use at least 8 characters.</p>}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" disabled={busy}>
          {busy ? "Please wait…" : title}
        </button>
      </form>
      {joinMode && (
        <p className="muted small">
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      )}
    </div>
  );
}
