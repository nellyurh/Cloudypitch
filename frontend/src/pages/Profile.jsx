import React, { useEffect, useState } from "react";
import api from "../lib/api";
import { useAuth } from "../lib/auth";
import { Navigate, Link, useNavigate } from "react-router-dom";
import { Trophy, Target, Sparkles, ShieldCheck, LogOut, Wallet, Users } from "lucide-react";

export const Profile = () => {
  const { user, signout } = useAuth();
  const nav = useNavigate();
  const [stats, setStats] = useState(null);
  const [signingOut, setSigningOut] = useState(false);
  useEffect(() => { if (user) (async () => { try { const { data } = await api.get("/users/me/stats"); setStats(data); } catch (_) {} })(); }, [user]);
  if (!user) return <Navigate to="/signin" replace />;
  if (!stats) return <div className="cp-surface p-6 text-sm" style={{ color: "var(--cp-text-muted)" }}>Loading…</div>;
  const s = stats.stats;
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

  return (
    <div className="max-w-4xl mx-auto" data-testid="profile-page">
      <div className="cp-surface p-5 flex items-center gap-4 flex-wrap">
        <div className="cp-logo-circle" style={{ width: 56, height: 56, fontSize: 24 }}>
          {(user.display_name || user.email).slice(0,1).toUpperCase()}
        </div>
        <div className="flex-1 min-w-0">
          <h1 className="text-xl font-extrabold">{user.display_name}</h1>
          <div className="text-sm" style={{ color: "var(--cp-text-muted)" }}>{user.email}</div>
          <div className="text-[10px] uppercase tracking-widest mt-1" style={{ color: "var(--cp-text-muted)" }}>{user.country_code} · {user.role}</div>
        </div>
        <button
          onClick={handleSignout}
          disabled={signingOut}
          className="flex items-center gap-1.5 rounded px-3 py-2 text-xs font-extrabold disabled:opacity-50"
          style={{ background: "var(--cp-surface-2)", color: "#FF6B7A", border: "1px solid var(--cp-border)" }}
          data-testid="profile-signout"
        >
          <LogOut size={14}/> {signingOut ? "Signing out…" : "Sign out"}
        </button>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3">
        <Stat icon={Target} label="Predictions" value={s.predictions_made}/>
        <Stat icon={Trophy} label="Pred. Points" value={s.predictions_points}/>
        <Stat icon={Sparkles} label="Cards" value={s.cards_owned}/>
        <Stat icon={ShieldCheck} label="Fantasy Pts" value={s.fantasy_total_points}/>
      </div>

      {/* Shortcuts */}
      <div className="grid grid-cols-3 gap-2 mt-3">
        <Link to="/my-teams" className="cp-surface p-3 text-center text-xs font-bold hover:bg-white/5" data-testid="profile-my-teams">
          <Users size={16} className="mx-auto text-cp-lime mb-1"/> My Teams
        </Link>
        <Link to="/wallet" className="cp-surface p-3 text-center text-xs font-bold hover:bg-white/5" data-testid="profile-wallet">
          <Wallet size={16} className="mx-auto text-cp-lime mb-1"/> Wallet
        </Link>
        <Link to="/cards" className="cp-surface p-3 text-center text-xs font-bold hover:bg-white/5" data-testid="profile-cards">
          <Sparkles size={16} className="mx-auto text-cp-lime mb-1"/> Legend Cards
        </Link>
      </div>

      {stats.fantasy_squad && (
        <div className="cp-surface mt-3 p-4">
          <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Your Fantasy Squad</div>
          <div className="text-lg font-bold">{stats.fantasy_squad.squad_name}</div>
          <div className="text-sm mt-1" style={{ color: "var(--cp-text-muted)" }}>{stats.fantasy_squad.players?.length || 0} players · GW Pts: {stats.fantasy_squad.gw_points || 0}</div>
          <Link to="/fantasy" className="cp-btn-primary mt-3" data-testid="profile-edit-squad">Manage Squad</Link>
        </div>
      )}

      {/* Secondary sign-out button at the bottom for thumb-reach on mobile */}
      <button
        onClick={handleSignout}
        disabled={signingOut}
        className="w-full mt-6 py-3 rounded font-extrabold text-sm flex items-center justify-center gap-2 disabled:opacity-50"
        style={{ background: "var(--cp-surface-2)", border: "1px solid var(--cp-border)", color: "#FF6B7A" }}
        data-testid="profile-signout-bottom"
      >
        <LogOut size={14}/> {signingOut ? "Signing out…" : "Sign out of Cloudy Pitch"}
      </button>
    </div>
  );
};

export default Profile;
