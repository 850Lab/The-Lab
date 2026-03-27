import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import * as authApi from "@/lib/authApi";
import type { AuthUser } from "@/lib/authTypes";
import {
  clearStoredSessionToken,
  readSessionBearerToken,
  setCustomerSessionToken,
} from "@/lib/sessionToken";

export type AuthContextValue = {
  /** Raw session token for workflow API (empty when signed out). */
  token: string;
  user: AuthUser | null;
  /** True until initial token read + optional `/api/auth/me` completes. */
  authBootstrapping: boolean;
  emailVerified: boolean;
  signIn: (email: string, password: string) => Promise<AuthUser>;
  signUp: (
    email: string,
    password: string,
    displayName: string,
  ) => Promise<AuthUser>;
  signOut: () => Promise<void>;
  refreshUser: () => Promise<void>;
  verifyEmail: (code: string) => Promise<void>;
  resendVerification: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState("");
  const [user, setUser] = useState<AuthUser | null>(null);
  const [authBootstrapping, setAuthBootstrapping] = useState(true);

  const applySession = useCallback((t: string, u: AuthUser) => {
    setCustomerSessionToken(t);
    setToken(t);
    setUser(u);
  }, []);

  const clearSession = useCallback(() => {
    clearStoredSessionToken();
    setToken("");
    setUser(null);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      const t = readSessionBearerToken();
      if (!t) {
        if (!cancelled) {
          setToken("");
          setUser(null);
          setAuthBootstrapping(false);
        }
        return;
      }
      try {
        const u = await authApi.authMe(t);
        if (!cancelled) {
          setToken(t);
          setUser(u);
        }
      } catch {
        if (!cancelled) {
          clearStoredSessionToken();
          setToken("");
          setUser(null);
        }
      } finally {
        if (!cancelled) setAuthBootstrapping(false);
      }
    };
    void run();
    return () => {
      cancelled = true;
    };
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const { token: t, user: u } = await authApi.authLogin(email, password);
    applySession(t, u);
    return u;
  }, [applySession]);

  const signUp = useCallback(
    async (email: string, password: string, displayName: string) => {
      const { token: t, user: u } = await authApi.authSignup(
        email,
        password,
        displayName,
      );
      applySession(t, u);
      return u;
    },
    [applySession],
  );

  const signOut = useCallback(async () => {
    const t = token;
    if (t) {
      try {
        await authApi.authLogout(t);
      } catch {
        /* still clear locally */
      }
    }
    clearSession();
  }, [token, clearSession]);

  const refreshUser = useCallback(async () => {
    const t = readSessionBearerToken();
    if (!t) {
      clearSession();
      return;
    }
    const u = await authApi.authMe(t);
    setToken(t);
    setUser(u);
  }, [clearSession]);

  const verifyEmail = useCallback(
    async (code: string) => {
      const t = readSessionBearerToken();
      if (!t) throw new Error("Not signed in");
      await authApi.authVerifyEmail(t, code);
      await refreshUser();
    },
    [refreshUser],
  );

  const resendVerification = useCallback(async () => {
    const t = readSessionBearerToken();
    if (!t) throw new Error("Not signed in");
    await authApi.authResendVerification(t);
  }, []);

  const emailVerified = Boolean(user?.emailVerified);

  const value = useMemo<AuthContextValue>(
    () => ({
      token,
      user,
      authBootstrapping,
      emailVerified,
      signIn,
      signUp,
      signOut,
      refreshUser,
      verifyEmail,
      resendVerification,
    }),
    [
      token,
      user,
      authBootstrapping,
      emailVerified,
      signIn,
      signUp,
      signOut,
      refreshUser,
      verifyEmail,
      resendVerification,
    ],
  );

  return (
    <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
