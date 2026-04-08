import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

const API = process.env.EXPO_PUBLIC_BACKEND_URL;

interface User {
  id: string;
  email: string;
  name: string;
  role: string;
  subscription: { status: string; plan: string; expires_at: string | null };
  is_premium?: boolean;
  limits?: any;
  token?: string;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<{ success: boolean; error?: string }>;
  register: (email: string, password: string, name: string) => Promise<{ success: boolean; error?: string }>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  token: string | null;
}

const AuthContext = createContext<AuthContextType>({
  user: null, loading: true,
  login: async () => ({ success: false }),
  register: async () => ({ success: false }),
  logout: async () => {},
  refresh: async () => {},
  token: null,
});

export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState<string | null>(null);

  const getHeaders = useCallback(() => {
    const h: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) h['Authorization'] = `Bearer ${token}`;
    return h;
  }, [token]);

  const refresh = useCallback(async () => {
    try {
      if (!token) { setLoading(false); return; }
      const res = await fetch(`${API}/api/auth/me`, {
        headers: { 'Authorization': `Bearer ${token}` },
        credentials: 'include',
      });
      if (res.ok) {
        const data = await res.json();
        setUser(data);
      } else {
        setUser(null);
        setToken(null);
      }
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (token) {
      refresh();
    } else {
      setLoading(false);
    }
  }, [token]);

  const login = async (email: string, password: string) => {
    try {
      const res = await fetch(`${API}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
        credentials: 'include',
      });
      if (!res.ok) {
        const err = await res.json();
        const detail = err.detail;
        const msg = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((e: any) => e.msg || JSON.stringify(e)).join(' ') : 'Login failed';
        return { success: false, error: msg };
      }
      const data = await res.json();
      setToken(data.token);
      setUser(data);
      return { success: true };
    } catch (e: any) {
      return { success: false, error: e.message || 'Network error' };
    }
  };

  const register = async (email: string, password: string, name: string) => {
    try {
      const res = await fetch(`${API}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, name }),
        credentials: 'include',
      });
      if (!res.ok) {
        const err = await res.json();
        const detail = err.detail;
        const msg = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((e: any) => e.msg || JSON.stringify(e)).join(' ') : 'Registration failed';
        return { success: false, error: msg };
      }
      const data = await res.json();
      setToken(data.token);
      setUser(data);
      return { success: true };
    } catch (e: any) {
      return { success: false, error: e.message || 'Network error' };
    }
  };

  const logout = async () => {
    try {
      if (token) {
        await fetch(`${API}/api/auth/logout`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}` },
          credentials: 'include',
        });
      }
    } catch {}
    setUser(null);
    setToken(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, refresh, token }}>
      {children}
    </AuthContext.Provider>
  );
}
