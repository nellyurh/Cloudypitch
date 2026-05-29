import React, { useEffect, useState } from "react";
import api from "../lib/api";
import { Link } from "react-router-dom";
import { Trophy, Coins, Calendar, Layers, Users2, History, Sparkles } from "lucide-react";
import { MatchRow } from "../components/MatchRow";
import { flagUrl } from "../lib/flags";
import AdSlot from "../components/AdSlot";

function CountdownLarge({ to }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t); }, []);
  const ms = new Date(to).getTime() - now;
  const d = Math.max(0, Math.floor(ms / 86400000));
  const h = Math.max(0, Math.floor((ms % 86400000) / 3600000));
  const min = Math.max(0, Math.floor((ms % 3600000) / 60000));
  const s = Math.max(0, Math.floor((ms % 60000) / 1000));
  const B = ({ v, l }) => (
    <div className="text-center px-3 md:px-5 py-2 cp-surface min-w-[80px]" data-testid={`countdown-${l.toLowerCase()}`}>
      <div className="text-3xl md:text-5xl font-extrabold tabular-nums" style={{ color: "#A3E635" }}>{String(v).padStart(2, "0")}</div>
      <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>{l}</div>
    </div>
  );
  return (
    <div className="flex items-center justify-center gap-2 md:gap-3 flex-wrap" data-testid="wc-hub-countdown">
      <B v={d} l="Days"/><B v={h} l="Hours"/><B v={min} l="Mins"/><B v={s} l="Secs"/>
    </div>
  );
}

const BracketSlot = ({ label, source }) => (
  <div className="cp-surface px-3 py-2 text-xs flex flex-col gap-1 min-w-[140px]" data-testid={`bracket-slot-${label}`}>
    <span className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>{label}</span>
    <span className="font-medium truncate">{source}</span>
  </div>
);

function BracketView() {
  const groups = ["A","B","C","D","E","F","G","H","I","J","K","L"];
  return (
    <div className="space-y-6 overflow-x-auto pb-3" data-testid="bracket-view">
      {/* Round of 32 */}
      <section>
        <h3 className="text-sm font-extrabold uppercase tracking-widest mb-3" style={{ color: "var(--cp-text-muted)" }}>
          Round of 32 · 12 June 2026
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {groups.map((g, i) => (
            <div key={g} className="cp-surface p-3 space-y-2" data-testid={`r32-${g}`}>
              <div className="text-[10px] uppercase tracking-widest text-cp-lime">Match {i+1}</div>
              <BracketSlot label="1st" source={`Winner Group ${g}`} />
              <div className="text-center text-[10px]" style={{ color: "var(--cp-text-muted)" }}>vs</div>
              <BracketSlot label="3rd" source={`Best 3rd / Group ${groups[(i+1)%12]}`} />
            </div>
          ))}
        </div>
      </section>

      {/* Round of 16 */}
      <section>
        <h3 className="text-sm font-extrabold uppercase tracking-widest mb-3" style={{ color: "var(--cp-text-muted)" }}>Round of 16</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="cp-surface p-3 space-y-2" data-testid={`r16-${i+1}`}>
              <div className="text-[10px] uppercase tracking-widest text-cp-lime">Match {i+1}</div>
              <BracketSlot label="W" source={`Winner R32-${i*2+1}`} />
              <div className="text-center text-[10px]" style={{ color: "var(--cp-text-muted)" }}>vs</div>
              <BracketSlot label="W" source={`Winner R32-${i*2+2}`} />
            </div>
          ))}
        </div>
      </section>

      {/* Quarterfinals + Semifinals + Final */}
      <section>
        <h3 className="text-sm font-extrabold uppercase tracking-widest mb-3" style={{ color: "var(--cp-text-muted)" }}>Quarters · Semis · Final</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="cp-surface p-3 space-y-3">
            <div className="text-[10px] uppercase tracking-widest text-cp-lime">Quarterfinals</div>
            {[1,2,3,4].map(i => <BracketSlot key={i} label={`QF${i}`} source="TBD" />)}
          </div>
          <div className="cp-surface p-3 space-y-3">
            <div className="text-[10px] uppercase tracking-widest text-cp-lime">Semifinals</div>
            {[1,2].map(i => <BracketSlot key={i} label={`SF${i}`} source="TBD" />)}
          </div>
          <div className="cp-surface p-3 space-y-3 ring-1 ring-cp-lime/40">
            <div className="text-[10px] uppercase tracking-widest text-cp-lime flex items-center gap-1">
              <Trophy size={11}/> FINAL — 19 July 2026
            </div>
            <BracketSlot label="🏆" source="TBD" />
          </div>
        </div>
      </section>
    </div>
  );
}

