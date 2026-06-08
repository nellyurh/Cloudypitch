import React, { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Link, useNavigate, NavLink } from "react-router-dom";
import api from "../lib/api";
import { Brand } from "./Brand";
import { SportIcon } from "./SportIcon";
import { useAuth } from "../lib/auth";
import { useTheme } from "../lib/theme";
import { Search, Moon, SunMedium, Trophy, ChevronDown, LogOut, User, ShieldCheck, Menu, X, Coins, Target, Crown } from "lucide-react";

const ALL_SPORTS = [
  { slug: "football", name: "Football" },
  { slug: "basketball", name: "Basketball" },
  { slug: "tennis", name: "Tennis" },
  { slug: "baseball", name: "Baseball" },
  { slug: "hockey", name: "Hockey" },
  { slug: "cricket", name: "Cricket" },
  { slug: "rugby", name: "Rugby" },
  { slug: "nba", name: "NBA" },
  { slug: "volleyball", name: "Volleyball" },
  { slug: "handball", name: "Handball" },
  { slug: "mma", name: "MMA" },
  { slug: "f1", name: "F1" },
  { slug: "afl", name: "AFL" },
  { slug: "golf", name: "Golf" },
];

export const Header = () => {
  const { user, signout } = useAuth();
  const { theme, toggle } = useTheme();
  const [q, setQ] = useState("");
  const [menu, setMenu] = useState(false);
  const [drawer, setDrawer] = useState(false);
  const [siteCfg, setSiteCfg] = useState({ enabled_sports: ALL_SPORTS.map(s => s.slug), show_wc_tab: true });
  const nav = useNavigate();

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/site-config");
        setSiteCfg({
          enabled_sports: Array.isArray(data?.enabled_sports) && data.enabled_sports.length
            ? data.enabled_sports
            : ALL_SPORTS.map(s => s.slug),
          show_wc_tab: data?.show_wc_tab !== false,
        });
      } catch (_e) { /* ignore — keep defaults */ }
    })();
  }, []);

  const SPORTS = ALL_SPORTS.filter(s => siteCfg.enabled_sports.includes(s.slug));

  const submit = (e) => {
    e.preventDefault();
    if (q.trim().length >= 2) nav(`/search?q=${encodeURIComponent(q.trim())}`);
  };

  return (
    <header
      className="sticky top-0 z-30 backdrop-blur"
      style={{
        background: "linear-gradient(180deg, #0F6E56 0%, #075A45 60%, #064E3B 100%)",
        borderBottom: "1px solid #042e22",
        boxShadow: "0 2px 12px rgba(0,0,0,0.25)",
      }}
      data-testid="site-header"
    >
      {/* Top row */}
      <div className="max-w-[1400px] mx-auto px-3 md:px-5 py-1 md:py-2.5 flex items-center gap-3 min-h-[56px]">
        {/* Mobile hamburger */}
        <button onClick={() => setDrawer(true)} className="lg:hidden cp-btn-ghost !p-2" style={{ color: "#fff" }} aria-label="Open menu" data-testid="mobile-menu-btn">
          <Menu size={18} />
        </button>

        <Link to="/" data-testid="brand-home-link" className="shrink-0">
          <Brand size={44} />
        </Link>

        {/* Desktop-only search */}
        <form onSubmit={submit} className="ml-auto relative w-44 lg:w-72 hidden md:block" data-testid="search-form">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2" style={{ color: "rgba(255,255,255,0.55)" }} />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search teams, leagues, players…"
            className="pl-8 pr-3 py-2 text-sm w-full rounded"
            style={{
              background: "rgba(0,0,0,0.18)",
              border: "1px solid rgba(255,255,255,0.18)",
              color: "#fff",
            }}
            data-testid="search-input"
          />
        </form>

        {/* Theme toggle — visible everywhere */}
        <button onClick={toggle} className="cp-btn-ghost !p-2 ml-auto md:ml-0" style={{ color: "#fff" }} aria-label="Toggle theme" data-testid="theme-toggle">
          {theme === "dark" ? <SunMedium size={16} /> : <Moon size={16} />}
        </button>

        {/* Desktop user actions */}
        {user ? (
          <div className="relative hidden md:block">
            <button onClick={() => setMenu(m => !m)} className="cp-btn-ghost !py-1.5" style={{ color: "#fff" }} data-testid="user-menu-btn">
              <span className="cp-logo-circle" style={{ width: 22, height: 22, fontSize: 11 }}>
                {(user.display_name || user.email || "U").slice(0, 1).toUpperCase()}
              </span>
              <span className="hidden lg:inline text-sm">{user.display_name}</span>
              <ChevronDown size={14} />
            </button>
            {menu && (
              <div onMouseLeave={() => setMenu(false)} className="absolute right-0 mt-2 w-56 cp-surface p-1 shadow-xl z-40" data-testid="user-menu">
                <Link to="/fantasy" className="flex items-center gap-2 px-2 py-2 text-sm hover:bg-white/5 rounded" data-testid="menu-fantasy">
                  <ShieldCheck size={14} className="text-cp-lime"/> Fantasy & WC Games
                </Link>
                <Link to="/build-team" className="flex items-center gap-2 px-2 py-2 text-sm hover:bg-white/5 rounded" data-testid="menu-build-team">
                  <ShieldCheck size={14} className="text-cp-lime"/> Build a Team
                </Link>
                <Link to="/my-teams" className="flex items-center gap-2 px-2 py-2 text-sm hover:bg-white/5 rounded" data-testid="menu-my-teams">
                  <ShieldCheck size={14} className="text-cp-lime"/> My Teams
                </Link>
                <Link to="/cards" className="flex items-center gap-2 px-2 py-2 text-sm hover:bg-white/5 rounded" data-testid="menu-cards">
                  <Crown size={14} className="text-cp-lime"/> Legend Cards
                </Link>
                <div className="my-1 border-t" style={{ borderColor: "var(--cp-border)" }}/>
                <Link to="/profile" className="flex items-center gap-2 px-2 py-2 text-sm hover:bg-white/5 rounded" data-testid="menu-profile">
                  <User size={14} /> Profile
                </Link>
                <Link to="/wallet" className="flex items-center gap-2 px-2 py-2 text-sm hover:bg-white/5 rounded" data-testid="menu-wallet">
                  <Coins size={14} className="text-cp-lime"/> Wallet
                </Link>
                <Link to="/premium" className="flex items-center gap-2 px-2 py-2 text-sm hover:bg-white/5 rounded" data-testid="menu-premium">
                  <Crown size={14} className="text-cp-lime"/> {user?.is_premium ? "Premium ✓" : "Go Premium"}
                </Link>
                <Link to="/referrals" className="flex items-center gap-2 px-2 py-2 text-sm hover:bg-white/5 rounded" data-testid="menu-referrals">
                  <Target size={14} className="text-cp-lime"/> Invite & Earn
                </Link>
                {user.role === "admin" && (
                  <Link to="/admin" className="flex items-center gap-2 px-2 py-2 text-sm hover:bg-white/5 rounded" data-testid="menu-admin">
                    <ShieldCheck size={14} /> Admin
                  </Link>
                )}
                <button onClick={async () => { await signout(); nav("/"); }} className="w-full flex items-center gap-2 px-2 py-2 text-sm hover:bg-white/5 rounded" data-testid="menu-signout">
                  <LogOut size={14} /> Sign out
                </button>
              </div>
            )}
          </div>
        ) : (
          <div className="hidden md:flex items-center gap-2">
            <Link
              to="/signin"
              className="!py-1.5 px-3 rounded text-sm font-bold transition"
              style={{ color: "#fff", background: "rgba(0,0,0,0.18)" }}
              data-testid="nav-signin"
            >
              Sign in
            </Link>
            <Link
              to="/signup"
              className="!py-1.5 px-3 rounded text-sm font-extrabold"
              style={{ background: "var(--cp-lime)", color: "var(--cp-forest)" }}
              data-testid="nav-signup"
            >
              Sign up
            </Link>
          </div>
        )}
      </div>

      {/* Sports nav with icons — sits on the same forest-green header band. WC 2026 is the first tab. */}
      <div className="cp-sports-band" style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}>
        <div className="max-w-[1400px] mx-auto px-3 md:px-5">
          <div className="flex items-center gap-1 overflow-x-auto no-scrollbar pb-1 pt-1" data-testid="sports-nav">
            {siteCfg.show_wc_tab && (
              <NavLink
                to="/worldcup"
                className={({ isActive }) => `cp-sport-tab cp-sport-tab--on-band flex items-center gap-1.5 ${isActive ? "active" : ""}`}
                data-testid="sport-tab-wc2026"
                style={{ color: "#fff" }}
              >
                <Trophy size={14} className="text-cp-lime"/>
                <span>WC 2026</span>
              </NavLink>
            )}
            {SPORTS.map(s => (
              <NavLink
                key={s.slug}
                to={s.slug === "football" ? "/" : `/sport/${s.slug}`}
                className={({ isActive }) => `cp-sport-tab cp-sport-tab--on-band flex items-center gap-1.5 ${isActive ? "active" : ""}`}
                data-testid={`sport-tab-${s.slug}`}
                end={s.slug === "football"}
              >
                <SportIcon slug={s.slug} className="text-[13px]" />
                {s.name}
              </NavLink>
            ))}
          </div>
        </div>
      </div>

      {/* Mobile drawer — rendered via portal directly under <body> so no
          parent's `transform`, `filter`, or `contain` can break the fixed
          positioning. */}
      {drawer && createPortal((
        <div className="lg:hidden" data-testid="mobile-drawer-root">
          <div
            className="fixed inset-0"
            onClick={() => setDrawer(false)}
            style={{ background: "rgba(0,0,0,0.6)", zIndex: 9998 }}
            data-testid="mobile-drawer-backdrop"
          />
          <aside
            className="fixed left-0 top-0 bottom-0 w-[85vw] max-w-[320px] p-4 flex flex-col gap-2 animate-fade-in overflow-y-auto"
            data-testid="mobile-drawer"
            style={{
              background: "var(--cp-surface)",
              color: "var(--cp-text)",
              borderRight: "1px solid var(--cp-border)",
              boxShadow: "8px 0 32px rgba(0,0,0,0.5)",
              zIndex: 9999,
            }}
          >
            <div className="flex items-center justify-between mb-2 shrink-0">
              <Brand size={40}/>
              <button onClick={() => setDrawer(false)} className="cp-btn-ghost !p-2" data-testid="drawer-close-btn"><X size={16}/></button>
            </div>
            <form onSubmit={(e) => { submit(e); setDrawer(false); }} className="relative" data-testid="mobile-search-form">
              <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-cp-muted" />
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search teams, leagues…" className="cp-input pl-8 text-sm" data-testid="mobile-search-input"/>
            </form>
            <Link to="/worldcup" onClick={() => setDrawer(false)} className="cp-btn-ghost justify-start" data-testid="drawer-wc"><Trophy size={14} className="text-cp-lime"/> WC 2026</Link>
            <Link to="/predictions" onClick={() => setDrawer(false)} className="cp-btn-ghost justify-start" data-testid="drawer-predictions"><Target size={14}/> Predictions</Link>
            <Link to="/fantasy" onClick={() => setDrawer(false)} className="cp-btn-ghost justify-start" data-testid="drawer-fantasy"><ShieldCheck size={14}/> Fantasy & WC Games</Link>
            <Link to="/build-team" onClick={() => setDrawer(false)} className="cp-btn-ghost justify-start" data-testid="drawer-build-team"><ShieldCheck size={14}/> Build a Team</Link>
            <Link to="/my-teams" onClick={() => setDrawer(false)} className="cp-btn-ghost justify-start" data-testid="drawer-my-teams"><ShieldCheck size={14}/> My Teams</Link>
            <Link to="/cards" onClick={() => setDrawer(false)} className="cp-btn-ghost justify-start" data-testid="drawer-cards"><Crown size={14}/> Legend Cards</Link>
            <Link to="/leaderboards" onClick={() => setDrawer(false)} className="cp-btn-ghost justify-start" data-testid="drawer-leaderboards"><Trophy size={14}/> Leaderboards</Link>
            <Link to="/prize-pools" onClick={() => setDrawer(false)} className="cp-btn-ghost justify-start" data-testid="drawer-pools"><Coins size={14}/> Prize Pools</Link>
            <div className="border-t my-2" style={{ borderColor: "var(--cp-border)" }} />
            {user ? (
              <>
                <Link to="/profile" onClick={() => setDrawer(false)} className="cp-btn-ghost justify-start" data-testid="drawer-profile"><User size={14}/> Profile</Link>
                <Link to="/wallet" onClick={() => setDrawer(false)} className="cp-btn-ghost justify-start" data-testid="drawer-wallet"><Coins size={14} className="text-cp-lime"/> Wallet</Link>
                <Link to="/premium" onClick={() => setDrawer(false)} className="cp-btn-ghost justify-start" data-testid="drawer-premium"><Crown size={14} className="text-cp-lime"/> {user?.is_premium ? "Premium ✓" : "Go Premium"}</Link>
                <Link to="/referrals" onClick={() => setDrawer(false)} className="cp-btn-ghost justify-start" data-testid="drawer-referrals"><Target size={14} className="text-cp-lime"/> Invite & Earn</Link>
                {user.role === "admin" && <Link to="/admin" onClick={() => setDrawer(false)} className="cp-btn-ghost justify-start" data-testid="drawer-admin"><ShieldCheck size={14}/> Admin</Link>}
                <button onClick={async () => { await signout(); setDrawer(false); nav("/"); }} className="cp-btn-ghost justify-start" data-testid="drawer-signout"><LogOut size={14}/> Sign out</button>
              </>
            ) : (
              <>
                <Link to="/signin" onClick={() => setDrawer(false)} className="cp-btn-ghost justify-start" data-testid="drawer-signin">Sign in</Link>
                <Link to="/signup" onClick={() => setDrawer(false)} className="cp-btn-primary justify-center" data-testid="drawer-signup">Sign up free</Link>
              </>
            )}
          </aside>
        </div>
      ), document.body)}
    </header>
  );
};

export default Header;
