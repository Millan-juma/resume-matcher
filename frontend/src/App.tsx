import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./AuthProvider";
import Layout from "./components/Layout";
import RequireAuth from "./components/RequireAuth";
import RequireRole from "./components/RequireRole";
import AuthPage from "./pages/AuthPage";
import Home from "./pages/Home";
import JobDetail from "./pages/JobDetail";
import Skills from "./pages/Skills";
import Team from "./pages/Team";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/login" element={<AuthPage />} />
            <Route path="/join/:orgId" element={<AuthPage joinMode />} />
            <Route element={<RequireAuth />}>
              <Route path="/" element={<Home />} />
              <Route element={<RequireRole roles={["admin", "recruiter"]} />}>
                <Route path="/jobs/:jobId" element={<JobDetail />} />
                <Route path="/skills" element={<Skills />} />
              </Route>
              <Route element={<RequireRole roles={["admin"]} />}>
                <Route path="/team" element={<Team />} />
              </Route>
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
