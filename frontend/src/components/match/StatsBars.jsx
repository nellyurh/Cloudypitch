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

/**
 * DualProgressBar — Sofascore-style single bar split at center.
 * Left half fills right-to-left for home; right half fills left-to-right for away.
 * The winning side gets the lime accent; losing side stays slate.
 */
function DualProgressBar({ homePct, awayPct, homeWinning, awayWinning }) {
  const LIME = "var(--cp-lime, #A3E635)";
  const SLATE = "#94A3B8";
  return (
    <div className="relative h-1.5 w-full" data-testid="dual-progress">
      <div className="grid grid-cols-2 gap-0 h-full">
        {/* Home half: fills from center → left */}
        <div className="relative h-full rounded-l-full overflow-hidden" style={{ background: "#2A2E36" }}>
          <div
            className="absolute right-0 top-0 h-full transition-[width] duration-500 ease-out"
            style={{
              width: `${homePct}%`,
              background: homeWinning ? LIME : SLATE,
              opacity: homeWinning ? 1 : 0.55,
            }}
          />
        </div>
        {/* Away half: fills from center → right */}
        <div className="relative h-full rounded-r-full overflow-hidden" style={{ background: "#2A2E36" }}>
          <div
            className="absolute left-0 top-0 h-full transition-[width] duration-500 ease-out"
            style={{
              width: `${awayPct}%`,
              background: awayWinning ? LIME : SLATE,
              opacity: awayWinning ? 1 : 0.55,
            }}
          />
        </div>
      </div>
      {/* Center divider notch */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-px h-2.5"
           style={{ background: "rgba(255,255,255,0.25)" }}/>
    </div>
  );
}

function StatRow({ label, home, away }) {
  const h = Number(home ?? 0) || 0;
  const a = Number(away ?? 0) || 0;
  const total = h + a;
  let homePct = 50, awayPct = 50;
  if (PERCENT_STATS.has(label)) {
    homePct = Math.max(0, Math.min(100, h));
    awayPct = Math.max(0, Math.min(100, a));
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
    <div className="py-2.5" data-testid={`stat-${label}`}>
      <div className="grid grid-cols-[1fr_auto_1fr] items-center text-xs mb-1.5">
        <div className={`text-right font-bold tabular-nums text-sm ${isHomeWinning ? "text-cp-lime" : "text-slate-200"}`}>
          {home ?? "—"}
        </div>
        <div className="px-3 text-[10px] uppercase tracking-[0.08em] font-semibold" style={{ color: "var(--cp-text-muted)" }}>
          {prettyStat(label)}
        </div>
        <div className={`text-left font-bold tabular-nums text-sm ${isAwayWinning ? "text-cp-lime" : "text-slate-200"}`}>
          {away ?? "—"}
        </div>
      </div>
      <DualProgressBar
        homePct={homePct}
        awayPct={awayPct}
        homeWinning={isHomeWinning}
        awayWinning={isAwayWinning}
      />
    </div>
  );
}

export default function StatsBars({ statistics, homeTeamId, awayTeamId, homeName, awayName }) {
  if (!statistics || statistics.length === 0) {
    return <div className="text-sm" style={{ color: "var(--cp-text-muted)" }}>No stats yet.</div>;
  }
  const homeBlock = statistics.find((s) => s.team_id === homeTeamId) || statistics[0] || {};
  const awayBlock = statistics.find((s) => s.team_id === awayTeamId) || statistics[1] || {};
  const homeStats = homeBlock.stats || {};
  const awayStats = awayBlock.stats || {};

  const allKeys = new Set([...Object.keys(homeStats), ...Object.keys(awayStats)]);
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
      <div className="grid grid-cols-[1fr_auto_1fr] items-center text-[10px] uppercase tracking-[0.1em] font-semibold mb-4 pb-3 border-b" style={{ color: "var(--cp-text-muted)", borderColor: "var(--cp-border)" }}>
        <div className="text-right text-cp-lime">{homeName}</div>
        <div className="px-3 opacity-60">vs</div>
        <div className="text-left" style={{ color: "#94A3B8" }}>{awayName}</div>
      </div>
      <div className="divide-y" style={{ borderColor: "var(--cp-border)" }}>
        {filtered.map((k) => (
          <StatRow key={k} label={k} home={homeStats[k]} away={awayStats[k]} />
        ))}
      </div>
    </div>
  );
}
