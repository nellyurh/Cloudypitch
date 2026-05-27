import React, { useEffect, useState, useMemo } from "react";
import { LeftSidebar } from "../components/LeftSidebar";
import { RightRail } from "../components/RightRail";
import { LeagueGroup } from "../components/LeagueGroup";
import api from "../lib/api";
import { Filter, Radio, ChevronLeft, ChevronRight, Calendar } from "lucide-react";

const FILTERS = [
  { id: "all", label: "All" },
  { id: "live", label: "Live" },
  { id: "upcoming", label: "Upcoming" },
  { id: "finished", label: "Finished" },
];

function dayOffsets() {
  // Build a window: 3 days back → 7 days ahead
  const out = [];
  const base = new Date();
  base.setHours(0, 0, 0, 0);
  for (let i = -3; i <= 7; i++) {
    const d = new Date(base);
    d.setDate(d.getDate() + i);
    out.push(d);
  }
  return out;
}

function fmtDay(d) {
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const t = new Date(d); t.setHours(0, 0, 0, 0);
  const diff = Math.round((t - today) / 86400000);
  if (diff === 0) return "Today";
  if (diff === -1) return "Yesterday";
  if (diff === 1) return "Tomorrow";
  return d.toLocaleDateString([], { weekday: "short", day: "numeric", month: "short" });
}

function isoDate(d) {
  return d.toISOString().slice(0, 10);
}

export const Dashboard = ({ sport = "football" }) => {
  const [grouped, setGrouped] = useState([]);
  const [count, setCount] = useState(0);
  const [filter, setFilter] = useState("all");
  const today = useMemo(() => { const d = new Date(); d.setHours(0,0,0,0); return d; }, []);
  const [selectedDate, setSelectedDate] = useState(today);
  const [loading, setLoading] = useState(true);

  const days = useMemo(() => dayOffsets(), []);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const params = new URLSearchParams({ sport });
        if (filter === "live" || filter === "upcoming" || filter === "finished") {
          params.append("status", filter);
        } else {
          params.append("date", isoDate(selectedDate));
        }
        const { data } = await api.get(`/matches?${params}`);
        if (!cancelled) {
          setGrouped(data.grouped || []);
          setCount(data.count || 0);
          setLoading(false);
        }
      } catch (_) {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    const t = setInterval(load, 20000);
    return () => { cancelled = true; clearInterval(t); };
  }, [sport, filter, selectedDate]);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[240px_1fr_320px] gap-4" data-testid="dashboard-grid">
      <div className="hidden lg:block">
        <LeftSidebar sport={sport} />
      </div>

      <section data-testid="center-feed">
        {/* Date strip */}
        <div className="cp-surface mb-3 overflow-hidden">
          <div className="flex items-center px-2 py-1.5 gap-1 overflow-x-auto no-scrollbar" data-testid="date-strip">
            <Calendar size={14} className="text-cp-lime mx-1 shrink-0" />
            {days.map(d => {
              const sel = isoDate(d) === isoDate(selectedDate) && filter === "all";
              return (
                <button
                  key={d.toISOString()}
                  onClick={() => { setSelectedDate(d); setFilter("all"); }}
                  className={`px-2.5 py-1 rounded text-xs font-semibold whitespace-nowrap transition ${sel ? "bg-cp-lime text-cp-forest" : "hover:bg-white/5"}`}
                  style={!sel ? { color: "var(--cp-text-muted)" } : {}}
                  data-testid={`date-${isoDate(d)}`}
                >
                  {fmtDay(d)}
                </button>
              );
            })}
          </div>
        </div>

        <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-extrabold tracking-tight capitalize">
              {sport} <span className="text-cp-lime">·</span> <span style={{ color: "var(--cp-text-muted)" }} className="text-sm font-medium">{count} matches</span>
            </h1>
          </div>
          <div className="flex items-center gap-1 cp-surface p-1" data-testid="match-filter">
            {FILTERS.map(f => (
              <button
                key={f.id}
                onClick={() => setFilter(f.id)}
                className={`px-2.5 py-1 rounded text-xs font-bold transition ${filter === f.id ? "bg-cp-lime text-cp-forest" : "hover:bg-white/5"}`}
                style={filter !== f.id ? { color: "var(--cp-text-muted)" } : {}}
                data-testid={`filter-${f.id}`}
              >
                {f.id === "live" && <Radio size={10} className="inline mr-1" />}
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {loading && (
          <div className="cp-surface p-6 text-sm" style={{ color: "var(--cp-text-muted)" }}>Loading live data…</div>
        )}
        {!loading && grouped.length === 0 && (
          <div className="cp-surface p-6 text-sm" style={{ color: "var(--cp-text-muted)" }}>
            <Filter className="inline mr-2" size={14} />
            No matches for this view. Try another date or filter.
          </div>
        )}
        {grouped.map(g => <LeagueGroup key={g.league_id} group={g} sport={sport} />)}
      </section>

      <div className="hidden lg:block">
        <RightRail />
      </div>
    </div>
  );
};

export default Dashboard;
