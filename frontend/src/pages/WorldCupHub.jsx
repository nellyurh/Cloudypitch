import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import api from "../lib/api";
import { Trophy, Calendar, Layers, Users2, ChevronLeft, ChevronRight, MapPin } from "lucide-react";
import { flagUrl } from "../lib/flags";
import AdSlot from "../components/AdSlot";

/** Compact days/hrs/min/sec ribbon shown in the top group strip. */
function CountdownRibbon({ to, label = "Kicks off in" }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t); }, []);
  const ms = Math.max(0, new Date(to).getTime() - now);
  const d = Math.floor(ms / 86400000);
  const h = Math.floor((ms % 86400000) / 3600000);
  const m = Math.floor((ms % 3600000) / 60000);
  const s = Math.floor((ms % 60000) / 1000);
  if (ms <= 0) {
    return <span className="text-[11px] font-extrabold text-cp-lime uppercase tracking-wider" data-testid="wc-ribbon-live">Tournament live</span>;
  }
  return (
    <span className="text-[11px] font-extrabold whitespace-nowrap flex items-center gap-1" data-testid="wc-countdown-ribbon">
      <span className="text-cp-lime">{d}D</span>:
      <span>{String(h).padStart(2, "0")}H</span>:
      <span>{String(m).padStart(2, "0")}M</span>:
      <span>{String(s).padStart(2, "0")}S</span>
    </span>
  );
}

