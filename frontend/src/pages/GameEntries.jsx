import React, { useEffect, useState, useMemo } from "react";
import { useParams, Link } from "react-router-dom";
import api from "../lib/api";
import { Trophy, ChevronDown, ChevronRight, ShieldCheck, Star, Lock } from "lucide-react";

const fmt = (n) => (Math.round((n || 0) * 10) / 10).toFixed(1);
const POSITION_ORDER = { GK: 0, DEF: 1, MID: 2, FWD: 3, ATT: 3 };

export default function GameEntries() {
  const { gameId } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState({});

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const { data: d } = await api.get(`/wc/games/${gameId}/entries?limit=200`);
        if (mounted) setData(d);
      } catch (e) {
        if (mounted) setError(e?.response?.data?.detail || e.message);
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, [gameId]);

  if (loading) {
    return <div className="max-w-[1100px] mx-auto p-4 text-sm" style={{ color: "var(--cp-text-muted)" }} data-testid="game-entries-loading">Loading entries…</div>;
  }
  if (error) {
    return <div className="max-w-[1100px] mx-auto p-4 text-sm text-red-400" data-testid="game-entries-error">Error: {error}</div>;
  }
  if (!data?.visible) {
    return (
      <div className="max-w-[1100px] mx-auto p-4" data-testid="game-entries-hidden">
        <div className="cp-surface p-5 flex items-start gap-3">
          <Lock size={20} className="text-cp-lime mt-0.5"/>
          <div>
            <div className="font-extrabold mb-1">Entries hidden</div>
            <div className="text-sm" style={{ color: "var(--cp-text-muted)" }}>
              {data?.reason || "Game not yet settled — entries open once all match results are final."}
            </div>
            {data?.game?.closes_at && (
              <div className="text-xs mt-2" style={{ color: "var(--cp-text-muted)" }}>
                Closes: {new Date(data.game.closes_at).toLocaleString()}
              </div>
            )}
            <Link to="/fantasy" className="inline-block mt-3 text-xs font-bold underline">← Back to mini-games</Link>
          </div>
        </div>
      </div>
    );
  }

  const entries = data.entries || [];
  const game = data.game || {};

  return (
    <div className="max-w-[1100px] mx-auto p-3 md:p-5" data-testid="game-entries-page">
      <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
        <div>
          <h1 className="text-xl md:text-2xl font-extrabold flex items-center gap-2">
            <Trophy size={20} className="text-cp-lime"/>
            Mini-game entries
          </h1>
          <div className="text-[11px] mt-1" style={{ color: "var(--cp-text-muted)" }}>
            {game.game_type === "group" ? `Group ${game.group_letter} · MD${game.matchday}` : (game.game_type || "Game")}
            {" · "}{entries.length} squad{entries.length === 1 ? "" : "s"} settled
          </div>
        </div>
        <Link to="/fantasy" className="text-xs font-bold underline" data-testid="back-to-mini-games">← Back</Link>
      </div>

      {entries.length === 0 ? (
        <div className="cp-surface p-5 text-sm" style={{ color: "var(--cp-text-muted)" }}>
          No squads were entered into this game.
        </div>
      ) : (
        <div className="space-y-2" data-testid="entries-list">
          {entries.map((e) => (
            <EntryRow
              key={e.user_id}
              entry={e}
              open={!!expanded[e.user_id]}
              onToggle={() => setExpanded((m) => ({ ...m, [e.user_id]: !m[e.user_id] }))}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function EntryRow({ entry, open, onToggle }) {
  // Build a points lookup keyed on player_id for fast joining onto the squad
  const breakdown = useMemo(() => {
    const map = {};
    for (const b of entry.breakdown_by_player || []) {
      if (b.player_id) map[b.player_id] = b;
    }
    return map;
  }, [entry]);

  // Group squad rows by position for the open view
  const squadByPos = useMemo(() => {
    const groups = { GK: [], DEF: [], MID: [], FWD: [] };
    for (const p of entry.players || []) {
      const pos = (p.position_in_squad || p.position || "MID").toUpperCase();
      const key = pos === "ATT" ? "FWD" : pos;
      (groups[key] || groups.MID).push(p);
    }
    return groups;
  }, [entry]);

  // Per-team points totals (the user's specific ask)
  const teamTotals = useMemo(() => {
    const sums = {};
    for (const b of entry.breakdown_by_player || []) {
      const tid = b.team_id || "—";
      sums[tid] = sums[tid] || { team_id: tid, points: 0, players: 0, team_name: null };
      sums[tid].points += b.points || 0;
      sums[tid].players += 1;
    }
    // Resolve team_name from squad
    for (const p of entry.players || []) {
      if (p.team_id && sums[p.team_id] && !sums[p.team_id].team_name) {
        sums[p.team_id].team_name = p.team_name || p.country;
      }
    }
    return Object.values(sums).sort((a, b) => b.points - a.points);
  }, [entry]);

  return (
    <div className="cp-surface" data-testid={`entry-row-${entry.user_id}`}>
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 p-3 text-left"
        data-testid={`entry-toggle-${entry.user_id}`}
      >
        <div className="text-xs font-extrabold tabular-nums w-8 text-cp-lime">#{entry.rank}</div>
        <div className="flex-1 min-w-0">
          <div className="font-bold text-sm truncate flex items-center gap-2">
            {entry.display_name}
            {entry.is_premium && <ShieldCheck size={12} className="text-cp-lime"/>}
          </div>
          <div className="text-[10px]" style={{ color: "var(--cp-text-muted)" }}>
            {entry.country_code} · {(entry.players || []).length} players
            {entry.points_multiplier_applied !== 1 && entry.points_multiplier_applied && (
              <> · ×{entry.points_multiplier_applied} stage mult</>
            )}
          </div>
        </div>
        <div className="text-right">
          <div className="font-extrabold tabular-nums text-lg leading-none">{entry.points_scored}</div>
          <div className="text-[9px] uppercase tracking-wider" style={{ color: "var(--cp-text-muted)" }}>pts</div>
        </div>
        {open ? <ChevronDown size={16}/> : <ChevronRight size={16}/>}
      </button>

      {open && (
        <div className="border-t" style={{ borderColor: "var(--cp-border)" }}>
          {/* Per-team breakdown */}
          {teamTotals.length > 0 && (
            <div className="p-3 border-b" style={{ borderColor: "var(--cp-border)" }} data-testid={`entry-team-totals-${entry.user_id}`}>
              <div className="text-[10px] uppercase tracking-wider font-bold mb-2" style={{ color: "var(--cp-text-muted)" }}>
                Points by team (this round only)
              </div>
              <div className="flex flex-wrap gap-2">
                {teamTotals.map((t) => (
                  <div
                    key={t.team_id}
                    className="rounded px-2 py-1 text-xs flex items-center gap-2"
                    style={{ background: "var(--cp-surface-2)" }}
                    data-testid={`team-total-${entry.user_id}-${t.team_id}`}
                  >
                    <span className="font-bold">{t.team_name || t.team_id}</span>
                    <span className="tabular-nums" style={{ color: "var(--cp-lime)" }}>{t.points}</span>
                    <span className="text-[9px]" style={{ color: "var(--cp-text-muted)" }}>({t.players}p)</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Position-grouped squad list with per-player points */}
          <div className="p-3 space-y-3">
            {["GK", "DEF", "MID", "FWD"].map((pos) => {
              const rows = (squadByPos[pos] || []).slice().sort((a, b) => {
                const ap = breakdown[a.id]?.points || 0;
                const bp = breakdown[b.id]?.points || 0;
                return bp - ap;
              });
              if (rows.length === 0) return null;
              return (
                <div key={pos}>
                  <div className="text-[9px] font-extrabold uppercase tracking-widest mb-1" style={{ color: "var(--cp-text-muted)" }}>{pos}</div>
                  <div className="space-y-1">
                    {rows.map((p) => {
                      const b = breakdown[p.id] || {};
                      const isCap = p.id === entry.captain_player_id;
                      const isVice = p.id === entry.vice_captain_player_id;
                      return (
                        <div
                          key={p.id}
                          className="flex items-center gap-2 py-1 px-2 rounded"
                          style={{ background: "var(--cp-surface-2)" }}
                          data-testid={`pick-row-${entry.user_id}-${p.id}`}
                        >
                          <div className="flex-1 min-w-0">
                            <div className="text-xs font-bold truncate flex items-center gap-1.5">
                              {p.name || "—"}
                              {isCap && <span className="px-1 rounded text-[9px] font-extrabold" style={{ background: "var(--cp-lime)", color: "var(--cp-forest)" }}>C</span>}
                              {isVice && <span className="px-1 rounded text-[9px] font-extrabold" style={{ background: "var(--cp-border)", color: "var(--cp-text)" }}>V</span>}
                              {b.card_boost > 0 && <Star size={10} className="text-cp-lime"/>}
                            </div>
                            <div className="text-[10px] tabular-nums" style={{ color: "var(--cp-text-muted)" }}>
                              {p.team_name || p.country || "—"}
                              {b.minutes ? <> · {b.minutes}'</> : null}
                              {b.base_points ? <> · base {b.base_points}</> : null}
                              {b.multiplier && b.multiplier !== 1 ? <> · ×{b.multiplier}</> : null}
                            </div>
                          </div>
                          <div className="text-right tabular-nums">
                            <div className="text-sm font-extrabold" style={{ color: (b.points || 0) > 0 ? "var(--cp-lime)" : "var(--cp-text)" }}>
                              {b.points ?? 0}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
