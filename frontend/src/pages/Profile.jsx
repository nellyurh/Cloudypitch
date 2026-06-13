import React, { useEffect, useState } from "react";
import api from "../lib/api";
import { useAuth } from "../lib/auth";
import { Navigate, Link, useNavigate } from "react-router-dom";
import {
  Trophy, Target, Sparkles, ShieldCheck, LogOut, Wallet, Users,
  Crown, Coins, ShoppingCart, Award, Gift, ShieldAlert, Settings,
} from "lucide-react";
import QualifyProgress from "../components/QualifyProgress";

/** Profile screen — also the central nav surface for signed-in users.
 *  All menu items previously living in the burger drawer are surfaced here
 *  in a tidy 3-column grid so users can reach everything in one tap. */
export const Profile = () => {
  const { user, signout } = useAuth();
  const nav = useNavigate();
  const [stats, setStats] = useState(null);
  const [signingOut, setSigningOut] = useState(false);

  useEffect(() => {
    if (user) (async () => {
      try { const { data } = await api.get("/users/me/stats"); setStats(data); } catch (_) {}
    })();
  }, [user]);

  if (!user) return <Navigate to="/signin" replace />;
  const s = stats?.stats || {};

  const Stat = ({ icon: Icon, label, value }) => (
    <div className="cp-surface p-3">
      <Icon size={16} className="text-cp-lime mb-1.5"/>
      <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>{label}</div>
      <div className="text-2xl font-extrabold tabular-nums mt-0.5">{value}</div>
    </div>
  );

  const handleSignout = async () => {
    if (signingOut) return;
    setSigningOut(true);
    try { await signout(); } catch (_) {}
    nav("/");
  };

  // All menu items previously in the burger drawer.
  const menu = [
    { to: "/worldcup",     label: "WC26",            icon: Trophy,        testid: "profile-menu-wc" },
    { to: "/predictions",  label: "Predictions",     icon: Target,        testid: "profile-menu-predictions" },
    { to: "/fantasy",      label: "Fantasy",         icon: ShieldCheck,   testid: "profile-menu-fantasy" },
    { to: "/build-team",   label: "Build a Team",    icon: ShieldCheck,   testid: "profile-menu-build" },
    { to: "/my-teams",     label: "My Teams",        icon: Users,         testid: "profile-menu-my-teams" },
    { to: "/cards",        label: "Legend Cards",    icon: Sparkles,      testid: "profile-menu-cards" },
    { to: "/leaderboards", label: "Leaderboards",    icon: Trophy,        testid: "profile-menu-leaderboards" },
    { to: "/prize-pools",  label: "Prize Pools",     icon: Coins,         testid: "profile-menu-pools" },
    { to: "/wallet",       label: "Wallet",          icon: Wallet,        testid: "profile-menu-wallet" },
    { to: "/premium",      label: user?.is_premium ? "Premium ✓" : "Go Premium", icon: Crown, testid: "profile-menu-premium" },
    { to: "/referrals",    label: "Invite & Earn",   icon: Gift,          testid: "profile-menu-referrals" },
  ];
  if (user.role === "admin") {
    menu.push({ to: "/admin", label: "Admin", icon: ShieldAlert, testid: "profile-menu-admin" });
  }

  return (
    <div className="max-w-4xl mx-auto pb-10" data-testid="profile-page">
      {/* Identity card + top-right sign out (absolute on small screens so it
          never wraps under the avatar). */}
      <div className="cp-surface p-5 relative">
        <button
          onClick={handleSignout}
          disabled={signingOut}
          className="absolute top-3 right-3 flex items-center gap-1.5 rounded px-2 py-1.5 text-[10px] sm:text-xs font-extrabold disabled:opacity-50"
          style={{ background: "var(--cp-surface-2)", color: "#FF6B7A", border: "1px solid var(--cp-border)" }}
          data-testid="profile-signout"
        >
          <LogOut size={12}/> <span className="hidden sm:inline">{signingOut ? "Signing out…" : "Sign out"}</span>
        </button>
        <div className="flex items-center gap-4 pr-16 sm:pr-24">
          <div className="cp-logo-circle shrink-0" style={{ width: 56, height: 56, fontSize: 24 }}>
            {(user.display_name || user.email).slice(0,1).toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-lg sm:text-xl font-extrabold truncate">{user.display_name}</h1>
            <div className="text-xs sm:text-sm truncate" style={{ color: "var(--cp-text-muted)" }}>{user.email}</div>
            <div className="text-[10px] uppercase tracking-widest mt-1 flex items-center gap-1.5 flex-wrap" style={{ color: "var(--cp-text-muted)" }}>
              <span>{user.country_code}</span>
              <span>·</span>
              <span>{user.role}</span>
              {user.referral_code && <span className="font-bold text-cp-lime">· REF · {user.referral_code}</span>}
            </div>
          </div>
        </div>
      </div>

      {/* Prize-pool qualification progress */}
      <div className="mt-3">
        <QualifyProgress/>
      </div>

      {/* Stat grid */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3">
          <Stat icon={Target}      label="Predictions"  value={s.predictions_made ?? 0}/>
          <Stat icon={Trophy}      label="Pred. Points" value={s.predictions_points ?? 0}/>
          <Stat icon={Sparkles}    label="Cards"        value={s.cards_owned ?? 0}/>
          <Stat icon={ShieldCheck} label="Fantasy Pts"  value={s.fantasy_total_points ?? 0}/>
        </div>
      )}

      {/* Squad shortcut card */}
      {stats?.fantasy_squad && (
        <div className="cp-surface mt-3 p-4">
          <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Your Fantasy Squad</div>
          <div className="text-lg font-bold">{stats.fantasy_squad.squad_name}</div>
          <div className="text-sm mt-1" style={{ color: "var(--cp-text-muted)" }}>
            {stats.fantasy_squad.players?.length || 0} players · GW Pts: {stats.fantasy_squad.gw_points || 0}
          </div>
          <Link to="/build-team" className="cp-btn-primary mt-3" data-testid="profile-edit-squad">Manage Squad</Link>
        </div>
      )}

      {/* MENU — every nav item previously in the burger drawer, now here. */}
      <div className="cp-surface mt-3 p-3">
        <div className="text-[10px] uppercase tracking-widest mb-2 px-1" style={{ color: "var(--cp-text-muted)" }}>
          Menu
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {menu.map(({ to, label, icon: Icon, testid }) => (
            <Link
              key={to}
              to={to}
              className="cp-surface-2 rounded p-3 flex items-center gap-2.5 hover:bg-white/5 transition"
              style={{ border: "1px solid var(--cp-border)" }}
              data-testid={testid}
            >
              <Icon size={16} className="text-cp-lime shrink-0"/>
              <span className="text-sm font-bold truncate">{label}</span>
            </Link>
          ))}
        </div>
      </div>

      {/* Secondary signout for mobile thumb-reach */}
      <button
        onClick={handleSignout}
        disabled={signingOut}
        className="w-full mt-4 py-3 rounded font-extrabold text-sm flex items-center justify-center gap-2 disabled:opacity-50"
        style={{ background: "var(--cp-surface-2)", border: "1px solid var(--cp-border)", color: "#FF6B7A" }}
        data-testid="profile-signout-bottom"
      >
        <LogOut size={14}/> {signingOut ? "Signing out…" : "Sign out of Cloudy Pitch"}
      </button>
    </div>
  );
};

export default Profile;
