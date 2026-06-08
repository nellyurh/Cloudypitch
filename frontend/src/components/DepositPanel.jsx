import React, { useEffect, useState } from "react";
import api from "../lib/api";
import { Landmark, Bitcoin, Loader2, Copy, CheckCircle2, ExternalLink, AlertTriangle } from "lucide-react";

/**
 * DepositPanel — two-tab deposit flow.
 *  • NGN tab → PocketFi dynamic virtual account
 *  • Crypto tab → Trybit hosted-invoice checkout (USDT/BTC/ETH/etc.)
 *
 * Each provider exposes a `/config` endpoint that returns `{configured: bool}`
 * so we can disable the tab cleanly until the admin pastes API keys.
 */
const DepositPanel = ({ user, onReload, onErr, onMsg }) => {
  const [tab, setTab] = useState("ngn"); // 'ngn' | 'crypto'
  const [pfConfig, setPfConfig] = useState(null);
  const [tbConfig, setTbConfig] = useState(null);

  // NGN form state
  const [ngnAmount, setNgnAmount] = useState(5000);
  const [bank, setBank] = useState("kuda");
  const [firstName, setFirstName] = useState(user?.first_name || (user?.display_name || "").split(" ")[0] || "");
  const [lastName, setLastName] = useState(user?.last_name || (user?.display_name || "").split(" ").slice(1).join(" ") || "");
  const [phone, setPhone] = useState(user?.phone || "");
  const [email] = useState(user?.email || "");
  const [nin, setNin] = useState("");
  const [bvn, setBvn] = useState("");
  const [ngnDeposit, setNgnDeposit] = useState(null); // { banks, deposit_id, amount_ngn }
  const [ngnBusy, setNgnBusy] = useState(false);

  // Crypto form state
  const [usdAmount, setUsdAmount] = useState(20);
  const [cryptoBusy, setCryptoBusy] = useState(false);
  const [activeInvoice, setActiveInvoice] = useState(null); // { pay_url, invoice_uuid }

  useEffect(() => {
    (async () => {
      try {
        const [pf, tb] = await Promise.all([
          api.get("/payments/pocketfi/config"),
          api.get("/payments/trybit/config"),
        ]);
        setPfConfig(pf.data);
        setTbConfig(tb.data);
      } catch (_e) { /* ignore — providers will show as disabled */ }
    })();
  }, []);

  const submitNgn = async (e) => {
    e?.preventDefault?.();
    if (!firstName || !lastName || !phone || !email) {
      onErr("Please fill first name, last name, phone and email.");
      return;
    }
    if (bank === "palmpay" && !nin && !bvn) {
      onErr("PalmPay requires KYC: enter your NIN or BVN.");
      return;
    }
    setNgnBusy(true); onErr(""); onMsg("");
    try {
      const { data } = await api.post("/payments/pocketfi/dynamic-account", {
        amount_ngn: ngnAmount, bank,
        first_name: firstName, last_name: lastName, phone, email,
        nin: nin || undefined, bvn: bvn || undefined,
      });
      setNgnDeposit(data);
      // poll for completion every 6 s, up to 5 minutes
      pollNgn(data.deposit_id, 50);
    } catch (e2) {
      onErr(e2?.response?.data?.detail || e2.message);
    }
    setNgnBusy(false);
  };

  const pollNgn = async (depositId, attemptsLeft) => {
    if (attemptsLeft <= 0) return;
    try {
      const { data } = await api.get(`/payments/pocketfi/deposit/${depositId}`);
      if (data?.deposit?.status === "credited") {
        onMsg(`✓ ${formatNgn(data.deposit.credited_amount_ngn)} credited to your wallet.`);
        setNgnDeposit(null);
        onReload?.();
        return;
      }
    } catch (_e) { /* keep polling */ }
    setTimeout(() => pollNgn(depositId, attemptsLeft - 1), 6000);
  };

  const submitCrypto = async (e) => {
    e?.preventDefault?.();
    setCryptoBusy(true); onErr(""); onMsg("");
    try {
      const { data } = await api.post("/payments/trybit/invoice", {
        amount_usd: Number(usdAmount),
        email: email || undefined,
      });
      setActiveInvoice(data);
      // Open the hosted checkout in a new tab so the user can pay
      try { window.open(data.pay_url, "_blank", "noopener"); } catch (_e) { /* user can click the link */ }
      pollCrypto(data.invoice_uuid, 60);
    } catch (e2) {
      onErr(e2?.response?.data?.detail || e2.message);
    }
    setCryptoBusy(false);
  };

  const pollCrypto = async (uuid, attemptsLeft) => {
    if (attemptsLeft <= 0) return;
    try {
      const { data } = await api.get(`/payments/trybit/invoice/${uuid}`);
      if (data?.invoice?.status === "paid") {
        onMsg(`✓ Crypto deposit confirmed: $${data.invoice.credited_amount_usd?.toFixed(2)} (≈ ${formatNgn(data.invoice.credited_amount_ngn)})`);
        setActiveInvoice(null);
        onReload?.();
        return;
      }
    } catch (_e) { /* keep polling */ }
    setTimeout(() => pollCrypto(uuid, attemptsLeft - 1), 10000);
  };

  return (
    <div data-testid="deposit-panel">
      <div className="flex items-center gap-1 mb-3 p-1 rounded" style={{ background: "var(--cp-surface-2)", border: "1px solid var(--cp-border)" }}>
        <TabButton active={tab === "ngn"} onClick={() => setTab("ngn")} icon={<Landmark size={14}/>} label="Nigerian Bank Transfer" testId="tab-ngn"/>
        <TabButton active={tab === "crypto"} onClick={() => setTab("crypto")} icon={<Bitcoin size={14}/>} label="Crypto (USDT / BTC / ETH …)" testId="tab-crypto"/>
      </div>

      {tab === "ngn" && (
        <div data-testid="pane-ngn">
          {pfConfig && !pfConfig.configured && (
            <NotConfigured label="Bank transfer (PocketFi)" envVars={["POCKETFI_SECRET_KEY", "POCKETFI_BUSINESS_ID"]}/>
          )}
          {!ngnDeposit && pfConfig?.configured && (
            <form onSubmit={submitNgn} className="space-y-3" data-testid="ngn-form">
              <AmountPills value={ngnAmount} onChange={setNgnAmount} pills={[1000, 5000, 10000, 25000, 50000]} suffix="₦" testIdPrefix="ngn"/>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                <input className="cp-input" placeholder="First name *" value={firstName} onChange={e => setFirstName(e.target.value)} data-testid="ngn-firstname"/>
                <input className="cp-input" placeholder="Last name *" value={lastName} onChange={e => setLastName(e.target.value)} data-testid="ngn-lastname"/>
                <input className="cp-input" placeholder="Phone *" value={phone} onChange={e => setPhone(e.target.value)} data-testid="ngn-phone"/>
                <select className="cp-input" value={bank} onChange={e => setBank(e.target.value)} data-testid="ngn-bank">
                  {(pfConfig?.banks || ["kuda", "9psb", "paga", "palmpay", "saveheaven"]).map(b => <option key={b} value={b}>{b}</option>)}
                </select>
                {bank === "palmpay" && (
                  <>
                    <input className="cp-input" placeholder="NIN (11 digits)" value={nin} onChange={e => setNin(e.target.value)} maxLength={11} data-testid="ngn-nin"/>
                    <input className="cp-input" placeholder="BVN (11 digits)" value={bvn} onChange={e => setBvn(e.target.value)} maxLength={11} data-testid="ngn-bvn"/>
                  </>
                )}
              </div>
              <button type="submit" disabled={ngnBusy} className="cp-btn-primary inline-flex items-center gap-2 disabled:opacity-50" data-testid="ngn-submit">
                {ngnBusy ? <Loader2 size={14} className="animate-spin"/> : <Landmark size={14}/>}
                Generate bank account
              </button>
            </form>
          )}
          {ngnDeposit && <NgnInstructions deposit={ngnDeposit} onCancel={() => setNgnDeposit(null)}/>}
        </div>
      )}

      {tab === "crypto" && (
        <div data-testid="pane-crypto">
          {tbConfig && !tbConfig.configured && (
            <NotConfigured label="Crypto (Trybit)" envVars={["TRYBIT_API_KEY", "TRYBIT_SHOP_ID", "TRYBIT_SECRET_KEY"]}/>
          )}
          {!activeInvoice && tbConfig?.configured && (
            <form onSubmit={submitCrypto} className="space-y-3" data-testid="crypto-form">
              <AmountPills value={usdAmount} onChange={setUsdAmount} pills={[10, 25, 50, 100, 250]} suffix="$" testIdPrefix="crypto"/>
              <div className="text-[11px]" style={{ color: "var(--cp-text-muted)" }}>
                You&apos;ll be redirected to <b>pay.trybit.com</b> to complete the payment in your preferred coin/network. Funds settle in NGN at the current rate.
              </div>
              <button type="submit" disabled={cryptoBusy} className="cp-btn-primary inline-flex items-center gap-2 disabled:opacity-50" data-testid="crypto-submit">
                {cryptoBusy ? <Loader2 size={14} className="animate-spin"/> : <Bitcoin size={14}/>}
                Generate crypto invoice
              </button>
            </form>
          )}
          {activeInvoice && <CryptoInstructions invoice={activeInvoice} onCancel={() => setActiveInvoice(null)}/>}
        </div>
      )}
    </div>
  );
};

