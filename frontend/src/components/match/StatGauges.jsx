import React from "react";

/**
 * Dual-ring percentage gauge — Sofascore style.
 * Renders side-by-side circles for home / away with a label between.
 *   <StatGauge label="Free throws" homeMade={11} homeAtt={12} awayMade={21} awayAtt={25} />
 */
export function StatGauge({ label, homeMade, homeAtt, awayMade, awayAtt }) {
  const homePct = homeAtt ? (homeMade / homeAtt) * 100 : 0;
  const awayPct = awayAtt ? (awayMade / awayAtt) * 100 : 0;
  return (
    <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 py-2.5" data-testid={`gauge-${label}`}>
      <div className="text-right text-xs tabular-nums" style={{ color: "var(--cp-text-muted)" }}>
        {homeMade}/{homeAtt}
      </div>
      <div className="flex items-center gap-2">
        <Ring pct={homePct} color="#A3E635"/>
        <div className="text-[11px] uppercase tracking-widest text-center min-w-[80px]" style={{ color: "var(--cp-text-muted)" }}>{label}</div>
        <Ring pct={awayPct} color="#7DD3FC"/>
      </div>
      <div className="text-left text-xs tabular-nums" style={{ color: "var(--cp-text-muted)" }}>
        {awayMade}/{awayAtt}
      </div>
    </div>
  );
}

function Ring({ pct, color }) {
  const r = 18, c = 2 * Math.PI * r;
  const off = c - (Math.max(0, Math.min(100, pct)) / 100) * c;
  return (
    <svg width="44" height="44" viewBox="0 0 44 44">
      <circle cx="22" cy="22" r={r} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="3.5"/>
      <circle
        cx="22" cy="22" r={r} fill="none" stroke={color} strokeWidth="3.5"
        strokeDasharray={c} strokeDashoffset={off}
        strokeLinecap="round" transform="rotate(-90 22 22)"
        style={{ transition: "stroke-dashoffset 0.4s" }}
      />
      <text x="22" y="25" textAnchor="middle" fontSize="10" fontWeight="800" fill="var(--cp-text)">
        {Math.round(pct)}%
      </text>
    </svg>
  );
}

/**
 * Horizontal comparison bar — home left fill, away right fill, label centered.
 *   <CompareBar label="Rebounds" home={42} away={52} highlightWinner />
 */
export function CompareBar({ label, home, away, highlightWinner = true }) {
  const h = Number(home || 0), a = Number(away || 0);
  const total = h + a || 1;
  const hPct = (h / total) * 100;
  const aPct = (a / total) * 100;
  const winnerHome = highlightWinner && h > a;
  const winnerAway = highlightWinner && a > h;
  return (
    <div className="py-2" data-testid={`bar-${label}`}>
      <div className="grid grid-cols-[2.5rem_1fr_2.5rem] items-center text-xs mb-1">
        <div
          className={`text-center tabular-nums font-extrabold px-2 py-0.5 rounded ${winnerHome ? "text-cp-forest" : ""}`}
          style={{ background: winnerHome ? "#A3E635" : "transparent", color: winnerHome ? "#064E3B" : "var(--cp-text)" }}
        >
          {home ?? "—"}
        </div>
        <div className="text-center text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>{label}</div>
        <div
          className={`text-center tabular-nums font-extrabold px-2 py-0.5 rounded ${winnerAway ? "" : ""}`}
          style={{ background: winnerAway ? "#7DD3FC" : "transparent", color: winnerAway ? "#082F49" : "var(--cp-text)" }}
        >
          {away ?? "—"}
        </div>
      </div>
      <div className="flex h-1.5 rounded overflow-hidden" style={{ background: "var(--cp-surface-2)" }}>
        <div className="transition-all" style={{ width: `${hPct}%`, background: winnerHome ? "#A3E635" : "rgba(163,230,53,0.4)" }}/>
        <div className="transition-all" style={{ width: `${aPct}%`, background: winnerAway ? "#7DD3FC" : "rgba(125,211,252,0.4)" }}/>
      </div>
    </div>
  );
}

/**
 * Per-period score box (Q1 Q2 Q3 Q4 / sets / innings)
 *   <ScoreBox periods={[{home:22,away:35},{home:31,away:25}...]} />
 */
export function ScoreBox({ periods = [], total = null, labelPrefix = "Q" }) {
  if (!periods.length) return null;
  return (
    <div className="cp-surface p-3" data-testid="score-box">
      <div className="grid gap-1 text-center text-xs" style={{ gridTemplateColumns: `repeat(${periods.length}, 1fr)` }}>
        {periods.map((_, i) => (
          <div key={i} className="text-[10px] uppercase" style={{ color: "var(--cp-text-muted)" }}>{labelPrefix}{i + 1}</div>
        ))}
      </div>
      <div className="grid gap-1 text-center mt-1" style={{ gridTemplateColumns: `repeat(${periods.length}, 1fr)` }}>
        {periods.map((p, i) => (
          <div key={`h${i}`} className="tabular-nums text-sm font-bold">{p.home_score ?? p.home ?? "—"}</div>
        ))}
      </div>
      <div className="grid gap-1 text-center mt-0.5" style={{ gridTemplateColumns: `repeat(${periods.length}, 1fr)` }}>
        {periods.map((p, i) => (
          <div key={`a${i}`} className="tabular-nums text-sm font-bold" style={{ color: "var(--cp-text-muted)" }}>{p.away_score ?? p.away ?? "—"}</div>
        ))}
      </div>
    </div>
  );
}
