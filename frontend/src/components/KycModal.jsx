import React, { useEffect, useState } from "react";
import api from "../lib/api";
import { ShieldCheck, X, Lock, AlertTriangle, Check } from "lucide-react";

/**
 * KycModal — collects bank account + DOB for prize-pool USD withdrawals.
 * Submits to /api/auth-extras/kyc/submit with status='pending'.
 */
export const KycModal = ({ onClose, onSubmitted }) => {
  const [me, setMe] = useState(null);
  const [form, setForm] = useState({ full_name: "", date_of_birth: "", bank_name: "", account_number: "", bvn: "" });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/auth-extras/kyc/me").then(({ data }) => setMe(data.kyc)).catch(() => {});
  }, []);

  const submit = async (e) => {
    e.preventDefault(); setErr(""); setBusy(true);
    try {
      const payload = { ...form };
      if (!payload.bvn) delete payload.bvn;
      await api.post("/auth-extras/kyc/submit", payload);
      onSubmitted?.();
      onClose?.();
    } catch (e) { setErr(e?.response?.data?.detail || "Submit failed"); }
    setBusy(false);
  };

  return (
    <div className="fixed inset-0 z-[150] flex items-end md:items-center justify-center p-3" style={{ background: "rgba(0,0,0,0.65)" }} data-testid="kyc-modal">
      <div className="cp-surface w-full max-w-md max-h-[90vh] overflow-hidden flex flex-col">
        <div className="px-4 py-3 flex items-center justify-between border-b" style={{ borderColor: "var(--cp-border)" }}>
          <div className="flex items-center gap-2">
            <ShieldCheck size={16} className="text-cp-lime"/>
            <h2 className="text-base font-extrabold">Verify Bank Account</h2>
          </div>
          <button onClick={onClose} className="p-1 hover:bg-white/5 rounded" data-testid="kyc-close"><X size={16}/></button>
        </div>

        <div className="overflow-y-auto p-4">
          {me?.status === "approved" && (
            <div className="text-sm p-3 rounded mb-3 inline-flex items-center gap-2" style={{ background: "rgba(163,230,53,0.1)", color: "#A3E635" }}>
              <Check size={14}/> Approved · {me.bank_name} · {me.account_number_masked}
            </div>
          )}
          {me?.status === "pending" && (
            <div className="text-sm p-3 rounded mb-3 inline-flex items-center gap-2" style={{ background: "rgba(245,158,11,0.1)", color: "#FBBF24" }}>
              <Lock size={14}/> Submitted · awaiting admin review
            </div>
          )}
          {me?.status === "rejected" && (
            <div className="text-sm p-3 rounded mb-3 inline-flex items-center gap-2" style={{ background: "rgba(255,61,82,0.1)", color: "#FF3D52" }}>
              <AlertTriangle size={14}/> Rejected. {me.review_notes || "Resubmit below."}
            </div>
          )}

          <p className="text-[11px] mb-3" style={{ color: "var(--cp-text-muted)" }}>
            Required for prize-pool cash withdrawals. We never share your details. Encrypted at rest.
          </p>

          <form onSubmit={submit} className="space-y-2">
            <input required placeholder="Legal full name" value={form.full_name} onChange={(e) => setForm(f => ({ ...f, full_name: e.target.value }))} className="cp-input" data-testid="kyc-name"/>
            <label className="text-[10px] uppercase tracking-widest mt-1 block" style={{ color: "var(--cp-text-muted)" }}>Date of birth</label>
            <input type="date" required value={form.date_of_birth} onChange={(e) => setForm(f => ({ ...f, date_of_birth: e.target.value }))} className="cp-input" data-testid="kyc-dob"/>
            <input required placeholder="Bank name (e.g. GTBank)" value={form.bank_name} onChange={(e) => setForm(f => ({ ...f, bank_name: e.target.value }))} className="cp-input" data-testid="kyc-bank"/>
            <input required placeholder="Account number" value={form.account_number} onChange={(e) => setForm(f => ({ ...f, account_number: e.target.value }))} className="cp-input" data-testid="kyc-acct"/>
            <input placeholder="BVN (optional · NG)" value={form.bvn} onChange={(e) => setForm(f => ({ ...f, bvn: e.target.value }))} className="cp-input" data-testid="kyc-bvn"/>
            {err && <div className="text-xs" style={{ color: "#FF3D52" }}><AlertTriangle size={12} className="inline mr-1"/>{err}</div>}
            <button disabled={busy} className="cp-btn-primary w-full justify-center disabled:opacity-50" data-testid="kyc-submit">
              {busy ? "Submitting…" : (me?.status === "rejected" ? "Resubmit" : "Submit for review")}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default KycModal;
