import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import * as authService from "../services/authService";
import type { AuthResult, SimpleResult } from "../services/authService";
import type { User } from "../types";

type AuthContextValue = {
  user: User | null;
  loading: boolean; // true until the server has said who is signed in
  login: (email: string, password: string) => Promise<AuthResult>;
  register: (name: string, email: string, password: string) => Promise<AuthResult>;
  logout: () => Promise<void>;
  removeAccount: (password: string) => Promise<SimpleResult>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // ask the server once, when the app opens
  useEffect(() => {
    let cancelled = false;
    authService.getCurrentUser().then((found) => {
      if (!cancelled) {
        setUser(found);
        setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  async function login(email: string, password: string) {
    const result = await authService.login(email, password);
    if (result.ok) setUser(result.user);
    return result;
  }

  async function register(name: string, email: string, password: string) {
    const result = await authService.register(name, email, password);
    if (result.ok) setUser(result.user);
    return result;
  }

  async function logout() {
    await authService.logout();
    setUser(null);
  }

  async function removeAccount(password: string) {
    const result = await authService.deleteAccount(password);
    if (result.ok) setUser(null);
    return result;
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, removeAccount }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}