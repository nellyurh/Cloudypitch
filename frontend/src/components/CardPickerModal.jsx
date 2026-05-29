import React, { useEffect, useMemo, useState } from "react";
import api from "../lib/api";
import { X, Sparkles, Lock, Coins } from "lucide-react";
import { Link } from "react-router-dom";

const TIER_COLOR = { 1: "#A3E635", 2: "#0F6E56", 3: "#64748B" };
const TIER_NAME = { 1: "GOAT", 2: "Elite", 3: "Star" };

/**
 * CardPickerModal — multi-select up to N owned cards for a single match prediction.
 * Computes a live "boost preview" so the user sees the value before submitting.
 *
 * Props:
 *  match       — the match object (used for context: home_country/away_country)
 *  basePoints  — base points the user expects (default 30 = exact-score win)
 *  stageMult   — stage multiplier preview (default 1.0; pass higher for KO rounds)
 *  selectedIds — currently-selected user_card_ids (controlled)
 *  maxCards    — cap (default 2 per match)
 *  onSave      — (ids: string[]) => void
 *  onClose     — () => void
 */
export const CardPickerModal = ({ match, basePoints = 30, stageMult = 1.0, selectedIds = [], maxCards = 2, onSave, onClose }) => {
  const [owned, setOwned] = useState([]);
  const [selected, setSelected] = useState(selectedIds);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/cards/me");
        // Only show cards with uses remaining
        const live = (data.owned || []).filter(o => (o.uses_remaining || o.uses_left || 0) > 0);
        setOwned(live);
      } catch (_) {}
      setLoading(false);
    })();
  }, []);

  const toggle = (uc) => {
    setSelected(prev => {
      if (prev.includes(uc.id)) return prev.filter(x => x !== uc.id);
      if (prev.length >= maxCards) return prev;
      return [...prev, uc.id];
    });
  };

  const matchContext = useMemo(() => ({
    home_country: (match?.home_country || match?.home_team_country || "").toUpperCase(),
    away_country: (match?.away_country || match?.away_team_country || "").toUpperCase(),
  }), [match]);

  const cardMatches = (card) => {
    if (!card) return false;
    // Fantasy mode (no match) — show all cards as applicable; backend resolves per-player
    if (!match) return true;
    const etype = card.effect_type;
    const ev = card.effect_value || {};
    const cc = (card.country_code || "").toUpperCase();
    if (!etype || etype === "flat_boost") return true;
    if (etype === "country_boost" || etype === "score_boost" || etype === "outcome_boost") {
      const wanted = (ev.country || cc).toUpperCase();
      if (!wanted) return true;
      return [matchContext.home_country, matchContext.away_country].includes(wanted);
    }
    if (etype === "continent_boost") return false; // unknown continent in preview
    return false; // position/role only for fantasy
  };

  const boost = useMemo(() => {
    let b = 0;
    for (const id of selected) {
      const uc = owned.find(o => o.id === id);
      const card = uc?.card;
      if (!card) continue;
      if (!cardMatches(card)) continue;
      const m = Number((card.effect_value || {}).multiplier || 1.0);
      b += Math.max(0, m - 1.0);
    }
    return Math.min(b, 1.0);
  }, [selected, owned]);

  const previewExact = Math.round(basePoints * stageMult * (1 + boost));
  const previewBase = Math.round(basePoints * stageMult);

  return (
    <div className="fixed inset-0 z-[150] flex items-end md:items-center justify-center p-3" style={{ background: "rgba(0,0,0,0.65)" }} data-testid="card-picker-modal">
      <div className="cp-surface w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
        <div className="px-4 py-3 flex items-center justify-between border-b" style={{ borderColor: "var(--cp-border)" }}>
          <div className="flex items-center gap-2">
            <Sparkles size={16} className="text-cp-lime"/>
            <h2 className="text-base font-extrabold">Apply Boost Cards</h2>
            <span className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>
              {selected.length}/{maxCards} selected
            </span>
          </div>
          <button onClick={onClose} className="p-1 hover:bg-white/5 rounded" data-testid="cards-close">
            <X size={16}/>
          </button>
        </div>

        {/* Boost preview */}
        <div className="px-4 py-3 grid grid-cols-3 gap-3 text-center border-b" style={{ borderColor: "var(--cp-border)" }} data-testid="boost-preview">
          <div>
            <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Base × Stage</div>
            <div className="text-xl font-extrabold tabular-nums">{previewBase}</div>
            <div className="text-[10px]" style={{ color: "var(--cp-text-muted)" }}>{basePoints} × {stageMult.toFixed(1)}</div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Card Boost</div>
            <div className="text-xl font-extrabold tabular-nums" style={{ color: boost > 0 ? "#A3E635" : "var(--cp-text-muted)" }}>+{Math.round(boost * 100)}%</div>
            <div className="text-[10px]" style={{ color: "var(--cp-text-muted)" }}>cap +100%</div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>If exact</div>
            <div className="text-2xl font-extrabold tabular-nums text-cp-lime">{previewExact}</div>
            <div className="text-[10px]" style={{ color: "var(--cp-text-muted)" }}>potential pts</div>
          </div>
        </div>

        {/* Owned cards list */}
        <div className="overflow-y-auto flex-1 p-3 space-y-2">
          {loading && <div className="text-sm" style={{ color: "var(--cp-text-muted)" }}>Loading your collection…</div>}
          {!loading && owned.length === 0 && (
            <div className="cp-surface p-6 text-center" data-testid="cards-empty">
              <Lock size={28} className="mx-auto text-cp-lime opacity-60"/>
              <p className="text-sm mt-3" style={{ color: "var(--cp-text-muted)" }}>You don't own any cards with remaining uses.</p>
              <Link to="/cards" className="cp-btn-primary mt-3 inline-block" data-testid="cards-browse-cta">Browse Legend Cards</Link>
            </div>
          )}
          {owned.map(uc => {
            const c = uc.card;
            const isSel = selected.includes(uc.id);
            const matchesCtx = cardMatches(c);
            const mult = Number((c.effect_value || {}).multiplier || 1.0);
            return (
              <button
                key={uc.id}
                onClick={() => toggle(uc)}
                disabled={!isSel && selected.length >= maxCards}
                className={`w-full text-left px-3 py-2.5 rounded-lg flex items-center gap-3 transition disabled:opacity-40 ${isSel ? "ring-2 ring-cp-lime" : "hover:bg-white/5"}`}
                style={{ background: "var(--cp-surface-2)" }}
                data-testid={`card-pick-${uc.id}`}
              >
                <span className="cp-pill text-[9px] font-bold" style={{ background: TIER_COLOR[c.tier] + "22", color: TIER_COLOR[c.tier] }}>
                  {TIER_NAME[c.tier]}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="font-bold truncate">{c.name}</div>
                  <div className="text-[10px] truncate" style={{ color: "var(--cp-text-muted)" }}>
                    {c.player_name || c.country_code || "—"} · {c.description || c.effect_type}
                  </div>
                </div>
                <div className="text-right shrink-0">
                  <div className="text-sm font-extrabold tabular-nums" style={{ color: matchesCtx ? "#A3E635" : "var(--cp-text-muted)" }}>
                    +{Math.round((mult - 1) * 100)}%
                  </div>
                  <div className="text-[9px] uppercase" style={{ color: "var(--cp-text-muted)" }}>
                    {uc.uses_remaining ?? uc.uses_left} uses
                  </div>
                  {!matchesCtx && <div className="text-[9px] text-amber-400">no match for this game</div>}
                </div>
              </button>
            );
          })}
        </div>

        <div className="px-4 py-3 flex gap-2 border-t" style={{ borderColor: "var(--cp-border)" }}>
          <button onClick={onClose} className="cp-btn-ghost flex-1" data-testid="cards-cancel">Cancel</button>
          <button
            onClick={() => { onSave?.(selected); onClose?.(); }}
            disabled={selected.length === 0}
            className="cp-btn-primary flex-1 inline-flex items-center justify-center gap-1 disabled:opacity-40"
            data-testid="cards-save"
          >
            <Coins size={14}/> Apply {selected.length} card{selected.length === 1 ? "" : "s"}
          </button>
        </div>
      </div>
    </div>
  );
};

export default CardPickerModal;
