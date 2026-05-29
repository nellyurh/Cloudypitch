import React, { useEffect, useState } from "react";
import api from "../lib/api";
import { useAuth, formatApiErr } from "../lib/auth";
import { Wallet as WalletIcon, ShieldCheck, ShieldAlert, AlertTriangle, ArrowDownToLine, ArrowUpFromLine } from "lucide-react";
import AgeGateModal from "../components/AgeGateModal";

const tx_label = {
  deposit: { text: "Deposit", color: "text-cp-lime" },
  winning: { text: "Winnings", color: "text-cp-lime" },
  purchase: { text: "Card Purchase", color: "text-rose-400" },
  recharge: { text: "Card Recharge", color: "text-rose-400" },
  withdrawal: { text: "Withdrawal", color: "text-rose-400" },
  refund: { text: "Refund", color: "text-sky-400" },
};

export const WalletPage = () => {
  const { user } = useAuth();
  const [wallet, setWallet] = useState(null);
  const [txs, setTxs] = useState([]);
  const [compliance, setCompliance] = useState(null);
  const [amount, setAmount] = useState(500);  // $5.00 default deposit (stored as cents)
  const [daily, setDaily] = useState(500);    // $5.00 daily default
  const [monthly, setMonthly] = useState(2000); // $20.00 monthly default
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const fmtUsd = (cents) => `$${((cents || 0) / 100).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  const load = async () => {
    try {
      const [w, t, c] = await Promise.all([
        api.get("/wallet/me"),
        api.get("/wallet/transactions"),
        api.get("/compliance/me"),
      ]);
      setWallet(w.data.wallet);
      setTxs(t.data.transactions || []);
      setCompliance(c.data.profile);
      if (c.data.profile) {
        setDaily(c.data.profile.daily_cap_ngn || 500);
        setMonthly(c.data.profile.monthly_cap_ngn || 2000);
      }
    } catch (e) { setErr(formatApiErr(e)); }
  };

  useEffect(() => { if (user) load(); }, [user]);

  if (!user) return <div className="cp-surface p-6">Please sign in.</div>;
  if (!wallet) return <div className="cp-surface p-6 text-sm">Loading…</div>;

  const initPaystack = async () => {
    setErr(""); setMsg("");
    try {
      const callback_url = `${window.location.origin}/payment/callback`;
      const { data } = await api.post("/payments/paystack/initialize", {
        purpose: "wallet_deposit", amount_ngn: amount, callback_url,
      });
      window.location.href = data.authorization_url;
    } catch (e) { setErr(formatApiErr(e)); }
  };

  const directDeposit = async () => {
    // Test-mode shortcut — admin can self-credit (not for production)
    setErr(""); setMsg("");
    try {
      await api.post("/wallet/deposit", { amount_ngn: amount });
      setMsg(`${fmtUsd(amount)} credited (test mode)`);
      load();
    } catch (e) { setErr(formatApiErr(e)); }
  };

  const updateCaps = async () => {
    setErr(""); setMsg("");
    try {
      const { data } = await api.post("/compliance/caps", { daily_cap_ngn: daily, monthly_cap_ngn: monthly });
      setMsg(data.applied_immediately ? "Caps lowered immediately" : data.message);
      load();
    } catch (e) { setErr(formatApiErr(e)); }
  };

  const toggleExclude = async () => {
    if (!confirm("Self-exclude from all real-money features? This blocks deposits, purchases, and withdrawals.")) return;
    try {
      await api.post("/compliance/self-exclude", { excluded: !compliance.self_excluded });
      load();
    } catch (e) { setErr(formatApiErr(e)); }
  };

  return (
    <div data-testid="wallet-page" className="grid grid-cols-1 lg:grid-cols-[1fr_400px] gap-4">
      <AgeGateModal />

      <div>
        <div className="cp-surface p-5" data-testid="wallet-balance">
          <div className="flex items-center gap-3">
            <WalletIcon size={28} className="text-cp-lime"/>
            <div>
              <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Wallet Balance</div>
              <div className="text-3xl font-extrabold tabular-nums text-cp-lime">{fmtUsd(wallet.balance_ngn || 0)}</div>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3 mt-5 text-center">
            <div>
              <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Deposited</div>
              <div className="text-base font-bold tabular-nums">{fmtUsd(wallet.total_deposited || 0)}</div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Won</div>
              <div className="text-base font-bold text-cp-lime tabular-nums">{fmtUsd(wallet.total_won || 0)}</div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Spent</div>
              <div className="text-base font-bold tabular-nums">{fmtUsd(wallet.total_spent || 0)}</div>
            </div>
          </div>
        </div>

        <div className="cp-surface p-5 mt-3" data-testid="wallet-deposit">
          <h3 className="text-sm font-extrabold uppercase tracking-widest mb-3" style={{ color: "var(--cp-text-muted)" }}>Add Funds</h3>
          <div className="flex flex-wrap items-center gap-2">
            {[100, 500, 1000, 2000, 5000].map(v => (
              <button key={v} onClick={() => setAmount(v)} className={`cp-pill ${amount === v ? "bg-cp-lime text-cp-forest" : ""}`} data-testid={`amt-${v}`}>{fmtUsd(v)}</button>
            ))}
            <input type="number" value={amount} onChange={(e) => setAmount(Number(e.target.value))} className="cp-input w-32 ml-auto" data-testid="amt-input"/>
          </div>
          <div className="flex gap-2 mt-3">
            <button onClick={initPaystack} className="cp-btn-primary flex-1 inline-flex items-center justify-center gap-1" data-testid="deposit-paystack">
              <ArrowDownToLine size={14}/> Deposit
            </button>
            {user?.role === "admin" && (
              <button onClick={directDeposit} className="cp-btn-ghost" data-testid="deposit-test">Test-Credit</button>
            )}
          </div>
        </div>

        <div className="cp-surface mt-3 overflow-hidden">
          <div className="cp-card-header normal-case"><span className="font-bold">Recent Transactions</span></div>
          <ul className="divide-y" style={{ borderColor: "var(--cp-border)" }}>
            {txs.length === 0 && <li className="p-4 text-sm" style={{ color: "var(--cp-text-muted)" }}>No transactions yet.</li>}
            {txs.map(t => {
              const meta = tx_label[t.type] || { text: t.type, color: "" };
              const positive = (t.amount_ngn || 0) >= 0;
              return (
                <li key={t.id} className="px-3 py-2 flex items-center justify-between text-sm" data-testid={`tx-${t.id}`}>
                  <div>
                    <div className={`font-medium ${meta.color}`}>{meta.text}</div>
                    <div className="text-[10px]" style={{ color: "var(--cp-text-muted)" }}>{new Date(t.created_at).toLocaleString()}</div>
                  </div>
                  <span className={`font-bold tabular-nums ${positive ? "text-cp-lime" : "text-rose-400"}`}>
                    {positive ? "+" : ""}{fmtUsd(Math.abs(t.amount_ngn || 0))}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      </div>

      {/* Right rail: compliance */}
      <aside className="cp-surface p-5 h-fit" data-testid="compliance-panel">
        <div className="flex items-center gap-2 mb-3">
          {compliance?.age_verified ? <ShieldCheck size={18} className="text-cp-lime"/> : <ShieldAlert size={18} className="text-amber-400"/>}
          <h3 className="text-base font-extrabold">Responsible Play</h3>
        </div>
        {!compliance?.age_verified ? (
          <div className="text-sm mb-4 p-3 rounded" style={{ background: "var(--cp-surface-2)" }}>
            <AlertTriangle size={14} className="text-amber-400 inline mr-1"/>
            18+ verification required to deposit or play real-money features.
          </div>
        ) : (
          <div className="text-xs mb-4" style={{ color: "var(--cp-text-muted)" }}>
            Verified · DOB {compliance.date_of_birth}
          </div>
        )}

        <label className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Daily cap ($ in cents)</label>
        <input type="number" value={daily} onChange={(e) => setDaily(Number(e.target.value))} className="cp-input w-full mt-1" data-testid="caps-daily"/>
        <div className="text-[10px] mt-0.5" style={{ color: "var(--cp-text-muted)" }}>≈ {fmtUsd(daily)}</div>
        <label className="text-[10px] uppercase tracking-widest mt-3 block" style={{ color: "var(--cp-text-muted)" }}>Monthly cap ($ in cents)</label>
        <input type="number" value={monthly} onChange={(e) => setMonthly(Number(e.target.value))} className="cp-input w-full mt-1" data-testid="caps-monthly"/>
        <div className="text-[10px] mt-0.5" style={{ color: "var(--cp-text-muted)" }}>≈ {fmtUsd(monthly)}</div>
        <p className="text-[10px] mt-2" style={{ color: "var(--cp-text-muted)" }}>
          Lowering takes effect immediately. Raising takes effect after a 24-hour anti-impulse delay.
        </p>
        <button onClick={updateCaps} className="cp-btn-primary w-full mt-3" data-testid="caps-save">Save Caps</button>
        {compliance?.caps_pending && (
          <div className="text-[11px] mt-2 p-2 rounded" style={{ background: "rgba(245,158,11,0.1)", color: "#FBBF24" }}>
            Pending raise · effective {new Date(compliance.caps_pending_effective_at).toLocaleString()}
          </div>
        )}

        <hr className="my-4" style={{ borderColor: "var(--cp-border)" }}/>

        <button onClick={toggleExclude} className={`w-full ${compliance?.self_excluded ? "cp-btn-primary" : "cp-btn-ghost"} inline-flex items-center justify-center gap-1`} data-testid="self-exclude-toggle">
          <ArrowUpFromLine size={14}/>
          {compliance?.self_excluded ? "Lift Self-Exclusion" : "Self-Exclude"}
        </button>

        {err && <div className="text-sm text-rose-400 mt-3">{err}</div>}
        {msg && <div className="text-sm text-cp-lime mt-3">{msg}</div>}
      </aside>
    </div>
  );
};

export default WalletPage;
