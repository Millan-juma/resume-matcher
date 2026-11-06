import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import {
  getMe,
  hasStoredSession,
  login,
  logout,
  registerCandidate,
  registerOrg,
  restoreSession,
  setSessionExpiredHandler,
} from "./api";
import type { Me } from "./api";
import { AuthContext } from "./auth-context";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setSessionExpiredHandler(() => setUser(null));
    (async () => {
      try {
        if (hasStoredSession() && (await restoreSession())) {
          const me = await getMe();
          if (!cancelled) setUser(me);
        }
      } catch {
        // offline or server error: show the sign-in page, the stored session stays
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
      setSessionExpiredHandler(null);
    };
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        signIn: async (email, password) => {
          await login(email, password);
          setUser(await getMe());
        },
        signUpOrg: async (orgName, email, password) => {
          await registerOrg(orgName, email, password);
          setUser(await getMe());
        },
        signUpCandidate: async (orgId, email, password) => {
          await registerCandidate(orgId, email, password);
          setUser(await getMe());
        },
        signOut: async () => {
          await logout();
          setUser(null);
        },
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
