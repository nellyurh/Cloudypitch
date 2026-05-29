import React, { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../lib/auth";
import { Users, Database, Radio, Activity, RefreshCw, Trophy, Coins, Calendar, Settings2 } from "lucide-react";

export const AdminPanel = () => {
  const { user, loading } = useAuth();
  const [tab, setTab] = useState("dashboard");
  const [stats, setStats] = useState(null);
  const [matches, setMatches] = useState([]);
  const [users, setUsers] = useState([]);
  const [audit, setAudit] = useState([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  // Pools + WC config
  const [pools, setPools] = useState([]);
  const [editingPool, setEditingPool] = useState(null);
  const [wcConfig, setWcConfig] = useState([]);
  const [wcGames, setWcGames] = useState([]);
  const [wcGameFilter, setWcGameFilter] = useState({ game_type: "", status: "" });

  const refreshPools = async () => { try { const { data } = await api.get("/prize-pools"); setPools(data.pools || []); } catch (_) {} };
  const refreshWcConfig = async () => { try { const { data } = await api.get("/admin/wc/config"); setWcConfig(data.config || []); } catch (_) {} };
  const refreshWcGames = async () => {
    const params = new URLSearchParams();
    if (wcGameFilter.game_type) params.set("game_type", wcGameFilter.game_type);
    if (wcGameFilter.status) params.set("status", wcGameFilter.status);
    try { const { data } = await api.get(`/admin/wc/games?${params.toString()}`); setWcGames(data.games || []); } catch (_) {}
  };

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

  useEffect(() => {
    if (!user || user.role !== "admin") return;
    if (tab === "pools") refreshPools();
    if (tab === "wcconfig") refreshWcConfig();
    if (tab === "wcgames") refreshWcGames();
    /* eslint-disable-next-line */
  }, [tab, wcGameFilter]);

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
        {["dashboard", "matches", "users", "ingest", "audit", "pools", "wcconfig", "wcgames"].map(t => (
          <button key={t} onClick={() => setTab(t)} className={`px-3 py-1.5 text-sm rounded transition ${tab === t ? "bg-cp-lime text-cp-forest font-bold" : "hover:bg-white/5"}`} data-testid={`admin-tab-${t}`}>{t.toUpperCase()}</button>
        ))}
      </div>

      {tab === "dashboard" && stats && (
        <div className="space-y-3">
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
          <div className="cp-surface p-4" data-testid="admin-cleanup-card">
            <h3 className="text-sm font-extrabold mb-1">DB Cleanup</h3>
            <p className="text-xs mb-3" style={{ color: "var(--cp-text-muted)" }}>
              Remove cross-provider duplicate matches & merge duplicate league rows. Sportmonks always wins ties.
            </p>
            <div className="flex gap-2 flex-wrap">
              {["football", "basketball", "tennis", "cricket", "baseball", "hockey"].map(sport => (
                <button
                  key={sport}
                  onClick={async () => {
                    if (!confirm(`Run live duplicate cleanup for ${sport}?`)) return;
                    setBusy(true);
                    try {
                      const { data } = await api.post(`/admin/cleanup/duplicate-matches?sport_slug=${sport}&dry_run=false`);
                      setMsg(`${sport}: deleted ${data.duplicates_found} dupes from ${data.total_matches_scanned} matches`);
                    } catch (e) { setMsg(e?.response?.data?.detail || "Cleanup failed"); }
                    setBusy(false);
                  }}
                  disabled={busy}
                  className="cp-btn-ghost text-xs disabled:opacity-50"
                  data-testid={`cleanup-${sport}`}
                >
                  Dedupe {sport}
                </button>
              ))}
              <button
                onClick={async () => {
                  if (!confirm("Merge all duplicate league rows? Matches in losing leagues will be reassigned.")) return;
                  setBusy(true);
                  try {
                    const { data } = await api.post("/admin/cleanup/duplicate-leagues?dry_run=false");
                    setMsg(`Merged ${data.leagues_merged} leagues across ${data.duplicate_clusters} clusters`);
                  } catch (e) { setMsg(e?.response?.data?.detail || "Merge failed"); }
                  setBusy(false);
                }}
                disabled={busy}
                className="cp-btn-primary text-xs disabled:opacity-50"
                data-testid="cleanup-leagues"
              >
                Merge Leagues
              </button>
            </div>
            {msg && <div className="text-xs mt-3 font-mono p-2 rounded" style={{ background: "var(--cp-surface-2)", color: "var(--cp-text-muted)" }}>{msg}</div>}
          </div>
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

      {tab === "pools" && (
        <div className="space-y-3" data-testid="admin-pools">
          <p className="text-sm" style={{ color: "var(--cp-text-muted)" }}>Edit prize-pool USD value, payout structure, and dates.</p>
          {pools.map(p => {
            const isEdit = editingPool?.id === p.id;
            return (
              <div key={p.id} className="cp-surface p-3" data-testid={`pool-row-${p.id}`}>
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div>
                    <div className="text-sm font-extrabold">{p.title}</div>
                    <div className="text-[10px]" style={{ color: "var(--cp-text-muted)" }}>{p.id} · ${((p.amount_usd_cents || 0) / 100).toLocaleString()}</div>
                  </div>
                  <div className="flex gap-2">
                    <button onClick={() => setEditingPool(isEdit ? null : { ...p })} className={isEdit ? "cp-btn-ghost" : "cp-btn-primary"} data-testid={`pool-edit-${p.id}`}>{isEdit ? "Cancel" : "Edit"}</button>
                    <button onClick={async () => { setBusy(true); try { const { data } = await api.post(`/prize-pools/${p.id}/settle`); setMsg(`Settled: ${data.winners_count} winners`); refreshPools(); } catch (e) { setMsg(e?.response?.data?.detail || "Settle failed"); } setBusy(false); }} className="cp-btn-ghost" data-testid={`pool-settle-${p.id}`}>Settle</button>
                  </div>
                </div>
                {isEdit && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-3">
                    <div>
                      <label className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Title</label>
                      <input className="cp-input w-full" value={editingPool.title || ""} onChange={(e) => setEditingPool(s => ({ ...s, title: e.target.value }))} data-testid={`pool-title-${p.id}`}/>
                    </div>
                    <div>
                      <label className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>USD Cents</label>
                      <input type="number" className="cp-input w-full" value={editingPool.amount_usd_cents || 0} onChange={(e) => setEditingPool(s => ({ ...s, amount_usd_cents: Number(e.target.value) }))} data-testid={`pool-usd-${p.id}`}/>
                    </div>
                    <div>
                      <label className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Starts At (ISO)</label>
                      <input className="cp-input w-full" value={editingPool.starts_at || ""} onChange={(e) => setEditingPool(s => ({ ...s, starts_at: e.target.value }))} data-testid={`pool-starts-${p.id}`}/>
                    </div>
                    <div>
                      <label className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Ends At (ISO)</label>
                      <input className="cp-input w-full" value={editingPool.ends_at || ""} onChange={(e) => setEditingPool(s => ({ ...s, ends_at: e.target.value }))} data-testid={`pool-ends-${p.id}`}/>
                    </div>
                    <div className="md:col-span-2">
                      <label className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Payout structure (JSON list)</label>
                      <textarea className="cp-input w-full font-mono text-[11px]" rows={3} value={JSON.stringify(editingPool.payout_structure || [], null, 0)} onChange={(e) => { try { setEditingPool(s => ({ ...s, payout_structure: JSON.parse(e.target.value) })); } catch (_) {} }} data-testid={`pool-payout-${p.id}`}/>
                    </div>
                    <div className="md:col-span-2 flex justify-end gap-2">
                      <button
                        onClick={async () => {
                          setBusy(true);
                          try {
                            await api.patch(`/prize-pools/${p.id}`, {
                              title: editingPool.title,
                              amount_usd_cents: Number(editingPool.amount_usd_cents),
                              payout_structure: editingPool.payout_structure,
                              starts_at: editingPool.starts_at,
                              ends_at: editingPool.ends_at,
                            });
                            setMsg("Saved"); setEditingPool(null); refreshPools();
                          } catch (e) { setMsg(e?.response?.data?.detail || "Save failed"); }
                          setBusy(false);
                        }}
                        disabled={busy}
                        className="cp-btn-primary" data-testid={`pool-save-${p.id}`}
                      >{busy ? "Saving…" : "Save"}</button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
          {msg && <div className="cp-surface p-2 text-xs font-mono">{msg}</div>}
        </div>
      )}

      {tab === "wcconfig" && (
        <div className="space-y-3" data-testid="admin-wcconfig">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-sm flex-1" style={{ color: "var(--cp-text-muted)" }}>Edit card limits + points multipliers per stage. Changes are audited.</p>
            <button onClick={async () => { if (!confirm("Reset all card limits to defaults?")) return; setBusy(true); try { await api.post("/admin/wc/config/reset"); setMsg("All defaults restored"); refreshWcConfig(); } catch (e) { setMsg(e?.response?.data?.detail || "Reset failed"); } setBusy(false); }} className="cp-btn-ghost" data-testid="wc-reset-defaults">
              <Settings2 size={14}/> Reset to Defaults
            </button>
          </div>
          <div className="cp-surface overflow-hidden">
            <table className="w-full text-xs">
              <thead><tr style={{ color: "var(--cp-text-muted)" }}>
                <th className="text-left p-2">Type</th><th className="text-left">Stage</th>
                <th>Default</th><th>Current</th><th>Pts ×</th><th>Open Hrs</th><th>Active</th><th></th>
              </tr></thead>
              <tbody>
                {wcConfig.map(c => (
                  <tr key={c.id} className="border-t" style={{ borderColor: "var(--cp-border)" }}>
                    <td className="p-2 font-bold">{c.game_type}</td><td>{c.stage}</td>
                    <td className="text-center tabular-nums">{c.card_limit_default}</td>
                    <td className="text-center"><input type="number" className="cp-input !w-16 text-center" value={c.card_limit_current} onChange={(e) => setWcConfig(prev => prev.map(x => x.id === c.id ? { ...x, card_limit_current: Number(e.target.value) } : x))} data-testid={`wc-cur-${c.id}`}/></td>
                    <td className="text-center"><input type="number" step="0.1" className="cp-input !w-16 text-center" value={c.points_multiplier} onChange={(e) => setWcConfig(prev => prev.map(x => x.id === c.id ? { ...x, points_multiplier: Number(e.target.value) } : x))} data-testid={`wc-mult-${c.id}`}/></td>
                    <td className="text-center"><input type="number" className="cp-input !w-16 text-center" value={c.opens_hours_before} onChange={(e) => setWcConfig(prev => prev.map(x => x.id === c.id ? { ...x, opens_hours_before: Number(e.target.value) } : x))} data-testid={`wc-hrs-${c.id}`}/></td>
                    <td className="text-center"><input type="checkbox" checked={c.is_active} onChange={(e) => setWcConfig(prev => prev.map(x => x.id === c.id ? { ...x, is_active: e.target.checked } : x))} data-testid={`wc-act-${c.id}`}/></td>
                    <td className="text-right p-2">
                      <button onClick={async () => { setBusy(true); try { await api.patch(`/admin/wc/config/${c.id}`, { card_limit_current: c.card_limit_current, points_multiplier: c.points_multiplier, opens_hours_before: c.opens_hours_before, is_active: c.is_active }); setMsg(`Saved ${c.game_type}/${c.stage}`); } catch (e) { setMsg(e?.response?.data?.detail || "Save failed"); } setBusy(false); }} className="cp-btn-primary !text-[10px] !py-0.5" data-testid={`wc-save-${c.id}`}>Save</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {msg && <div className="cp-surface p-2 text-xs font-mono">{msg}</div>}
        </div>
      )}

      {tab === "wcgames" && (
        <div className="space-y-3" data-testid="admin-wcgames">
          <div className="flex items-center gap-2 flex-wrap">
            <select className="cp-input w-40" value={wcGameFilter.game_type} onChange={(e) => setWcGameFilter(f => ({ ...f, game_type: e.target.value }))} data-testid="wcgames-filter-type">
              <option value="">All types</option><option value="match">Match</option><option value="group">Group</option><option value="round">Round</option>
            </select>
            <select className="cp-input w-40" value={wcGameFilter.status} onChange={(e) => setWcGameFilter(f => ({ ...f, status: e.target.value }))} data-testid="wcgames-filter-status">
              <option value="">All status</option><option value="upcoming">Upcoming</option><option value="open">Open</option><option value="closed">Closed</option><option value="settled">Settled</option>
            </select>
            <button onClick={async () => { setBusy(true); try { const { data } = await api.post("/admin/wc/refresh-bracket"); setMsg(`Generated ${data.created} · transitions ${data.transitions}`); refreshWcGames(); } catch (e) { setMsg(e?.response?.data?.detail || "Refresh failed"); } setBusy(false); }} className="cp-btn-primary" data-testid="wcgames-generate">
              <Calendar size={14}/> Generate / Tick
            </button>
          </div>
          <div className="cp-surface overflow-x-auto">
            <table className="w-full text-xs">
              <thead><tr style={{ color: "var(--cp-text-muted)" }}>
                <th className="text-left p-2">Type</th><th className="text-left">Stage</th><th>Group/MD</th><th>Opens</th><th>Closes</th><th>Cards</th><th>Entries</th><th>Status</th><th></th>
              </tr></thead>
              <tbody>
                {wcGames.map(g => (
                  <tr key={g.id} className="border-t" style={{ borderColor: "var(--cp-border)" }}>
                    <td className="p-2 font-bold">{g.game_type}</td><td>{g.stage}</td>
                    <td className="text-center">{g.group_letter ? `${g.group_letter} · MD${g.matchday}` : "—"}</td>
                    <td className="text-center">{g.opens_at?.slice(5,16)}</td>
                    <td className="text-center">{g.closes_at?.slice(5,16)}</td>
                    <td className="text-center tabular-nums">{g.card_limit_current}</td>
                    <td className="text-center tabular-nums">{g.total_entries || 0}</td>
                    <td className="text-center"><span className="cp-pill" style={{ background: g.status === "open" ? "rgba(163,230,53,0.15)" : "var(--cp-surface-2)", color: g.status === "open" ? "#A3E635" : "var(--cp-text)" }}>{g.status}</span></td>
                    <td className="text-right p-2">
                      <select onChange={async (e) => { if (!e.target.value) return; setBusy(true); try { await api.patch(`/admin/wc/games/${g.id}`, { status: e.target.value }); setMsg(`Updated ${g.id} → ${e.target.value}`); refreshWcGames(); } catch (err) { setMsg(err?.response?.data?.detail || "Update failed"); } setBusy(false); e.target.value = ""; }} className="cp-input !text-[10px]" data-testid={`wc-game-status-${g.id}`}>
                        <option value="">Override…</option>
                        <option value="upcoming">→ upcoming</option>
                        <option value="open">→ open</option>
                        <option value="closed">→ closed</option>
                      </select>
                    </td>
                  </tr>
                ))}
                {wcGames.length === 0 && <tr><td colSpan={9} className="p-4 text-center" style={{ color: "var(--cp-text-muted)" }}>No games yet — click "Generate / Tick" once WC fixtures are ingested.</td></tr>}
              </tbody>
            </table>
          </div>
          {msg && <div className="cp-surface p-2 text-xs font-mono">{msg}</div>}
        </div>
      )}
    </div>
  );
};

export default AdminPanel;
