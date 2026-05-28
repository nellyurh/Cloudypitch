import React, { useEffect, useState } from "react";
import api from "../lib/api";
import { ShieldAlert } from "lucide-react";

/**
 * AgeGateModal — blocks real-money flows until the user provides DOB ≥ 18.
 * Usage: <AgeGateModal onVerified={() => ...} />
 * Renders nothing if user is already verified.
 */
export const AgeGateModal = ({ onVerified, open: openProp = null }) => {
  const [open, setOpen] = useState(false);
  const [dob, setDob] = useState("");
  const [agree, setAgree] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (openProp != null) {
      setOpen(openProp);
      return;
    }
    (async () => {
      try {
        const { data } = await api.get("/compliance/me");
        if (!data.profile.age_verified) setOpen(true);
      } catch (_) {}
    })();
  }, [openProp]);

  if (!open) return null;
  const submit = async () => {
    setErr("");
    setBusy(true);
    try {
      const { data } = await api.post("/compliance/age-gate", { date_of_birth: dob, confirm_18_plus: agree });
      if (data.ok) {
        setOpen(false);
        onVerified?.();
      }
    } catch (e) {
      setErr(e?.response?.data?.detail || "Verification failed");
    }
    setBusy(false);
  };

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.6)" }} data-testid="age-gate-modal">
      <div className="cp-surface max-w-md w-full p-6">
        <div className="flex items-center gap-2 mb-3">
          <ShieldAlert size={20} className="text-cp-lime" />
          <h2 className="text-lg font-extrabold tracking-tight">18+ Verification</h2>
        </div>
        <p className="text-sm mb-4" style={{ color: "var(--cp-text-muted)" }}>
          Cloudy Pitch is a skill-based prediction platform with real-money pools.
          By Nigerian law you must be <span className="text-cp-lime font-bold">18 or older</span> to play.
        </p>
        <label className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Date of Birth</label>
        <input
          type="date" value={dob} onChange={(e) => setDob(e.target.value)}
          className="cp-input w-full mt-1" data-testid="age-gate-dob"
        />
        <label className="mt-4 flex items-start gap-2 text-sm">
          <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} data-testid="age-gate-confirm"/>
          <span>I confirm I am 18+ and accept Cloudy Pitch's responsible-play terms.</span>
        </label>
        {err && <div className="mt-3 text-sm text-rose-400">{err}</div>}
        <button
          onClick={submit}
          disabled={!dob || !agree || busy}
          className="cp-btn-primary w-full mt-4 disabled:opacity-40"
          data-testid="age-gate-submit"
        >
          {busy ? "Verifying…" : "Verify & Continue"}
        </button>
        <button onClick={() => setOpen(false)} className="w-full mt-2 text-xs" style={{ color: "var(--cp-text-muted)" }} data-testid="age-gate-cancel">
          Maybe later (limits real-money features)
        </button>
      </div>
    </div>
  );
};

export default AgeGateModal;
