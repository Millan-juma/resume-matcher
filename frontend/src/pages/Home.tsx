import { useAuth } from "../auth-context";
import Jobs from "./Jobs";

export default function Home() {
  const { user } = useAuth();
  if (!user) return null;
  if (user.role === "candidate") {
    return (
      <>
        <h1>Welcome</h1>
        <div className="card">
          <p className="muted">Open jobs and your applications will appear here.</p>
        </div>
      </>
    );
  }
  return <Jobs />;
}
