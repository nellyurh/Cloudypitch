import React from "react";
import { Goal, Square, ArrowLeftRight, ShieldAlert, Footprints, AlertCircle } from "lucide-react";

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

const PRETTY = {
  "Yellowcard": "Yellow Card",
  "Redcard": "Red Card",
  "Owngoal": "Own Goal",
  "Yellowred Card": "Yellow-Red Card",
};

const iconFor = (type) => ICONS[type] || <Footprints size={14} className="text-gray-400" />;
const prettyType = (type) => PRETTY[type] || type;
const isGoal = (t) => /goal|penalty/i.test(t) && !/missed|cancelled|miss$/i.test(t);

/**
 * Sofascore-style vertical timeline rail.
 * Center column = vertical line + minute marker pill.
 * Home events align right of the rail; away events align left.
 */
export default function EventsList({ events, homeTeamId, awayTeamId, homeName, awayName }) {
  if (!events || events.length === 0) {
    return <div className="text-sm" style={{ color: "var(--cp-text-muted)" }}>No events yet.</div>;
  }

  return (
    <div className="relative" data-testid="events-list">
      {/* Header labels */}
      <div className="grid grid-cols-[1fr_auto_1fr] items-center text-[10px] uppercase tracking-[0.1em] font-semibold mb-4 pb-3 border-b"
           style={{ color: "var(--cp-text-muted)", borderColor: "var(--cp-border)" }}>
        <div className="text-right text-cp-lime">{homeName}</div>
        <div className="px-3 opacity-60">min</div>
        <div className="text-left" style={{ color: "#94A3B8" }}>{awayName}</div>
      </div>

      <div className="relative">
        {/* Vertical rail line */}
        <div
          aria-hidden
          className="absolute top-0 bottom-0 left-1/2 -translate-x-1/2 w-px"
          style={{ background: "var(--cp-border)" }}
        />

        <ul className="space-y-3">
          {events.map((e, i) => {
            const isHome = e.team_id && e.team_id === homeTeamId;
            const isAway = e.team_id && e.team_id === awayTeamId;
            const typeName = prettyType(e.type);
            const isSub = typeName === "Substitution";
            const goal = isGoal(typeName);
            const displayPlayer = e.player_name || e.detail || "";
            const assist = e.assist_player_name;
            const minuteLabel = e.minute != null ? `${e.minute}${e.extra_minute ? "+" + e.extra_minute : ""}'` : "—";

            return (
              <li
                key={i}
                className="grid grid-cols-[1fr_auto_1fr] items-center gap-3"
                data-testid={`event-${i}`}
              >
                {/* Home side */}
                <div className="text-right pr-2">
                  {isHome && (
                    <div className="inline-flex items-start gap-2 justify-end max-w-full" title={typeName}>
                      <div className="text-right min-w-0">
                        <div className={`font-semibold text-sm truncate ${goal ? "text-cp-lime" : "text-slate-100"}`}>
                          {displayPlayer}
                        </div>
                        {assist ? (
                          <div className="text-[11px] truncate" style={{ color: "var(--cp-text-muted)" }}>
                            {isSub ? `↓ ${assist}` : `assist: ${assist}`}
                          </div>
                        ) : (
                          <div className="text-[10px] uppercase tracking-wider" style={{ color: "var(--cp-text-muted)" }}>
                            {typeName}
                          </div>
                        )}
                      </div>
                      <span className="shrink-0 mt-0.5">{iconFor(typeName)}</span>
                    </div>
                  )}
                </div>

                {/* Center: minute pill on rail */}
                <div className="relative flex items-center justify-center">
                  <span
                    className="relative z-10 px-2 py-0.5 rounded-full text-[11px] font-mono font-bold tabular-nums border min-w-[42px] text-center"
                    style={{
                      background: goal ? "rgba(163,230,53,0.12)" : "var(--cp-surface, #1C2026)",
                      borderColor: goal ? "rgba(163,230,53,0.4)" : "var(--cp-border, #2A2E36)",
                      color: goal ? "#A3E635" : "var(--cp-text, #F8FAFC)",
                    }}
                  >
                    {minuteLabel}
                  </span>
                </div>

                {/* Away side */}
                <div className="text-left pl-2">
                  {isAway && (
                    <div className="inline-flex items-start gap-2 max-w-full" title={typeName}>
                      <span className="shrink-0 mt-0.5">{iconFor(typeName)}</span>
                      <div className="text-left min-w-0">
                        <div className={`font-semibold text-sm truncate ${goal ? "text-cp-lime" : "text-slate-100"}`}>
                          {displayPlayer}
                        </div>
                        {assist ? (
                          <div className="text-[11px] truncate" style={{ color: "var(--cp-text-muted)" }}>
                            {isSub ? `↓ ${assist}` : `assist: ${assist}`}
                          </div>
                        ) : (
                          <div className="text-[10px] uppercase tracking-wider" style={{ color: "var(--cp-text-muted)" }}>
                            {typeName}
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
      </div>
    </div>
  );
}
