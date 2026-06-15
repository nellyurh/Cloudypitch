import React, { useEffect, useState, useMemo } from "react";
import { useParams, Link } from "react-router-dom";
import api from "../lib/api";
import { ChevronLeft, MapPin, Tv, Calendar, RefreshCw, Star, CloudRain, User2 } from "lucide-react";
import EventsList from "../components/match/EventsList";
import StatsBars from "../components/match/StatsBars";
import LineupPitch from "../components/match/LineupPitch";
import BoxScore from "../components/match/BoxScore";
import Sets from "../components/match/Sets";
import Innings from "../components/match/Innings";
import { StatGauge, CompareBar, ScoreBox } from "../components/match/StatGauges";
import AttackMomentum from "../components/match/AttackMomentum";
import StandingsTable from "../components/match/StandingsTable";
import NBABracket from "../components/match/NBABracket";
import Commentary from "../components/match/Commentary";
import Trends from "../components/match/Trends";
import SidelinedCard from "../components/match/SidelinedCard";
import H2HCard from "../components/match/H2HCard";
import { AnimatedBrand } from "../components/Brand";
import AdSlot from "../components/AdSlot";

/* Sport-aware tab layout (Sofascore style). */
const SPORT_TABS = {
  football:          [{ k: "lineups", l: "Lineups" }, { k: "stats", l: "Stats" }, { k: "events", l: "Events" }, { k: "momentum", l: "Momentum" }, { k: "commentary", l: "Commentary" }, { k: "trends", l: "Trends" }, { k: "h2h", l: "H2H" }, { k: "standings", l: "Standings" }],
  basketball:        [{ k: "box",     l: "Box Score" }, { k: "stats", l: "Statistics" }, { k: "h2h", l: "H2H" }, { k: "standings", l: "Standings" }],
  basketball_nba:    [{ k: "box",     l: "Box Score" }, { k: "stats", l: "Statistics" }, { k: "playoffs", l: "Playoffs" }, { k: "h2h", l: "H2H" }, { k: "standings", l: "Standings" }],
  nba:               [{ k: "box",     l: "Box Score" }, { k: "stats", l: "Statistics" }, { k: "playoffs", l: "Playoffs" }, { k: "h2h", l: "H2H" }, { k: "standings", l: "Standings" }],
  "american-football": [{ k: "box",   l: "Box Score" }, { k: "stats", l: "Statistics" }, { k: "h2h", l: "H2H" }, { k: "standings", l: "Standings" }],
  tennis:            [{ k: "sets",    l: "Sets" }, { k: "stats", l: "Stats" }, { k: "h2h", l: "H2H" }],
  volleyball:        [{ k: "sets",    l: "Sets" }, { k: "stats", l: "Stats" }, { k: "h2h", l: "H2H" }, { k: "standings", l: "Standings" }],
  "table-tennis":    [{ k: "sets",    l: "Games" }, { k: "h2h", l: "H2H" }],
  badminton:         [{ k: "sets",    l: "Games" }, { k: "h2h", l: "H2H" }],
  cricket:           [{ k: "innings", l: "Innings" }, { k: "h2h", l: "H2H" }, { k: "standings", l: "Standings" }],
  baseball:          [{ k: "box",     l: "Box Score" }, { k: "stats", l: "Statistics" }, { k: "h2h", l: "H2H" }, { k: "standings", l: "Standings" }],
  hockey:            [{ k: "box",     l: "Periods" }, { k: "stats", l: "Stats" }, { k: "h2h", l: "H2H" }, { k: "standings", l: "Standings" }],
  rugby:             [{ k: "events",  l: "Events" }, { k: "stats", l: "Stats" }, { k: "h2h", l: "H2H" }],
  mma:               [{ k: "stats",   l: "Fight Stats" }, { k: "h2h", l: "H2H" }],
  default:           [{ k: "events",  l: "Events" }, { k: "stats", l: "Stats" }, { k: "h2h", l: "H2H" }],
};

const STADIUM_BG_URL = "https://images.unsplash.com/photo-1431324155629-1a6deb1dec8d?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA2ODl8MHwxfHNlYXJjaHwxfHxzdGFkaXVtJTIwYmFja2dyb3VuZCUyMGRhcmt8ZW58MHx8fHwxNzgxNTI2MTE0fDA&ixlib=rb-4.1.0&q=85";

