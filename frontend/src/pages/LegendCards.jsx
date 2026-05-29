import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../lib/auth";
import { Crown, Star, Sparkles, History, ShieldCheck, LogIn } from "lucide-react";

const TIER_META = {
  1: { label: "GOAT", color: "#A3E635", icon: Crown, bg: "linear-gradient(135deg, rgba(163,230,53,0.15), rgba(15,110,86,0.4))" },
  2: { label: "Elite", color: "#0F6E56", icon: Sparkles, bg: "linear-gradient(135deg, rgba(15,110,86,0.18), rgba(34,40,49,0.6))" },
  3: { label: "Star", color: "#94A3B8", icon: Star, bg: "linear-gradient(135deg, rgba(148,163,184,0.1), rgba(34,40,49,0.6))" },
};

const STAGE_LABEL = {
  any: "Match", group_md1: "Group MD1", group_md2: "Group MD2", group_md3: "Group MD3",
  r32: "R32", r16: "R16", qf: "QF", sf: "SF", finals: "Finals",
};

function CatalogTab() {
  const [cards, setCards] = useState([]);
  const [filter, setFilter] = useState(0);
  useEffect(() => { (async () => { try { const { data } = await api.get("/cards"); setCards(data.cards || []); } catch (_) {} })(); }, []);
  const visible = filter ? cards.filter(c => c.tier === filter) : cards;
  return (
    <>
      <div className="flex gap-2 mb-4 flex-wrap">
        {[{ id: 0, label: "All" }, { id: 1, label: "GOAT · $2.00" }, { id: 2, label: "Elite · $1.00" }, { id: 3, label: "Star · $0.50" }].map(f => (
          <button key={f.id} onClick={() => setFilter(f.id)} className={`px-3 py-1.5 rounded text-xs font-bold ${filter === f.id ? "bg-cp-lime text-cp-forest" : "cp-surface hover:bg-white/5"}`} data-testid={`tier-filter-${f.id}`}>{f.label}</button>
        ))}
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
        {visible.map(c => {
          const meta = TIER_META[c.tier];
          const Icon = meta.icon;
          const priceUsd = ((c.price_usd_cents || 0) / 100).toFixed(2);
          return (
            <div key={c.id} className="cp-surface overflow-hidden hover:scale-[1.02] transition-transform cursor-pointer" data-testid={`card-${c.id}`} style={{ background: meta.bg }}>
              <div className="p-3 flex flex-col h-full min-h-[180px]">
                <div className="flex items-center justify-between">
                  <span className="cp-pill" style={{ background: meta.color, color: c.tier === 2 ? "#fff" : "#064E3B" }}>
                    <Icon size={10} className="mr-0.5"/> {meta.label}
                  </span>
                  <span className="text-[11px] font-bold tabular-nums" style={{ color: meta.color }}>${priceUsd}</span>
                </div>
                <div className="font-extrabold text-sm mt-3 leading-tight">{c.name}</div>
                <div className="text-[11px] mt-0.5" style={{ color: "var(--cp-text-muted)" }}>{c.player_name}</div>
                <div className="text-[11px] mt-2 flex-1" style={{ color: "var(--cp-text)" }}>{c.description}</div>
                <button className="cp-btn-primary !py-1.5 mt-3 text-xs" data-testid={`unlock-${c.id}`}>Unlock · +5 uses</button>
              </div>
            </div>
          );
        })}
      </div>
    </>
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
      <h3 className="text-base font-bold mt-3">You don't own any cards yet</h3>
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
      <p className="text-xs mt-1" style={{ color: "var(--cp-text-muted)" }}>Apply boost cards to your WC squad picks and they'll appear here.</p>
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
        Each card has <b>one use per game</b>, applied to one player you've picked. Boost stacks: pre-stage points multiplier × card boost. <span className="text-cp-lime">Not gambling</span> — fixed effects, no random packs.
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
