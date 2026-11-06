import { Navigate, Outlet } from "react-router-dom";
import type { Role } from "../api";
import { useAuth } from "../auth-context";

export default function RequireRole({ roles }: { roles: Role[] }) {
  const { user } = useAuth();
  if (!user || !roles.includes(user.role)) return <Navigate to="/" replace />;
  return <Outlet />;
}