function StatusPill({ m, finished }) {
  const live = m.is_live;
  let label, bg, fg, border, dot = false;
  if (live) {
    label = m.minute != null ? `${m.minute}'` : (m.status === "HT" ? "HT" : "Live");
    bg = "rgba(239,68,68,0.12)";
    fg = "#EF4444";
    border = "rgba(239,68,68,0.35)";
    dot = true;
  } else if (finished) {
    label = m.status_long || m.status || "Finished";
    bg = "rgba(148,163,184,0.12)";
    fg = "#CBD5E1";
    border = "rgba(148,163,184,0.3)";
  } else {
    label = m.status_long || m.status || "Scheduled";
    bg = "rgba(163,230,53,0.10)";
    fg = "#A3E635";
    border = "rgba(163,230,53,0.3)";
  }
  return (
    <span
      className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold uppercase tracking-widest border"
      style={{ background: bg, color: fg, borderColor: border }}
      data-testid="match-status-pill"
    >
      {dot && <span className="inline-block w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse" />}
      {label}
    </span>
  );
}

function MatchHero({ m, finished }) {
  const isFootball = (m.sport_slug || "football") === "football";
  return (
    <div className="relative cp-surface overflow-hidden" data-testid="match-hero">
      {/* Stadium background — football only, dark gradient overlay on top */}
      {isFootball && (
        <>
          <div
            aria-hidden
            className="absolute inset-0 pointer-events-none"
            style={{
              backgroundImage: `url(${STADIUM_BG_URL})`,
              backgroundSize: "cover",
              backgroundPosition: "center",
              opacity: 0.45,
              filter: "saturate(0.75) contrast(1.05)",
            }}
          />
          <div
            aria-hidden
            className="absolute inset-0 pointer-events-none"
            style={{
              background:
                "linear-gradient(to top, var(--cp-bg, #0F1115) 0%, rgba(15,17,21,0.75) 50%, rgba(15,17,21,0.35) 100%)",
            }}
          />
        </>
      )}

      <div className="relative z-10 p-4 md:p-6">
        <div className="text-[10px] uppercase tracking-widest text-center mb-3" style={{ color: "var(--cp-text-muted)" }}>
          {m.league_country} · {m.league_name}
        </div>

        <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-4 md:gap-8">
          {/* Home */}
          <div className="flex flex-col items-center md:items-end gap-2 text-center md:text-right">
            {m.home_team_logo ? (
              <img src={m.home_team_logo} alt="" className="w-16 h-16 md:w-20 md:h-20 object-contain drop-shadow-[0_2px_8px_rgba(0,0,0,0.45)]" onError={(e)=>{e.target.style.display="none"}}/>
            ) : <div className="w-16 h-16 md:w-20 md:h-20 cp-logo-circle text-lg font-extrabold">{m.home_short}</div>}
            <div className="text-sm md:text-base font-extrabold text-slate-100">{m.home_team_name}</div>
          </div>

          {/* Score & status */}
          <div className="text-center min-w-[120px]">
            <div className="text-4xl md:text-6xl font-black tabular-nums tracking-tighter leading-none">
              <span className={m.home_score > m.away_score ? "text-cp-lime" : "text-slate-100"}>{m.home_score ?? "—"}</span>
              <span className="mx-2 opacity-40">:</span>
              <span className={m.away_score > m.home_score ? "text-cp-lime" : "text-slate-100"}>{m.away_score ?? "—"}</span>
            </div>
            <div className="mt-3 flex items-center justify-center">
              <StatusPill m={m} finished={finished} />
            </div>
          </div>

          {/* Away */}
          <div className="flex flex-col items-center md:items-start gap-2 text-center md:text-left">
            {m.away_team_logo ? (
              <img src={m.away_team_logo} alt="" className="w-16 h-16 md:w-20 md:h-20 object-contain drop-shadow-[0_2px_8px_rgba(0,0,0,0.45)]" onError={(e)=>{e.target.style.display="none"}}/>
            ) : <div className="w-16 h-16 md:w-20 md:h-20 cp-logo-circle text-lg font-extrabold">{m.away_short}</div>}
            <div className="text-sm md:text-base font-extrabold text-slate-100">{m.away_team_name}</div>
          </div>
        </div>

        {/* Meta strip */}
        <div className="mt-4 pt-3 border-t flex flex-wrap items-center justify-center gap-x-5 gap-y-1 text-[11px]" style={{ borderColor: "var(--cp-border)", color: "var(--cp-text-muted)" }}>
          <span className="inline-flex items-center gap-1"><Calendar size={11}/>{m.scheduled_at && new Date(m.scheduled_at).toLocaleString([], { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" })}</span>
          {m.venue_name && <span className="inline-flex items-center gap-1"><MapPin size={11}/>{m.venue_name}{m.venue_city ? `, ${m.venue_city}` : ""}</span>}
          {m.match_format && <span className="inline-flex items-center gap-1">{m.match_format}</span>}
          {m.weather && (m.weather.temperature_celcius != null || m.weather.type) && (
            <span className="inline-flex items-center gap-1" data-testid="hero-weather">
              <CloudRain size={11}/>
              {m.weather.temperature_celcius != null ? `${m.weather.temperature_celcius}°C` : m.weather.type}
            </span>
          )}
          {Array.isArray(m.tv_stations) && m.tv_stations.length > 0 && (
            <span className="inline-flex items-center gap-1" data-testid="hero-tv">
              <Tv size={11}/>{m.tv_stations.slice(0, 2).join(", ")}{m.tv_stations.length > 2 ? "…" : ""}
            </span>
          )}
          {Array.isArray(m.referees) && m.referees.length > 0 && (
            <span className="inline-flex items-center gap-1" data-testid="hero-ref">
              <User2 size={11}/>{m.referees[0]?.name}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function BasketballStatsView({ m, statistics, homeName, awayName }) {
  // Pick best-effort fields from API-Sports basketball / NBA shape
  const homeBlock = statistics?.find(s => s.team_id === m.home_team_id) || statistics?.[0] || {};
  const awayBlock = statistics?.find(s => s.team_id === m.away_team_id) || statistics?.[1] || {};
  const h = homeBlock.stats || {}, a = awayBlock.stats || {};
  const get = (obj, ...keys) => { for (const k of keys) if (obj[k] != null) return obj[k]; return null; };
  const ftH = get(h, "Free Throws", "ft", "free_throws"); const ftA = get(a, "Free Throws", "ft", "free_throws");
  const twoH = get(h, "2-Pointers", "two", "2pt"); const twoA = get(a, "2-Pointers", "two", "2pt");
  const threeH = get(h, "3-Pointers", "three", "3pt"); const threeA = get(a, "3-Pointers", "three", "3pt");
  const fgH = get(h, "Field Goals", "fg"); const fgA = get(a, "Field Goals", "fg");
  const parseShot = (v) => { if (!v) return [0, 0]; const m = String(v).match(/(\d+)\D+(\d+)/); return m ? [+m[1], +m[2]] : [0, 0]; };
  const [hFt, hFtA] = parseShot(ftH), [aFt, aFtA] = parseShot(ftA);
  const [h2, h2A] = parseShot(twoH), [a2, a2A] = parseShot(twoA);
  const [h3, h3A] = parseShot(threeH), [a3, a3A] = parseShot(threeA);
  const [hFg, hFgA] = parseShot(fgH), [aFg, aFgA] = parseShot(fgA);

  // Comparison stats
  const compareKeys = [
    ["Rebounds", "rebounds", "total_rebounds"],
    ["Defensive rebounds", "def_rebounds"],
    ["Offensive rebounds", "off_rebounds"],
    ["Assists", "assists"],
    ["Turnovers", "turnovers"],
    ["Steals", "steals"],
    ["Blocks", "blocks"],
    ["Fouls", "fouls", "personal_fouls"],
  ];
  return (
    <div data-testid="bball-stats">
      <div className="grid grid-cols-[1fr_auto_1fr] items-center text-[11px] uppercase tracking-widest mb-3" style={{ color: "var(--cp-text-muted)" }}>
        <div className="text-right font-bold text-cp-lime">{homeName}</div>
        <div className="px-3">vs</div>
        <div className="text-left font-bold" style={{ color: "#7DD3FC" }}>{awayName}</div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6">
        <div>
          <StatGauge label="Free throws" homeMade={hFt} homeAtt={hFtA} awayMade={aFt} awayAtt={aFtA}/>
          <StatGauge label="2 pointers" homeMade={h2} homeAtt={h2A} awayMade={a2} awayAtt={a2A}/>
          <StatGauge label="3 pointers" homeMade={h3} homeAtt={h3A} awayMade={a3} awayAtt={a3A}/>
          <StatGauge label="Field goals" homeMade={hFg} homeAtt={hFgA} awayMade={aFg} awayAtt={aFgA}/>
        </div>
        <div>
          {compareKeys.map(([label, ...keys]) => {
            const hv = get(h, label, ...keys);
            const av = get(a, label, ...keys);
            if (hv == null && av == null) return null;
            return <CompareBar key={label} label={label} home={hv} away={av}/>;
          })}
        </div>
      </div>
    </div>
  );
}

export const MatchDetail = () => {
  const { id } = useParams();
  const [m, setM] = useState(null);
  const [events, setEvents] = useState([]);
  const [stats, setStats] = useState([]);
  const [lineups, setLineups] = useState([]);
  const [h2h, setH2H] = useState([]);
  const [momentumCount, setMomentumCount] = useState(null);
  const [tab, setTab] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = async (refresh = false) => {
    try {
      const url = refresh ? `/matches/${id}?refresh=1` : `/matches/${id}`;
      const { data } = await api.get(url);
      setM(data.match); setEvents(data.events || []); setStats(data.statistics || []); setLineups(data.lineups || []);
    } catch (_) {}
    try { const { data: h } = await api.get(`/matches/${id}/h2h`); setH2H(h.matches || []); } catch (_) {}
    try {
      const { data: mm } = await api.get(`/matches/${id}/momentum`);
      setMomentumCount((mm?.momentum || []).length);
    } catch (_) { setMomentumCount(0); }
  };

  useEffect(() => { load(); const t = setInterval(() => load(false), 15000); return () => clearInterval(t); }, [id]);

  const sportSlug = m?.sport_slug || "football";
  const tabs = useMemo(() => SPORT_TABS[sportSlug] || SPORT_TABS.default, [sportSlug]);
  // 🛡️ Hide tabs that have no data. Saves users from clicking through to a
  // dead "Attack Momentum is empty" panel — Sofascore-style clean tab bar
  // where only populated tabs are visible.
  const tabHasData = (key) => {
    if (key === "events" || key === "commentary") return (events || []).length > 0;
    if (key === "stats") return (stats || []).length > 0;
    if (key === "lineups") return (lineups || []).length > 0;
    if (key === "momentum") return (momentumCount ?? 0) > 0;
    // H2H / Standings / Trends compute themselves from m + side fetches.
    return true;
  };
  const visibleTabs = useMemo(() => tabs.filter((t) => tabHasData(t.k)), [tabs, events, stats, lineups, momentumCount]);
  useEffect(() => { if (m && !tab) setTab(visibleTabs[0]?.k || tabs[0]?.k); }, [m, tab, tabs, visibleTabs]);

  const handleRefresh = async () => { setRefreshing(true); await load(true); setRefreshing(false); };

  if (!m) return (
    <div className="cp-surface p-12 flex items-center justify-center" data-testid="matchdetail-loading">
      <AnimatedBrand size={72} label="Loading match…"/>
    </div>
  );
  const finished = ["FT", "AET", "PEN", "Ended", "Finished"].includes(m.status);

  // Periods/sets/innings for left-rail score box
  const sideBoxData = m.periods || m.sets || [];
  const useBballStats = ["basketball", "basketball_nba", "american-football", "baseball"].includes(sportSlug) && stats?.length;

  return (
    <div data-testid="match-detail">
      <div className="flex items-center justify-between mb-3">
        <Link to="/" className="cp-btn-ghost inline-flex items-center gap-1" data-testid="back-home"><ChevronLeft size={14}/> Back</Link>
        <button onClick={handleRefresh} className="cp-btn-ghost inline-flex items-center gap-1" data-testid="refresh-match" disabled={refreshing}>
          <RefreshCw size={14} className={refreshing ? "animate-spin" : ""}/> Refresh
        </button>
      </div>

      <MatchHero m={m} finished={finished}/>

      <div className="grid grid-cols-1 lg:grid-cols-[260px_1fr_260px] gap-3 mt-3">
        {/* Left rail */}
        <aside className="space-y-3">
          {sideBoxData.length > 0 && (
            <ScoreBox periods={sideBoxData} labelPrefix={sportSlug === "tennis" || sportSlug === "volleyball" ? "S" : "Q"}/>
          )}
          {sportSlug === "football" && <AttackMomentum matchId={id} homeTeamId={m.home_team_id}/>}
          <div className="cp-surface p-3">
            <div className="text-[10px] uppercase tracking-widest mb-1" style={{ color: "var(--cp-text-muted)" }}>Full-time odds</div>
            <div className="grid grid-cols-3 gap-1.5 text-center">
              {["1", "X", "2"].map((k, i) => (
                <div key={k} className="cp-surface !bg-transparent p-2 ring-1 ring-white/10 rounded" data-testid={`odds-${k}`}>
                  <div className="text-[10px]" style={{ color: "var(--cp-text-muted)" }}>{k}</div>
                  <div className="font-extrabold text-sm tabular-nums">{(m.odds || {})[k] || (["2.10","3.40","3.20"][i])}</div>
                </div>
              ))}
            </div>
          </div>
          <AdSlot slot="sidebar"/>
        </aside>

        {/* Center tabs */}
        <div>
          <div className="flex gap-1 cp-surface p-1 overflow-x-auto" data-testid="match-tabs">
            {visibleTabs.map(t => (
              <button key={t.k} onClick={() => setTab(t.k)} className={`px-3 py-1.5 text-sm rounded transition whitespace-nowrap ${tab === t.k ? "bg-cp-lime text-cp-forest font-bold" : "hover:bg-white/5"}`} data-testid={`tab-${t.k}`}>
                {t.l}
              </button>
            ))}
          </div>

          <div className="cp-surface mt-3 p-4 min-h-[300px]">
            {tab === "events" && <EventsList events={events} homeTeamId={m.home_team_id} awayTeamId={m.away_team_id} homeName={m.home_team_name} awayName={m.away_team_name}/>}
            {tab === "stats" && (useBballStats
              ? <BasketballStatsView m={m} statistics={stats} homeName={m.home_team_name} awayName={m.away_team_name}/>
              : <StatsBars statistics={stats} homeTeamId={m.home_team_id} awayTeamId={m.away_team_id} homeName={m.home_team_name} awayName={m.away_team_name}/>)}
            {tab === "lineups" && (
              <>
                <LineupPitch lineups={lineups} homeTeamId={m.home_team_id} awayTeamId={m.away_team_id} homeName={m.home_team_name} awayName={m.away_team_name}/>
                <SidelinedCard
                  players={m.sidelined_raw || []}
                  homeTeamId={m.sportmonks_home_id}
                  awayTeamId={m.sportmonks_away_id}
                  homeTeamName={m.home_team_name}
                  awayTeamName={m.away_team_name}
                />
              </>
            )}
            {tab === "commentary" && <Commentary comments={m.comments || []} homeTeamName={m.home_team_name} awayTeamName={m.away_team_name}/>}
            {tab === "momentum" && <AttackMomentum matchId={id} homeTeamId={m.home_team_id} full/>}
            {tab === "trends" && <Trends facts={m.matchfacts || []} homeTeamName={m.home_team_name} awayTeamName={m.away_team_name}/>}
            {tab === "box" && <BoxScore match={m} lineups={lineups}/>}
            {tab === "sets" && <Sets match={m}/>}
            {tab === "innings" && <Innings match={m}/>}
            {tab === "standings" && <StandingsTable matchId={id}/>}
            {tab === "playoffs" && <NBABracket/>}
            {tab === "h2h" && (
              <H2HCard
                h2h={h2h}
                homeTeamId={m.home_team_id}
                awayTeamId={m.away_team_id}
                homeName={m.home_team_name}
                awayName={m.away_team_name}
              />
            )}
          </div>
        </div>

        {/* Right rail — ad + favourite */}
        <aside className="space-y-3 hidden lg:block">
          <div className="cp-surface p-3 text-center">
            <Star size={20} className="mx-auto text-cp-lime mb-1"/>
            <div className="text-xs font-bold">Follow this match</div>
            <div className="text-[10px] mt-1" style={{ color: "var(--cp-text-muted)" }}>Get push alerts for goals and key moments</div>
          </div>
          <AdSlot slot="sidebar"/>
        </aside>
      </div>
    </div>
  );
};

export default MatchDetail;
