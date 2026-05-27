import React, { useEffect, useState } from "react";
import api from "../lib/api";
import { useAuth } from "../lib/auth";
import { Navigate, Link } from "react-router-dom";
import { Trophy, Target, Sparkles, ShieldCheck } from "lucide-react";

export const Profile = () => {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
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
  return (
    <div className="max-w-4xl mx-auto" data-testid="profile-page">
      <div className="cp-surface p-5 flex items-center gap-4">
        <div className="cp-logo-circle" style={{ width: 56, height: 56, fontSize: 24 }}>
          {(user.display_name || user.email).slice(0,1).toUpperCase()}
        </div>
        <div>
          <h1 className="text-xl font-extrabold">{user.display_name}</h1>
          <div className="text-sm" style={{ color: "var(--cp-text-muted)" }}>{user.email}</div>
          <div className="text-[10px] uppercase tracking-widest mt-1" style={{ color: "var(--cp-text-muted)" }}>{user.country_code} · {user.role}</div>
        </div>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3">
        <Stat icon={Target} label="Predictions" value={s.predictions_made}/>
        <Stat icon={Trophy} label="Pred. Points" value={s.predictions_points}/>
        <Stat icon={Sparkles} label="Cards" value={s.cards_owned}/>
        <Stat icon={ShieldCheck} label="Fantasy Pts" value={s.fantasy_total_points}/>
      </div>

      {stats.fantasy_squad && (
        <div className="cp-surface mt-3 p-4">
          <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Your Fantasy Squad</div>
          <div className="text-lg font-bold">{stats.fantasy_squad.squad_name}</div>
          <div className="text-sm mt-1" style={{ color: "var(--cp-text-muted)" }}>{stats.fantasy_squad.players?.length || 0} players · GW Pts: {stats.fantasy_squad.gw_points || 0}</div>
          <Link to="/fantasy" className="cp-btn-primary mt-3" data-testid="profile-edit-squad">Manage Squad</Link>
        </div>
      )}
    </div>
  );
};

export default Profile;
