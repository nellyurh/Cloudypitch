import React, { useEffect, useState, useMemo, useRef } from "react";
import { LeftSidebar } from "../components/LeftSidebar";
import { RightRail } from "../components/RightRail";
import { LeagueGroup } from "../components/LeagueGroup";
import api from "../lib/api";
import { ChevronLeft, ChevronRight, Calendar, Radio, Filter } from "lucide-react";

function isoDate(d) { return d.toISOString().slice(0, 10); }
function dayLabel(d) {
  const today = new Date(); today.setHours(0,0,0,0);
  const t = new Date(d); t.setHours(0,0,0,0);
  const diff = Math.round((t - today) / 86400000);
  if (diff === 0) return "Today";
  if (diff === -1) return "Yesterday";
  if (diff === 1) return "Tomorrow";
  return d.toLocaleDateString([], { weekday: "short", day: "numeric", month: "short" });
}

export const Dashboard = ({ sport = "football" }) => {
  const [grouped, setGrouped] = useState([]);
  const [count, setCount] = useState(0);
  const today = useMemo(() => { const d = new Date(); d.setHours(0,0,0,0); return d; }, []);
  const [selectedDate, setSelectedDate] = useState(today);
  const [liveOnly, setLiveOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const dateInputRef = useRef(null);

  const shift = (delta) => {
    const d = new Date(selectedDate);
    d.setDate(d.getDate() + delta);
    d.setHours(0,0,0,0);
    setSelectedDate(d);
    setLiveOnly(false);
  };

  const openPicker = () => {
    const el = dateInputRef.current;
    if (!el) return;
    if (typeof el.showPicker === "function") el.showPicker();
    else el.focus();
  };

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const params = new URLSearchParams({ sport });
        if (liveOnly) params.append("status", "live");
        else params.append("date", isoDate(selectedDate));
        const { data } = await api.get(`/matches?${params}`);
        if (!cancelled) {
          setGrouped(data.grouped || []);
          setCount(data.count || 0);
          setLoading(false);
        }
      } catch (_) { if (!cancelled) setLoading(false); }
    };
    load();
    const t = setInterval(load, 20000);
    return () => { cancelled = true; clearInterval(t); };
  }, [sport, selectedDate, liveOnly]);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[240px_1fr_320px] gap-4" data-testid="dashboard-grid">
      <div className="hidden lg:block">
        <LeftSidebar sport={sport} />
      </div>

      <section data-testid="center-feed">
        {/* Single-row date control + live toggle */}
        <div className="cp-surface flex items-center gap-1 px-2 py-1.5 mb-3" data-testid="date-bar">
          <button onClick={() => shift(-1)} className="cp-btn-ghost !p-1.5" aria-label="Previous day" data-testid="date-prev">
            <ChevronLeft size={16} />
          </button>
          <button
            onClick={openPicker}
            className={`flex-1 flex items-center justify-center gap-2 px-3 py-1.5 rounded-md text-sm font-bold transition relative ${liveOnly ? "" : "bg-cp-lime text-cp-forest"}`}
            data-testid="date-current"
          >
            <Calendar size={14} />
            <span>{liveOnly ? "Live" : dayLabel(selectedDate)}</span>
            {!liveOnly && <span className="text-[10px] font-medium opacity-70 ml-1">{selectedDate.toLocaleDateString([], { day: "2-digit", month: "short", year: "numeric" })}</span>}
            {/* hidden native date input as the picker host */}
            <input
              ref={dateInputRef}
              type="date"
              value={isoDate(selectedDate)}
              onChange={(e) => {
                const v = e.target.value;
                if (!v) return;
                const [y, mo, d] = v.split("-");
                const dt = new Date(Number(y), Number(mo) - 1, Number(d));
                setSelectedDate(dt);
                setLiveOnly(false);
              }}
              className="absolute opacity-0 pointer-events-none w-px h-px"
              data-testid="date-input"
            />
          </button>
          <button onClick={() => shift(1)} className="cp-btn-ghost !p-1.5" aria-label="Next day" data-testid="date-next">
            <ChevronRight size={16} />
          </button>
          <span className="hidden md:inline mx-1" style={{ color: "var(--cp-border)" }}>|</span>
          <button
            onClick={() => setLiveOnly(v => !v)}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-bold transition ${liveOnly ? "bg-cp-live text-white" : "hover:bg-white/5"}`}
            style={!liveOnly ? { color: "var(--cp-text-muted)" } : {}}
            data-testid="live-toggle"
          >
            <Radio size={10} className={liveOnly ? "animate-pulse" : ""}/>
            LIVE
          </button>
          <span className="hidden md:inline text-xs font-medium ml-2" style={{ color: "var(--cp-text-muted)" }} data-testid="match-count">{count}</span>
        </div>

        {loading && (
          <div className="cp-surface p-6 text-sm" style={{ color: "var(--cp-text-muted)" }}>Loading live data…</div>
        )}
        {!loading && grouped.length === 0 && (
          <div className="cp-surface p-6 text-sm" style={{ color: "var(--cp-text-muted)" }}>
            <Filter className="inline mr-2" size={14} />
            {liveOnly ? "No live matches right now." : `No matches for ${dayLabel(selectedDate)}. Try ← or → to navigate days.`}
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
