import React, { useEffect, useState } from "react";
import api from "../lib/api";
import { Crown, Star, Sparkles } from "lucide-react";

const TIER_META = {
  1: { label: "GOAT", color: "#A3E635", icon: Crown, bg: "linear-gradient(135deg, rgba(163,230,53,0.15), rgba(15,110,86,0.4))" },
  2: { label: "Elite", color: "#0F6E56", icon: Sparkles, bg: "linear-gradient(135deg, rgba(15,110,86,0.18), rgba(34,40,49,0.6))" },
  3: { label: "Star", color: "#94A3B8", icon: Star, bg: "linear-gradient(135deg, rgba(148,163,184,0.1), rgba(34,40,49,0.6))" },
};

export const LegendCards = () => {
  const [cards, setCards] = useState([]);
  const [filter, setFilter] = useState(0);

  useEffect(() => { (async () => { try { const { data } = await api.get("/cards"); setCards(data.cards || []); } catch (_) {} })(); }, []);

  const visible = filter ? cards.filter(c => c.tier === filter) : cards;

  return (
    <div data-testid="legend-cards-page">
      <h1 className="text-2xl font-extrabold mb-1">Legend Cards</h1>
      <p className="text-sm mb-4" style={{ color: "var(--cp-text-muted)" }}>Boost your predictions & fantasy points with deterministic legendary effects. 100 cards across 3 tiers. <span className="text-cp-lime">Not gambling</span> — fixed effects, no random packs.</p>

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
    </div>
  );
};

export default LegendCards;
