import React from "react";
import { Goal, Square, RectangleHorizontal, ArrowLeftRight, ShieldAlert, Footprints, AlertCircle } from "lucide-react";

const ICONS = {
  "Goal": <Goal size={14} className="text-cp-lime" />,
  "Own Goal": <Goal size={14} className="text-orange-400" />,
  "Owngoal": <Goal size={14} className="text-orange-400" />,
  "Penalty": <Goal size={14} className="text-cp-lime" />,
  "Missed Penalty": <ShieldAlert size={14} className="text-orange-400" />,
  "Penalty Shootout Goal": <Goal size={14} className="text-cp-lime" />,
  "Pen. Shootout Goal": <Goal size={14} className="text-cp-lime" />,
  "Penalty Shootout Miss": <ShieldAlert size={14} className="text-orange-400" />,
  "Pen. Shootout Miss": <ShieldAlert size={14} className="text-orange-400" />,
  "Yellow Card": <Square size={14} className="fill-yellow-400 text-yellow-400" />,
  "Yellowcard": <Square size={14} className="fill-yellow-400 text-yellow-400" />,
  "Red Card": <Square size={14} className="fill-red-500 text-red-500" />,
  "Redcard": <Square size={14} className="fill-red-500 text-red-500" />,
  "Yellow-Red Card": <Square size={14} className="fill-orange-400 text-orange-400" />,
  "Yellowred Card": <Square size={14} className="fill-orange-400 text-orange-400" />,
  "Substitution": <ArrowLeftRight size={14} className="text-sky-400" />,
  "VAR": <AlertCircle size={14} className="text-purple-400" />,
  "Var Card": <AlertCircle size={14} className="text-purple-400" />,
  "VAR Goal Cancelled": <AlertCircle size={14} className="text-red-400" />,
  "Var Goal Cancelled": <AlertCircle size={14} className="text-red-400" />,
};

// Pretty-print Sportmonks raw names like "Yellowcard" → "Yellow Card"
const PRETTY = {
  "Yellowcard": "Yellow Card",
  "Redcard": "Red Card",
  "Owngoal": "Own Goal",
  "Yellowred Card": "Yellow-Red Card",
};

const iconFor = (type) => ICONS[type] || <Footprints size={14} className="text-gray-400" />;
const prettyType = (type) => PRETTY[type] || type;

export default function EventsList({ events, homeTeamId, awayTeamId, homeName, awayName }) {
  if (!events || events.length === 0) {
    return <div className="text-sm" style={{ color: "var(--cp-text-muted)" }}>No events yet.</div>;
  }
  return (
    <ul className="space-y-1" data-testid="events-list">
      {events.map((e, i) => {
        const isHome = e.team_id && e.team_id === homeTeamId;
        const isAway = e.team_id && e.team_id === awayTeamId;
        const typeName = prettyType(e.type);
        // Sub formatting
        const isSub = typeName === "Substitution";
        const displayPlayer = e.player_name || e.detail || "";
        const assist = e.assist_player_name;
        return (
          <li
            key={i}
            className="grid grid-cols-[1fr_auto_1fr] items-center gap-2 text-sm py-1.5 border-b"
            style={{ borderColor: "var(--cp-border)" }}
            data-testid={`event-${i}`}
          >
            {/* Home side */}
            <div className="text-right pr-2">
              {isHome && (
                <div className="inline-flex items-center gap-2 justify-end">
                  <div className="text-right">
                    <div className="font-medium">{displayPlayer}</div>
                    {assist && (
                      <div className="text-[11px]" style={{ color: "var(--cp-text-muted)" }}>
                        {isSub ? `↓ ${assist}` : `assist: ${assist}`}
                      </div>
                    )}
                  </div>
                  {iconFor(e.type)}
                </div>
              )}
            </div>
            {/* Minute marker */}
            <div className="text-center min-w-[44px]">
              <span className="px-2 py-0.5 rounded text-[11px] font-bold tabular-nums"
                    style={{ background: "var(--cp-surface-2)", color: "var(--cp-text)" }}>
                {e.minute != null ? `${e.minute}${e.extra_minute ? "+" + e.extra_minute : ""}'` : "—"}
              </span>
            </div>
            {/* Away side */}
            <div className="text-left pl-2">
              {isAway && (
                <div className="inline-flex items-center gap-2">
                  {iconFor(e.type)}
                  <div className="text-left">
                    <div className="font-medium">{displayPlayer}</div>
                    {assist && (
                      <div className="text-[11px]" style={{ color: "var(--cp-text-muted)" }}>
                        {isSub ? `↓ ${assist}` : `assist: ${assist}`}
                      </div>
                    )}
                  </div>
                </div>
              )}
              {!isHome && !isAway && (
                <div className="text-xs" style={{ color: "var(--cp-text-muted)" }}>{typeName} — {displayPlayer}</div>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
