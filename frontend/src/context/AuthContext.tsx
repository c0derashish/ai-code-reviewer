import { createContext, useContext, useState } from "react";
import type { ReactNode } from "react";
import * as authService from "../services/authService";
import type { AuthResult } from "../services/authService";
import type { User } from "../types";

type AuthContextValue = {
  user: User | null;
  login: (email: string, password: string) => Promise<AuthResult>;
  register: (name: string, email: string, password: string) => Promise<AuthResult>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => authService.getStoredSession());

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

  function logout() {
    authService.logout();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}