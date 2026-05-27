import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import api from "./api";

const AuthCtx = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const { data } = await api.get("/auth/me");
      setUser(data.user);
    } catch (_) {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const signin = async (email, password) => {
    const { data } = await api.post("/auth/signin", { email, password });
    setUser(data.user);
    return data.user;
  };
  const signup = async (payload) => {
    const { data } = await api.post("/auth/signup", payload);
    setUser(data.user);
    return data.user;
  };
  const signout = async () => {
    try { await api.post("/auth/signout"); } catch (_) {}
    setUser(null);
  };

  return (
    <AuthCtx.Provider value={{ user, loading, signin, signup, signout, refresh }}>
      {children}
    </AuthCtx.Provider>
  );
};

export const useAuth = () => useContext(AuthCtx);

export function formatApiErr(err) {
  const d = err?.response?.data?.detail;
  if (!d) return err?.message || "Something went wrong";
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x?.msg || JSON.stringify(x)).join(" ");
  return String(d);
}
