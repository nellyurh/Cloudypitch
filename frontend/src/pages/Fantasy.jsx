import React, { useEffect, useState } from "react";
import api from "../lib/api";
import { useAuth } from "../lib/auth";
import { Link, useNavigate } from "react-router-dom";
import { Trophy, LogIn, ArrowRight, Lock, Plus, Repeat, Sparkles, Star } from "lucide-react";
import { WcGamesPanel } from "./WcGames";
import { useServiceStatus } from "../lib/serviceStatus";
import ServicePausedScreen from "../components/ServicePausedScreen";

/**
 * Fantasy entry page — Sofascore-style competition picker.
 *
 *   Click `/fantasy` → see the list of competitions (only "World Cup 2026"
 *   today; extensible later).
 *
 *   Pick WC → if no main 15-man squad yet, push them to /build-team.
 *   If they HAVE a main squad, show:
 *     • Card summary of their main team (link → /build-team)
 *     • Grid of 148 WC mini-games (entry status + admin lock badge)
 */

const COMPETITIONS = [
  {
    id: "wc2026",
    name: "FIFA World Cup 2026",
    subtitle: "1 main 15-man squad · 148 mini-games · €100M budget",
    accent: "#A3E635",
    logo: "https://customer-assets.emergentagent.com/job_fantasy-wc/artifacts/gbyjrmxz_world-cup-2026-logo.webp",
    enabled: true,
  },
  // Future competitions (Champions League, Euros, etc.) — show as locked.
  { id: "ucl", name: "Champions League 2026/27", subtitle: "Coming soon", accent: "#3B5BDB", enabled: false },
  { id: "euros", name: "Euros 2028", subtitle: "Coming soon", accent: "#FFB400", enabled: false },
];

