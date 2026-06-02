import React, { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../lib/auth";
import { CheckCircle2, X, Search, ChevronLeft, Trophy, Save, Zap } from "lucide-react";

const POSITIONS = ["GK", "DEF", "MID", "FWD"];
const SQUAD_PROFILES = {
  "15": { total: 15, budget: 100, slots: { GK: 2, DEF: 5, MID: 5, FWD: 3 } },
  "20": { total: 20, budget: 120, slots: { GK: 3, DEF: 7, MID: 6, FWD: 4 } },
};
const POS_LABEL = { GK: "Goalkeepers", DEF: "Defenders", MID: "Midfielders", FWD: "Forwards" };
const POS_COLOR = { GK: "#FFC857", DEF: "#A3E635", MID: "#7DD3FC", FWD: "#FB7185" };

const fmt = (n) => `£${(n || 0).toFixed(1)}`;

function Jersey({ color = "#A3E635", size = 44 }) {
  return (
    <svg viewBox="0 0 64 64" width={size} height={size} aria-hidden>
      <path
        d="M14 8 L24 4 C28 8 36 8 40 4 L50 8 L58 18 L50 24 L48 22 L48 56 C48 58 46 60 44 60 L20 60 C18 60 16 58 16 56 L16 22 L14 24 L6 18 Z"
        fill={color} stroke="rgba(0,0,0,0.35)" strokeWidth="1.6"
      />
      <path d="M16 30 L48 30" stroke="rgba(255,255,255,0.6)" strokeWidth="2"/>
    </svg>
  );
}

/** A pitch slot — either populated or an empty "+ add" tile */
function PitchSlot({ pos, picked, onPick, onRemove }) {
  if (!picked) {
    return (
      <button
        onClick={() => onPick(pos)}
        className="flex flex-col items-center min-w-0 w-full max-w-[88px] gap-1 hover:scale-105 transition"
        data-testid={`pitch-slot-empty-${pos}`}
      >
        <span
          className="rounded-md flex items-center justify-center text-cp-forest font-extrabold text-lg shadow"
          style={{ width: 42, height: 50, background: "rgba(255,255,255,0.85)", border: "2px dashed rgba(255,255,255,0.7)" }}
        >
          +
        </span>
        <span className="text-[9px] font-bold px-1 rounded text-center" style={{ background: "rgba(0,0,0,0.55)", color: "#fff" }}>
          {pos}
        </span>
      </button>
    );
  }
  const lastName = (picked.name || "?").split(" ").slice(-1)[0];
  return (
    <div className="flex flex-col items-center min-w-0 max-w-[90px] w-full" data-testid={`pitch-slot-${picked.id}`}>
      <button onClick={() => onRemove(picked)} className="relative hover:scale-105 transition" title="Remove">
        <Jersey color={POS_COLOR[pos]} size={42}/>
        {picked.shirt_number && (
          <span className="absolute inset-0 flex items-center justify-center text-[11px] font-extrabold text-cp-forest pointer-events-none" style={{ paddingTop: 6 }}>
            {picked.shirt_number}
          </span>
        )}
      </button>
      <div className="mt-0.5 w-full max-w-[88px]">
        <div className="text-[9px] font-extrabold leading-tight px-1 py-0.5 rounded-t truncate text-center" style={{ background: "#FFFFFF", color: "#1A1F26" }}>
          {lastName}
        </div>
        <div className="text-[8px] font-medium leading-tight px-1 py-0.5 rounded-b truncate text-center" style={{ background: "#F1F4EF", color: "#475569" }}>
          {fmt(picked.price)}
        </div>
      </div>
    </div>
  );
}

/** Build A Team — focused page, only the squad-build UI. */
export default function BuildTeam() {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  // ?mode=15 (default, 15 players £100m) | ?mode=20 (20 players £120m for >2-team games)
  const mode = searchParams.get("mode") === "20" ? "20" : "15";
  const profile = SQUAD_PROFILES[mode];
  const POS_LIMIT = profile.slots;
  const BUDGET = profile.budget;
  const [players, setPlayers] = useState([]);
  const [squad, setSquad] = useState([]);
  const [view, setView] = useState("pitch");
  const [pickerPos, setPickerPos] = useState(null);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState(null);
  const [benchBoost, setBenchBoost] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/fantasy/players?wc=true&limit=2000");
        setPlayers(data.players || []);
      } catch (_) {}
    })();
  }, []);

  // Load existing squad
  useEffect(() => {
    if (!user) return;
    (async () => {
      try {
        const { data } = await api.get("/fantasy/squad");
        if (data?.squad?.players) {
          setSquad(data.squad.players.map(sp => ({
            ...players.find(p => p.id === sp.player_id),
            ...sp,
            id: sp.player_id,
          })).filter(p => p.position));
        }
      } catch (_) {}
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, players.length]);

  const counts = useMemo(() => {
    const c = { GK: 0, DEF: 0, MID: 0, FWD: 0 };
    squad.forEach(p => { if (c[p.position] != null) c[p.position] += 1; });
    return c;
  }, [squad]);
  const totalSpent = useMemo(() => squad.reduce((s, p) => s + (p.price || 0), 0), [squad]);
  const remaining = BUDGET - totalSpent;
  const totalCount = squad.length;
  const isFull = totalCount === profile.total;

  const addPlayer = (p) => {
    if (squad.find(x => x.id === p.id)) return;
    if (counts[p.position] >= POS_LIMIT[p.position]) return;
    if (totalSpent + p.price > BUDGET) return;
    setSquad([...squad, p]);
    setPickerPos(null);
  };
  const removePlayer = (p) => setSquad(squad.filter(x => x.id !== p.id));

  const saveSquad = async () => {
    setSaving(true);
    try {
      await api.post("/fantasy/squad", {
        players: squad.map(p => ({ player_id: p.id, position: p.position, is_captain: false, is_vice: false })),
        mode,
        bench_boost: benchBoost,
      });
      setSavedAt(new Date());
    } catch (e) {
      alert(e?.response?.data?.detail || "Save failed");
    }
    setSaving(false);
  };

  return (
    <div className="max-w-[1400px] mx-auto p-3 md:p-5" data-testid="build-team-page">
      <div className="flex items-center justify-between gap-3 flex-wrap mb-3">
        <div className="flex items-center gap-2">
          <h1 className="text-xl md:text-2xl font-extrabold">Build a Team</h1>
          <span className="text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider" style={{ background: "var(--cp-surface-2)", color: "var(--cp-text-muted)" }}>
            {profile.total}-man · £{profile.budget}m
          </span>
        </div>
        <div className="flex items-center gap-2">
          {mode === "20" && (
            <button
              onClick={() => setBenchBoost(!benchBoost)}
              className={`px-2.5 py-1.5 rounded text-xs font-bold flex items-center gap-1 ${benchBoost ? "bg-cp-lime text-cp-forest" : ""}`}
              style={!benchBoost ? { background: "var(--cp-surface-2)" } : {}}
              data-testid="bench-boost-toggle"
              title="Bench Boost — bench players also score this game"
            >
              <Zap size={12}/> Bench Boost
            </button>
          )}
          <div className="flex items-center gap-1 cp-surface p-1 text-xs" role="tablist">
            <button onClick={() => setView("pitch")} className={`px-3 py-1.5 rounded ${view === "pitch" ? "bg-cp-lime text-cp-forest font-bold" : "hover:bg-white/5"}`} data-testid="view-pitch">Pitch</button>
            <button onClick={() => setView("list")}  className={`px-3 py-1.5 rounded ${view === "list"  ? "bg-cp-lime text-cp-forest font-bold" : "hover:bg-white/5"}`} data-testid="view-list">List</button>
          </div>
        </div>
      </div>

      {/* Budget header */}
      <div className="cp-surface p-3 mb-3 grid grid-cols-3 md:grid-cols-4 gap-2 text-center" data-testid="budget-bar">
        <Stat label="Players" value={`${totalCount}/${profile.total}`} tone={isFull ? "good" : "warn"}/>
        <Stat label="Spent"   value={fmt(totalSpent)}/>
        <Stat label="Bank"    value={fmt(remaining)} tone={remaining < 0 ? "bad" : "good"}/>
        <button
          onClick={saveSquad}
          disabled={!isFull || saving}
          className="hidden md:flex items-center justify-center gap-2 rounded px-3 py-2 text-xs font-extrabold disabled:opacity-40"
          style={{ background: "var(--cp-lime)", color: "var(--cp-forest)" }}
          data-testid="save-squad"
        >
          <Save size={14}/> {saving ? "Saving…" : (savedAt ? "Saved ✓" : (mode === "20" ? "Save 20-man" : "Save squad"))}
        </button>
      </div>

      {/* Position progress dots */}
      <div className={`grid grid-cols-4 gap-2 mb-3`} data-testid="position-progress">
        {POSITIONS.map(pos => (
          <div key={pos} className="cp-surface p-2 text-center">
            <div className="text-[10px] uppercase font-bold opacity-60">{pos}</div>
            <div className="text-sm font-extrabold">{counts[pos]}/{POS_LIMIT[pos]}</div>
            <div className="flex gap-0.5 justify-center mt-1">
              {Array.from({ length: POS_LIMIT[pos] }).map((_, i) => (
                <span key={i} className="w-1.5 h-1.5 rounded-full" style={{ background: i < counts[pos] ? POS_COLOR[pos] : "var(--cp-border)" }}/>
              ))}
            </div>
          </div>
        ))}
      </div>

      {view === "pitch" ? (
        <PitchView counts={counts} squad={squad} onPick={setPickerPos} onRemove={removePlayer} posLimit={POS_LIMIT}/>
      ) : (
        <ListView squad={squad} counts={counts} onPick={setPickerPos} onRemove={removePlayer} posLimit={POS_LIMIT}/>
      )}

      {/* Mobile sticky save bar */}
      <button
        onClick={saveSquad}
        disabled={!isFull || saving}
        className="md:hidden fixed bottom-3 left-3 right-3 flex items-center justify-center gap-2 rounded px-3 py-3 font-extrabold disabled:opacity-40 z-30"
        style={{ background: "var(--cp-lime)", color: "var(--cp-forest)", boxShadow: "0 6px 24px rgba(0,0,0,0.4)" }}
        data-testid="save-squad-mobile"
      >
        <Save size={14}/> {saving ? "Saving…" : isFull ? (savedAt ? "Saved ✓" : "Save squad") : `Pick ${profile.total - totalCount} more`}
      </button>

      {/* Player picker modal */}
      {pickerPos && (
        <PlayerPicker
          position={pickerPos}
          allPlayers={players}
          alreadyPickedIds={new Set(squad.map(p => p.id))}
          counts={counts}
          remaining={remaining}
          onClose={() => setPickerPos(null)}
          onAdd={addPlayer}
          posLimit={POS_LIMIT}
        />
      )}
    </div>
  );
}

function Stat({ label, value, tone }) {
  const color = tone === "bad" ? "#FB7185" : tone === "good" ? "#A3E635" : "var(--cp-text)";
  return (
    <div>
      <div className="text-[10px] uppercase font-bold opacity-60">{label}</div>
      <div className="text-lg md:text-2xl font-extrabold tabular-nums" style={{ color }}>{value}</div>
    </div>
  );
}

function PitchView({ counts, squad, onPick, onRemove, posLimit }) {
  const slots = POSITIONS.flatMap(pos => {
    const picks = squad.filter(p => p.position === pos);
    const emptyN = posLimit[pos] - picks.length;
    return [
      ...picks.map(p => ({ pos, player: p })),
      ...Array.from({ length: emptyN }, () => ({ pos, player: null })),
    ];
  });
  const rowFor = (pos) => slots.filter(s => s.pos === pos);
  return (
    <div
      className="relative w-full rounded-lg overflow-hidden"
      style={{
        aspectRatio: "10 / 14",
        background: "repeating-linear-gradient(180deg, #0E6B3A 0 7%, #0A5A31 7% 14%)",
        maxHeight: "70vh",
      }}
      data-testid="build-team-pitch"
    >
      <div className="absolute top-1/2 left-0 right-0 h-px bg-white/50"/>
      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-16 h-16 border border-white/50 rounded-full"/>
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[60%] h-[16%] border-x border-b border-white/50"/>
      <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[60%] h-[16%] border-x border-t border-white/50"/>
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[30%] h-[7%] border-x border-b border-white/50"/>
      <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[30%] h-[7%] border-x border-t border-white/50"/>

      <div className="absolute inset-0 flex flex-col justify-around py-3">
        {POSITIONS.map(pos => (
          <div key={pos} className="flex items-start justify-around gap-1 px-1">
            {rowFor(pos).map((s, i) => (
              <PitchSlot key={`${pos}-${i}`} pos={pos} picked={s.player} onPick={onPick} onRemove={onRemove}/>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

function ListView({ squad, counts, onPick, onRemove, posLimit }) {
  return (
    <div className="space-y-3" data-testid="build-team-list">
      {POSITIONS.map(pos => {
        const picks = squad.filter(p => p.position === pos);
        const empty = posLimit[pos] - picks.length;
        return (
          <div key={pos} className="cp-surface overflow-hidden">
            <div
              className="px-3 py-2 flex items-center justify-between"
              style={{ background: `${POS_COLOR[pos]}22`, borderBottom: "1px solid var(--cp-border)" }}
            >
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full" style={{ background: POS_COLOR[pos] }}/>
                <span className="font-extrabold">{POS_LABEL[pos]}</span>
                <span className="text-xs opacity-60">{counts[pos]}/{posLimit[pos]}</span>
              </div>
              {empty > 0 && (
                <button onClick={() => onPick(pos)} className="text-xs font-bold px-2 py-1 rounded" style={{ background: POS_COLOR[pos], color: "var(--cp-forest)" }} data-testid={`list-add-${pos}`}>
                  + Add {pos}
                </button>
              )}
            </div>
            {picks.length === 0 ? (
              <div className="p-3 text-xs opacity-60 text-center">No {pos} picked yet. Tap "+ Add" to choose.</div>
            ) : (
              <ul className="divide-y" style={{ borderColor: "var(--cp-border)" }}>
                {picks.map(p => (
                  <li key={p.id} className="flex items-center gap-3 p-2.5" data-testid={`list-player-${p.id}`}>
                    <Jersey color={POS_COLOR[pos]} size={36}/>
                    <div className="flex-1 min-w-0">
                      <div className="font-bold truncate">{p.name}</div>
                      <div className="text-[11px] opacity-60 truncate">{p.team_name}</div>
                    </div>
                    <div className="font-extrabold text-cp-lime tabular-nums">{fmt(p.price)}</div>
                    <button onClick={() => onRemove(p)} className="cp-btn-ghost !p-2" data-testid={`list-remove-${p.id}`} aria-label="Remove">
                      <X size={14}/>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        );
      })}
    </div>
  );
}

function PlayerPicker({ position, allPlayers, alreadyPickedIds, counts, remaining, onClose, onAdd, posLimit }) {
  const [search, setSearch] = useState("");
  const [teamFilter, setTeamFilter] = useState("ALL");
  const [sortBy, setSortBy] = useState("price");
  const limitReached = counts[position] >= posLimit[position];

  const teamOptions = useMemo(() => {
    const set = new Set(allPlayers.filter(p => p.position === position).map(p => p.team_name).filter(Boolean));
    return ["ALL", ...Array.from(set).sort()];
  }, [allPlayers, position]);

  const list = useMemo(() => {
    const q = search.toLowerCase();
    const arr = allPlayers.filter(p =>
      p.position === position &&
      !alreadyPickedIds.has(p.id) &&
      (teamFilter === "ALL" || p.team_name === teamFilter) &&
      (!q || (p.name + " " + p.team_name).toLowerCase().includes(q))
    );
    if (sortBy === "price") arr.sort((a, b) => (b.price || 0) - (a.price || 0));
    else if (sortBy === "name") arr.sort((a, b) => a.name.localeCompare(b.name));
    return arr;
  }, [allPlayers, position, alreadyPickedIds, search, teamFilter, sortBy]);

  return (
    <div className="fixed inset-0 z-[10000] flex items-end md:items-center justify-center p-0 md:p-4" data-testid="player-picker">
      <div className="absolute inset-0" onClick={onClose} style={{ background: "rgba(0,0,0,0.6)" }}/>
      <div
        className="relative w-full md:max-w-2xl max-h-[88vh] flex flex-col rounded-t-2xl md:rounded-xl overflow-hidden animate-fade-in"
        style={{ background: "var(--cp-surface)", border: "1px solid var(--cp-border)" }}
      >
        <div className="flex items-center gap-2 p-3 shrink-0" style={{ borderBottom: "1px solid var(--cp-border)" }}>
          <button onClick={onClose} className="cp-btn-ghost !p-2 md:hidden" data-testid="picker-close-mobile"><ChevronLeft size={16}/></button>
          <span className="w-2.5 h-2.5 rounded-full" style={{ background: POS_COLOR[position] }}/>
          <h2 className="font-extrabold">Pick a {POS_LABEL[position].slice(0, -1)}</h2>
          <span className="text-xs opacity-60 ml-auto">Bank {fmt(remaining)}</span>
          <button onClick={onClose} className="cp-btn-ghost !p-2 hidden md:inline-flex" data-testid="picker-close"><X size={16}/></button>
        </div>
        <div className="p-3 flex gap-2 shrink-0">
          <div className="relative flex-1">
            <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 opacity-50"/>
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search players or teams…"
              className="cp-input pl-7 w-full"
              data-testid="picker-search"
            />
          </div>
          <select value={teamFilter} onChange={e => setTeamFilter(e.target.value)} className="cp-input text-xs max-w-[140px]" data-testid="picker-team">
            {teamOptions.map(t => <option key={t} value={t}>{t === "ALL" ? "All teams" : t}</option>)}
          </select>
          <select value={sortBy} onChange={e => setSortBy(e.target.value)} className="cp-input text-xs max-w-[110px]" data-testid="picker-sort">
            <option value="price">£ High → Low</option>
            <option value="name">Name A–Z</option>
          </select>
        </div>
        <div className="flex-1 overflow-y-auto" data-testid="picker-list">
          {limitReached && (
            <div className="p-3 text-xs text-center bg-red-500/10 text-red-400">You already have {posLimit[position]} {position}s. Remove one first.</div>
          )}
          {list.length === 0 ? (
            <div className="p-6 text-center opacity-60 text-sm">No players match your filters.</div>
          ) : (
            <ul className="divide-y" style={{ borderColor: "var(--cp-border)" }}>
              {list.map(p => {
                const tooExpensive = p.price > remaining;
                const disabled = limitReached || tooExpensive;
                return (
                  <li
                    key={p.id}
                    className={`flex items-center gap-3 p-2.5 transition ${disabled ? "opacity-40" : "hover:bg-white/3"}`}
                    data-testid={`picker-row-${p.id}`}
                  >
                    <Jersey color={POS_COLOR[position]} size={32}/>
                    <div className="flex-1 min-w-0">
                      <div className="font-bold truncate">{p.name}</div>
                      <div className="text-[11px] opacity-60 truncate">{p.team_name}{p.shirt_number ? ` · #${p.shirt_number}` : ""}</div>
                    </div>
                    <div className="font-extrabold text-cp-lime tabular-nums">{fmt(p.price)}</div>
                    <button
                      onClick={() => onAdd(p)}
                      disabled={disabled}
                      className="rounded px-2.5 py-1.5 text-xs font-extrabold disabled:cursor-not-allowed"
                      style={{ background: disabled ? "var(--cp-surface-2)" : "var(--cp-lime)", color: "var(--cp-forest)" }}
                      data-testid={`picker-add-${p.id}`}
                      title={tooExpensive ? "Over budget" : limitReached ? "Position full" : "Add"}
                    >
                      <CheckCircle2 size={14}/>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
