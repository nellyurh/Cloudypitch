import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../lib/auth";
import { Crown, Star, Sparkles, History, ShieldCheck, LogIn, X, Wallet, Loader2 } from "lucide-react";
import LegendCardArt from "../components/LegendCardArt";

// Tier mapping: backend tier (1/2/3) → LegendCardArt visual tier
const TIER_ART = { 1: "gold", 2: "elite", 3: "epic" };
const TIER_META = {
  1: { label: "GOAT", color: "#FFD27A", icon: Crown },
  2: { label: "Elite", color: "#A3E635", icon: Sparkles },
  3: { label: "Star", color: "#F25C1B", icon: Star },
};

const STAGE_LABEL = {
  any: "Match", group_md1: "Group MD1", group_md2: "Group MD2", group_md3: "Group MD3",
  r32: "R32", r16: "R16", qf: "QF", sf: "SF", finals: "Finals",
};

function CatalogTab() {
  const [cards, setCards] = useState([]);
  const [filter, setFilter] = useState(0);
  const [buyTarget, setBuyTarget] = useState(null); // card being bought
  useEffect(() => { (async () => { try { const { data } = await api.get("/cards"); setCards(data.cards || []); } catch (_e) { /* ignore */ } })(); }, []);
  const visible = filter ? cards.filter(c => c.tier === filter) : cards;
  return (
    <>
      <div className="flex gap-2 mb-4 flex-wrap">
        {[{ id: 0, label: "All" }, { id: 1, label: "GOAT · $2.00" }, { id: 2, label: "Elite · $1.00" }, { id: 3, label: "Star · $0.50" }].map(f => (
          <button key={f.id} onClick={() => setFilter(f.id)} className={`px-3 py-1.5 rounded text-xs font-bold ${filter === f.id ? "bg-cp-lime text-cp-forest" : "cp-surface hover:bg-white/5"}`} data-testid={`tier-filter-${f.id}`}>{f.label}</button>
        ))}
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
        {visible.map(c => {
          const tierArt = TIER_ART[c.tier] || "epic";
          const priceUsd = ((c.price_usd_cents || 0) / 100).toFixed(2);
          return (
            <div key={c.id} className="cursor-pointer hover:scale-[1.02] transition-transform" data-testid={`card-${c.id}`} onClick={() => setBuyTarget(c)}>
              <LegendCardArt tier={tierArt} title={c.name?.toUpperCase()} size={220} data-testid={`card-art-${c.id}`}/>
              <div className="mt-2 px-1 text-center">
                <div className="text-[11px] font-bold truncate">{c.player_name}</div>
                <div className="text-[11px] tabular-nums text-cp-lime mt-0.5">${priceUsd} · +{c.uses_granted || 5} uses</div>
              </div>
            </div>
          );
        })}
      </div>
      {buyTarget && <BuyCardModal card={buyTarget} onClose={() => setBuyTarget(null)}/>}
    </>
  );
}

