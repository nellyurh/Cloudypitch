import React from "react";

/* ============================================================
 * Sofascore-style statistics tab
 * - Sectioned blocks (Match overview / Shots / Attack / Passes / Duels / Defending / Goalkeeping)
 * - Two-column responsive grid on desktop
 * - Home always rendered in lime, Away in cyan (constant tones — not "winner only")
 * - Continuous dual bar that meets in the middle (no notch)
 * - Ring/donut % for accuracy stats (Pass Accuracy %, Header / Dribble Success %)
 * ============================================================ */

const HOME = "#A3E635"; // lime
const AWAY = "#7DD3FC"; // sky-300 — readable on dark, distinct from lime
const TRACK = "#2A2E36";

const PERCENT_STATS = new Set([
  "Ball Possession %",
  "Passes %",
  "Long Pass Accuracy %",
  "Pass Accuracy %",
  "Dribble Success %",
  "Header Success %",
  "Successful Passes Percentage",
  "Successful Long Passes Percentage",
  "Successful Dribbles Percentage",
  "Successful Headers Percentage",
]);

// Stats that should render as a donut ring (always %).
const RING_STATS = new Set([
  "Pass Accuracy %",
  "Long Pass Accuracy %",
  "Dribble Success %",
  "Header Success %",
  "Successful Passes Percentage",
  "Successful Long Passes Percentage",
  "Successful Dribbles Percentage",
  "Successful Headers Percentage",
]);

const PRETTY = {
  "Ball Possession %": "Ball possession",
  "Shots Total": "Total shots",
  "Shots on Target": "Shots on target",
  "Shots On Target": "Shots on target",
  "Shots off Target": "Shots off target",
  "Shots Off Target": "Shots off target",
  "Shots Blocked": "Blocked shots",
  "Shots Inside Box": "Shots inside box",
  "Shots Outside Box": "Shots outside box",
  "Hit Woodwork": "Hit woodwork",
  "Expected Goals (xG)": "Expected goals (xG)",
  "Big Chances Created": "Big chances",
  "Big Chances Scored": "Big chances scored",
  "Big Chances Missed": "Big chances missed",
  "Corners": "Corner kicks",
  "Saves": "Goalkeeper saves",
  "Passes": "Passes",
  "Passes Total": "Passes",
  "Successful Passes": "Accurate passes",
  "Accurate Passes": "Accurate passes",
  "Successful Passes Percentage": "Pass accuracy %",
  "Pass Accuracy %": "Pass accuracy %",
  "Key Passes": "Key passes",
  "Successful Crosses": "Accurate crosses",
  "Accurate Crosses": "Accurate crosses",
  "Total Crosses": "Total crosses",
  "Successful Long Passes": "Accurate long passes",
  "Successful Long Passes Percentage": "Long pass accuracy %",
  "Long Pass Accuracy %": "Long pass accuracy %",
  "Successful Dribbles": "Successful dribbles",
  "Successful Dribbles Percentage": "Dribble success %",
  "Dribble Success %": "Dribble success %",
  "Successful Headers": "Accurate headers",
  "Successful Headers Percentage": "Header success %",
  "Header Success %": "Header success %",
  "Tackles": "Total tackles",
  "Interceptions": "Interceptions",
  "Counter Attacks": "Counter attacks",
  "Attacks": "Attacks",
  "Dangerous Attacks": "Dangerous attacks",
  "Free Kicks": "Free kicks",
  "Throw-Ins": "Throw-ins",
  "Throwins": "Throw-ins",
  "Goal Kicks": "Goal kicks",
  "Offsides": "Offsides",
  "Fouls": "Fouls",
  "Yellow Cards": "Yellow cards",
  "Yellowcards": "Yellow cards",
  "Red Cards": "Red cards",
  "Redcards": "Red cards",
};
const prettyStat = (k) => PRETTY[k] || k;