const FantasyHub = () => {
  const { user } = useAuth();
  const nav = useNavigate();
  const svc = useServiceStatus();
  const [selected, setSelected] = useState(null);  // selected competition id
  const [mainSquad, setMainSquad] = useState(null); // user's main WC squad (15-man)
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) { setLoading(false); return; }
    (async () => {
      try {
        const { data } = await api.get("/fantasy/squad/me");
        setMainSquad(data?.squad || null);
      } catch (_) {}
      setLoading(false);
    })();
  }, [user]);

  // 🛑 Admin kill-switch: if Fantasy is paused, show shutdown screen.
  // Placed AFTER all hooks so React hook order is consistent.
  if (svc?.fantasy && svc.fantasy.enabled === false) {
    return <ServicePausedScreen service="fantasy" reason={svc.fantasy.shutdown_reason}/>;
  }

  if (!user) {
    return (
      <div className="cp-surface p-10 text-center max-w-xl mx-auto mt-6" data-testid="fantasy-signin-gate">
        <Trophy size={36} className="mx-auto text-cp-lime"/>
        <h1 className="text-2xl font-extrabold mt-3">Build your fantasy team</h1>
        <p className="text-sm mt-2" style={{ color: "var(--cp-text-muted)" }}>
          Sign in to pick players, captain your stars, play 148 mini-games and chase the prize pool.
        </p>
        <div className="flex gap-2 mt-5 justify-center">
          <Link to="/signin" className="cp-btn-primary inline-flex items-center gap-1" data-testid="fantasy-go-signin"><LogIn size={14}/> Sign in</Link>
          <Link to="/signup" className="cp-btn-ghost" data-testid="fantasy-go-signup">Create free account</Link>
        </div>
      </div>
    );
  }

  // STEP 1 — Competition picker (default landing)
  if (!selected) {
    return (
      <div className="max-w-[900px] mx-auto" data-testid="competition-picker">
        <div className="cp-surface p-4 mb-3">
          <h1 className="text-xl md:text-2xl font-extrabold">Choose a competition</h1>
          <p className="text-xs mt-1" style={{ color: "var(--cp-text-muted)" }}>
            Build a separate fantasy squad for each competition. Apply your Legend Cards on any team to boost points.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {COMPETITIONS.map(c => (
            <button
              key={c.id}
              disabled={!c.enabled}
              onClick={() => c.enabled && setSelected(c.id)}
              className="cp-surface p-4 text-left hover:bg-white/5 transition disabled:opacity-50 disabled:cursor-not-allowed flex flex-col gap-3"
              style={{ borderTop: `3px solid ${c.accent}` }}
              data-testid={`competition-${c.id}`}
            >
              <div className="flex items-center gap-3">
                {c.logo ? (
                  <img src={c.logo} alt="" className="w-10 h-10 object-contain"/>
                ) : (
                  <div className="w-10 h-10 rounded-full" style={{ background: c.accent + "33" }}/>
                )}
                <div className="flex-1 min-w-0">
                  <div className="font-extrabold truncate">{c.name}</div>
                  <div className="text-[11px]" style={{ color: "var(--cp-text-muted)" }}>{c.subtitle}</div>
                </div>
                {!c.enabled && <Lock size={14} className="opacity-60"/>}
              </div>
              {c.enabled && (
                <div className="text-xs font-extrabold flex items-center gap-1.5" style={{ color: c.accent }}>
                  Enter <ArrowRight size={12}/>
                </div>
              )}
            </button>
          ))}
        </div>
      </div>
    );
  }

  // STEP 2 — WC2026 hub: main squad summary + 148 WC mini-games grid
  if (selected === "wc2026") {
    return (
      <div className="max-w-[1100px] mx-auto" data-testid="wc2026-hub">
        <div className="cp-surface p-4 mb-3 flex items-center justify-between gap-3 flex-wrap">
          <div>
            <button
              onClick={() => setSelected(null)}
              className="text-[11px] uppercase tracking-widest font-bold mb-1 inline-flex items-center gap-1"
              style={{ color: "var(--cp-text-muted)" }}
              data-testid="back-to-competitions"
            >
              ← All competitions
            </button>
            <h1 className="text-xl md:text-2xl font-extrabold flex items-center gap-2">
              <Trophy size={20} className="text-cp-lime"/> FIFA World Cup 2026
            </h1>
          </div>
        </div>

        {/* Main 15-man squad card */}
        {loading ? (
          <div className="cp-surface p-6 text-center text-sm opacity-60">Loading…</div>
        ) : !mainSquad ? (
          <div className="cp-surface p-6 text-center" data-testid="main-squad-empty">
            <Plus size={28} className="mx-auto text-cp-lime mb-2"/>
            <h2 className="font-extrabold text-lg">Build your main 15-man squad</h2>
            <p className="text-xs mt-1 mb-4" style={{ color: "var(--cp-text-muted)" }}>
              Required first. €100M budget · 2 GK / 5 DEF / 5 MID / 3 FWD. Used as your default team across all 148 mini-games.
            </p>
            <Link
              to="/build-team?mode=15"
              className="inline-flex items-center gap-1.5 rounded px-4 py-2.5 font-extrabold text-sm"
              style={{ background: "var(--cp-lime)", color: "var(--cp-forest)" }}
              data-testid="build-main-squad-cta"
            >
              Build main squad <ArrowRight size={14}/>
            </Link>
          </div>
        ) : (
          <Link
            to="/build-team?mode=15"
            className="cp-surface p-4 mb-3 flex items-center gap-3 hover:bg-white/5 transition"
            data-testid="main-squad-card"
          >
            <div className="w-12 h-12 rounded-full flex items-center justify-center" style={{ background: "rgba(163,230,53,0.15)" }}>
              <Trophy size={20} className="text-cp-lime"/>
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-extrabold truncate">{mainSquad.squad_name || "My WC Squad"}</div>
              <div className="text-[11px] mt-0.5 flex items-center gap-2" style={{ color: "var(--cp-text-muted)" }}>
                <span><b className="text-cp-text">{(mainSquad.players || []).length}</b>/15 players</span>
                <span>·</span>
                <span><b className="text-cp-text">€{((mainSquad.players || []).reduce((s, p) => s + (p.price_paid || 0), 0)).toFixed(1)}M</b> spent</span>
                <span>·</span>
                <span><b className="text-cp-lime">{mainSquad.total_points || 0}</b> pts</span>
              </div>
            </div>
            <div className="flex items-center gap-1 text-xs font-extrabold text-cp-lime">
              Edit <ArrowRight size={12}/>
            </div>
          </Link>
        )}

        {/* Quick actions row — same Substitutions / Transfers / Cards / Leaderboard
            buttons that appear on every team page. */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-3">
          <Link to="/build-team?mode=15" className="cp-surface p-3 text-center hover:bg-white/5" data-testid="qa-build">
            <Repeat size={16} className="mx-auto text-cp-lime mb-1"/>
            <div className="text-xs font-bold">Substitutions</div>
          </Link>
          <Link to="/my-teams" className="cp-surface p-3 text-center hover:bg-white/5" data-testid="qa-transfers">
            <Sparkles size={16} className="mx-auto text-cp-lime mb-1"/>
            <div className="text-xs font-bold">Transfers</div>
          </Link>
          <Link to="/cards" className="cp-surface p-3 text-center hover:bg-white/5" data-testid="qa-cards">
            <Star size={16} className="mx-auto text-cp-lime mb-1"/>
            <div className="text-xs font-bold">Apply Cards</div>
          </Link>
          <Link to="/leaderboards" className="cp-surface p-3 text-center hover:bg-white/5" data-testid="qa-leaderboard">
            <Trophy size={16} className="mx-auto text-cp-lime mb-1"/>
            <div className="text-xs font-bold">Leaderboard</div>
          </Link>
        </div>

        {/* 148 WC mini-games — only visible once main squad exists */}
        {mainSquad && (
          <div className="cp-surface overflow-hidden">
            <div className="cp-card-header normal-case">
              <span className="flex items-center gap-2 font-bold" style={{ color: "var(--cp-text)" }}>
                <Trophy size={14} className="text-cp-lime"/> WC Mini-Games (148)
              </span>
              <span className="text-[10px]" style={{ color: "var(--cp-text-muted)" }}>
                Build a custom team for each. Locked games unlock when admin opens them.
              </span>
            </div>
            <div className="p-2">
              <WcGamesPanel user={user}/>
            </div>
          </div>
        )}
      </div>
    );
  }

  // Future competition picked (shouldn't be reachable since disabled)
  return null;
};

export { FantasyHub };
export default FantasyHub;
