import React, { useEffect, useState } from "react";
import api from "../../lib/api";
import { Activity } from "lucide-react";

/**
 * Attack-momentum chart — green bars up = home pressure, blue bars down = away
 * pressure, like Sofascore. Pulls from /api/matches/{id}/momentum which sources
 * Sportmonks `pressure[]` (Pro plan).
 */
const AttackMomentum = ({ matchId, homeTeamId }) => {
  const [data, setData] = useState(null);
  useEffect(() => {
    let mounted = true;
    api.get(`/matches/${matchId}/momentum`)
      .then(({ data }) => { if (mounted) setData(data); })
      .catch(() => mounted && setData({ momentum: [] }));
    return () => { mounted = false; };
  }, [matchId]);
  if (data === null) return null;
  const series = data.momentum || [];
  if (!series.length) {
    return (
      <div className="cp-surface p-3" data-testid="momentum-empty">
        <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Attack momentum</div>
        <div className="flex items-center gap-2 mt-2 text-[10px]" style={{ color: "var(--cp-text-muted)" }}>
          <Activity size={12}/> Will appear minute-by-minute once play starts
        </div>
      </div>
    );
  }
  // Normalise to per-minute home/away values
  const byMin = {};
  for (const p of series) {
    const min = Number(p.minute) || 0;
    if (!byMin[min]) byMin[min] = { home: 0, away: 0 };
    const isHome = p.team_id === (data.home_team_id || homeTeamId);
    const v = Math.max(0, Math.min(100, Number(p.value) || 0));
    if (isHome) byMin[min].home = Math.max(byMin[min].home, v);
    else byMin[min].away = Math.max(byMin[min].away, v);
  }
  const minutes = Object.keys(byMin).map(Number).sort((a, b) => a - b);
  const max = minutes[minutes.length - 1] || 90;
  const w = 220, h = 60, mid = h / 2;
  const barW = w / Math.max(45, max + 1);
  return (
    <div className="cp-surface p-3" data-testid="attack-momentum">
      <div className="flex items-center justify-between mb-1">
        <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Attack momentum</div>
        <div className="flex items-center gap-2 text-[9px]">
          <span className="inline-flex items-center gap-1"><span className="w-2 h-2 rounded-sm" style={{ background: "#A3E635" }}/>Home</span>
          <span className="inline-flex items-center gap-1"><span className="w-2 h-2 rounded-sm" style={{ background: "#7DD3FC" }}/>Away</span>
        </div>
      </div>
      <svg width={w} height={h} className="block">
        <line x1="0" y1={mid} x2={w} y2={mid} stroke="rgba(255,255,255,0.1)" strokeWidth="0.5"/>
        {minutes.map((m, i) => {
          const x = (m / Math.max(45, max + 1)) * w;
          const homeH = (byMin[m].home / 100) * (mid - 2);
          const awayH = (byMin[m].away / 100) * (mid - 2);
          return (
            <g key={i}>
              <rect x={x} y={mid - homeH} width={Math.max(1, barW - 0.5)} height={homeH} fill="#A3E635" opacity="0.85"/>
              <rect x={x} y={mid} width={Math.max(1, barW - 0.5)} height={awayH} fill="#7DD3FC" opacity="0.85"/>
            </g>
          );
        })}
        {/* HT marker at 45' */}
        <line x1={(45 / Math.max(45, max + 1)) * w} y1="0" x2={(45 / Math.max(45, max + 1)) * w} y2={h} stroke="rgba(255,255,255,0.2)" strokeWidth="0.5" strokeDasharray="2,2"/>
      </svg>
      <div className="flex justify-between text-[9px] mt-0.5" style={{ color: "var(--cp-text-muted)" }}>
        <span>0'</span><span>HT</span><span>{max}'</span>
      </div>
    </div>
  );
};

export default AttackMomentum;
