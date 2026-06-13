import React, { useEffect, useState } from "react";
import { Trophy, Check, Lock } from "lucide-react";
import { Link } from "react-router-dom";
import api from "../lib/api";

/**
 * QualifyProgress — gamified prize-pool eligibility bar.
 *
 * Shows the user how far they are from prize-pool eligibility:
 *   · X / 20 predictions
 *   · Y / 50 WC mini-games
 *   · Combined % progress
 *
 * If both thresholds are met, swaps to a celebratory "ELIGIBLE" badge.
 * Otherwise it nudges the user toward the next action with a deep link.
 */
export const QualifyProgress = ({ compact = false }) => {
  const [data, setData] = useState(null);
  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/users/me/stats");
        setData(data?.eligibility || null);
      } catch (_e) { /* noop */ }
    })();
  }, []);

  if (!data) return null;
  const {
    min_predictions: minP,
    min_wc_games: minW,
    predictions_made: pCount,
    wc_games_played: wCount,
    is_eligible: eligible,
    progress_pct: pct,
  } = data;
  const predPct = Math.min(100, Math.round((pCount / Math.max(minP, 1)) * 100));
  const wcPct   = Math.min(100, Math.round((wCount / Math.max(minW, 1)) * 100));

  return (
    <div
      className="cp-surface p-3 space-y-2"
      data-testid="qualify-progress"
      style={{ borderColor: eligible ? "#A3E635" : "var(--cp-border)" }}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {eligible
            ? <Check size={14} className="text-cp-lime"/>
            : <Lock size={14} style={{ color: "var(--cp-text-muted)" }}/>}
          <span className="text-[11px] uppercase tracking-widest font-bold" style={{ color: eligible ? "#A3E635" : "var(--cp-text)" }}>
            {eligible ? "Prize-Pool Eligible" : "Prize-Pool Qualifier"}
          </span>
        </div>
        <span className="text-base font-extrabold tabular-nums" data-testid="qualify-pct" style={{ color: eligible ? "#A3E635" : "var(--cp-text)" }}>
          {pct}%
        </span>
      </div>

      {/* Combined bar */}
      <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "var(--cp-surface-2)" }}>
        <div
          className="h-full transition-all"
          style={{
            width: `${pct}%`,
            background: eligible
              ? "linear-gradient(90deg,#A3E635 0%,#FBBF24 100%)"
              : "linear-gradient(90deg,#FBBF24 0%,#A3E635 100%)",
          }}
        />
      </div>

      {!compact && (
        <div className="grid grid-cols-2 gap-2 pt-1">
          <PillStat
            label="Predictions"
            value={pCount}
            target={minP}
            pct={predPct}
            href="/predictions"
            testid="qualify-preds"
          />
          <PillStat
            label="Mini-games"
            value={wCount}
            target={minW}
            pct={wcPct}
            href="/worldcup"
            testid="qualify-minis"
          />
        </div>
      )}

      {eligible ? (
        <Link to="/leaderboards" className="cp-btn-primary w-full justify-center !text-xs" data-testid="qualify-cta-leaderboards">
          <Trophy size={12}/> Check your rank
        </Link>
      ) : (
        <p className="text-[10px] text-center" style={{ color: "var(--cp-text-muted)" }}>
          Hit both targets — {minP} predictions + {minW} mini-games — to unlock prize-pool payouts.
        </p>
      )}
    </div>
  );
};

function PillStat({ label, value, target, pct, href, testid }) {
  const done = value >= target;
  return (
    <Link to={href} className="block group" data-testid={testid}>
      <div className="flex items-center justify-between text-[10px] uppercase tracking-widest mb-1">
        <span style={{ color: "var(--cp-text-muted)" }}>{label}</span>
        <span className="tabular-nums font-bold" style={{ color: done ? "#A3E635" : "var(--cp-text)" }}>
          {value}/{target}
        </span>
      </div>
      <div className="h-1 rounded-full overflow-hidden" style={{ background: "var(--cp-surface-2)" }}>
        <div
          className="h-full transition-all"
          style={{
            width: `${pct}%`,
            background: done ? "#A3E635" : "#FBBF24",
          }}
        />
      </div>
    </Link>
  );
}

export default QualifyProgress;
