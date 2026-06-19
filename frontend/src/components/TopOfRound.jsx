import React, { useEffect, useState } from "react";
import api from "../lib/api";
import { Trophy } from "lucide-react";

/* Renders the top-5 main squads for a single WC round (by round_points).
 * Mounted under the main-team pitch and re-fetches whenever the active
 * round (`round` prop) changes. Uses ISO-2 country codes to render flag
 * emojis without bundling an image set. */
function flagFromCC(cc) {
  if (!cc || cc.length !== 2) return "🏳️";
  try {
    const base = 127397;
    return String.fromCodePoint(base + cc.charCodeAt(0)) +
           String.fromCodePoint(base + cc.charCodeAt(1));
  } catch { return "🏳️"; }
}

export default function TopOfRound({ round }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [meta, setMeta] = useState({ matches_in_round: 0, squads_scanned: 0 });

  useEffect(() => {
    if (!round) return;
    let alive = true;
    setLoading(true);
    api.get(`/fantasy/leaderboard/round`, { params: { round, limit: 5 } })
      .then(({ data }) => {
        if (!alive) return;
        setRows(data.leaderboard || []);
        setMeta({
          matches_in_round: data.matches_in_round || 0,
          squads_scanned: data.squads_scanned || 0,
        });
      })
      .catch(() => alive && setRows([]))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [round]);

  if (!round) return null;

  return (
    <div className="cp-surface p-3 mt-3" data-testid="top-of-round-leaderboard">
      <div className="flex items-center gap-2 mb-2">
        <Trophy size={14} className="text-cp-lime" />
        <h3 className="text-[11px] font-extrabold uppercase tracking-widest">
          Top of {round}
        </h3>
        <span className="ml-auto text-[10px]" style={{ color: "var(--cp-text-muted)" }}>
          {meta.matches_in_round} matches · {meta.squads_scanned} squads
        </span>
      </div>

      {loading && rows.length === 0 ? (
        <div className="text-[11px] py-3 text-center" style={{ color: "var(--cp-text-muted)" }}>
          Crunching round points…
        </div>
      ) : rows.length === 0 ? (
        <div className="text-[11px] py-3 text-center" style={{ color: "var(--cp-text-muted)" }}>
          No squads scored this round yet.
        </div>
      ) : (
        <ol className="space-y-1">
          {rows.map((r) => (
            <li
              key={r.squad_id}
              data-testid={`top-of-round-row-${r.rank}`}
              className="flex items-center gap-2 text-xs px-2 py-1.5 rounded"
              style={{
                background: r.rank === 1 ? "rgba(163,230,53,0.10)" : "var(--cp-surface-2)",
                border: r.rank === 1 ? "1px solid rgba(163,230,53,0.35)" : "1px solid transparent",
              }}
            >
              <span
                className="w-5 text-center font-extrabold tabular-nums"
                style={{ color: r.rank <= 3 ? "var(--cp-lime)" : "var(--cp-text-muted)" }}
              >
                {r.rank}
              </span>
              <span className="text-base leading-none">{flagFromCC(r.country_code)}</span>
              <span className="flex-1 min-w-0 truncate font-bold">
                {r.display_name}
              </span>
              <span className="text-[10px] truncate max-w-[35%]" style={{ color: "var(--cp-text-muted)" }}>
                {r.squad_name}
              </span>
              <span className="font-extrabold tabular-nums">{r.round_points}</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
