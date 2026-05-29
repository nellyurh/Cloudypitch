import React, { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth, formatApiErr } from "../lib/auth";
import { Brand } from "../components/Brand";
import api from "../lib/api";
import { Check, AlertCircle } from "lucide-react";

export const SignUp = () => {
  const { signup } = useAuth();
  const [params] = useSearchParams();
  const initialRef = (params.get("ref") || "").toUpperCase().trim();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [country, setCountry] = useState("NG");
  const [refCode, setRefCode] = useState(initialRef);
  const [refStatus, setRefStatus] = useState({ checking: false, valid: false, name: null, error: null });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const nav = useNavigate();

  // Live-validate referral code
  useEffect(() => {
    if (!refCode || refCode.length < 4) {
      setRefStatus({ checking: false, valid: false, name: null, error: null });
      return;
    }
    setRefStatus(s => ({ ...s, checking: true }));
    const t = setTimeout(async () => {
      try {
        const { data } = await api.post(`/referrals/validate/${refCode}`);
        setRefStatus({ checking: false, valid: true, name: data.referrer_name, error: null });
      } catch (_) {
        setRefStatus({ checking: false, valid: false, name: null, error: "Code not recognised" });
      }
    }, 400);
    return () => clearTimeout(t);
  }, [refCode]);

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      await signup({
        email, password, display_name: name, country_code: country,
        referral_code: refCode || undefined,
      });
      nav("/");
    } catch (e) {
      setErr(formatApiErr(e));
    }
    setBusy(false);
  };

  return (
    <div className="max-w-sm mx-auto mt-10 cp-surface p-6" data-testid="signup-page">
      <div className="flex justify-center mb-4"><Brand size={40}/></div>
      <h1 className="text-xl font-extrabold text-center">Join Cloudy Pitch</h1>
      <p className="text-xs text-center mt-1" style={{ color: "var(--cp-text-muted)" }}>
        Free starter pack: 5 Star cards on signup
      </p>
      <form onSubmit={submit} className="mt-5 space-y-3">
        <input required minLength={2} placeholder="Display name" value={name} onChange={(e)=>setName(e.target.value)} className="cp-input" data-testid="signup-name"/>
        <input type="email" required placeholder="you@email.com" value={email} onChange={(e)=>setEmail(e.target.value)} className="cp-input" data-testid="signup-email"/>
        <input type="password" required minLength={8} placeholder="Password (min 8 chars)" value={password} onChange={(e)=>setPassword(e.target.value)} className="cp-input" data-testid="signup-password"/>
        <select value={country} onChange={(e)=>setCountry(e.target.value)} className="cp-input" data-testid="signup-country">
          <option value="NG">🇳🇬 Nigeria</option><option value="GH">🇬🇭 Ghana</option><option value="ZA">🇿🇦 South Africa</option><option value="KE">🇰🇪 Kenya</option><option value="EG">🇪🇬 Egypt</option><option value="MA">🇲🇦 Morocco</option><option value="CI">🇨🇮 Côte d'Ivoire</option><option value="SN">🇸🇳 Senegal</option><option value="CM">🇨🇲 Cameroon</option><option value="US">🇺🇸 USA</option><option value="GB">🇬🇧 UK</option><option value="OT">🌍 Other</option>
        </select>
        <div>
          <input
            value={refCode}
            onChange={(e) => setRefCode(e.target.value.toUpperCase())}
            placeholder="Referral code (optional)"
            maxLength={12}
            className="cp-input"
            data-testid="signup-referral"
          />
          {refCode && refStatus.checking && (
            <div className="text-[10px] mt-1" style={{ color: "var(--cp-text-muted)" }}>Validating…</div>
          )}
          {refCode && refStatus.valid && (
            <div className="text-[11px] mt-1 inline-flex items-center gap-1 text-cp-lime" data-testid="referral-valid">
              <Check size={11}/> Invited by <strong>{refStatus.name}</strong>
            </div>
          )}
          {refCode && refStatus.error && !refStatus.checking && (
            <div className="text-[11px] mt-1 inline-flex items-center gap-1 text-amber-400" data-testid="referral-invalid">
              <AlertCircle size={11}/> {refStatus.error}
            </div>
          )}
        </div>
        {err && <div className="text-xs" style={{ color: "#FF3D52" }} data-testid="signup-error">{err}</div>}
        <button disabled={busy} className="cp-btn-primary w-full justify-center disabled:opacity-50" data-testid="signup-submit">
          {busy ? "Creating…" : "Create account"}
        </button>
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
