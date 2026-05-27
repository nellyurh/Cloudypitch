import React, { useEffect, useState } from "react";
import { LeftSidebar } from "../components/LeftSidebar";
import { RightRail } from "../components/RightRail";
import { LeagueGroup } from "../components/LeagueGroup";
import api from "../lib/api";
import { Filter, Radio } from "lucide-react";

const FILTERS = [
  { id: "all", label: "All" },
  { id: "live", label: "Live" },
  { id: "upcoming", label: "Upcoming" },
  { id: "finished", label: "Finished" },
];

export const Dashboard = ({ sport = "football" }) => {
  const [grouped, setGrouped] = useState([]);
  const [count, setCount] = useState(0);
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const params = new URLSearchParams({ sport });
        if (filter !== "all") params.append("status", filter);
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
  }, [sport, filter]);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[240px_1fr_320px] gap-4" data-testid="dashboard-grid">
      <div className="hidden lg:block">
        <LeftSidebar sport={sport} />
      </div>

      <section data-testid="center-feed">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-extrabold tracking-tight capitalize">
              {sport} <span className="text-cp-lime">·</span> <span style={{ color: "var(--cp-text-muted)" }} className="text-sm font-medium">{count} matches today</span>
            </h1>
          </div>
          <div className="flex items-center gap-1 cp-surface p-1" data-testid="match-filter">
            {FILTERS.map(f => (
              <button
                key={f.id}
                onClick={() => setFilter(f.id)}
                className={`px-2.5 py-1 rounded text-xs font-bold transition ${filter === f.id ? "bg-cp-lime text-cp-forest" : "hover:bg-white/5"}`}
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
            No matches matching this filter. Try another or come back later.
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
