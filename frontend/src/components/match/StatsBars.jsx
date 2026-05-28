import React from "react";

const PERCENT_STATS = new Set([
  "Ball Possession %",
  "Passes %",
  "Long Pass Accuracy %",
  "Successful Passes Percentage",
  "Successful Long Passes Percentage",
  "Successful Dribbles Percentage",
  "Successful Headers Percentage",
]);

// Pretty-print raw Sportmonks names like "Successful Passes Percentage" → "Pass Accuracy %"
const PRETTY = {
  "Successful Passes Percentage": "Pass Accuracy %",
  "Successful Long Passes Percentage": "Long Pass Accuracy %",
  "Successful Dribbles Percentage": "Dribble Success %",
  "Successful Headers Percentage": "Header Success %",
  "Successful Passes": "Accurate Passes",
  "Successful Long Passes": "Accurate Long Passes",
  "Successful Headers": "Accurate Headers",
  "Successful Dribbles": "Successful Dribbles",
  "Successful Crosses": "Accurate Crosses",
  "Accurate Crosses": "Accurate Crosses",
  "Yellowcards": "Yellow Cards",
  "Redcards": "Red Cards",
  "Shots On Target": "Shots on Target",
  "Shots Off Target": "Shots off Target",
  "Throwins": "Throw-Ins",
};
const prettyStat = (k) => PRETTY[k] || k;

// Display order — most important stats first
const PRIORITY = [
  "Ball Possession %",
  "Shots Total",
  "Shots on Target",
  "Shots off Target",
  "Shots Blocked",
  "Shots Inside Box",
  "Shots Outside Box",
  "Expected Goals (xG)",
  "Big Chances Created",
  "Big Chances Missed",
  "Corners",
  "Offsides",
  "Fouls",
  "Yellow Cards",
  "Red Cards",
  "Saves",
  "Passes",
  "Passes Total",
  "Accurate Passes",
  "Successful Passes",
  "Pass Accuracy %",
  "Passes %",
  "Successful Passes Percentage",
  "Key Passes",
  "Accurate Crosses",
  "Successful Crosses",
  "Total Crosses",
  "Tackles",
  "Interceptions",
  "Counter Attacks",
  "Attacks",
  "Dangerous Attacks",
  "Free Kicks",
  "Throw-Ins",
  "Goal Kicks",
];

function StatRow({ label, home, away }) {
  const h = Number(home ?? 0) || 0;
  const a = Number(away ?? 0) || 0;
  const total = h + a;
  let homePct = 50, awayPct = 50;
  if (PERCENT_STATS.has(label)) {
    // values are already percentages
    homePct = Math.max(0, Math.min(100, h));
    awayPct = Math.max(0, Math.min(100, a));
    // normalise so they sum to 100 if both look like %
    const sum = homePct + awayPct;
    if (sum > 0 && Math.abs(sum - 100) > 5) {
      homePct = (homePct / sum) * 100;
      awayPct = (awayPct / sum) * 100;
    }
  } else if (total > 0) {
    homePct = (h / total) * 100;
    awayPct = (a / total) * 100;
  } else {
    homePct = awayPct = 0;
  }
  const isHomeWinning = h > a;
  const isAwayWinning = a > h;
  return (
    <div className="py-2" data-testid={`stat-${label}`}>
      <div className="grid grid-cols-[1fr_auto_1fr] items-center text-xs mb-1">
        <div className={`text-right font-bold tabular-nums ${isHomeWinning ? "text-cp-lime" : ""}`}>
          {home ?? "—"}
        </div>
        <div className="px-3 text-[10px] uppercase tracking-wider" style={{ color: "var(--cp-text-muted)" }}>
          {prettyStat(label)}
        </div>
        <div className={`text-left font-bold tabular-nums ${isAwayWinning ? "text-cp-lime" : ""}`}>
          {away ?? "—"}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-1 h-1.5">
        {/* Home bar — fills from right */}
        <div className="relative rounded overflow-hidden" style={{ background: "var(--cp-surface-2)" }}>
          <div
            className="absolute right-0 top-0 h-full transition-all"
            style={{
              width: `${homePct}%`,
              background: isHomeWinning ? "var(--cp-lime)" : "rgba(180,180,180,0.6)",
            }}
          />
        </div>
        {/* Away bar — fills from left */}
        <div className="relative rounded overflow-hidden" style={{ background: "var(--cp-surface-2)" }}>
          <div
            className="absolute left-0 top-0 h-full transition-all"
            style={{
              width: `${awayPct}%`,
              background: isAwayWinning ? "var(--cp-lime)" : "rgba(180,180,180,0.6)",
            }}
          />
        </div>
      </div>
    </div>
  );
}

export default function StatsBars({ statistics, homeTeamId, awayTeamId, homeName, awayName }) {
  if (!statistics || statistics.length === 0) {
    return <div className="text-sm" style={{ color: "var(--cp-text-muted)" }}>No stats yet.</div>;
  }
  // Pick home and away stat blocks
  const homeBlock = statistics.find((s) => s.team_id === homeTeamId) || statistics[0] || {};
  const awayBlock = statistics.find((s) => s.team_id === awayTeamId) || statistics[1] || {};
  const homeStats = homeBlock.stats || {};
  const awayStats = awayBlock.stats || {};

  // Collect all keys
  const allKeys = new Set([...Object.keys(homeStats), ...Object.keys(awayStats)]);
  // Filter: only render keys that are in our priority list OR have at least one numeric value
  const orderedKeys = [
    ...PRIORITY.filter((k) => allKeys.has(k)),
    ...[...allKeys].filter((k) => !PRIORITY.includes(k)).sort(),
  ];
  const filtered = orderedKeys.filter((k) => {
    const h = homeStats[k];
    const a = awayStats[k];
    return (h != null && h !== "") || (a != null && a !== "");
  });

  if (filtered.length === 0) {
    return <div className="text-sm" style={{ color: "var(--cp-text-muted)" }}>No stats yet.</div>;
  }

  return (
    <div data-testid="stats-bars">
      {/* Team name header */}
      <div className="grid grid-cols-[1fr_auto_1fr] items-center text-[11px] uppercase tracking-widest mb-3" style={{ color: "var(--cp-text-muted)" }}>
        <div className="text-right font-bold">{homeName}</div>
        <div className="px-3">vs</div>
        <div className="text-left font-bold">{awayName}</div>
      </div>
      {filtered.map((k) => (
        <StatRow key={k} label={k} home={homeStats[k]} away={awayStats[k]} />
      ))}
    </div>
  );
}
