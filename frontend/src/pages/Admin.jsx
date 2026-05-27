import React, { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../lib/auth";
import { Users, Database, Radio, Activity, RefreshCw, Trophy } from "lucide-react";

export const AdminPanel = () => {
  const { user, loading } = useAuth();
  const [tab, setTab] = useState("dashboard");
  const [stats, setStats] = useState(null);
  const [matches, setMatches] = useState([]);
  const [users, setUsers] = useState([]);
  const [audit, setAudit] = useState([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (!user || user.role !== "admin") return;
    (async () => {
      try {
        const [a, b, c, d] = await Promise.all([
          api.get("/admin/stats"),
          api.get("/admin/matches?limit=50"),
          api.get("/admin/users?limit=50"),
          api.get("/admin/audit?limit=50"),
        ]);
        setStats(a.data); setMatches(b.data.matches); setUsers(c.data.users); setAudit(d.data.audit);
      } catch (_) {}
    })();
  }, [user]);

  if (loading) return <div className="cp-surface p-6 text-sm">Checking permissions…</div>;
  if (!user || user.role !== "admin") return <Navigate to="/signin" replace />;

  const trigger = async (url) => {
    setBusy(true); setMsg("");
    try { const { data } = await api.post(url); setMsg(JSON.stringify(data)); } catch (e) { setMsg("Failed: " + (e?.response?.data?.detail || e.message)); }
    setBusy(false);
  };

  const Card = ({ icon: Icon, label, value }) => (
    <div className="cp-surface p-3">
      <Icon size={16} className="text-cp-lime mb-1.5"/>
      <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>{label}</div>
      <div className="text-2xl font-extrabold tabular-nums">{value ?? 0}</div>
    </div>
  );

  return (
    <div data-testid="admin-panel">
      <h1 className="text-2xl font-extrabold mb-3">Admin Panel</h1>
      <div className="flex gap-1 cp-surface p-1 w-fit mb-3 flex-wrap">
        {["dashboard", "matches", "users", "ingest", "audit"].map(t => (
          <button key={t} onClick={() => setTab(t)} className={`px-3 py-1.5 text-sm rounded transition ${tab === t ? "bg-cp-lime text-cp-forest font-bold" : "hover:bg-white/5"}`} data-testid={`admin-tab-${t}`}>{t.toUpperCase()}</button>
        ))}
      </div>

      {tab === "dashboard" && stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Card icon={Users} label="Users" value={stats.users}/>
          <Card icon={Activity} label="Active Sessions" value={stats.active_sessions}/>
          <Card icon={Database} label="Matches" value={stats.matches}/>
          <Card icon={Radio} label="Live Now" value={stats.live_matches}/>
          <Card icon={Database} label="Leagues" value={stats.leagues}/>
          <Card icon={Database} label="Teams" value={stats.teams}/>
          <Card icon={Trophy} label="Predictions" value={stats.predictions}/>
          <Card icon={Trophy} label="Fantasy Squads" value={stats.fantasy_squads}/>
        </div>
      )}

      {tab === "matches" && (
        <div className="cp-surface overflow-hidden">
          <table className="w-full text-sm">
            <thead><tr style={{ color: "var(--cp-text-muted)" }} className="text-xs"><th className="text-left p-2">When</th><th className="text-left">League</th><th className="text-left">Match</th><th>Status</th></tr></thead>
            <tbody>
              {matches.map(m => (
                <tr key={m.id} className="border-t" style={{ borderColor: "var(--cp-border)" }}>
                  <td className="p-2 text-xs">{new Date(m.scheduled_at).toLocaleString()}</td>
                  <td className="text-xs">{m.league_country} · {m.league_name}</td>
                  <td>{m.home_team_name} {m.home_score} - {m.away_score} {m.away_team_name}</td>
                  <td className="text-center"><span className="cp-pill" style={{ background: m.is_live ? "#FF3D52" : "var(--cp-surface-2)", color: m.is_live ? "#fff" : "var(--cp-text)" }}>{m.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "users" && (
        <div className="cp-surface overflow-hidden">
          <table className="w-full text-sm">
            <thead><tr style={{ color: "var(--cp-text-muted)" }} className="text-xs"><th className="text-left p-2">Email</th><th className="text-left">Name</th><th>Role</th><th>Active</th><th>Joined</th></tr></thead>
            <tbody>
              {users.map(u => (
                <tr key={u.id} className="border-t" style={{ borderColor: "var(--cp-border)" }}>
                  <td className="p-2">{u.email}</td><td>{u.display_name}</td>
                  <td className="text-center"><span className="cp-pill" style={{ background: u.role === "admin" ? "#A3E635" : "var(--cp-surface-2)", color: u.role === "admin" ? "#064E3B" : "var(--cp-text)" }}>{u.role}</span></td>
                  <td className="text-center">{u.is_active ? "✓" : "✗"}</td>
                  <td className="text-xs">{u.created_at?.slice(0,10)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "ingest" && (
        <div className="space-y-2" data-testid="admin-ingest">
          <p className="text-sm" style={{ color: "var(--cp-text-muted)" }}>Trigger ingestion jobs immediately:</p>
          {msg && <div className="cp-surface p-2 text-xs font-mono">{msg}</div>}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <button disabled={busy} onClick={() => trigger("/admin/ingest/sportmonks/sync?days=7")} className="cp-btn-primary justify-start" data-testid="ingest-sm-sync"><RefreshCw size={14}/> Sportmonks: Sync next 7 days</button>
            <button disabled={busy} onClick={() => trigger("/admin/ingest/sportmonks/live")} className="cp-btn-primary justify-start" data-testid="ingest-sm-live"><RefreshCw size={14}/> Sportmonks: Live poll now</button>
            <button disabled={busy} onClick={() => trigger("/admin/ingest/statpal/tennis/sync")} className="cp-btn-ghost justify-start" data-testid="ingest-statpal"><RefreshCw size={14}/> StatPal: Tennis sync</button>
            <button disabled={busy} onClick={() => trigger("/admin/ingest/apisports/basketball/sync")} className="cp-btn-ghost justify-start" data-testid="ingest-as-basketball"><RefreshCw size={14}/> API-Sports: Basketball</button>
            <button disabled={busy} onClick={() => trigger("/admin/ingest/apisports/nba/sync")} className="cp-btn-ghost justify-start" data-testid="ingest-as-nba"><RefreshCw size={14}/> API-Sports: NBA</button>
            <button disabled={busy} onClick={() => trigger("/predictions/settle")} className="cp-btn-ghost justify-start" data-testid="ingest-settle"><RefreshCw size={14}/> Settle predictions</button>
          </div>
        </div>
      )}

      {tab === "audit" && (
        <div className="cp-surface overflow-hidden">
          <ul className="divide-y" style={{ borderColor: "var(--cp-border)" }}>
            {audit.map(a => (
              <li key={a.id} className="px-3 py-2 text-xs flex items-center gap-3">
                <span className="cp-pill" style={{ background: "var(--cp-surface-2)" }}>{a.action}</span>
                <span style={{ color: "var(--cp-text-muted)" }}>{a.created_at?.slice(0,19).replace("T", " ")}</span>
                <span className="flex-1 truncate">{a.email}</span>
                <span style={{ color: "var(--cp-text-muted)" }}>{a.ip_address}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

export default AdminPanel;
