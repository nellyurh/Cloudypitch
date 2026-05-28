import React, { useEffect, useState } from "react";
import api from "../lib/api";
import { useAuth, formatApiErr } from "../lib/auth";
import { Link } from "react-router-dom";
import { Crown, Check, X, ShieldCheck, AlertTriangle } from "lucide-react";

const PREMIUM_PRICE_NGN = 2000;
const PREMIUM_FEATURES = [
  { name: "Zero ads", desc: "No banners, interstitials, or sponsor cards anywhere", on: ["premium"], off: ["free"] },
  { name: "Priority match polling", desc: "Live scores update at 5s rate instead of 15s for free", on: ["premium"], off: ["free"] },
  { name: "5 free card-uses per week", desc: "Auto-credited every Monday — no purchase required", on: ["premium"], off: ["free"] },
  { name: "Exclusive Premium leaderboard", desc: "Compete only against other Premium members in side pools", on: ["premium"], off: ["free"] },
  { name: "Early predictions window", desc: "Submit picks 24h before normal cutoff", on: ["premium"], off: ["free"] },
  { name: "Live scores", desc: "All sports, all leagues", on: ["free", "premium"] },
  { name: "Predictions & Fantasy", desc: "Full access to make picks and build squads", on: ["free", "premium"] },
  { name: "Legend Cards", desc: "Buy and apply boost cards", on: ["free", "premium"] },
];

export const PremiumPage = () => {
  const { user, refresh } = useAuth();
  const [paystackConfigured, setPaystackConfigured] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/payments/paystack/config");
        setPaystackConfigured(data.configured);
      } catch (_) {}
    })();
  }, []);

  const subscribe = async () => {
    if (!user) { window.location.href = "/signin"; return; }
    setBusy(true); setErr("");
    try {
      // Compliance check first — premium subscribe is a real-money transaction
      const check = await api.get(`/compliance/can-spend?amount_ngn=${PREMIUM_PRICE_NGN}`);
      if (!check.data.ok) {
        setErr(check.data.reason || "Cannot proceed");
        setBusy(false);
        return;
      }
      const callback_url = `${window.location.origin}/payment/callback`;
      const { data } = await api.post("/payments/paystack/initialize", {
        purpose: "premium_sub",
        amount_ngn: PREMIUM_PRICE_NGN,
        callback_url,
      });
      window.location.href = data.authorization_url;
    } catch (e) {
      setErr(formatApiErr(e));
      setBusy(false);
    }
  };

  const isPremium = user?.is_premium;
  const premiumUntil = user?.premium_until;

  return (
    <div className="max-w-3xl mx-auto" data-testid="premium-page">
      <div
        className="relative overflow-hidden rounded-xl"
        style={{ background: "linear-gradient(135deg, #064E3B 0%, #1A1F26 100%)" }}
      >
        <div className="px-6 md:px-10 py-10 md:py-14 text-white">
          <div className="inline-flex items-center gap-2 cp-pill" style={{ background: "rgba(163,230,53,0.2)", color: "#A3E635" }}>
            <Crown size={12}/> CLOUDY PITCH PREMIUM
          </div>
          <h1 className="text-3xl md:text-5xl font-extrabold mt-3 tracking-tight">
            Ad-free. Faster. <span className="text-cp-lime">Pro.</span>
          </h1>
          <p className="text-sm md:text-base mt-3 max-w-lg" style={{ color: "rgba(255,255,255,0.85)" }}>
            Get the smoothest Cloudy Pitch experience — zero ads, priority polling, 5 weekly card-uses on the house, and exclusive Premium pools.
          </p>
          <div className="flex items-baseline gap-2 mt-5">
            <span className="text-4xl font-extrabold text-cp-lime">₦{PREMIUM_PRICE_NGN.toLocaleString()}</span>
            <span className="text-base" style={{ color: "rgba(255,255,255,0.7)" }}>/ month</span>
          </div>
          {isPremium ? (
            <div className="mt-5 cp-pill inline-flex items-center gap-1" style={{ background: "rgba(163,230,53,0.2)", color: "#A3E635" }} data-testid="premium-status-active">
              <ShieldCheck size={12}/> Active{premiumUntil ? ` until ${new Date(premiumUntil).toLocaleDateString()}` : ""}
            </div>
          ) : (
            <div className="mt-5">
              <button
                onClick={subscribe}
                disabled={busy || !paystackConfigured}
                className="cp-btn-primary text-base px-6 py-2.5"
                data-testid="premium-subscribe"
              >
                {busy ? "Initialising…" : `Subscribe for ₦${PREMIUM_PRICE_NGN.toLocaleString()}/mo`}
              </button>
              {!paystackConfigured && (
                <div className="mt-2 text-xs inline-flex items-center gap-1" style={{ color: "#FBBF24" }}>
                  <AlertTriangle size={12}/> Paystack keys not yet configured. Contact admin.
                </div>
              )}
              {err && (
                <div className="mt-3 text-sm" style={{ color: "#FCA5A5" }}>{err}</div>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="cp-surface mt-5 overflow-hidden">
        <div className="cp-card-header normal-case">
          <span className="font-bold">Compare Plans</span>
        </div>
        <div className="grid grid-cols-[1fr_auto_auto] gap-x-4 gap-y-2 px-4 py-3 text-sm">
          <div></div>
          <div className="text-center text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Free</div>
          <div className="text-center text-[10px] uppercase tracking-widest text-cp-lime">Premium</div>
          {PREMIUM_FEATURES.map((f, i) => (
            <React.Fragment key={i}>
              <div className="border-t pt-2" style={{ borderColor: "var(--cp-border)" }}>
                <div className="font-medium">{f.name}</div>
                <div className="text-[11px]" style={{ color: "var(--cp-text-muted)" }}>{f.desc}</div>
              </div>
              <div className="border-t pt-2 flex justify-center items-start" style={{ borderColor: "var(--cp-border)" }}>
                {(f.on || []).includes("free") ? <Check size={16} className="text-cp-lime"/> : <X size={16} style={{ color: "var(--cp-text-muted)" }}/>}
              </div>
              <div className="border-t pt-2 flex justify-center items-start" style={{ borderColor: "var(--cp-border)" }}>
                {(f.on || []).includes("premium") ? <Check size={16} className="text-cp-lime"/> : <X size={16} style={{ color: "var(--cp-text-muted)" }}/>}
              </div>
            </React.Fragment>
          ))}
        </div>
      </div>

      <div className="mt-4 text-xs" style={{ color: "var(--cp-text-muted)" }}>
        Cancel anytime. Subscription renews monthly via Paystack. By subscribing you accept Cloudy Pitch's responsible-play terms.
        <Link to="/wallet" className="text-cp-lime ml-2 hover:underline">Manage spending caps</Link>
      </div>
    </div>
  );
};

export default PremiumPage;
