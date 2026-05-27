import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import api from "../lib/api";
import { ChevronLeft, MapPin, User2 } from "lucide-react";

const TABS = ["events", "stats", "lineups", "h2h"];

export const MatchDetail = () => {
  const { id } = useParams();
  const [m, setM] = useState(null);
  const [events, setEvents] = useState([]);
  const [stats, setStats] = useState([]);
  const [lineups, setLineups] = useState([]);
  const [h2h, setH2H] = useState([]);
  const [tab, setTab] = useState("events");

  useEffect(() => {
    let cancel = false;
    const load = async () => {
      try {
        const { data } = await api.get(`/matches/${id}`);
        if (cancel) return;
        setM(data.match);
        setEvents(data.events || []);
        setStats(data.statistics || []);
        setLineups(data.lineups || []);
      } catch (_) {}
      try {
        const { data: h } = await api.get(`/matches/${id}/h2h`);
        if (!cancel) setH2H(h.matches || []);
      } catch (_) {}
    };
    load();
    const t = setInterval(load, 15000);
    return () => { cancel = true; clearInterval(t); };
  }, [id]);

  if (!m) return <div className="cp-surface p-6 text-sm" style={{ color: "var(--cp-text-muted)" }}>Loading match…</div>;

  const finished = ["FT", "AET", "PEN"].includes(m.status);

  return (
    <div className="max-w-4xl mx-auto" data-testid="match-detail">
      <Link to="/" className="inline-flex items-center gap-1 text-sm mb-2 hover:text-cp-lime"><ChevronLeft size={14}/> Back</Link>

      <div className="cp-surface p-5">
        <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>
          {m.league_country} · {m.league_name}
        </div>
        <div className="grid grid-cols-3 items-center mt-3">
          <div className="text-center">
            {m.home_team_logo && <img src={m.home_team_logo} className="w-14 h-14 mx-auto object-contain" alt="" onError={(e)=>{e.target.style.display="none"}}/>}
            <div className="font-bold mt-2" data-testid="match-home-name">{m.home_team_name}</div>
          </div>
          <div className="text-center">
            {m.is_live && (
              <div className="flex items-center justify-center gap-1.5 mb-1">
                <span className="cp-live-dot" />
                <span className="text-xs font-bold" style={{ color: "#FF3D52" }}>{m.minute ? `${m.minute}'` : (m.status_long || "LIVE")}</span>
              </div>
            )}
            <div className="text-4xl md:text-5xl font-extrabold tabular-nums" data-testid="match-score">
              {m.home_score} <span style={{ color: "var(--cp-text-muted)" }}>:</span> {m.away_score}
            </div>
            <div className="text-[11px] mt-1" style={{ color: "var(--cp-text-muted)" }}>
              {finished ? "Full Time" : (m.is_live ? "Live" : new Date(m.scheduled_at).toLocaleString())}
            </div>
            {m.home_score_ht != null && m.away_score_ht != null && (
              <div className="text-[10px] mt-0.5" style={{ color: "var(--cp-text-muted)" }}>
                HT {m.home_score_ht} - {m.away_score_ht}
              </div>
            )}
          </div>
          <div className="text-center">
            {m.away_team_logo && <img src={m.away_team_logo} className="w-14 h-14 mx-auto object-contain" alt="" onError={(e)=>{e.target.style.display="none"}}/>}
            <div className="font-bold mt-2" data-testid="match-away-name">{m.away_team_name}</div>
          </div>
        </div>

        <div className="flex items-center justify-center gap-4 text-xs mt-4" style={{ color: "var(--cp-text-muted)" }}>
          {m.venue_name && <span className="inline-flex items-center gap-1"><MapPin size={12}/> {m.venue_name}{m.venue_city ? `, ${m.venue_city}` : ""}</span>}
          {m.referee && <span className="inline-flex items-center gap-1"><User2 size={12}/> {m.referee}</span>}
        </div>
      </div>

      <div className="flex gap-1 mt-4 cp-surface p-1" data-testid="match-tabs">
        {TABS.map(t => (
          <button key={t} onClick={() => setTab(t)} className={`px-3 py-1.5 text-sm rounded transition ${tab === t ? "bg-cp-lime text-cp-forest font-bold" : "hover:bg-white/5"}`} data-testid={`tab-${t}`}>
            {t.toUpperCase()}
          </button>
        ))}
      </div>

      <div className="cp-surface mt-3 p-4 min-h-[160px]">
        {tab === "events" && (
          events.length === 0 ? <div className="text-sm" style={{ color: "var(--cp-text-muted)" }}>No events yet.</div> :
            <ul className="space-y-2">
              {events.map((e, i) => (
                <li key={i} className="flex items-center gap-3 text-sm" data-testid={`event-${i}`}>
                  <span className="w-10 text-xs tabular-nums" style={{ color: "var(--cp-text-muted)" }}>{e.minute || 0}'</span>
                  <span className="cp-pill" style={{ background: "var(--cp-surface-2)", color: "var(--cp-text)" }}>{e.type}</span>
                  <span>{e.player_name || e.detail}</span>
                </li>
              ))}
            </ul>
        )}
        {tab === "stats" && (
          stats.length === 0 ? <div className="text-sm" style={{ color: "var(--cp-text-muted)" }}>No stats yet.</div> :
          <div className="text-sm" style={{ color: "var(--cp-text-muted)" }}>{stats.length} stat blocks loaded.</div>
        )}
        {tab === "lineups" && (
          lineups.length === 0 ? <div className="text-sm" style={{ color: "var(--cp-text-muted)" }}>No lineups yet.</div> :
          <div className="text-sm">{lineups.length} players in lineup.</div>
        )}
        {tab === "h2h" && (
          h2h.length === 0 ? <div className="text-sm" style={{ color: "var(--cp-text-muted)" }}>No prior head-to-head found.</div> :
          <ul className="space-y-1">
            {h2h.map(p => (
              <li key={p.id} className="flex items-center justify-between text-sm py-1 border-b" style={{ borderColor: "var(--cp-border)" }}>
                <span>{new Date(p.scheduled_at).toLocaleDateString()}</span>
                <span>{p.home_team_name} {p.home_score} - {p.away_score} {p.away_team_name}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};

export default MatchDetail;