const TABS = [
  { k: "groups", l: "Groups", icon: Users2 },
  { k: "bracket", l: "Knockout", icon: Layers },
  { k: "schedule", l: "Schedule", icon: Calendar },
  { k: "past", l: "Past Tournaments", icon: History },
  { k: "prize", l: "Prize Pool", icon: Coins },
];

function PastTournamentsView() {
  const [tours, setTours] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    (async () => {
      try { const { data } = await api.get("/worldcup/past"); setTours(data.tournaments || []); } catch (_) {}
      setLoading(false);
    })();
  }, []);
  if (loading) return <div className="cp-surface p-6 text-sm">Loading archive…</div>;
  return (
    <div className="space-y-4" data-testid="wc-past-list">
      <div className="cp-surface p-4">
        <h3 className="text-base font-extrabold inline-flex items-center gap-2"><Sparkles size={16} className="text-cp-lime"/> Legendary Performances Archive</h3>
        <p className="text-xs mt-1" style={{ color: "var(--cp-text-muted)" }}>
          Every Legend Card in your collection earned its place at a World Cup. Tap any card-linked highlight to view the live card.
        </p>
      </div>
      {tours.map(t => (
        <div key={t.year} className="cp-surface overflow-hidden" data-testid={`past-tour-${t.year}`}>
          <div
            className="relative px-4 py-5 text-white"
            style={{ background: `linear-gradient(180deg, rgba(6,78,59,0.65) 0%, rgba(26,31,38,0.92) 100%), url('${t.image_url}')`, backgroundSize: "cover", backgroundPosition: "center" }}
          >
            <div className="text-[10px] uppercase tracking-widest" style={{ color: "#A3E635" }}>FIFA WORLD CUP · {t.host}</div>
            <h2 className="text-3xl font-extrabold mt-1">{t.year} · 🏆 {t.champion}</h2>
            <p className="text-sm mt-1" style={{ color: "rgba(255,255,255,0.85)" }}>{t.final}</p>
            <div className="flex gap-3 mt-2 text-xs flex-wrap">
              <span><span className="opacity-60">Golden Ball:</span> <b>{t.golden_ball}</b></span>
              <span><span className="opacity-60">Golden Boot:</span> <b>{t.golden_boot}</b></span>
            </div>
          </div>
          <ul className="divide-y" style={{ borderColor: "var(--cp-border)" }}>
            {t.highlights.map((h, idx) => {
              const hasCard = !!h.card_doc;
              const Body = (
                <div className="px-4 py-3 flex items-start gap-3 hover:bg-white/5 transition" data-testid={`past-hl-${t.year}-${idx}`}>
                  <div className="w-10 h-10 rounded flex items-center justify-center shrink-0" style={{ background: hasCard ? "rgba(163,230,53,0.15)" : "var(--cp-surface-2)" }}>
                    {hasCard ? <Sparkles size={16} className="text-cp-lime"/> : <Trophy size={16} className="opacity-60"/>}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-extrabold">{h.player}</span>
                      <span className="text-[10px] cp-pill" style={{ background: "var(--cp-surface-2)", color: "var(--cp-text-muted)" }}>{h.country_code}</span>
                      {hasCard && (
                        <span className="text-[10px] cp-pill font-bold" style={{ background: "rgba(163,230,53,0.15)", color: "#A3E635" }}>
                          Legend Card · ${((h.card_doc.price_usd_cents || 0) / 100).toFixed(2)}
                        </span>
                      )}
                    </div>
                    <div className="text-sm font-medium mt-1">{h.stat}</div>
                    <div className="text-xs mt-1" style={{ color: "var(--cp-text-muted)" }}>{h.moment}</div>
                  </div>
                </div>
              );
              return (
                <li key={idx}>
                  {hasCard ? <Link to="/cards" data-testid={`past-card-${h.card_doc.id}`}>{Body}</Link> : Body}
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </div>
  );
}

export const WorldCupHub = () => {
  const [data, setData] = useState(null);
  const [tab, setTab] = useState("groups");
  useEffect(() => {
    (async () => {
      try { const { data } = await api.get("/worldcup"); setData(data); } catch (_) {}
    })();
  }, []);

  return (
    <div data-testid="worldcup-hub">
      <div
        className="relative overflow-hidden rounded-xl"
        style={{
          background: `linear-gradient(180deg, rgba(6,78,59,0.7) 0%, rgba(26,31,38,0.92) 90%), url('https://images.unsplash.com/photo-1705593973313-75de7bf95b56?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2NjZ8MHwxfHNlYXJjaHwxfHxmb290YmFsbCUyMHN0YWRpdW0lMjBjcm93ZHxlbnwwfHx8fDE3Nzk5MTk4MTF8MA&ixlib=rb-4.1.0&q=85')`,
          backgroundSize: "cover",
          backgroundPosition: "center",
        }}
      >
        <div className="px-6 md:px-10 py-10 md:py-14 text-white">
          <div className="inline-flex items-center gap-2 cp-pill" style={{ background: "rgba(163,230,53,0.2)", color: "#A3E635" }}>
            <Trophy size={12}/> FIFA WORLD CUP 2026
          </div>
          <h1 className="text-3xl md:text-5xl font-extrabold mt-3 tracking-tight">USA · Canada · Mexico</h1>
          <p className="text-sm md:text-base mt-1" style={{ color: "rgba(255,255,255,0.85)" }}>
            48 teams · 12 groups · 104 matches · One champion. Predict, build squads, win the pool.
          </p>
          <div className="mt-5"><CountdownLarge to={data?.starts_at || "2026-06-11T18:00:00+00:00"} /></div>
          <div className="flex gap-2 mt-5">
            <Link to="/predictions" className="cp-btn-primary" data-testid="wc-cta-predict">Make Predictions</Link>
            <Link to="/fantasy" className="cp-btn-ghost text-white" data-testid="wc-cta-fantasy" style={{ background: "rgba(255,255,255,0.08)", borderColor: "rgba(255,255,255,0.2)" }}>Build Fantasy Squad</Link>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 cp-surface p-1 mt-5 overflow-x-auto" data-testid="wc-tabs">
        {TABS.map(({ k, l, icon: Icon }) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            className={`px-3 py-2 text-sm rounded transition whitespace-nowrap inline-flex items-center gap-1.5 ${
              tab === k ? "bg-cp-lime text-cp-forest font-bold" : "hover:bg-white/5"
            }`}
            data-testid={`wc-tab-${k}`}
          >
            <Icon size={13}/> {l}
          </button>
        ))}
      </div>

      <div className="mt-4">
        {tab === "groups" && (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3" data-testid="groups-grid">
              {(data?.groups || []).slice(0, 6).map(g => (
                <div key={g.group} className="cp-surface p-3" data-testid={`group-${g.group}`}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Group</span>
                    <span className="text-2xl font-extrabold text-cp-lime">{g.group}</span>
                  </div>
                  <div className="grid grid-cols-[1fr_auto_auto_auto_auto] text-[10px] uppercase tracking-widest border-b pb-1 mb-1" style={{ color: "var(--cp-text-muted)", borderColor: "var(--cp-border)" }}>
                    <span>Team</span><span>P</span><span>W</span><span>D</span><span>Pts</span>
                  </div>
                  <ul className="divide-y" style={{ borderColor: "var(--cp-border)" }}>
                    {(g.teams || []).map(t => (
                      <li key={t} className="grid grid-cols-[1fr_auto_auto_auto_auto] items-center gap-2 py-1.5 text-sm">
                        <div className="flex items-center gap-2 truncate">
                          {flagUrl(t, 40) ? (
                            <img src={flagUrl(t, 40)} className="w-5 h-3.5 object-cover rounded-sm shrink-0 ring-1 ring-black/30" alt="" />
                          ) : (
                            <span className="w-5 h-3.5 rounded-sm shrink-0" style={{ background: "var(--cp-surface-2)" }} />
                          )}
                          <span className="truncate text-xs">{t}</span>
                        </div>
                        <span className="text-[10px] font-mono tabular-nums" style={{ color: "var(--cp-text-muted)" }}>0</span>
                        <span className="text-[10px] font-mono tabular-nums" style={{ color: "var(--cp-text-muted)" }}>0</span>
                        <span className="text-[10px] font-mono tabular-nums" style={{ color: "var(--cp-text-muted)" }}>0</span>
                        <span className="text-[10px] font-bold tabular-nums">0</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
            <AdSlot placementKey="wc_hub_sponsor" className="my-4"/>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
              {(data?.groups || []).slice(6).map(g => (
                <div key={g.group} className="cp-surface p-3" data-testid={`group-${g.group}`}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Group</span>
                    <span className="text-2xl font-extrabold text-cp-lime">{g.group}</span>
                  </div>
                  <div className="grid grid-cols-[1fr_auto_auto_auto_auto] text-[10px] uppercase tracking-widest border-b pb-1 mb-1" style={{ color: "var(--cp-text-muted)", borderColor: "var(--cp-border)" }}>
                    <span>Team</span><span>P</span><span>W</span><span>D</span><span>Pts</span>
                  </div>
                  <ul className="divide-y" style={{ borderColor: "var(--cp-border)" }}>
                    {(g.teams || []).map(t => (
                      <li key={t} className="grid grid-cols-[1fr_auto_auto_auto_auto] items-center gap-2 py-1.5 text-sm">
                        <div className="flex items-center gap-2 truncate">
                          {flagUrl(t, 40) ? (
                            <img src={flagUrl(t, 40)} className="w-5 h-3.5 object-cover rounded-sm shrink-0 ring-1 ring-black/30" alt="" />
                          ) : (
                            <span className="w-5 h-3.5 rounded-sm shrink-0" style={{ background: "var(--cp-surface-2)" }} />
                          )}
                          <span className="truncate text-xs">{t}</span>
                        </div>
                        <span className="text-[10px] font-mono tabular-nums" style={{ color: "var(--cp-text-muted)" }}>0</span>
                        <span className="text-[10px] font-mono tabular-nums" style={{ color: "var(--cp-text-muted)" }}>0</span>
                        <span className="text-[10px] font-mono tabular-nums" style={{ color: "var(--cp-text-muted)" }}>0</span>
                        <span className="text-[10px] font-bold tabular-nums">0</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </>
        )}

        {tab === "bracket" && <BracketView />}

        {tab === "schedule" && (
          (data?.matches?.length || 0) > 0 ? (
            <div className="cp-surface overflow-hidden" data-testid="wc-schedule">
              {data.matches.map(m => <MatchRow key={m.id} m={m} />)}
            </div>
          ) : (
            <div className="cp-surface p-10 text-center" data-testid="wc-schedule-empty">
              <Calendar size={36} className="mx-auto text-cp-lime opacity-60"/>
              <h3 className="text-base font-bold mt-3">WC 2026 schedule lands on draw day</h3>
              <p className="text-xs mt-1 max-w-md mx-auto" style={{ color: "var(--cp-text-muted)" }}>
                Official tournament fixtures (June 11 – July 19, 2026) are ingested live from Sportmonks once FIFA publishes the final draw. In the meantime, explore <Link to="/fantasy" className="text-cp-lime">Fantasy & WC Games</Link> or relive past tournaments above.
              </p>
            </div>
          )
        )}

        {tab === "past" && <PastTournamentsView/>}

        {tab === "prize" && (
          data?.prize_pool ? (
            <div className="cp-surface p-6" data-testid="wc-prize-pool-card">
              <div className="flex items-center gap-3">
                <Coins size={36} className="text-cp-lime" />
                <div className="flex-1">
                  <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Grand Prize Pool</div>
                  <div className="text-lg font-bold">{data.prize_pool.title}</div>
                  <div className="text-3xl font-extrabold text-cp-lime mt-1">${(((data.prize_pool.amount_usd_cents || 0) / 100)).toLocaleString(undefined, { minimumFractionDigits: 2 })}</div>
                </div>
                <Link to={`/prize-pool/${data.prize_pool.id}`} className="cp-btn-primary" data-testid="wc-prize-cta">View Payouts</Link>
              </div>
              {data?.competition && (
                <div className="mt-5 pt-5 border-t" style={{ borderColor: "var(--cp-border)" }}>
                  <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Fantasy Competition</div>
                  <div className="font-bold mt-1">{data.competition.name}</div>
                  <p className="text-xs mt-1" style={{ color: "var(--cp-text-muted)" }}>
                    Squad size {data.competition.squad_size || 15} · Budget £{data.competition.budget_total || 100}m · {data.competition.transfers_per_gw || 1} transfer/gameweek
                  </p>
                  <Link to="/fantasy" className="cp-btn-primary mt-3 inline-block">Open Squad Builder</Link>
                </div>
              )}
            </div>
          ) : (
            <div className="cp-surface p-10 text-center">
              <Coins size={36} className="mx-auto text-cp-lime opacity-60"/>
              <p className="text-sm mt-3" style={{ color: "var(--cp-text-muted)" }}>Prize pool details coming soon.</p>
            </div>
          )
        )}
      </div>
    </div>
  );
};

export default WorldCupHub;