const TabButton = ({ active, onClick, icon, label, testId }) => (
  <button
    onClick={onClick}
    className="flex-1 px-3 py-2 text-xs font-extrabold rounded inline-flex items-center justify-center gap-1.5 transition"
    style={{
      background: active ? "var(--cp-lime)" : "transparent",
      color: active ? "var(--cp-forest)" : "var(--cp-text-muted)",
    }}
    data-testid={testId}
  >
    {icon}
    <span className="hidden sm:inline">{label}</span>
    <span className="sm:hidden">{label.split(" ")[0]}</span>
  </button>
);

const AmountPills = ({ value, onChange, pills, suffix, testIdPrefix }) => (
  <div className="flex flex-wrap items-center gap-2">
    {pills.map(v => (
      <button type="button" key={v} onClick={() => onChange(v)}
        className={`cp-pill ${value === v ? "bg-cp-lime text-cp-forest" : ""}`} data-testid={`${testIdPrefix}-pill-${v}`}>
        {suffix === "$" ? `$${v}` : `${suffix}${v.toLocaleString()}`}
      </button>
    ))}
    <input type="number" value={value} onChange={e => onChange(Number(e.target.value))} className="cp-input w-28 ml-auto" data-testid={`${testIdPrefix}-amt`}/>
  </div>
);

