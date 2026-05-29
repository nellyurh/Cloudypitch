import React from "react";
import { MessageSquare, Target } from "lucide-react";

/**
 * Commentary tab — minute-by-minute feed from Sportmonks `comments`.
 * Goals get a green-tinted background; important moments get a left lime border.
 */
const Commentary = ({ comments = [], homeTeamName, awayTeamName }) => {
  if (!Array.isArray(comments) || comments.length === 0) {
    return (
      <div className="text-center text-sm py-6" style={{ color: "var(--cp-text-muted)" }} data-testid="commentary-empty">
        <MessageSquare size={24} className="mx-auto opacity-60 mb-2"/>
        No commentary yet. Live updates appear minute-by-minute once play starts.
      </div>
    );
  }
  // Newest first (highest minute or highest order)
  const sorted = [...comments].sort((a, b) => {
    const am = (a.minute ?? 0) * 100 + (a.extra_minute ?? 0);
    const bm = (b.minute ?? 0) * 100 + (b.extra_minute ?? 0);
    if (am !== bm) return bm - am;
    return (b.order ?? 0) - (a.order ?? 0);
  });
  return (
    <ul className="space-y-1.5" data-testid="commentary-list">
      {sorted.map((c, i) => {
        const minLabel = c.minute != null ? `${c.minute}${c.extra_minute ? `+${c.extra_minute}` : ""}'` : "—";
        const goal = c.is_goal;
        const important = c.is_important;
        return (
          <li
            key={i}
            className="flex items-start gap-2 px-3 py-2 rounded"
            style={{
              background: goal ? "rgba(163,230,53,0.12)" : important ? "rgba(125,211,252,0.08)" : "var(--cp-surface)",
              borderLeft: goal ? "3px solid #A3E635" : important ? "3px solid #7DD3FC" : "3px solid transparent",
            }}
            data-testid={`commentary-row-${i}`}
          >
            <span className="text-[10px] font-extrabold tabular-nums shrink-0 mt-0.5" style={{ color: goal ? "#A3E635" : "var(--cp-text-muted)" }}>{minLabel}</span>
            {goal && <Target size={12} className="text-cp-lime shrink-0 mt-0.5"/>}
            <span className="text-xs flex-1 leading-snug">{c.text}</span>
          </li>
        );
      })}
    </ul>
  );
};

export default Commentary;
