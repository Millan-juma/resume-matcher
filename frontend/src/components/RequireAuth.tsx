import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../auth-context";

export default function RequireAuth() {
  const { user, loading } = useAuth();
  if (loading) return <p className="muted center">Loading…</p>;
  if (!user) return <Navigate to="/login" replace />;
  return <Outlet />;
}
