import React, { useState } from "react";
import { Link, useNavigate, NavLink } from "react-router-dom";
import { Brand } from "./Brand";
import { useAuth } from "../lib/auth";
import { useTheme } from "../lib/theme";
import { Search, Moon, SunMedium, Trophy, ChevronDown, LogOut, User, ShieldCheck } from "lucide-react";

const SPORTS = [
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
  const nav = useNavigate();

  const submit = (e) => {
    e.preventDefault();
    if (q.trim().length >= 2) nav(`/search?q=${encodeURIComponent(q.trim())}`);
  };

  return (
    <header
      className="sticky top-0 z-30 backdrop-blur"
      style={{ background: "color-mix(in oklab, var(--cp-bg) 88%, transparent)", borderBottom: "1px solid var(--cp-border)" }}
      data-testid="site-header"
    >
      <div className="max-w-[1400px] mx-auto px-3 md:px-5 py-2.5 flex items-center gap-3">
        <Link to="/" data-testid="brand-home-link"><Brand /></Link>

        <nav className="hidden md:flex items-center gap-1 ml-4">
          <NavLink to="/worldcup" className="cp-btn-ghost !py-1.5" data-testid="nav-worldcup">
            <Trophy size={16} className="text-cp-lime" /> WC 2026
          </NavLink>
          <NavLink to="/predictions" className="cp-btn-ghost !py-1.5" data-testid="nav-predictions">Predictions</NavLink>
          <NavLink to="/fantasy" className="cp-btn-ghost !py-1.5" data-testid="nav-fantasy">Fantasy</NavLink>
          <NavLink to="/cards" className="cp-btn-ghost !py-1.5" data-testid="nav-cards">Legend Cards</NavLink>
          <NavLink to="/leaderboards" className="cp-btn-ghost !py-1.5" data-testid="nav-leaderboards">Leaderboards</NavLink>
        </nav>

        <form onSubmit={submit} className="ml-auto relative w-44 md:w-64" data-testid="search-form">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-cp-muted" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search teams, leagues…"
            className="cp-input pl-8 text-sm"
            data-testid="search-input"
          />
        </form>

        <button onClick={toggle} className="cp-btn-ghost !p-2" aria-label="Toggle theme" data-testid="theme-toggle">
          {theme === "dark" ? <SunMedium size={16} /> : <Moon size={16} />}
        </button>

        {user ? (
          <div className="relative">
            <button onClick={() => setMenu(m => !m)} className="cp-btn-ghost !py-1.5" data-testid="user-menu-btn">
              <span className="cp-logo-circle" style={{ width: 22, height: 22, fontSize: 11 }}>
                {(user.display_name || user.email || "U").slice(0, 1).toUpperCase()}
              </span>
              <span className="hidden md:inline text-sm">{user.display_name}</span>
              <ChevronDown size={14} />
            </button>
            {menu && (
              <div onMouseLeave={() => setMenu(false)} className="absolute right-0 mt-2 w-52 cp-surface p-1 shadow-xl" data-testid="user-menu">
                <Link to="/profile" className="flex items-center gap-2 px-2 py-2 text-sm hover:bg-white/5 rounded" data-testid="menu-profile">
                  <User size={14} /> Profile
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
          <div className="flex items-center gap-2">
            <Link to="/signin" className="cp-btn-ghost !py-1.5 text-sm" data-testid="nav-signin">Sign in</Link>
            <Link to="/signup" className="cp-btn-primary !py-1.5 text-sm" data-testid="nav-signup">Sign up</Link>
          </div>
        )}
      </div>

      {/* Sports nav */}
      <div className="max-w-[1400px] mx-auto px-3 md:px-5">
        <div className="flex items-center gap-1 overflow-x-auto no-scrollbar" data-testid="sports-nav">
          {SPORTS.map(s => (
            <NavLink
              key={s.slug}
              to={s.slug === "football" ? "/" : `/sport/${s.slug}`}
              className={({ isActive }) => `cp-sport-tab ${isActive ? "active" : ""}`}
              data-testid={`sport-tab-${s.slug}`}
              end={s.slug === "football"}
            >
              {s.name}
            </NavLink>
          ))}
        </div>
      </div>
    </header>
  );
};

export default Header;
