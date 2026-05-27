import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth, formatApiErr } from "../lib/auth";
import { Brand } from "../components/Brand";

export const SignUp = () => {
  const { signup } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [country, setCountry] = useState("NG");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const nav = useNavigate();
  const submit = async (e) => {
    e.preventDefault(); setErr(""); setBusy(true);
    try { await signup({ email, password, display_name: name, country_code: country }); nav("/"); } catch (e) { setErr(formatApiErr(e)); }
    setBusy(false);
  };
  return (
    <div className="max-w-sm mx-auto mt-10 cp-surface p-6" data-testid="signup-page">
      <div className="flex justify-center mb-4"><Brand size={40}/></div>
      <h1 className="text-xl font-extrabold text-center">Join Cloudy Pitch</h1>
      <p className="text-xs text-center mt-1" style={{ color: "var(--cp-text-muted)" }}>Free starter pack: 5 Star cards on signup</p>
      <form onSubmit={submit} className="mt-5 space-y-3">
        <input required minLength={2} placeholder="Display name" value={name} onChange={(e)=>setName(e.target.value)} className="cp-input" data-testid="signup-name"/>
        <input type="email" required placeholder="you@email.com" value={email} onChange={(e)=>setEmail(e.target.value)} className="cp-input" data-testid="signup-email"/>
        <input type="password" required minLength={8} placeholder="Password (min 8 chars)" value={password} onChange={(e)=>setPassword(e.target.value)} className="cp-input" data-testid="signup-password"/>
        <select value={country} onChange={(e)=>setCountry(e.target.value)} className="cp-input" data-testid="signup-country">
          <option value="NG">🇳🇬 Nigeria</option><option value="GH">🇬🇭 Ghana</option><option value="ZA">🇿🇦 South Africa</option><option value="KE">🇰🇪 Kenya</option><option value="EG">🇪🇬 Egypt</option><option value="MA">🇲🇦 Morocco</option><option value="CI">🇨🇮 Côte d'Ivoire</option><option value="SN">🇸🇳 Senegal</option><option value="CM">🇨🇲 Cameroon</option><option value="OT">🌍 Other</option>
        </select>
        {err && <div className="text-xs" style={{ color: "#FF3D52" }} data-testid="signup-error">{err}</div>}
        <button disabled={busy} className="cp-btn-primary w-full justify-center disabled:opacity-50" data-testid="signup-submit">{busy ? "Creating…" : "Create account"}</button>
      </form>
      <div className="text-xs text-center mt-4" style={{ color: "var(--cp-text-muted)" }}>
        Have an account? <Link to="/signin" className="text-cp-lime" data-testid="signup-to-signin">Sign in</Link>
      </div>
      <div className="text-[10px] text-center mt-3" style={{ color: "var(--cp-text-muted)" }}>
        18+ required for real-money features. Self-imposed spending caps available.
      </div>
    </div>
  );
};

export default SignUp;
