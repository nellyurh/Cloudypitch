import React from "react";
import { AlertTriangle } from "lucide-react";

/**
 * Sidelined / Injuries card — surfaced inside the Lineups tab.
 * `players` is an array of {player_id, player_name, player_image, team_id, reason}.
 */
const SidelinedCard = ({ players = [], homeTeamId, awayTeamId, homeTeamName, awayTeamName }) => {
  if (!Array.isArray(players) || players.length === 0) return null;
  const home = players.filter(p => p.team_id === homeTeamId);
  const away = players.filter(p => p.team_id === awayTeamId);
  const Side = ({ rows, name, accent }) => rows.length === 0 ? null : (
    <div>
      <div className="text-[10px] uppercase tracking-widest mb-1.5 flex items-center gap-1" style={{ color: accent }}>
        <AlertTriangle size={10}/> {name} · {rows.length} sidelined
      </div>
      <ul className="space-y-1">
        {rows.map((p, i) => (
          <li key={i} className="flex items-center gap-2 px-2 py-1.5 rounded text-xs" style={{ background: "var(--cp-surface-2)" }} data-testid={`sidelined-${p.player_id}`}>
            {p.player_image ? (
              <img src={p.player_image} className="w-6 h-6 rounded-full object-cover" alt="" onError={(e)=>{e.target.style.display="none"}}/>
            ) : <div className="w-6 h-6 rounded-full cp-logo-circle text-[9px] font-extrabold">{(p.player_name || "?").split(" ").map(s => s[0]).slice(0, 2).join("")}</div>}
            <span className="font-bold flex-1 truncate">{p.player_name || "Unknown"}</span>
            <span className="text-[10px]" style={{ color: "var(--cp-text-muted)" }}>{p.reason}</span>
          </li>
        ))}
      </ul>
    </div>
  );
  return (
    <div className="cp-surface p-3 mt-3" data-testid="sidelined-card">
      <div className="text-sm font-extrabold mb-2 inline-flex items-center gap-1.5">
        <AlertTriangle size={14} className="text-rose-400"/> Injuries & Suspensions
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Side rows={home} name={homeTeamName || "Home"} accent="#A3E635"/>
        <Side rows={away} name={awayTeamName || "Away"} accent="#7DD3FC"/>
      </div>
    </div>
  );
};

export default SidelinedCard;
