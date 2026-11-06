import { Link, NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth-context";

const linkClass = ({ isActive }: { isActive: boolean }) => (isActive ? "navlink active" : "navlink");

export default function Layout() {
  const { user, signOut } = useAuth();
  const isStaff = user !== null && user.role !== "candidate";
  return (
    <>
      <header className="topbar">
        <Link to="/" className="brand">
          Resume Matcher
        </Link>
        {isStaff ? (
          <nav className="links" aria-label="Main">
            <NavLink to="/" end className={linkClass}>
              Jobs
            </NavLink>
            <NavLink to="/skills" className={linkClass}>
              Skills
            </NavLink>
            {user?.role === "admin" && (
              <NavLink to="/team" className={linkClass}>
                Team
              </NavLink>
            )}
          </nav>
        ) : (
          <span className="links" />
        )}
        {user && (
          <div className="who">
            <span className="muted">{user.email}</span>
            <span className="badge">{user.role}</span>
            <button className="ghost" onClick={() => void signOut()}>
              Sign out
            </button>
          </div>
        )}
      </header>
      <main className="container">
        <Outlet />
      </main>
    </>
  );
}
