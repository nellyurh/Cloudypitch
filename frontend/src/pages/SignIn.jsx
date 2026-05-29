import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth, formatApiErr } from "../lib/auth";
import { Brand } from "../components/Brand";

export const SignIn = () => {
  const { signin } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const nav = useNavigate();
  const submit = async (e) => {
    e.preventDefault(); setErr(""); setBusy(true);
    try { await signin(email, password); nav("/"); } catch (e) { setErr(formatApiErr(e)); }
    setBusy(false);
  };
  return (
    <div className="max-w-sm mx-auto mt-10 cp-surface p-6" data-testid="signin-page">
      <div className="flex justify-center mb-4"><Brand size={40}/></div>
      <h1 className="text-xl font-extrabold text-center">Welcome back</h1>
      <p className="text-xs text-center mt-1" style={{ color: "var(--cp-text-muted)" }}>Sign in to predict, play fantasy, and win prizes</p>
      <form onSubmit={submit} className="mt-5 space-y-3">
        <input type="email" required placeholder="you@email.com" value={email} onChange={(e)=>setEmail(e.target.value)} className="cp-input" data-testid="signin-email"/>
        <input type="password" required placeholder="Password" value={password} onChange={(e)=>setPassword(e.target.value)} className="cp-input" data-testid="signin-password"/>
        {err && <div className="text-xs" style={{ color: "#FF3D52" }} data-testid="signin-error">{err}</div>}
        <button disabled={busy} className="cp-btn-primary w-full justify-center disabled:opacity-50" data-testid="signin-submit">{busy ? "Signing in…" : "Sign in"}</button>
      </form>
      <div className="text-xs text-center mt-4" style={{ color: "var(--cp-text-muted)" }}>
        <Link to="/forgot-password" className="text-cp-lime" data-testid="signin-forgot">Forgot password?</Link>
      </div>
      <div className="text-xs text-center mt-2" style={{ color: "var(--cp-text-muted)" }}>
        No account? <Link to="/signup" className="text-cp-lime" data-testid="signin-to-signup">Sign up free</Link>
      </div>
    </div>
  );
};

export default SignIn;
