import React, { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { X, Info } from "lucide-react";
import { flagUrl } from "../lib/flags";
import api from "../lib/api";

const POS_LABEL_FULL = { GK: "Goalkeeper", DEF: "Defender", MID: "Midfielder", FWD: "Forward" };
const POS_COLOR = { GK: "#FFC857", DEF: "#A3E635", MID: "#7DD3FC", FWD: "#FB7185" };

// Difficulty colour (1=easiest → 5=hardest), matches Sofascore palette
const DIFF_COLORS = {
  1: "#0EAD69",
  2: "#7BC242",
  3: "#F1C40F",
  4: "#E67E22",
  5: "#E74C3C",
};

const fmtMoney = (n) => `€${(n || 0).toFixed(1)}M`;

/**
 * Player Detail Bottom Sheet — Sofascore-style modal showing:
 *  • Photo + flag + country + position + price
 *  • 4 stat boxes (PTS/MATCH, FORM, SELECTED %, TOTAL) each with "n of 493"
 *  • R1/R2/R3 fixture difficulty bars (opponent + venue + difficulty colour)
 *  • Remove / Replace action buttons
 *
 * Pure presentational + 2 small data fetches. `playerPoolSize` = total players
 * in the same position so the "(208 of 493)" sub-labels look correct.
 */
export const PlayerDetailSheet = ({
  player,
  onClose,
  onRemove,
  onReplace,
  playerPoolSize = 493,
  inSquad = true,
}) => {
  const [fixtures, setFixtures] = useState([]);
  const [stats, setStats] = useState(null);

  useEffect(() => {
    if (!player) return;
    let cancelled = false;
    (async () => {
      // Best-effort fetches. Both endpoints fail silently — UI shows
      // sensible 0.0 placeholders matching Sofascore pre-tournament state.
      try {
        const { data } = await api.get("/worldcup");
        if (cancelled) return;
        const country = player.country;
        const ms = (data?.matches || []).filter(m =>
          m.home_team_name === country || m.away_team_name === country
        ).slice(0, 3);
        setFixtures(ms.map((m, idx) => ({
          round: `R${idx + 1}`,
          opp: m.home_team_name === country ? m.away_team_name : m.home_team_name,
          venue: m.home_team_name === country ? "H" : "A",
          // Tournament hasn't started — default to medium difficulty (3).
          difficulty: 3,
          scheduled_at: m.scheduled_at,
        })));
      } catch (_) {}
      try {
        const { data } = await api.get(`/fantasy/players/${player.id}/stats`).catch(() => ({ data: null }));
        if (cancelled) return;
        if (data) setStats(data);
      } catch (_) {}
    })();
    return () => { cancelled = true; };
  }, [player]);

  if (!player) return null;

  // Stat numbers — backend may not yet have real data pre-tournament; safe defaults.
  const pts_per_match = stats?.pts_per_match ?? 0.0;
  const form = stats?.form ?? 0.0;
  const selected_pct = stats?.selected_pct ?? 0.0;
  const total_pts = stats?.total_pts ?? 0;
  const samePosRank = stats?.position_rank ?? Math.floor(playerPoolSize / 2);
  const sel_count = stats?.selected_count ?? Math.floor(playerPoolSize / 50);

  const StatBox = ({ label, value, sub, isPercent }) => (
    <div className="flex-1 min-w-0 px-2 py-2.5 text-center">
      <div className="text-[10px] uppercase tracking-widest font-bold" style={{ color: "var(--cp-text-muted)" }}>
        {label}
      </div>
      <div className="text-2xl font-extrabold tabular-nums mt-0.5" style={{ color: "var(--cp-text)" }}>
        {isPercent ? `${value.toFixed(1)}%` : (Number.isInteger(value) ? value : value.toFixed(1))}
      </div>
      <div className="text-[10px] mt-0.5 tabular-nums" style={{ color: "var(--cp-text-muted)" }}>{sub}</div>
    </div>
  );

  const flag = flagUrl(player.country, 80);

  return createPortal((
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center"
      style={{ background: "rgba(0,0,0,0.6)" }}
      onClick={onClose}
      data-testid="player-detail-sheet"
    >
      <div
        className="cp-surface w-full sm:max-w-md rounded-t-2xl sm:rounded-2xl overflow-hidden"
        style={{ animation: "cp-sheet-up 240ms ease-out" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header — photo + name + price */}
        <div className="relative px-4 pt-4 pb-2 flex items-center gap-3" style={{ borderBottom: "1px solid var(--cp-border)" }}>
          <span className="relative inline-block" style={{ width: 64, height: 64 }}>
            <span className="absolute inset-0 rounded-full overflow-hidden" style={{ background: "#fff" }}>
              {player.photo_url ? (
                <img
                  src={player.photo_url}
                  alt={player.name}
                  style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: "top center" }}
                  onError={(e) => { e.currentTarget.style.display = "none"; }}
                />
              ) : (
                <span className="flex items-center justify-center text-cp-forest font-extrabold text-2xl w-full h-full" style={{ background: POS_COLOR[player.position] || "#A3E635" }}>
                  {(player.name || "?").split(" ").slice(-1)[0].slice(0, 1)}
                </span>
              )}
            </span>
            {flag && (
              <img src={flag} alt={player.country}
                style={{
                  position: "absolute", left: -3, bottom: -3, width: 22, height: 16,
                  objectFit: "cover", borderRadius: 3, border: "2px solid #fff",
                  boxShadow: "0 1px 3px rgba(0,0,0,0.5)",
                }}
              />
            )}
          </span>
          <div className="flex-1 min-w-0">
            <div className="text-lg font-extrabold truncate">{player.name}</div>
            <div className="text-xs" style={{ color: "var(--cp-text-muted)" }}>
              {fmtMoney(player.price)} · {POS_LABEL_FULL[player.position] || player.position} · {player.country || player.team_name}
            </div>
          </div>
          <button
            onClick={onClose}
            className="cp-btn-ghost !p-1.5"
            aria-label="Close"
            data-testid="player-detail-close"
          >
            <X size={18}/>
          </button>
        </div>

        {/* 4 stat boxes — PTS/MATCH, FORM, SELECTED %, TOTAL */}
        <div className="flex divide-x" style={{ borderColor: "var(--cp-border)", borderBottom: "1px solid var(--cp-border)" }}>
          <StatBox label="PTS/MATCH" value={pts_per_match} sub={`${samePosRank} of ${playerPoolSize}`} />
          <StatBox label="FORM"      value={form}          sub={`${samePosRank} of ${playerPoolSize}`} />
          <StatBox label="SELECTED"  value={selected_pct}  sub={`${sel_count} of ${playerPoolSize}`} isPercent />
          <StatBox label="TOTAL"     value={total_pts}     sub={`${samePosRank} of ${playerPoolSize}`} />
        </div>

        {/* Fixtures R1 / R2 / R3 with difficulty bars */}
        <div className="px-4 py-3" style={{ borderBottom: "1px solid var(--cp-border)" }}>
          <div className="text-[10px] uppercase tracking-widest font-bold mb-2" style={{ color: "var(--cp-text-muted)" }}>
            Fixtures
          </div>
          {fixtures.length === 0 ? (
            <div className="text-xs opacity-60">No upcoming fixtures.</div>
          ) : (
            <div className="grid grid-cols-3 gap-2" data-testid="player-fixtures">
              {fixtures.map((f, idx) => (
                <div key={idx} className="rounded overflow-hidden">
                  <div className="text-[10px] font-bold px-2 py-1 flex items-center justify-between" style={{ background: "var(--cp-surface-2)", color: "var(--cp-text-muted)" }}>
                    <span>{f.round}</span>
                    <span className="opacity-70">({f.venue})</span>
                  </div>
                  <div className="flex items-center gap-1.5 px-2 py-1.5" style={{ background: DIFF_COLORS[f.difficulty] || DIFF_COLORS[3] }}>
                    {flagUrl(f.opp, 40) && (
                      <img src={flagUrl(f.opp, 40)} alt="" style={{ width: 14, height: 10, objectFit: "cover", borderRadius: 2 }}/>
                    )}
                    <span className="text-[10px] font-extrabold text-white truncate">
                      {f.opp.slice(0, 12)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
          {fixtures[0]?.scheduled_at && (
            <div className="text-[11px] mt-2 px-1" style={{ color: "var(--cp-text-muted)" }}>
              Next: <span className="font-bold" style={{ color: "var(--cp-text)" }}>{player.country}</span> vs {fixtures[0].opp} ·{" "}
              {new Date(fixtures[0].scheduled_at).toLocaleString(undefined, { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })}
            </div>
          )}
        </div>

        {/* Action buttons */}
        {inSquad ? (
          <div className="flex p-3 gap-2">
            <button
              onClick={() => { onRemove?.(player); onClose?.(); }}
              className="flex-1 py-2.5 rounded font-extrabold text-sm"
              style={{ background: "var(--cp-surface-2)", border: "1px solid var(--cp-border)", color: "#FF6B7A" }}
              data-testid="player-detail-remove"
            >
              Remove
            </button>
            <button
              onClick={() => { onReplace?.(player); onClose?.(); }}
              className="flex-1 py-2.5 rounded font-extrabold text-sm"
              style={{ background: "var(--cp-lime)", color: "var(--cp-forest)" }}
              data-testid="player-detail-replace"
            >
              Replace
            </button>
          </div>
        ) : (
          <div className="p-3">
            <button
              onClick={() => { onReplace?.(player); onClose?.(); }}
              className="w-full py-2.5 rounded font-extrabold text-sm"
              style={{ background: "var(--cp-lime)", color: "var(--cp-forest)" }}
              data-testid="player-detail-add"
            >
              Add to squad
            </button>
          </div>
        )}
      </div>
      <style>{`@keyframes cp-sheet-up { from { transform: translateY(40px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }`}</style>
    </div>
  ), document.body);
};

/** Tiny "info" icon button that opens the bottom sheet — drop-in for player rows. */
export const PlayerInfoButton = ({ player, onClick, className = "" }) => (
  <button
    onClick={(e) => { e.stopPropagation(); onClick?.(player); }}
    className={`p-1 rounded-full hover:bg-white/10 ${className}`}
    title="Player info"
    aria-label="Player info"
    data-testid={`player-info-${player.id}`}
  >
    <Info size={14} style={{ color: "var(--cp-text-muted)" }}/>
  </button>
);

export default PlayerDetailSheet;