const SECTIONS = [
  {
    id: "overview",
    title: "Match overview",
    keys: [
      "Ball Possession %",
      "Expected Goals (xG)",
      "Big Chances Created",
      "Shots Total",
      "Saves",
      "Corners",
      "Fouls",
      "Passes",
      "Tackles",
      "Free Kicks",
      "Yellow Cards",
      "Red Cards",
      "Yellowcards",
      "Redcards",
    ],
  },
  {
    id: "shots",
    title: "Shots",
    keys: [
      "Shots Total",
      "Shots on Target",
      "Shots On Target",
      "Shots off Target",
      "Shots Off Target",
      "Hit Woodwork",
      "Shots Blocked",
      "Shots Inside Box",
      "Shots Outside Box",
    ],
  },
  {
    id: "attack",
    title: "Attack",
    keys: [
      "Big Chances Scored",
      "Big Chances Missed",
      "Counter Attacks",
      "Attacks",
      "Dangerous Attacks",
      "Offsides",
    ],
  },
  {
    id: "passes",
    title: "Passes",
    keys: [
      "Passes Total",
      "Passes",
      "Accurate Passes",
      "Successful Passes",
      "Pass Accuracy %",
      "Successful Passes Percentage",
      "Key Passes",
      "Accurate Crosses",
      "Successful Crosses",
      "Total Crosses",
      "Successful Long Passes",
      "Long Pass Accuracy %",
      "Successful Long Passes Percentage",
      "Throw-Ins",
      "Throwins",
    ],
  },
  {
    id: "duels",
    title: "Duels",
    keys: [
      "Successful Dribbles",
      "Dribble Success %",
      "Successful Dribbles Percentage",
      "Successful Headers",
      "Header Success %",
      "Successful Headers Percentage",
    ],
  },
  {
    id: "defending",
    title: "Defending",
    keys: ["Tackles", "Interceptions", "Shots Blocked"],
  },
  {
    id: "goalkeeping",
    title: "Goalkeeping",
    keys: ["Saves", "Goal Kicks"],
  },
];

// ── building blocks ──────────────────────────────────────────

function DualBar({ homePct, awayPct }) {
  return (
    <div className="relative w-full h-1.5 rounded-full overflow-hidden" style={{ background: TRACK }}>
      {/* Home portion grows right-to-center from left */}
      <div
        className="absolute left-0 top-0 h-full transition-[width] duration-500 ease-out"
        style={{ width: `${homePct / 2}%`, background: HOME }}
      />
      {/* Away portion grows left-to-center from right */}
      <div
        className="absolute right-0 top-0 h-full transition-[width] duration-500 ease-out"
        style={{ width: `${awayPct / 2}%`, background: AWAY }}
      />
    </div>
  );
}

function RingPercent({ value, tone }) {
  const pct = Math.max(0, Math.min(100, Number(value) || 0));
  const r = 14;
  const C = 2 * Math.PI * r;
  const dash = (pct / 100) * C;
  return (
    <div className="relative w-9 h-9 shrink-0" data-testid="stat-ring">
      <svg width="36" height="36" viewBox="0 0 36 36">
        <circle cx="18" cy="18" r={r} fill="none" stroke={TRACK} strokeWidth="3" />
        <circle
          cx="18" cy="18" r={r}
          fill="none" stroke={tone}
          strokeWidth="3" strokeLinecap="round"
          strokeDasharray={`${dash} ${C - dash}`}
          transform="rotate(-90 18 18)"
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center text-[10px] font-bold tabular-nums" style={{ color: tone }}>
        {Math.round(pct)}%
      </div>
    </div>
  );
}

function StatRow({ label, home, away }) {
  const h = Number(home ?? 0) || 0;
  const a = Number(away ?? 0) || 0;
  let homePct = 50, awayPct = 50;
  if (PERCENT_STATS.has(label)) {
    homePct = Math.max(0, Math.min(100, h));
    awayPct = Math.max(0, Math.min(100, a));
    const sum = homePct + awayPct;
    if (sum > 0 && Math.abs(sum - 100) > 5) {
      homePct = (homePct / sum) * 100;
      awayPct = (awayPct / sum) * 100;
    }
  } else {
    const total = h + a;
    if (total > 0) {
      homePct = (h / total) * 100;
      awayPct = (a / total) * 100;
    } else { homePct = awayPct = 0; }
  }

  const isRing = RING_STATS.has(label);

  return (
    <div className="py-2" data-testid={`stat-${label}`}>
      <div className="grid grid-cols-[auto_1fr_auto] items-center gap-3 text-xs mb-1.5">
        <div className="flex items-center justify-end gap-2 min-w-[44px]">
          {isRing && <RingPercent value={h} tone={HOME} />}
          <span className="font-bold tabular-nums text-sm" style={{ color: HOME }}>
            {home ?? "—"}{PERCENT_STATS.has(label) && !isRing ? "%" : ""}
          </span>
        </div>
        <div className="px-2 text-center text-[10px] uppercase tracking-[0.06em] font-semibold" style={{ color: "var(--cp-text-muted)" }}>
          {prettyStat(label)}
        </div>
        <div className="flex items-center justify-start gap-2 min-w-[44px]">
          <span className="font-bold tabular-nums text-sm" style={{ color: AWAY }}>
            {away ?? "—"}{PERCENT_STATS.has(label) && !isRing ? "%" : ""}
          </span>
          {isRing && <RingPercent value={a} tone={AWAY} />}
        </div>
      </div>
      {!isRing && <DualBar homePct={homePct} awayPct={awayPct} />}
    </div>
  );
}