/** Top strip: countdown + horizontally-scrolling list of groups with country flags. */
function WcGroupStrip({ startsAt, groups }) {
  return (
    <div className="rounded-md overflow-hidden mb-4" style={{
      background: "linear-gradient(90deg, #5b1d3a 0%, #6b2a47 40%, #5a3a1b 70%, #3a4b1b 100%)",
      border: "1px solid rgba(255,255,255,0.05)",
    }} data-testid="wc-group-strip">
      <div className="flex items-stretch gap-2 px-2 py-1.5 overflow-x-auto no-scrollbar">
        <div className="flex items-center px-3 shrink-0 border-r" style={{ borderColor: "rgba(255,255,255,0.12)" }}>
          <CountdownRibbon to={startsAt}/>
        </div>
        {(groups || []).map(g => (
          <div key={g.group} className="flex items-center gap-1.5 px-2.5 py-1 shrink-0" data-testid={`strip-group-${g.group}`}>
            <span className="text-[10px] uppercase tracking-widest font-bold opacity-80" style={{ color: "#fff" }}>Group {g.group}</span>
            <div className="flex items-center gap-0.5">
              {(g.teams || []).slice(0, 4).map(t => (
                flagUrl(t, 40) ? (
                  <img key={t} src={flagUrl(t, 40)} alt={t} title={t} className="w-4 h-3 rounded-sm object-cover ring-1 ring-black/30"/>
                ) : <span key={t} className="w-4 h-3 rounded-sm" style={{ background: "rgba(0,0,0,0.3)" }}/>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Hero card (Sofascore-style): trophy + title + previous-edition selector + stage progress. */
function WcHero({ startsAt }) {
  const editions = [2026, 2022, 2018, 2014, 2010, 2006, 2002, 1998, 1994, 1990, 1986, 1982, 1978, 1974, 1970, 1966];
  return (
    <div className="cp-surface overflow-hidden p-4 md:p-6 relative" data-testid="wc-hero" style={{
      background: "radial-gradient(circle at 90% 30%, rgba(163,230,53,0.05), transparent 60%), var(--cp-surface)",
    }}>
      <div className="flex items-start gap-4">
        <div className="shrink-0 flex items-center justify-center w-16 h-20 md:w-20 md:h-24 rounded-md" style={{ background: "linear-gradient(180deg, #FCD34D 0%, #B45309 100%)" }}>
          <Trophy size={36} className="text-amber-900"/>
        </div>
        <div className="flex-1 min-w-0">
          <h1 className="text-xl md:text-2xl font-extrabold leading-tight">FIFA World Cup 2026</h1>
          <div className="text-xs mt-0.5" style={{ color: "var(--cp-text-muted)" }}>
            <CountdownRibbon to={startsAt} label="Kicks off in"/>
          </div>
          <div className="mt-3 flex items-center gap-1.5 overflow-x-auto no-scrollbar" data-testid="wc-edition-strip">
            {editions.map(y => (
              <button
                key={y}
                disabled={y !== 2026}
                className={`shrink-0 text-[11px] font-bold rounded-full px-3 py-1.5 transition ${y === 2026 ? "bg-white text-cp-forest" : "opacity-60 hover:opacity-100"}`}
                style={y === 2026 ? {} : { background: "var(--cp-surface-2)", color: "var(--cp-text-muted)" }}
                data-testid={`wc-edition-${y}`}
              >
                {y}
              </button>
            ))}
          </div>
        </div>
        <Link to="/build-team" className="hidden md:inline-flex cp-btn-primary text-xs whitespace-nowrap" data-testid="wc-hero-cta">
          Build Fantasy
        </Link>
      </div>
      {/* Stage progress bar */}
      <div className="mt-4 relative">
        <div className="h-1.5 rounded-full" style={{ background: "linear-gradient(90deg,#7c2d12 0%, #92400e 20%, #65a30d 50%, #166534 75%, #064e3b 100%)" }}/>
        <div className="flex justify-between mt-1 text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>
          <span>Group stage</span><span>R32</span><span>R16</span><span>QF</span><span>SF</span><span>3rd</span><span>Final</span>
        </div>
      </div>
    </div>
  );
}

/** Left column: Matches with By date / By round / By group toggles. */
function MatchesPane({ matches }) {
  const [mode, setMode] = useState("round"); // 'date' | 'round' | 'group'
  const dates = useMemo(() => {
    const set = new Set();
    matches.forEach(m => { if (m.scheduled_at) set.add(m.scheduled_at.slice(0, 10)); });
    return [...set].sort();
  }, [matches]);
  const rounds = useMemo(() => {
    const set = new Set();
    matches.forEach(m => { if (m.round) set.add(m.round); });
    return [...set];
  }, [matches]);
  const groups = useMemo(() => {
    const set = new Set();
    matches.forEach(m => { if (m.group) set.add(m.group); });
    return [...set].sort();
  }, [matches]);

  const sections = useMemo(() => {
    if (mode === "date") return dates.map(d => ({ key: d, label: d, matches: matches.filter(m => (m.scheduled_at || "").slice(0, 10) === d) }));
    if (mode === "round") return rounds.map(r => ({ key: r, label: r, matches: matches.filter(m => m.round === r) }));
    return groups.map(g => ({ key: g, label: `Group ${g}`, matches: matches.filter(m => m.group === g) }));
  }, [mode, matches, dates, rounds, groups]);

  return (
    <div className="cp-surface overflow-hidden" data-testid="wc-matches-pane">
      <div className="px-3 py-2.5 text-center font-extrabold text-sm border-b" style={{ borderColor: "var(--cp-border)" }}>Matches</div>
      <div className="flex items-center justify-center gap-1 px-2 py-2">
        {[
          { k: "date", label: "By date" },
          { k: "round", label: "By round" },
          { k: "group", label: "By group" },
        ].map(t => (
          <button key={t.k} onClick={() => setMode(t.k)} className="text-[11px] font-extrabold px-3 py-1.5 rounded-full transition"
            style={{ background: mode === t.k ? "var(--cp-forest)" : "transparent", color: mode === t.k ? "#fff" : "var(--cp-text-muted)" }}
            data-testid={`wc-matches-mode-${t.k}`}>
            {t.label}
          </button>
        ))}
      </div>
      <div className="max-h-[70vh] overflow-y-auto">
        {sections.length === 0 && (
          <div className="px-3 py-8 text-center text-xs" style={{ color: "var(--cp-text-muted)" }}>
            No fixtures ingested yet. Once the WC fixtures sync runs, they&apos;ll appear here grouped by date/round/group.
          </div>
        )}
        {sections.map(sec => (
          <div key={sec.key} data-testid={`wc-section-${sec.key}`}>
            <div className="px-3 py-1.5 text-[10px] uppercase tracking-widest font-bold" style={{ background: "var(--cp-surface-2)", color: "var(--cp-text-muted)" }}>{sec.label}</div>
            <ul className="divide-y" style={{ borderColor: "var(--cp-border)" }}>
              {sec.matches.map(m => <MatchPaneRow key={m.id} m={m}/>)}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}

function MatchPaneRow({ m }) {
  const dt = m.scheduled_at ? new Date(m.scheduled_at.replace(" ", "T") + (m.scheduled_at.endsWith("Z") ? "" : "Z")) : null;
  const date = dt ? `${String(dt.getDate()).padStart(2, "0")}/${String(dt.getMonth() + 1).padStart(2, "0")}/${String(dt.getFullYear()).slice(-2)}` : "—";
  const time = dt ? `${String(dt.getHours()).padStart(2, "0")}:${String(dt.getMinutes()).padStart(2, "0")}` : "";
  return (
    <li className="grid grid-cols-[55px_1fr_auto] gap-2 px-3 py-2 items-center text-xs hover:bg-white/[0.02]" data-testid={`wc-match-${m.id}`}>
      <div className="text-[10px] text-center" style={{ color: "var(--cp-text-muted)" }}>
        <div>{date}</div>
        <div className="font-bold">{time}</div>
      </div>
      <div className="min-w-0 space-y-1">
        <TeamRow team={m.home_team_name} short={m.home_short}/>
        <TeamRow team={m.away_team_name} short={m.away_short}/>
      </div>
      <div className="text-[10px] text-right tabular-nums" style={{ color: "var(--cp-text-muted)" }}>
        {m.home_score != null ? <div>{m.home_score}</div> : <div>-</div>}
        {m.away_score != null ? <div>{m.away_score}</div> : <div>-</div>}
      </div>
    </li>
  );
}

function TeamRow({ team, short }) {
  return (
    <div className="flex items-center gap-1.5 min-w-0">
      {flagUrl(team, 40) ? (
        <img src={flagUrl(team, 40)} className="w-4 h-3 object-cover rounded-sm ring-1 ring-black/30 shrink-0" alt=""/>
      ) : <span className="w-4 h-3 rounded-sm shrink-0" style={{ background: "var(--cp-surface-2)" }}/>}
      <span className="truncate">{team || short || "—"}</span>
    </div>
  );
}

/** Middle column tabs: Overview / Standings / Knockout / Media. */
function MiddlePane({ matches, groups }) {
  const [tab, setTab] = useState("overview");
  const round1 = matches.filter(m => m.matchday === 1).slice(0, 4);
  return (
    <div className="cp-surface" data-testid="wc-middle-pane">
      <div className="flex items-center gap-1 px-2 py-1.5 border-b overflow-x-auto" style={{ borderColor: "var(--cp-border)" }}>
        {[
          { k: "overview", label: "Overview" },
          { k: "standings", label: "Standings" },
          { k: "knockout", label: "Knockout" },
          { k: "media", label: "Media" },
        ].map(t => (
          <button key={t.k} onClick={() => setTab(t.k)} className="text-xs font-extrabold px-3 py-2 transition relative"
            style={{ color: tab === t.k ? "var(--cp-text)" : "var(--cp-text-muted)", borderBottom: tab === t.k ? "2px solid var(--cp-lime)" : "2px solid transparent" }}
            data-testid={`wc-middle-tab-${t.k}`}>
            {t.label}
          </button>
        ))}
      </div>
      <div className="p-4">
        {tab === "overview" && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {round1.map(m => <OverviewMatchCard key={m.id} m={m}/>)}
              {round1.length === 0 && <div className="text-xs col-span-2" style={{ color: "var(--cp-text-muted)" }}>Round 1 fixtures appear here once ingested.</div>}
            </div>
            <StandingsTable groups={groups} matches={matches} compact/>
          </div>
        )}
        {tab === "standings" && <StandingsTable groups={groups} matches={matches}/>}
        {tab === "knockout" && (
          <div className="text-xs" style={{ color: "var(--cp-text-muted)" }}>
            Knockout bracket unlocks after the group stage. Round of 32 begins <b>2 July 2026</b>.
          </div>
        )}
        {tab === "media" && (
          <div className="text-xs" style={{ color: "var(--cp-text-muted)" }}>
            Highlight reels and recaps will appear here once matches kick off.
          </div>
        )}
      </div>
    </div>
  );
}

function OverviewMatchCard({ m }) {
  const dt = m.scheduled_at ? new Date(m.scheduled_at.replace(" ", "T") + (m.scheduled_at.endsWith("Z") ? "" : "Z")) : null;
  const date = dt ? `${String(dt.getDate()).padStart(2, "0")}/${String(dt.getMonth() + 1).padStart(2, "0")}/${String(dt.getFullYear()).slice(-2)}` : "—";
  const time = dt ? `${String(dt.getHours()).padStart(2, "0")}:${String(dt.getMinutes()).padStart(2, "0")}` : "";
  return (
    <div className="rounded-lg p-3" style={{ background: "var(--cp-surface-2)" }} data-testid={`overview-card-${m.id}`}>
      <div className="flex items-center justify-between text-[10px] uppercase tracking-widest mb-2" style={{ color: "var(--cp-text-muted)" }}>
        <span>{m.group ? `Group ${m.group}` : m.round || "Group"}, Round {m.matchday || "1"}</span>
        <span className="inline-flex items-center gap-1"><MapPin size={10}/>{m.venue_city || m.venue_name || "TBC"}</span>
      </div>
      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3">
        <div className="flex flex-col items-center gap-1">
          {flagUrl(m.home_team_name, 80) ? <img src={flagUrl(m.home_team_name, 80)} className="w-10 h-7 object-cover rounded-sm ring-1 ring-black/30" alt=""/> : <span className="w-10 h-7 rounded-sm" style={{ background: "var(--cp-surface)" }}/>}
          <span className="text-xs font-bold text-center">{m.home_team_name}</span>
        </div>
        <div className="text-center">
          <div className="text-sm font-extrabold tabular-nums">{date}</div>
          <div className="text-[10px]" style={{ color: "var(--cp-text-muted)" }}>{time}</div>
        </div>
        <div className="flex flex-col items-center gap-1">
          {flagUrl(m.away_team_name, 80) ? <img src={flagUrl(m.away_team_name, 80)} className="w-10 h-7 object-cover rounded-sm ring-1 ring-black/30" alt=""/> : <span className="w-10 h-7 rounded-sm" style={{ background: "var(--cp-surface)" }}/>}
          <span className="text-xs font-bold text-center">{m.away_team_name}</span>
        </div>
      </div>
    </div>
  );
}

function StandingsTable({ groups, matches, compact = false }) {
  // Compute live standings from finished matches.
  const teamStats = useMemo(() => {
    const stats = {};
    groups.forEach(g => (g.teams || []).forEach(t => {
      stats[t] = { team: t, group: g.group, P: 0, W: 0, D: 0, L: 0, GF: 0, GA: 0, PTS: 0 };
    }));
    matches.forEach(m => {
      if (m.home_score == null || m.away_score == null) return;
      const h = stats[m.home_team_name]; const a = stats[m.away_team_name];
      if (!h || !a) return;
      h.P += 1; a.P += 1;
      h.GF += m.home_score; h.GA += m.away_score;
      a.GF += m.away_score; a.GA += m.home_score;
      if (m.home_score > m.away_score) { h.W += 1; a.L += 1; h.PTS += 3; }
      else if (m.home_score < m.away_score) { a.W += 1; h.L += 1; a.PTS += 3; }
      else { h.D += 1; a.D += 1; h.PTS += 1; a.PTS += 1; }
    });
    return stats;
  }, [groups, matches]);

  const [pick, setPick] = useState(groups[0]?.group || "A");
  const groupTeams = (groups.find(g => g.group === pick)?.teams || []);
  const rows = groupTeams.map(t => teamStats[t] || { team: t, P: 0, W: 0, D: 0, L: 0, GF: 0, GA: 0, PTS: 0 })
    .sort((a, b) => b.PTS - a.PTS || (b.GF - b.GA) - (a.GF - a.GA) || b.GF - a.GF);

  return (
    <div data-testid="wc-standings">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-extrabold">Standings</span>
        {!compact && <Link to="/leaderboards" className="text-[11px] font-bold text-cp-lime hover:underline">Full view →</Link>}
      </div>
      <div className="flex items-center gap-1 mb-2 overflow-x-auto no-scrollbar">
        {groups.map(g => (
          <button key={g.group} onClick={() => setPick(g.group)} className="text-[11px] font-extrabold px-3 py-1.5 rounded-full whitespace-nowrap"
            style={{ background: pick === g.group ? "var(--cp-forest)" : "var(--cp-surface-2)", color: pick === g.group ? "#fff" : "var(--cp-text-muted)" }}
            data-testid={`standings-group-${g.group}`}>
            Group {g.group}
          </button>
        ))}
      </div>
      <table className="w-full text-xs">
        <thead>
          <tr style={{ color: "var(--cp-text-muted)" }} className="text-[10px] uppercase tracking-widest">
            <th className="text-left font-normal py-1.5">#</th>
            <th className="text-left font-normal py-1.5">Team</th>
            <th className="font-normal py-1.5">P</th>
            <th className="font-normal py-1.5">W</th>
            <th className="font-normal py-1.5">D</th>
            <th className="font-normal py-1.5">L</th>
            <th className="font-normal py-1.5">GF</th>
            <th className="font-normal py-1.5">GA</th>
            <th className="font-normal py-1.5">PTS</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, idx) => (
            <tr key={r.team} className="border-t" style={{ borderColor: "var(--cp-border)" }}>
              <td className="py-1.5 font-bold tabular-nums">{idx + 1}</td>
              <td className="py-1.5 flex items-center gap-1.5">
                {flagUrl(r.team, 40) ? <img src={flagUrl(r.team, 40)} className="w-4 h-3 object-cover rounded-sm ring-1 ring-black/30" alt=""/> : null}
                <span>{r.team}</span>
              </td>
              <td className="py-1.5 text-center tabular-nums">{r.P}</td>
              <td className="py-1.5 text-center tabular-nums">{r.W}</td>
              <td className="py-1.5 text-center tabular-nums">{r.D}</td>
              <td className="py-1.5 text-center tabular-nums">{r.L}</td>
              <td className="py-1.5 text-center tabular-nums">{r.GF}</td>
              <td className="py-1.5 text-center tabular-nums">{r.GA}</td>
              <td className="py-1.5 text-center font-extrabold tabular-nums text-cp-lime">{r.PTS}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Right column: World Cup News cards (admin-curated). */
function NewsPane({ news }) {
  return (
    <div className="space-y-3" data-testid="wc-news-pane">
      <h3 className="text-center text-sm font-extrabold py-2">World Cup news</h3>
      {(news || []).length === 0 && (
        <div className="cp-surface p-4 text-xs text-center" style={{ color: "var(--cp-text-muted)" }}>
          No news yet — admins can publish stories from Admin → WC News.
        </div>
      )}
      {(news || []).map(n => (
        <a key={n.id} href={n.source_url || "#"} target={n.source_url ? "_blank" : undefined} rel="noopener noreferrer"
           className="cp-surface overflow-hidden block hover:bg-white/[0.02]" data-testid={`wc-news-${n.id}`}>
          {n.image_url && <img src={n.image_url} alt="" className="w-full aspect-[16/10] object-cover" loading="lazy"/>}
          <div className="p-3 space-y-1.5">
            <div className="text-sm font-bold leading-snug line-clamp-2">{n.title}</div>
            {n.summary && <p className="text-[11px] line-clamp-3" style={{ color: "var(--cp-text-muted)" }}>{n.summary}</p>}
            <div className="text-[10px] flex items-center gap-1" style={{ color: "var(--cp-text-muted)" }}>
              <Trophy size={10} className="text-cp-lime"/>
              {n.source_name || "Cloudy Pitch"}
              {n.created_at && <span className="opacity-60">· {n.created_at.slice(0, 10)}</span>}
            </div>
          </div>
        </a>
      ))}
    </div>
  );
}

export const WorldCupHub = () => {
  const [data, setData] = useState(null);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data: d } = await api.get("/worldcup");
        if (!cancelled) setData(d);
      } catch (_e) { /* ignore */ }
    })();
    return () => { cancelled = true; };
  }, []);

  const matches = data?.matches || [];
  const groups = data?.groups || [];
  const news = data?.news || [];
  const startsAt = data?.starts_at || "2026-06-11T18:00:00+00:00";

  return (
    <div data-testid="worldcup-hub" className="space-y-3">
      <WcGroupStrip startsAt={startsAt} groups={groups}/>
      <AdSlot placement="wc_hub_top" minHeight={0} className="mb-3"/>
      <WcHero startsAt={startsAt}/>
      <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr_320px] gap-3 mt-4">
        <MatchesPane matches={matches}/>
        <MiddlePane matches={matches} groups={groups}/>
        <NewsPane news={news}/>
      </div>
    </div>
  );
};

export default WorldCupHub;