const NotConfigured = ({ label, envVars }) => (
  <div className="rounded-lg p-3 flex items-start gap-2" style={{ background: "rgba(251, 191, 36, 0.1)", border: "1px solid rgba(251, 191, 36, 0.3)" }} data-testid="provider-not-configured">
    <AlertTriangle size={14} className="text-amber-400 mt-0.5"/>
    <div className="text-[11px] flex-1">
      <b>{label}</b> isn&apos;t live yet. Admin must add the API credentials to <code>/app/backend/.env</code>:
      <code className="block mt-1 text-[10px] opacity-80">{envVars.join(" · ")}</code>
    </div>
  </div>
);

const formatNgn = (n) => `₦${Number(n || 0).toLocaleString()}`;

const NgnInstructions = ({ deposit, onCancel }) => {
  const [copied, setCopied] = useState(null);
  const copy = (val, key) => {
    try { navigator.clipboard.writeText(val); setCopied(key); setTimeout(() => setCopied(null), 1500); } catch (_e) { /* ignore */ }
  };
  return (
    <div className="rounded-lg p-4 space-y-3" style={{ background: "rgba(163, 230, 53, 0.07)", border: "1px solid rgba(163, 230, 53, 0.25)" }} data-testid="ngn-instructions">
      <div className="text-sm font-bold">Send <span className="text-cp-lime">{formatNgn(deposit.amount_ngn)}</span> to the account below to top up your wallet.</div>
      {deposit.banks?.map((b, i) => (
        <div key={i} className="rounded p-3 grid grid-cols-3 gap-2 items-center" style={{ background: "var(--cp-surface)", border: "1px solid var(--cp-border)" }} data-testid={`ngn-bank-${i}`}>
          <div>
            <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Bank</div>
            <div className="text-xs font-bold capitalize">{b.bankName}</div>
          </div>
          <div className="col-span-1">
            <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Account number</div>
            <div className="text-base font-extrabold tabular-nums">{b.accountNumber}</div>
          </div>
          <div className="col-span-1 flex items-center gap-1">
            <div className="flex-1">
              <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Account name</div>
              <div className="text-xs font-bold truncate">{b.accountName}</div>
            </div>
            <button onClick={() => copy(b.accountNumber, i)} className="cp-btn-ghost !p-2" title="Copy account number" data-testid={`ngn-copy-${i}`}>
              {copied === i ? <CheckCircle2 size={14} className="text-cp-lime"/> : <Copy size={14}/>}
            </button>
          </div>
        </div>
      ))}
      <div className="text-[11px] flex items-center gap-1.5" style={{ color: "var(--cp-text-muted)" }}>
        <Loader2 size={12} className="animate-spin"/> Waiting for transfer · your wallet credits automatically once PocketFi confirms.
      </div>
      <button onClick={onCancel} className="cp-btn-ghost text-xs" data-testid="ngn-back">Use a different account</button>
    </div>
  );
};

const CryptoInstructions = ({ invoice, onCancel }) => (
  <div className="rounded-lg p-4 space-y-3" style={{ background: "rgba(125, 211, 252, 0.07)", border: "1px solid rgba(125, 211, 252, 0.25)" }} data-testid="crypto-instructions">
    <div className="text-sm font-bold">Invoice created for <span className="text-cp-lime">${invoice.amount_usd}</span></div>
    <a href={invoice.pay_url} target="_blank" rel="noopener noreferrer" className="cp-btn-primary inline-flex items-center gap-2" data-testid="crypto-pay-link">
      <ExternalLink size={14}/> Open Trybit checkout
    </a>
    <div className="text-[11px] flex items-center gap-1.5" style={{ color: "var(--cp-text-muted)" }}>
      <Loader2 size={12} className="animate-spin"/> Waiting for payment confirmation on the blockchain. We&apos;ll credit your wallet automatically.
    </div>
    <button onClick={onCancel} className="cp-btn-ghost text-xs" data-testid="crypto-back">Start over</button>
  </div>
);

export default DepositPanel;