function Section({ title, rows, homeStats, awayStats }) {
  if (!rows.length) return null;
  return (
    <section className="cp-surface !bg-transparent ring-1 ring-white/5 rounded-lg p-3 md:p-4" data-testid={`stat-section-${title.toLowerCase().replace(/\s+/g, "-")}`}>
      <h4 className="text-center text-[13px] md:text-sm font-bold mb-3 pb-2 border-b" style={{ borderColor: "var(--cp-border)", color: "var(--cp-text)" }}>
        {title}
      </h4>
      <div className="divide-y" style={{ borderColor: "var(--cp-border)" }}>
        {rows.map((k) => (
          <StatRow key={k} label={k} home={homeStats[k]} away={awayStats[k]} />
        ))}
      </div>
    </section>
  );
}

// ── main export ──────────────────────────────────────────────

export default function StatsBars({ statistics, homeTeamId, awayTeamId, homeName, awayName }) {
  if (!statistics || statistics.length === 0) {
    return <div className="text-sm" style={{ color: "var(--cp-text-muted)" }}>No stats yet.</div>;
  }
  const homeBlock = statistics.find((s) => s.team_id === homeTeamId) || statistics[0] || {};
  const awayBlock = statistics.find((s) => s.team_id === awayTeamId) || statistics[1] || {};
  const homeStats = homeBlock.stats || {};
  const awayStats = awayBlock.stats || {};

  const hasValue = (k) => {
    const h = homeStats[k]; const a = awayStats[k];
    return (h != null && h !== "") || (a != null && a !== "");
  };

  // Resolve section rows + de-dup keys assigned earlier
  const usedKeys = new Set();
  const renderedSections = SECTIONS.map((s) => {
    // pick first variant per section for dedup, but keep all that exist
    const rows = s.keys.filter((k) => hasValue(k) && !usedKeys.has(k));
    rows.forEach((k) => usedKeys.add(k));
    return { ...s, rows };
  }).filter((s) => s.rows.length > 0);

  // Leftovers — any keys not yet rendered
  const allKeys = new Set([...Object.keys(homeStats), ...Object.keys(awayStats)]);
  const leftover = [...allKeys].filter((k) => !usedKeys.has(k) && hasValue(k)).sort();
  if (leftover.length) renderedSections.push({ id: "more", title: "More", rows: leftover });

  if (!renderedSections.length) {
    return <div className="text-sm" style={{ color: "var(--cp-text-muted)" }}>No stats yet.</div>;
  }

  return (
    <div data-testid="stats-bars">
      {/* Team headline */}
      <div className="grid grid-cols-[1fr_auto_1fr] items-center text-[11px] uppercase tracking-[0.1em] font-bold mb-4 pb-3 border-b" style={{ borderColor: "var(--cp-border)" }}>
        <div className="text-right inline-flex items-center justify-end gap-2">
          <span className="inline-block w-2 h-2 rounded-full" style={{ background: HOME }} />
          <span style={{ color: HOME }}>{homeName}</span>
        </div>
        <div className="px-3 opacity-60" style={{ color: "var(--cp-text-muted)" }}>vs</div>
        <div className="text-left inline-flex items-center gap-2">
          <span style={{ color: AWAY }}>{awayName}</span>
          <span className="inline-block w-2 h-2 rounded-full" style={{ background: AWAY }} />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 md:gap-4">
        {renderedSections.map((s) => (
          <Section
            key={s.id}
            title={s.title}
            rows={s.rows}
            homeStats={homeStats}
            awayStats={awayStats}
          />
        ))}
      </div>
    </div>
  );
}
