import React, { useEffect, useState, useMemo } from "react";
import { LeftSidebar } from "../components/LeftSidebar";
import { RightRail } from "../components/RightRail";
import { LeagueGroup } from "../components/LeagueGroup";
import api from "../lib/api";
import { ChevronLeft, ChevronRight, Calendar as CalendarIcon, Radio, Filter, Clock, Check } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "../components/ui/popover";
import { Calendar } from "../components/ui/calendar";
import AdSlot from "../components/AdSlot";

function isoDate(d) {
  const y = d.getFullYear();
  const mo = String(d.getMonth() + 1).padStart(2, "0");
  const da = String(d.getDate()).padStart(2, "0");
  return `${y}-${mo}-${da}`;
}
function dayLabel(d) {
  const today = new Date(); today.setHours(0,0,0,0);
  const t = new Date(d); t.setHours(0,0,0,0);
  const diff = Math.round((t - today) / 86400000);
  if (diff === 0) return "Today";
  if (diff === -1) return "Yesterday";
  if (diff === 1) return "Tomorrow";
  return d.toLocaleDateString([], { weekday: "short", day: "numeric", month: "short" });
}

const TZ_OFFSET_MIN = -new Date().getTimezoneOffset();

export const Dashboard = ({ sport = "football" }) => {
  const [grouped, setGrouped] = useState([]);
  const [count, setCount] = useState(0);
  const today = useMemo(() => { const d = new Date(); d.setHours(0,0,0,0); return d; }, []);
  const [selectedDate, setSelectedDate] = useState(today);
  const [mode, setMode] = useState("date");
  const [loading, setLoading] = useState(true);
  const [pickerOpen, setPickerOpen] = useState(false);

  const shift = (delta) => {
    const d = new Date(selectedDate);
    d.setDate(d.getDate() + delta);
    d.setHours(0,0,0,0);
    setSelectedDate(d);
    setMode("date");
  };

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const params = new URLSearchParams({ sport, tz_offset_min: String(TZ_OFFSET_MIN) });
        if (mode === "live" || mode === "upcoming" || mode === "finished") {
          params.append("status", mode);
        } else {
          params.append("date", isoDate(selectedDate));
        }
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
  }, [sport, selectedDate, mode]);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[240px_1fr_320px] gap-4" data-testid="dashboard-grid">
      <div className="hidden lg:block">
        <LeftSidebar sport={sport} />
      </div>

      <section data-testid="center-feed">
        <div className="cp-surface flex items-center gap-1 px-2 py-1.5 mb-3 flex-wrap" data-testid="date-bar">
          <button onClick={() => shift(-1)} className="cp-btn-ghost !p-1.5" aria-label="Previous day" data-testid="date-prev">
            <ChevronLeft size={16} />
          </button>

          <Popover open={pickerOpen} onOpenChange={setPickerOpen}>
            <PopoverTrigger asChild>
              <button
                onClick={() => { if (mode !== "date") setMode("date"); }}
                className={`flex items-center justify-center gap-2 px-3 py-1.5 rounded-md text-sm font-bold transition min-w-[110px] ${mode === "date" ? "bg-cp-lime text-cp-forest" : "hover:bg-white/5"}`}
                style={mode !== "date" ? { color: "var(--cp-text-muted)" } : {}}
                data-testid="date-current"
              >
                <CalendarIcon size={14} />
                <span>{mode === "date" ? dayLabel(selectedDate) : "Date"}</span>
              </button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0" align="start" data-testid="date-picker-popover" style={{ background: "var(--cp-surface)", borderColor: "var(--cp-border)" }}>
              <Calendar
                mode="single"
                selected={selectedDate}
                onSelect={(d) => {
                  if (!d) return;
                  const nd = new Date(d);
                  nd.setHours(0,0,0,0);
                  setSelectedDate(nd);
                  setMode("date");
                  setPickerOpen(false);
                }}
                initialFocus
              />
            </PopoverContent>
          </Popover>

          <button onClick={() => shift(1)} className="cp-btn-ghost !p-1.5" aria-label="Next day" data-testid="date-next">
            <ChevronRight size={16} />
          </button>

          <span className="hidden md:inline-block w-px h-5 mx-1" style={{ background: "var(--cp-border)" }} />

          <button
            onClick={() => setMode(m => m === "live" ? "date" : "live")}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-bold transition ${mode === "live" ? "bg-cp-live text-white" : "hover:bg-white/5"}`}
            style={mode !== "live" ? { color: "var(--cp-text-muted)" } : {}}
            data-testid="filter-live"
          >
            <Radio size={11} className={mode === "live" ? "animate-pulse" : ""}/>
            LIVE
          </button>
          <button
            onClick={() => setMode(m => m === "upcoming" ? "date" : "upcoming")}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-bold transition ${mode === "upcoming" ? "bg-cp-lime text-cp-forest" : "hover:bg-white/5"}`}
            style={mode !== "upcoming" ? { color: "var(--cp-text-muted)" } : {}}
            data-testid="filter-upcoming"
          >
            <Clock size={11}/>
            UPCOMING
          </button>
          <button
            onClick={() => setMode(m => m === "finished" ? "date" : "finished")}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-bold transition ${mode === "finished" ? "bg-cp-lime text-cp-forest" : "hover:bg-white/5"}`}
            style={mode !== "finished" ? { color: "var(--cp-text-muted)" } : {}}
            data-testid="filter-finished"
          >
            <Check size={11}/>
            FINISHED
          </button>
          <span className="ml-auto text-xs font-medium" style={{ color: "var(--cp-text-muted)" }} data-testid="match-count">{count}</span>
        </div>

        {loading && (
          <div className="cp-surface p-6 text-sm" style={{ color: "var(--cp-text-muted)" }}>Loading live data…</div>
        )}
        {!loading && grouped.length === 0 && (
          <div className="cp-surface p-6 text-sm" style={{ color: "var(--cp-text-muted)" }}>
            <Filter className="inline mr-2" size={14} />
            {mode === "live" ? "No live matches right now." : mode === "upcoming" ? "No matches in the next 24 hours." : mode === "finished" ? "No finished matches in the past 24 hours." : `No matches for ${dayLabel(selectedDate)}.`}
          </div>
        )}
        {grouped.map(g => <LeagueGroup key={g.league_id} group={g} sport={sport} />)}

        <AdSlot placementKey="home_bottom_banner" className="mt-3"/>
      </section>

      <div className="hidden lg:block">
        <RightRail />
      </div>
    </div>
  );
};

export default Dashboard;
