import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { api, getToken, setToken as persistToken } from "./api";

interface AuthContextValue {
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(() => getToken());

  const login = useCallback(async (username: string, password: string) => {
    const { token } = await api.login(username, password);
    persistToken(token);
    setTokenState(token);
  }, []);

  const register = useCallback(async (username: string, password: string) => {
    const { token } = await api.register(username, password);
    persistToken(token);
    setTokenState(token);
  }, []);

  const logout = useCallback(() => {
    persistToken(null);
    setTokenState(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ isAuthenticated: token !== null, login, register, logout }),
    [token, login, register, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
