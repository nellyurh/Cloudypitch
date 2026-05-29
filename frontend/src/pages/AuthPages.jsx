import React, { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import api from "../lib/api";
import { Brand } from "../components/Brand";
import { Mail, Check, AlertTriangle, Lock } from "lucide-react";

const Card = ({ children, testid }) => (
  <div className="max-w-sm mx-auto mt-10 cp-surface p-6" data-testid={testid}>
    <div className="flex justify-center mb-4"><Brand size={40}/></div>
    {children}
  </div>
);

const Notice = ({ kind, children }) => {
  const colour = kind === "error" ? "#FF3D52" : kind === "ok" ? "#A3E635" : "var(--cp-text-muted)";
  const Icon = kind === "error" ? AlertTriangle : kind === "ok" ? Check : Mail;
  return (
    <div className="text-xs mt-3 inline-flex items-start gap-1.5" style={{ color: colour }}>
      <Icon size={12} className="mt-0.5"/>
      <span>{children}</span>
    </div>
  );
};

export const ForgotPassword = () => {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [err, setErr] = useState("");
  const [devUrl, setDevUrl] = useState("");
  const submit = async (e) => {
    e.preventDefault(); setErr("");
    try {
      const { data } = await api.post("/auth-extras/reset/request", { email });
      setSent(true);
      if (data.dev_url) setDevUrl(data.dev_url);
    } catch (e) { setErr(e?.response?.data?.detail || "Request failed"); }
  };
  return (
    <Card testid="forgot-password-page">
      <h1 className="text-xl font-extrabold text-center">Reset your password</h1>
      <p className="text-xs text-center mt-1" style={{ color: "var(--cp-text-muted)" }}>We'll send a one-time link to your email</p>
      {!sent ? (
        <form onSubmit={submit} className="mt-5 space-y-3">
          <input type="email" required placeholder="you@email.com" value={email} onChange={(e) => setEmail(e.target.value)} className="cp-input" data-testid="forgot-email"/>
          {err && <Notice kind="error">{err}</Notice>}
          <button className="cp-btn-primary w-full justify-center" data-testid="forgot-submit">Send reset link</button>
        </form>
      ) : (
        <div className="mt-5 text-center">
          <Check size={28} className="mx-auto text-cp-lime"/>
          <p className="text-sm mt-3">If that email is registered you'll receive a link shortly.</p>
          {devUrl && (
            <div className="mt-3 text-[10px] p-2 rounded break-all" style={{ background: "var(--cp-surface-2)", color: "var(--cp-text-muted)" }}>
              <span className="text-cp-lime block mb-1">DEV mode:</span>
              <Link to={devUrl} className="underline" data-testid="forgot-dev-link">{devUrl}</Link>
            </div>
          )}
        </div>
      )}
      <div className="text-xs text-center mt-4" style={{ color: "var(--cp-text-muted)" }}>
        <Link to="/signin" className="text-cp-lime" data-testid="forgot-back">Back to sign in</Link>
      </div>
    </Card>
  );
};

export const ResetPassword = () => {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [err, setErr] = useState("");
  const [done, setDone] = useState(false);
  const nav = useNavigate();
  const submit = async (e) => {
    e.preventDefault(); setErr("");
    if (pw.length < 8) return setErr("Password must be at least 8 characters");
    if (pw !== pw2) return setErr("Passwords don't match");
    try {
      await api.post("/auth-extras/reset/confirm", { token, new_password: pw });
      setDone(true);
      setTimeout(() => nav("/signin"), 1500);
    } catch (e) { setErr(e?.response?.data?.detail || "Reset failed"); }
  };
  return (
    <Card testid="reset-password-page">
      <h1 className="text-xl font-extrabold text-center">Choose a new password</h1>
      {!token && <Notice kind="error">Missing token — request a new reset link</Notice>}
      {done ? (
        <div className="mt-5 text-center">
          <Check size={28} className="mx-auto text-cp-lime"/>
          <p className="text-sm mt-3">Password updated. Redirecting…</p>
        </div>
      ) : (
        <form onSubmit={submit} className="mt-5 space-y-3">
          <div className="relative">
            <Lock size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-cp-muted"/>
            <input type="password" required placeholder="New password" value={pw} onChange={(e) => setPw(e.target.value)} className="cp-input pl-8" data-testid="reset-pw1"/>
          </div>
          <div className="relative">
            <Lock size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-cp-muted"/>
            <input type="password" required placeholder="Confirm" value={pw2} onChange={(e) => setPw2(e.target.value)} className="cp-input pl-8" data-testid="reset-pw2"/>
          </div>
          {err && <Notice kind="error">{err}</Notice>}
          <button disabled={!token} className="cp-btn-primary w-full justify-center disabled:opacity-50" data-testid="reset-submit">Update password</button>
        </form>
      )}
    </Card>
  );
};

export const VerifyEmail = () => {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [phase, setPhase] = useState(token ? "verifying" : "needs-token");
  const [msg, setMsg] = useState("");
  useEffect(() => {
    if (!token) return;
    (async () => {
      try {
        await api.post("/auth-extras/verify/confirm", { token });
        setPhase("ok");
        setMsg("Email verified. Welcome aboard!");
      } catch (e) {
        setPhase("error");
        setMsg(e?.response?.data?.detail || "Verification failed");
      }
    })();
  }, [token]);
  return (
    <Card testid="verify-email-page">
      <h1 className="text-xl font-extrabold text-center">Verify your email</h1>
      <div className="mt-5 text-center">
        {phase === "verifying" && <p className="text-sm" style={{ color: "var(--cp-text-muted)" }}>Verifying…</p>}
        {phase === "ok" && (
          <>
            <Check size={28} className="mx-auto text-cp-lime"/>
            <p className="text-sm mt-3 text-cp-lime">{msg}</p>
            <Link to="/" className="cp-btn-primary mt-4 inline-block" data-testid="verify-home">Go home</Link>
          </>
        )}
        {phase === "error" && (
          <>
            <AlertTriangle size={28} className="mx-auto" style={{ color: "#FF3D52" }}/>
            <p className="text-sm mt-3" style={{ color: "#FF3D52" }}>{msg}</p>
          </>
        )}
        {phase === "needs-token" && <p className="text-sm" style={{ color: "var(--cp-text-muted)" }}>Open the verification link from your email to continue.</p>}
      </div>
    </Card>
  );
};