/** Custom buy modal — replaces the browser window.prompt. */
function BuyCardModal({ card, onClose }) {
  const [qty, setQty] = useState(1);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [wallet, setWallet] = useState(null);

  useEffect(() => {
    api.get("/wallet").then(({ data }) => setWallet(data)).catch(() => {});
  }, []);

  const unitUsdCents = card.price_usd_cents || 0;
  const totalUsdCents = unitUsdCents * qty;
  const usdCost = (totalUsdCents / 100).toFixed(2);

  const tierArt = TIER_ART[card.tier] || "epic";

  const buy = async () => {
    setBusy(true); setMsg(""); setErr("");
    try {
      const { data } = await api.post(`/cards/${card.id}/purchase`, { quantity: qty });
      setMsg(`✓ +${data.uses_granted || (5 * qty)} uses added to your wallet.`);
      setTimeout(onClose, 1400);
    } catch (e) {
      setErr(e?.response?.data?.detail || e.message);
    }
    setBusy(false);
  };

  return (
    <div className="fixed inset-0 z-[10001] flex items-end md:items-center justify-center p-0 md:p-4" data-testid="buy-card-modal">
      <div className="absolute inset-0" onClick={() => !busy && onClose()} style={{ background: "rgba(0,0,0,0.7)" }}/>
      <div className="relative w-full md:max-w-md rounded-t-2xl md:rounded-xl overflow-hidden animate-fade-in" style={{ background: "var(--cp-surface)", border: "1px solid var(--cp-border)" }}>
        <div className="px-4 py-3 flex items-center gap-2" style={{ borderBottom: "1px solid var(--cp-border)" }}>
          <h2 className="font-extrabold">Unlock {card.name}</h2>
          <button onClick={onClose} disabled={busy} className="ml-auto cp-btn-ghost !p-2 disabled:opacity-40" data-testid="buy-modal-close"><X size={14}/></button>
        </div>
        <div className="p-4 grid grid-cols-[140px_1fr] gap-4">
          <LegendCardArt tier={tierArt} title={card.name?.toUpperCase()} size={140}/>
          <div className="space-y-3">
            <div>
              <div className="text-[11px] opacity-60 uppercase tracking-widest">Card</div>
              <div className="font-extrabold text-sm">{card.name}</div>
              <div className="text-[11px] opacity-70 mt-0.5">{card.description}</div>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <span className="opacity-60">Quantity</span>
              <button onClick={() => setQty(q => Math.max(1, q - 1))} disabled={busy} className="cp-btn-ghost !p-1.5" data-testid="buy-qty-minus">−</button>
              <span className="font-extrabold tabular-nums w-8 text-center" data-testid="buy-qty">{qty}</span>
              <button onClick={() => setQty(q => Math.min(10, q + 1))} disabled={busy} className="cp-btn-ghost !p-1.5" data-testid="buy-qty-plus">+</button>
            </div>
            <div className="text-[11px] opacity-70">+{(card.uses_granted || 5) * qty} uses · ${(unitUsdCents / 100).toFixed(2)} ea.</div>
            {wallet && (
              <div className="text-[11px] flex items-center gap-1.5" style={{ color: "var(--cp-text-muted)" }}>
                <Wallet size={11}/> Balance: ${((wallet.balance_usd_cents || 0) / 100).toFixed(2)}
              </div>
            )}
            <div className="rounded p-2 flex items-center justify-between" style={{ background: "var(--cp-surface-2)" }}>
              <span className="text-xs opacity-70">Total</span>
              <span className="font-extrabold text-cp-lime text-base tabular-nums">${usdCost}</span>
            </div>
            {msg && <div className="text-[11px] text-cp-lime" data-testid="buy-success">{msg}</div>}
            {err && <div className="text-[11px] text-rose-400" data-testid="buy-error">{err}</div>}
            <button onClick={buy} disabled={busy} className="cp-btn-primary w-full inline-flex items-center justify-center gap-2 disabled:opacity-50" data-testid="buy-confirm">
              {busy ? <Loader2 size={14} className="animate-spin"/> : <Crown size={14}/>}
              {busy ? "Processing…" : `Buy for $${usdCost}`}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function MyCardsTab({ user }) {
  const [owned, setOwned] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    if (!user) return;
    api.get("/cards/me").then(({ data }) => { setOwned(data.owned || []); setLoading(false); }).catch(() => setLoading(false));
  }, [user]);
  if (loading) return <div className="cp-surface p-6 text-sm">Loading…</div>;
  if (!owned.length) return (
    <div className="cp-surface p-8 text-center" data-testid="my-cards-empty">
      <Sparkles size={32} className="mx-auto text-cp-lime opacity-60"/>
      <h3 className="text-base font-bold mt-3">You don&apos;t own any cards yet</h3>
      <p className="text-xs mt-1" style={{ color: "var(--cp-text-muted)" }}>Unlock your first card from the Catalog tab.</p>
    </div>
  );
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3" data-testid="my-cards-grid">
      {owned.map(o => {
        const c = o.card || {};
        const meta = TIER_META[c.tier] || TIER_META[3];
        const Icon = meta.icon;
        const uses = o.uses_remaining ?? o.uses_left ?? 0;
        return (
          <div key={o.id} className="cp-surface overflow-hidden" style={{ background: meta.bg }} data-testid={`owned-${o.id}`}>
            <div className="p-3">
              <div className="flex items-center justify-between">
                <span className="cp-pill" style={{ background: meta.color, color: c.tier === 2 ? "#fff" : "#064E3B" }}>
                  <Icon size={10} className="mr-0.5"/> {meta.label}
                </span>
                <span className="text-[11px] font-bold tabular-nums" style={{ color: uses === 0 ? "#FF3D52" : "#A3E635" }}>{uses} uses left</span>
              </div>
              <div className="font-extrabold text-sm mt-2">{c.name}</div>
              <div className="text-[11px] mt-1" style={{ color: "var(--cp-text-muted)" }}>{o.total_uses || 0} times used · +5 uses for $0.20 recharge</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function HistoryTab({ user }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    if (!user) return;
    api.get("/cards/me/history").then(({ data }) => { setRows(data.history || []); setLoading(false); }).catch(() => setLoading(false));
  }, [user]);
  if (loading) return <div className="cp-surface p-6 text-sm">Loading…</div>;
  if (!rows.length) return (
    <div className="cp-surface p-8 text-center" data-testid="history-empty">
      <History size={32} className="mx-auto text-cp-lime opacity-60"/>
      <h3 className="text-base font-bold mt-3">No cards used yet</h3>
      <p className="text-xs mt-1" style={{ color: "var(--cp-text-muted)" }}>Apply boost cards to your WC squad picks and they&apos;ll appear here.</p>
    </div>
  );
  return (
    <div className="cp-surface overflow-hidden" data-testid="card-usage-history">
      <div className="cp-card-header normal-case"><span className="font-bold flex items-center gap-2"><History size={14} className="text-cp-lime"/> Card Usage History · {rows.length} uses</span></div>
      <ul className="divide-y" style={{ borderColor: "var(--cp-border)" }}>
        {rows.map(r => {
          const c = r.card || {};
          const meta = TIER_META[c.tier] || TIER_META[3];
          const Icon = meta.icon;
          const tp = r.target_player || {};
          const g = r.game || {};
          return (
            <li key={r.id} className="px-3 py-2.5 flex items-center gap-3" data-testid={`use-row-${r.id}`}>
              <span className="cp-pill text-[10px] font-bold" style={{ background: meta.color, color: c.tier === 2 ? "#fff" : "#064E3B" }}>
                <Icon size={10} className="mr-0.5"/> {meta.label}
              </span>
              <div className="flex-1 min-w-0">
                <div className="font-extrabold text-sm truncate">{c.name || "Card"}</div>
                <div className="text-[11px]" style={{ color: "var(--cp-text-muted)" }}>
                  → <b style={{ color: "var(--cp-text)" }}>{tp.name || "—"}</b>
                  {tp.team_name ? <span className="opacity-70"> · {tp.team_name}</span> : null}
                </div>
              </div>
              <div className="text-right shrink-0">
                <div className="text-[11px] cp-pill" style={{ background: "var(--cp-surface-2)", color: "var(--cp-text-muted)" }}>{STAGE_LABEL[g.stage] || g.stage}</div>
                <div className="text-[10px] mt-1 tabular-nums" style={{ color: "var(--cp-text-muted)" }}>{r.created_at?.slice(0, 10)}</div>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export const LegendCards = () => {
  const { user } = useAuth();
  const [tab, setTab] = useState("catalog");
  return (
    <div data-testid="legend-cards-page">
      <h1 className="text-2xl font-extrabold mb-1">Legend Cards</h1>
      <p className="text-sm mb-4" style={{ color: "var(--cp-text-muted)" }}>
        Each card has <b>one use per game</b>, applied to one player you&apos;ve picked. Boost stacks: pre-stage points multiplier × card boost. <span className="text-cp-lime">Not gambling</span> — fixed effects, no random packs.
      </p>

      <div className="flex gap-1 cp-surface p-1 mt-3 w-fit mb-3">
        <button onClick={() => setTab("catalog")} className={`px-3 py-1.5 text-sm rounded ${tab === "catalog" ? "bg-cp-lime text-cp-forest font-bold" : "hover:bg-white/5"}`} data-testid="cards-tab-catalog">Catalog</button>
        <button onClick={() => setTab("mine")} className={`px-3 py-1.5 text-sm rounded ${tab === "mine" ? "bg-cp-lime text-cp-forest font-bold" : "hover:bg-white/5"}`} data-testid="cards-tab-mine">
          <ShieldCheck size={12} className="inline mr-1"/> My Cards
        </button>
        <button onClick={() => setTab("history")} className={`px-3 py-1.5 text-sm rounded ${tab === "history" ? "bg-cp-lime text-cp-forest font-bold" : "hover:bg-white/5"}`} data-testid="cards-tab-history">
          <History size={12} className="inline mr-1"/> My Usage
        </button>
      </div>

      {tab !== "catalog" && !user ? (
        <div className="cp-surface p-8 text-center" data-testid="cards-signin-gate">
          <LogIn size={32} className="mx-auto text-cp-lime"/>
          <h3 className="text-base font-bold mt-3">Sign in to view your cards</h3>
          <Link to="/signin" className="cp-btn-primary mt-4 inline-block" data-testid="cards-go-signin">Sign in</Link>
        </div>
      ) : (
        <>
          {tab === "catalog" && <CatalogTab/>}
          {tab === "mine" && <MyCardsTab user={user}/>}
          {tab === "history" && <HistoryTab user={user}/>}
        </>
      )}
    </div>
  );
};

export default LegendCards;
