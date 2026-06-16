import React, { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../lib/auth";
import { Users, Database, Radio, Activity, RefreshCw, Trophy, Coins, Calendar, Settings2, Image as ImageIcon, UserPlus } from "lucide-react";
import { refreshBrand } from "../components/Brand";
import { AdsTab } from "../components/AdsTab";

const TAB_HINTS = {
  dashboard: "Live platform health — users, matches, predictions, fantasy squads. Use DB Cleanup to remove cross-provider duplicates.",
  matches: "Browse and edit raw match rows pulled from Sportmonks/API-Sports. Useful for fixing kickoff times or hiding bad fixtures.",
  users: "User directory. Promote to admin, flip premium, or ban abusive accounts.",
  ingest: "Trigger ingestion jobs by hand (full pull / today / past 3 days). Check provider health before running.",
  audit: "Latest 50 admin actions for compliance. Every settings change is logged here.",
  pools: "Prize pools shown on the home leaderboards. Set total payout in DOLLARS — backend stores cents.",
  wcconfig: "World Cup game configuration: when each WC mini-game opens/closes for predictions and fantasy edits.",
  wcgames: "All 148 WC games. Generate fixtures, tick state forward, or rebuild the schedule.",
  players: "Curated player price overrides. Use this when Sportmonks' auto-pricing makes a star too cheap or a bench player too expensive.",
  playerpoints: "Season-points tracker. Total fantasy points each player has earned across every settled WC match → use this to retune prices before the next round.",
  ads: "AdSense status + sponsor ads. Disable Google Ads for premium subs is automatic. Add direct sponsor banners for any of 13 placements.",
  settings: "Currency rates (USD↔NGN), brand uploads, site config (which sports show, popup notice), and admin user creation. Every section has its own Save button.",
  cards: "Legend-card catalog — adjust prices for surge demand, change position locks, or do bulk tier price updates. Every change is audited.",
  payments: "PocketFi webhook failures (signature mismatches) and manual NGN wallet credits for stuck deposits. Use sparingly — every action is audited.",
};

const StatCard = ({ icon: Icon, label, value }) => (
  <div className="cp-surface p-3">
    <Icon size={16} className="text-cp-lime mb-1.5"/>
    <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>{label}</div>
    <div className="text-2xl font-extrabold tabular-nums">{value ?? 0}</div>
  </div>
);

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

  const refreshPools = async () => { try { const { data } = await api.get("/prize-pools"); setPools(data.pools || []); } catch (_e) { /* ignore */ } };
  const refreshWcConfig = async () => { try { const { data } = await api.get("/admin/wc/config"); setWcConfig(data.config || []); } catch (_e) { /* ignore */ } };
  const refreshWcGames = async () => {
    const params = new URLSearchParams();
    if (wcGameFilter.game_type) params.set("game_type", wcGameFilter.game_type);
    if (wcGameFilter.status) params.set("status", wcGameFilter.status);
    try { const { data } = await api.get(`/admin/wc/games?${params.toString()}`); setWcGames(data.games || []); } catch (_e) { /* ignore */ }
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
      } catch (_e) { /* ignore */ }
    })();
  }, [user]);

  useEffect(() => {
    if (!user || user.role !== "admin") return;
    if (tab === "pools") refreshPools();
    if (tab === "wcconfig") refreshWcConfig();
    if (tab === "wcgames") refreshWcGames();
  }, [tab, wcGameFilter]); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) return <div className="cp-surface p-6 text-sm">Checking permissions…</div>;
  if (!user || user.role !== "admin") return <Navigate to="/signin" replace />;

  const trigger = async (url) => {
    setBusy(true); setMsg("");
    try { const { data } = await api.post(url); setMsg(JSON.stringify(data)); } catch (e) { setMsg("Failed: " + (e?.response?.data?.detail || e.message)); }
    setBusy(false);
  };

  return (
    <div data-testid="admin-panel">
      <h1 className="text-2xl font-extrabold mb-3">Admin Panel</h1>
      <div className="flex gap-1 cp-surface p-1 w-fit mb-3 flex-wrap">
        {["dashboard", "matches", "users", "ingest", "audit", "pools", "wcconfig", "wcgames", "players", "playerpoints", "cards", "payments", "ads", "settings"].map(t => (
          <button key={t} onClick={() => setTab(t)} className={`px-3 py-1.5 text-sm rounded transition ${tab === t ? "bg-cp-lime text-cp-forest font-bold" : "hover:bg-white/5"}`} data-testid={`admin-tab-${t}`}>{t.toUpperCase()}</button>
        ))}
      </div>

      {/* Tab hint banner */}
      <div className="cp-surface p-3 mb-3 text-xs flex items-start gap-2" style={{ background: "rgba(163,230,53,0.06)", border: "1px solid rgba(163,230,53,0.18)" }} data-testid="admin-tab-hint">
        <span className="text-cp-lime mt-0.5">›</span>
        <span style={{ color: "var(--cp-text)" }}>{TAB_HINTS[tab] || "Configure platform settings."}</span>
      </div>

      {tab === "dashboard" && stats && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard icon={Users} label="Users" value={stats.users}/>
            <StatCard icon={Activity} label="Active Sessions" value={stats.active_sessions}/>
            <StatCard icon={Database} label="Matches" value={stats.matches}/>
            <StatCard icon={Radio} label="Live Now" value={stats.live_matches}/>
            <StatCard icon={Database} label="Leagues" value={stats.leagues}/>
            <StatCard icon={Database} label="Teams" value={stats.teams}/>
            <StatCard icon={Trophy} label="Predictions" value={stats.predictions}/>
            <StatCard icon={Trophy} label="Fantasy Squads" value={stats.fantasy_squads}/>
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

          <div className="cp-surface p-4" data-testid="admin-fantasy-settle-card">
            <h3 className="text-sm font-extrabold mb-1">Fantasy Settle</h3>
            <p className="text-xs mb-3" style={{ color: "var(--cp-text-muted)" }}>
              <b>Rebuild</b> wipes every snapshot, resets <code>total_points = 0</code> on every squad, then re-settles
              every finished WC match using the latest CBIT/CBIRT scoring (FT bonus, defensive contributions,
              card / own-goal / goals-conceded deductions). Run after any scoring spec change. Idempotent.
              <br/><b>Settle now</b> re-credits points without wiping — safe to run any time.
            </p>
            <div className="flex gap-2 flex-wrap">
              <button
                onClick={async () => {
                  if (!confirm("Rebuild all fantasy points from scratch using the latest CBIT/CBIRT scoring? This will wipe and recompute every snapshot.")) return;
                  setBusy(true);
                  try {
                    const { data } = await api.post("/fantasy/settle/rebuild");
                    setMsg(`Rebuild ok · wiped ${data.snapshots_wiped} snapshots · reset ${data.squads_reset} squads · settled ${data.settled} · ${data.scoring_version}`);
                  } catch (e) { setMsg(e?.response?.data?.detail || "Rebuild failed"); }
                  setBusy(false);
                }}
                disabled={busy}
                className="cp-btn-primary text-xs disabled:opacity-50"
                data-testid="fantasy-settle-rebuild"
              >
                {busy ? "Rebuilding…" : "Rebuild all fantasy points"}
              </button>
              <button
                onClick={async () => {
                  if (!confirm("Rebuild all WC mini-game entries from scratch using the latest CBIT/CBIRT scoring? This will wipe every settled entry and recompute their points + ranks. Idempotent.")) return;
                  setBusy(true);
                  try {
                    const { data } = await api.post("/admin/wc/games/rebuild-settle");
                    setMsg(`Mini-games rebuild · games=${data.games_targeted} · entries=${data.entries_reset} · re-settled=${data.games_resettled}${data.failed?.length ? ` · failed=${data.failed.length}` : ""} · ${data.scoring_version}`);
                  } catch (e) { setMsg(e?.response?.data?.detail || "Mini-game rebuild failed"); }
                  setBusy(false);
                }}
                disabled={busy}
                className="cp-btn-primary text-xs disabled:opacity-50"
                data-testid="wcgames-rebuild-settle"
              >
                {busy ? "Rebuilding…" : "Rebuild all mini-game points"}
              </button>
              <button
                onClick={async () => {
                  if (!confirm("Rebuild ALL predictions from scratch? Wipes points and re-scores in chronological order so streak bonuses are correctly credited (fixes the over-counted streak bonus bug).")) return;
                  setBusy(true);
                  try {
                    const { data } = await api.post("/predictions/rebuild");
                    setMsg(`Predictions rebuild · scanned=${data.scanned} rebuilt=${data.rebuilt} · ${data.scoring_version || ""}`);
                  } catch (e) { setMsg(e?.response?.data?.detail || "Predictions rebuild failed"); }
                  setBusy(false);
                }}
                disabled={busy}
                className="cp-btn-primary text-xs disabled:opacity-50"
                data-testid="predictions-rebuild"
              >
                {busy ? "Rebuilding…" : "Rebuild all predictions"}
              </button>
              <button
                onClick={async () => {
                  setBusy(true);
                  try {
                    const { data } = await api.post("/fantasy/settle/gameweek?gameweek=1");
                    setMsg(`Re-settled ${data.settled || 0} squads`);
                  } catch (e) { setMsg(e?.response?.data?.detail || "Settle failed"); }
                  setBusy(false);
                }}
                disabled={busy}
                className="cp-btn-ghost text-xs disabled:opacity-50"
                data-testid="fantasy-settle-now"
              >
                Settle now (no wipe)
              </button>
            </div>
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
            <thead><tr style={{ color: "var(--cp-text-muted)" }} className="text-xs"><th className="text-left p-2">Email</th><th className="text-left">Name</th><th>Role</th><th>Active</th><th>Joined</th><th></th></tr></thead>
            <tbody>
              {users.map(u => (
                <tr key={u.id} className="border-t" style={{ borderColor: "var(--cp-border)" }} data-testid={`admin-user-row-${u.id}`}>
                  <td className="p-2">{u.email}</td>
                  <td>
                    <span>{u.display_name}</span>
                  </td>
                  <td className="text-center"><span className="cp-pill" style={{ background: u.role === "admin" ? "#A3E635" : "var(--cp-surface-2)", color: u.role === "admin" ? "#064E3B" : "var(--cp-text)" }}>{u.role}</span></td>
                  <td className="text-center">{u.is_active ? "✓" : "✗"}</td>
                  <td className="text-xs">{u.created_at?.slice(0,10)}</td>
                  <td className="text-right pr-2">
                    <button
                      onClick={async () => {
                        const next = prompt(`Edit display name for ${u.email}`, u.display_name || "");
                        if (next == null) return;
                        const trimmed = String(next).trim();
                        if (trimmed === (u.display_name || "")) return;
                        try {
                          const { data } = await api.patch(`/admin/users/${u.id}/display-name`, { display_name: trimmed });
                          setUsers((arr) => arr.map((x) => x.id === u.id ? { ...x, display_name: data.display_name } : x));
                          setMsg(`✓ Renamed ${u.email} → ${data.display_name}`);
                        } catch (e) {
                          setMsg(e?.response?.data?.detail || "Rename failed");
                        }
                      }}
                      className="text-[11px] underline opacity-80 hover:opacity-100"
                      data-testid={`admin-rename-${u.id}`}
                    >
                      Edit name
                    </button>
                  </td>
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
                      <label className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Amount (USD $)</label>
                      <input
                        type="number" step="0.01" min="0"
                        className="cp-input w-full"
                        value={((editingPool.amount_usd_cents || 0) / 100).toString()}
                        onChange={(e) => setEditingPool(s => ({ ...s, amount_usd_cents: Math.round(Number(e.target.value || 0) * 100) }))}
                        data-testid={`pool-usd-${p.id}`}
                      />
                      <div className="text-[9px] opacity-60 mt-1">Stored as {editingPool.amount_usd_cents || 0} cents</div>
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
                      <textarea className="cp-input w-full font-mono text-[11px]" rows={3} value={JSON.stringify(editingPool.payout_structure || [], null, 0)} onChange={(e) => { try { setEditingPool(s => ({ ...s, payout_structure: JSON.parse(e.target.value) })); } catch (_e) { /* ignore */ } }} data-testid={`pool-payout-${p.id}`}/>
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
            <button onClick={async () => {
              if (!confirm("Open ALL upcoming WC2026 games for entry NOW? Users will be able to enter every game.")) return;
              setBusy(true);
              try {
                const { data } = await api.post("/admin/wc/games/open-all");
                setMsg(`✓ Opened ${data.modified} games (total now open: ${data.now_open_total})`);
                refreshWcGames();
              } catch (e) { setMsg(e?.response?.data?.detail || "Failed"); }
              setBusy(false);
            }} className="cp-btn-primary" style={{ background: "var(--cp-lime)", color: "var(--cp-forest)" }} data-testid="wcgames-open-all">
              <Trophy size={14}/> Open ALL 148 games
            </button>
            <select
              className="cp-input w-44"
              data-testid="wcgames-open-stage"
              defaultValue=""
              onChange={async (e) => {
                const stage = e.target.value;
                if (!stage) return;
                if (!confirm(`Open every WC2026 game in stage "${stage}"? (round + group games for that stage)`)) {
                  e.target.value = ""; return;
                }
                setBusy(true);
                try {
                  const { data } = await api.post(`/admin/wc/games/open-stage?stage=${encodeURIComponent(stage)}`);
                  setMsg(`✓ Opened ${data.modified} games in stage ${stage}`);
                  refreshWcGames();
                } catch (err) { setMsg(err?.response?.data?.detail || "Open-stage failed"); }
                setBusy(false);
                e.target.value = "";
              }}
            >
              <option value="">Open stage…</option>
              <option value="group_md1">Group MD1</option>
              <option value="group_md2">Group MD2</option>
              <option value="group_md3">Group MD3</option>
              <option value="r32">Round of 32</option>
              <option value="r16">Round of 16</option>
              <option value="qf">Quarter-finals</option>
              <option value="sf">Semi-finals</option>
              <option value="finals">Finals</option>
            </select>
            <button
              data-testid="wcgames-backfill-closes"
              onClick={async () => {
                if (!confirm("Recompute closes_at on every group/round game so each round stays open until 30 min before its LAST match KO?")) return;
                setBusy(true);
                try {
                  const { data } = await api.post("/admin/wc/games/backfill-closes-at");
                  setMsg(`✓ Backfilled closes_at on ${data.updated}/${data.scanned} games`);
                  refreshWcGames();
                } catch (e) { setMsg(e?.response?.data?.detail || "Backfill failed"); }
                setBusy(false);
              }}
              className="cp-btn-primary"
              style={{ background: "var(--cp-surface-2)" }}
            >
              <Calendar size={14}/> Backfill closes_at
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
                {wcGames.length === 0 && <tr><td colSpan={9} className="p-4 text-center" style={{ color: "var(--cp-text-muted)" }}>No games yet — click &ldquo;Generate / Tick&rdquo; once WC fixtures are ingested.</td></tr>}
              </tbody>
            </table>
          </div>
          {msg && <div className="cp-surface p-2 text-xs font-mono">{msg}</div>}
        </div>
      )}

      {tab === "ads" && (
        <AdsTab onMessage={setMsg}/>
      )}

      {tab === "settings" && (
        <SettingsTab onMessage={setMsg}/>
      )}

      {tab === "players" && (
        <PlayerPricesTab onMessage={setMsg}/>
      )}

      {tab === "playerpoints" && (
        <PlayerSeasonPointsTab onMessage={setMsg}/>
      )}

      {tab === "cards" && (
        <CardPricesTab onMessage={setMsg}/>
      )}

      {tab === "payments" && (
        <PaymentsAdminTab onMessage={setMsg}/>
      )}
    </div>
  );
};

function PlayerPricesTab({ onMessage }) {
  const [rows, setRows] = useState([]);
  const [search, setSearch] = useState("");
  const [position, setPosition] = useState("");
  const [team, setTeam] = useState("");
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (search) params.append("q", search);
      if (position) params.append("position", position);
      if (team) params.append("team", team);
      params.append("limit", "100");
      const { data } = await api.get(`/admin/players?${params}`);
      setRows(data.players || []);
    } catch (e) {
      onMessage(`✗ ${e?.response?.data?.detail || e.message}`);
    }
    setLoading(false);
  };
  useEffect(() => { load(); }, [position]); // eslint-disable-line react-hooks/exhaustive-deps

  const setPrice = async (id, value) => {
    const price = parseFloat(value);
    if (Number.isNaN(price)) return;
    try {
      await api.patch(`/admin/players/${id}/price`, { price });
      onMessage(`✓ Price updated to £${price.toFixed(1)}`);
      setRows(rs => rs.map(r => r.id === id ? { ...r, price, price_override: true } : r));
    } catch (e) {
      onMessage(`✗ ${e?.response?.data?.detail || e.message}`);
    }
  };

  const recompute = async () => {
    if (!confirm("Recompute auto-prices for ALL non-overridden players? Manually-edited players will be untouched.")) return;
    try {
      const { data } = await api.post("/admin/players/recompute-prices");
      onMessage(`✓ ${data.updated}/${data.scanned} updated, ${data.star_hits || 0} star tiers applied`);
      load();
    } catch (e) {
      onMessage(`✗ ${e?.response?.data?.detail || e.message}`);
    }
  };

  return (
    <div className="space-y-3" data-testid="admin-players">
      <div className="cp-surface p-3 flex flex-wrap gap-2 items-center">
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          onKeyDown={e => e.key === "Enter" && load()}
          placeholder="Search player or team…"
          className="cp-input flex-1 min-w-[160px]"
          data-testid="players-search"
        />
        <select value={position} onChange={e => setPosition(e.target.value)} className="cp-input text-xs max-w-[120px]" data-testid="players-position">
          <option value="">All positions</option>
          <option value="GK">GK</option><option value="DEF">DEF</option>
          <option value="MID">MID</option><option value="FWD">FWD</option>
        </select>
        <button onClick={load} className="cp-btn-primary" data-testid="players-search-btn">Search</button>
        <button onClick={recompute} className="cp-btn-ghost" data-testid="players-recompute">Recompute auto-prices</button>
      </div>
      <div className="cp-surface overflow-hidden" data-testid="players-table">
        {loading ? (
          <div className="p-6 text-center text-sm opacity-60">Loading…</div>
        ) : rows.length === 0 ? (
          <div className="p-6 text-center text-sm opacity-60">No players match your filters.</div>
        ) : (
          <ul className="divide-y" style={{ borderColor: "var(--cp-border)" }}>
            {rows.map(p => (
              <li key={p.id} className="flex items-center gap-3 px-3 py-2" data-testid={`player-row-${p.id}`}>
                <span className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded" style={{ background: "var(--cp-surface-2)" }}>
                  {p.position}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="font-bold truncate">{p.name}</div>
                  <div className="text-[10px] opacity-60 truncate">{p.team_name}{p.shirt_number ? ` · #${p.shirt_number}` : ""}</div>
                </div>
                <input
                  type="number" step="0.5" min="3.0" max="15.0"
                  defaultValue={p.price}
                  onKeyDown={e => e.key === "Enter" && setPrice(p.id, e.currentTarget.value)}
                  className="cp-input w-20 text-right tabular-nums"
                  data-testid={`player-price-${p.id}`}
                  id={`player-price-input-${p.id}`}
                />
                <button
                  onClick={() => setPrice(p.id, document.getElementById(`player-price-input-${p.id}`).value)}
                  className="cp-btn-primary !py-1 !px-2 text-[10px] font-extrabold"
                  data-testid={`player-save-${p.id}`}
                >Save</button>
                <span className="text-[10px] opacity-60 w-8 text-right">
                  {p.price_override ? "manual" : "auto"}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="text-[10px] opacity-60">
        Click <b>Save</b> (or press Enter) to commit a price. Manual prices survive auto-recompute.
      </div>
    </div>
  );
}

/* ──────────────────────────────────────────────────────────────────────── */
/** CardPricesTab — admin-only legend card price + position-lock editor.
 *  Surge pricing: when demand spikes (e.g. before a big match), edit the
 *  price here in cents. Bulk-set all cards in a tier via "Apply tier price".
 */
function CardPricesTab({ onMessage }) {
  const [cards, setCards] = useState([]);
  const [filter, setFilter] = useState(0); // tier 0 = all
  const [loading, setLoading] = useState(false);
  const [bulkPrice, setBulkPrice] = useState({ 1: "", 2: "", 3: "" });
  const POS_OPTIONS = ["ANY", "GK", "DEF", "MID", "FWD"];

  const load = async () => {
    setLoading(true);
    try {
      const params = filter ? `?tier=${filter}` : "";
      const { data } = await api.get(`/admin/cards${params}`);
      setCards(data.cards || []);
    } catch (e) {
      onMessage(`✗ ${e?.response?.data?.detail || e.message}`);
    }
    setLoading(false);
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [filter]);

  const patch = async (id, body) => {
    try {
      const { data } = await api.patch(`/admin/cards/${id}`, body);
      onMessage(`✓ Updated ${data.card.name}`);
      setCards(cs => cs.map(c => c.id === id ? data.card : c));
    } catch (e) {
      onMessage(`✗ ${e?.response?.data?.detail || e.message}`);
    }
  };

  const bulkApply = async (tier) => {
    const coins = parseInt(bulkPrice[tier] || "0", 10);
    if (!coins || coins < 1) return onMessage("Bulk price must be ≥ 1 coin");
    if (!confirm(`Set every Tier-${tier} card to 🪙 ${coins.toLocaleString()} coins?`)) return;
    try {
      const { data } = await api.post("/admin/cards/bulk-price", { tier, price_coins: coins });
      onMessage(`✓ Tier ${tier}: ${data.modified} cards re-priced to 🪙 ${coins.toLocaleString()}`);
      load();
    } catch (e) {
      onMessage(`✗ ${e?.response?.data?.detail || e.message}`);
    }
  };

  return (
    <div className="space-y-3" data-testid="admin-cards">
      <div className="cp-surface p-3 flex flex-wrap gap-2 items-center">
        {[{id:0,label:"All"},{id:1,label:"Legendary"},{id:2,label:"Elite"},{id:3,label:"Star"}].map(f => (
          <button
            key={f.id}
            onClick={() => setFilter(f.id)}
            className={`px-3 py-1.5 rounded text-xs font-bold ${filter === f.id ? "bg-cp-lime text-cp-forest" : "hover:bg-white/5"}`}
            style={filter !== f.id ? { background: "var(--cp-surface-2)" } : {}}
            data-testid={`admin-cards-filter-${f.id}`}
          >{f.label}</button>
        ))}
      </div>

      {/* Bulk tier-pricing — in COINS */}
      <div className="cp-surface p-3" data-testid="admin-cards-bulk">
        <h3 className="text-sm font-extrabold mb-2">Bulk re-price by tier (coins)</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
          {[1,2,3].map(tier => (
            <div key={tier} className="flex items-center gap-2" data-testid={`admin-cards-bulk-tier-${tier}`}>
              <span className="text-xs font-bold w-16">{tier === 1 ? "Legendary" : tier === 2 ? "Elite" : "Star"}</span>
              <span className="text-[10px] opacity-60">🪙</span>
              <input
                type="number" min="1" max="1000000"
                value={bulkPrice[tier]}
                onChange={e => setBulkPrice(bp => ({...bp, [tier]: e.target.value}))}
                placeholder={tier === 1 ? "1000" : tier === 2 ? "500" : "200"}
                className="cp-input flex-1 text-xs"
                data-testid={`admin-cards-bulk-input-${tier}`}
              />
              <button
                onClick={() => bulkApply(tier)}
                className="cp-btn-primary !py-1 !px-2 text-[10px] font-extrabold"
                data-testid={`admin-cards-bulk-apply-${tier}`}
              >Apply</button>
            </div>
          ))}
        </div>
        <p className="text-[10px] opacity-60 mt-2">Defaults: Legendary 🪙 1,000 · Elite 🪙 500 · Star 🪙 200. Surge-price during finals.</p>
      </div>

      <div className="cp-surface overflow-hidden" data-testid="admin-cards-table">
        {loading ? (
          <div className="p-6 text-center text-sm opacity-60">Loading cards…</div>
        ) : cards.length === 0 ? (
          <div className="p-6 text-center text-sm opacity-60">No cards.</div>
        ) : (
          <ul className="divide-y" style={{ borderColor: "var(--cp-border)" }}>
            {cards.map(c => {
              const tierLabel = c.tier === 1 ? "Legendary" : c.tier === 2 ? "Elite" : "Star";
              const tierColor = c.tier === 1 ? "#FFD27A" : c.tier === 2 ? "#A3E635" : "#F25C1B";
              const coins = c.price_coins || (c.tier === 1 ? 1000 : c.tier === 2 ? 500 : 200);
              return (
                <li key={c.id} className="flex items-center gap-3 px-3 py-2 flex-wrap" data-testid={`admin-card-row-${c.id}`}>
                  <span className="text-[10px] font-extrabold uppercase px-1.5 py-0.5 rounded" style={{ background: tierColor, color: "#0F1115", minWidth: 60, textAlign: "center" }}>
                    {tierLabel}
                  </span>
                  <div className="flex-1 min-w-[160px]">
                    <div className="font-bold truncate">{c.name}</div>
                    <div className="text-[10px] opacity-60 truncate">{c.player_name} · {c.country_code}</div>
                  </div>
                  {/* Position lock */}
                  <select
                    defaultValue={c.position || "ANY"}
                    onChange={e => patch(c.id, { position: e.target.value })}
                    className="cp-input text-xs"
                    style={{ maxWidth: 90 }}
                    data-testid={`admin-card-pos-${c.id}`}
                  >
                    {POS_OPTIONS.map(p => <option key={p} value={p}>{p}</option>)}
                  </select>
                  {/* Price (coins) */}
                  <div className="flex items-center gap-1">
                    <span className="text-[10px] opacity-60">🪙</span>
                    <input
                      id={`admin-card-price-input-${c.id}`}
                      type="number" step="50" min="1" max="1000000"
                      defaultValue={coins}
                      onKeyDown={e => e.key === "Enter" && patch(c.id, { price_coins: parseInt(e.currentTarget.value, 10) })}
                      className="cp-input text-xs tabular-nums"
                      style={{ width: 96 }}
                      data-testid={`admin-card-price-${c.id}`}
                    />
                    <span className="text-[10px] opacity-60 tabular-nums" style={{ minWidth: 38 }}>coins</span>
                  </div>
                  <button
                    onClick={() => {
                      const el = document.getElementById(`admin-card-price-input-${c.id}`);
                      patch(c.id, { price_coins: parseInt(el.value, 10) });
                    }}
                    className="cp-btn-primary !py-1 !px-2 text-[10px] font-extrabold"
                    data-testid={`admin-card-save-${c.id}`}
                  >Save</button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
      <div className="text-[10px] opacity-60">
        Press <b>Enter</b> (or <b>Save</b>) to commit. Position locks restrict which players a card can boost. Every change is logged in Audit.
      </div>
    </div>
  );
}



/* ──────────────────────────────────────────────────────────────────────── */

function SettingsTab({ onMessage }) {
  return (
    <div className="space-y-4 max-w-2xl" data-testid="admin-settings">
      <SiteConfigForm onMessage={onMessage}/>
      <CurrencyRateForm onMessage={onMessage}/>
      <BrandUploader onMessage={onMessage}/>
      <CreateAdminForm onMessage={onMessage}/>
    </div>
  );
}

/* ──────────────────────────────────────────────────────────────────────── */

const ALL_SPORT_SLUGS = [
  "football", "basketball", "tennis", "baseball", "hockey", "cricket",
  "rugby", "nba", "volleyball", "handball", "mma", "f1", "afl", "golf",
];

function SiteConfigForm({ onMessage }) {
  const [enabled, setEnabled] = useState(new Set(ALL_SPORT_SLUGS));
  const [showWcTab, setShowWcTab] = useState(true);
  const [popup, setPopup] = useState({ enabled: false, title: "", body: "", image_url: "", cta_text: "", cta_link: "" });
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  // Snapshot of the last-saved state — diff against current to compute "dirty"
  const [pristine, setPristine] = useState({ enabled: new Set(), showWcTab: true, popup: {} });

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/site-config");
        const en = new Set(data?.enabled_sports || ALL_SPORT_SLUGS);
        const swc = data?.show_wc_tab !== false;
        const p = data?.popup_notice || {};
        const popupShape = {
          enabled: !!p.enabled,
          title: p.title || "",
          body: p.body || "",
          image_url: p.image_url || "",
          cta_text: p.cta_text || "",
          cta_link: p.cta_link || "",
        };
        setEnabled(en);
        setShowWcTab(swc);
        setPopup(popupShape);
        setPristine({ enabled: new Set(en), showWcTab: swc, popup: { ...popupShape } });
      } catch (_e) { /* ignore — show defaults */ }
      setLoaded(true);
    })();
  }, []);

  const toggle = (slug) => {
    setEnabled(prev => {
      const next = new Set(prev);
      if (next.has(slug)) next.delete(slug);
      else next.add(slug);
      return next;
    });
  };

  // Compute dirty (unsaved) status — compare current to pristine.
  const isDirty = (() => {
    if (!loaded) return false;
    if (showWcTab !== pristine.showWcTab) return true;
    if (enabled.size !== pristine.enabled.size) return true;
    for (const s of enabled) if (!pristine.enabled.has(s)) return true;
    for (const k of Object.keys(popup)) if (popup[k] !== (pristine.popup || {})[k]) return true;
    return false;
  })();

  const save = async (bumpVersion = false) => {
    setBusy(true);
    try {
      await api.post("/admin/site-config", {
        enabled_sports: Array.from(enabled),
        show_wc_tab: showWcTab,
        popup_notice: { ...popup, bump_version: bumpVersion },
      });
      onMessage(`✓ Site config saved${bumpVersion ? " · popup re-shown for everyone" : ""}`);
      setPristine({ enabled: new Set(enabled), showWcTab, popup: { ...popup } });
    } catch (e) {
      onMessage(`✗ ${e?.response?.data?.detail || e.message}`);
    }
    setBusy(false);
  };

  if (!loaded) return <div className="cp-surface p-4 text-xs opacity-60">Loading site config…</div>;
  return (
    <div className="cp-surface p-4 space-y-4" data-testid="site-config-form">
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Settings2 size={16} className="text-cp-lime"/>
          <h2 className="font-extrabold">Sports navigation</h2>
        </div>
        <div className="text-[11px] opacity-60 mb-3">
          Disabled sports disappear from the header AND get skipped by the live ingestion worker (saves API quota).
        </div>
        <label className="inline-flex items-center gap-2 text-xs font-bold mb-2 cursor-pointer" data-testid="show-wc-tab">
          <input type="checkbox" checked={showWcTab} onChange={e => setShowWcTab(e.target.checked)}/>
          Show &ldquo;WC 2026&rdquo; tab in sports nav
        </label>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2" data-testid="sport-toggles">
          {ALL_SPORT_SLUGS.map(slug => {
            const on = enabled.has(slug);
            return (
              <button
                key={slug}
                onClick={() => toggle(slug)}
                className="text-xs font-bold px-2.5 py-2 rounded text-left flex items-center gap-2"
                style={{
                  background: on ? "rgba(163, 230, 53, 0.18)" : "var(--cp-surface-2)",
                  border: `1px solid ${on ? "rgba(163, 230, 53, 0.4)" : "var(--cp-border)"}`,
                  color: on ? "var(--cp-text)" : "var(--cp-text-muted)",
                  textTransform: "capitalize",
                }}
                data-testid={`toggle-sport-${slug}`}
              >
                <span style={{
                  width: 14, height: 14, borderRadius: 4,
                  background: on ? "var(--cp-lime)" : "transparent",
                  border: `1.5px solid ${on ? "var(--cp-lime)" : "var(--cp-text-muted)"}`,
                  display: "inline-flex", alignItems: "center", justifyContent: "center",
                  color: "var(--cp-forest)", fontSize: 10, fontWeight: 900,
                }}>{on ? "✓" : ""}</span>
                {slug}
              </button>
            );
          })}
        </div>
      </div>

      <div style={{ borderTop: "1px solid var(--cp-border)" }} className="pt-4">
        <div className="flex items-center gap-2 mb-1">
          <Settings2 size={16} className="text-cp-lime"/>
          <h2 className="font-extrabold">Popup notice (promo modal)</h2>
        </div>
        <div className="text-[11px] opacity-60 mb-3">
          Shown to every visitor once per device. Hit <b>&ldquo;Save &amp; re-show to everyone&rdquo;</b> to bump the version and re-trigger for users who already dismissed it.
        </div>
        <label className="inline-flex items-center gap-2 text-xs font-bold mb-3 cursor-pointer" data-testid="popup-enabled">
          <input type="checkbox" checked={popup.enabled} onChange={e => setPopup({ ...popup, enabled: e.target.checked })}/>
          Popup enabled
        </label>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          <input
            placeholder="Title (e.g. Cloudy Pitch Fantasy)"
            value={popup.title}
            onChange={e => setPopup({ ...popup, title: e.target.value })}
            maxLength={120}
            className="cp-input text-sm" data-testid="popup-title"
          />
          <input
            placeholder="Image URL (16:9, optional)"
            value={popup.image_url}
            onChange={e => setPopup({ ...popup, image_url: e.target.value })}
            maxLength={1024}
            className="cp-input text-sm" data-testid="popup-image"
          />
        </div>
        <textarea
          placeholder="Body — short pitch text"
          value={popup.body}
          onChange={e => setPopup({ ...popup, body: e.target.value })}
          maxLength={600}
          rows={3}
          className="cp-input text-sm w-full mt-2" data-testid="popup-body"
        />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-2">
          <input
            placeholder="CTA text (e.g. Play now)"
            value={popup.cta_text}
            onChange={e => setPopup({ ...popup, cta_text: e.target.value })}
            maxLength={40}
            className="cp-input text-sm" data-testid="popup-cta-text"
          />
          <input
            placeholder="CTA link (e.g. /build-team or https://…)"
            value={popup.cta_link}
            onChange={e => setPopup({ ...popup, cta_link: e.target.value })}
            maxLength={500}
            className="cp-input text-sm" data-testid="popup-cta-link"
          />
        </div>
      </div>

      <div
        className="flex flex-wrap items-center gap-2 pt-3 sticky bottom-0 z-10 -mx-4 px-4 pb-2"
        style={{
          background: "linear-gradient(180deg, transparent 0%, var(--cp-surface) 30%)",
          borderTop: isDirty ? "2px solid #FFB400" : "1px solid var(--cp-border)",
        }}
        data-testid="site-config-actions"
      >
        {isDirty && (
          <span
            className="cp-pill !text-[10px] !font-extrabold mr-1 animate-pulse"
            style={{ background: "rgba(255, 180, 0, 0.15)", color: "#FFB400" }}
            data-testid="site-config-dirty"
          >
            ● Unsaved changes
          </span>
        )}
        <button
          onClick={() => save(false)}
          disabled={busy || !isDirty}
          className="px-4 py-2 rounded text-sm font-extrabold disabled:opacity-40"
          style={{ background: "var(--cp-lime)", color: "var(--cp-forest)" }}
          data-testid="site-config-save"
        >
          {busy ? "Saving…" : isDirty ? "Save changes" : "Saved"}
        </button>
        <button
          onClick={() => save(true)}
          disabled={busy || !popup.enabled}
          className="px-4 py-2 rounded text-sm font-extrabold disabled:opacity-50"
          style={{ background: "var(--cp-surface-2)", border: "1px solid var(--cp-border)", color: "var(--cp-text)" }}
          data-testid="site-config-save-bump"
          title="Bumps popup_notice.version so users who dismissed see it again."
        >
          Save & re-show popup to everyone
        </button>
      </div>
    </div>
  );
}

/* ──────────────────────────────────────────────────────────────────────── */

function CurrencyRateForm({ onMessage }) {
  const [rate, setRate] = useState(1400);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/currency?force=NG");
        setRate(data.rate || 1400);
      } catch (_e) { /* ignore — show defaults */ }
      setLoaded(true);
    })();
  }, []);
  const save = async (e) => {
    e.preventDefault();
    try {
      await api.post("/admin/currency", { ngn_per_usd: Number(rate) });
      onMessage(`✓ NGN exchange rate updated to ₦${rate}/$1`);
    } catch (e) {
      onMessage(`✗ ${e?.response?.data?.detail || e.message}`);
    }
  };
  return (
    <form onSubmit={save} className="cp-surface p-4" data-testid="currency-rate-form">
      <h2 className="font-extrabold mb-1">Naira exchange rate</h2>
      <div className="text-[11px] opacity-60 mb-3">Nigerian visitors will see all prices auto-converted at this rate. Other countries continue seeing USD.</div>
      <div className="flex items-center gap-2">
        <span className="text-xs">₦</span>
        <input
          type="number" step="1" min="1" max="100000"
          value={loaded ? rate : ""}
          onChange={e => setRate(e.target.value)}
          className="cp-input flex-1"
          data-testid="ngn-rate-input"
        />
        <span className="text-xs">/ $1</span>
        <button type="submit" className="cp-btn-primary" data-testid="ngn-rate-save">Save</button>
      </div>
    </form>
  );
}

function BrandUploader({ onMessage }) {
  const slots = [
    { key: "logo",      label: "Light-theme logo (header default)." },
    { key: "logo_dark", label: "Dark-theme logo (auto-used when site is in dark mode)." },
    { key: "mark",      label: "Mark only (no text) — used in loader animation." },
    { key: "wordmark",  label: "Wordmark only (text part)." },
    { key: "favicon",   label: "Browser tab favicon (PNG/ICO 32×32 or 64×64). Replaces the static /cp-mark.png everywhere." },
  ];
  const [current, setCurrent] = useState({});
  const load = async () => {
    try { const { data } = await api.get("/brand"); setCurrent(data); } catch (_e) { /* ignore */ }
  };
  useEffect(() => { load(); }, []);

  const upload = async (slotKey, file) => {
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    fd.append("entity_type", "brand");
    fd.append("entity_id", slotKey);
    try {
      await api.post("/admin/uploads", fd, { headers: { "Content-Type": "multipart/form-data" } });
      onMessage(`✓ ${slotKey} updated. Refresh the page to see it everywhere.`);
      await refreshBrand();
      await load();
    } catch (e) {
      onMessage(`✗ Upload failed: ${e?.response?.data?.detail || e.message}`);
    }
  };

  return (
    <div className="cp-surface p-4" data-testid="brand-uploader">
      <div className="flex items-center gap-2 mb-3">
        <ImageIcon size={16} className="text-cp-lime"/>
        <h2 className="font-extrabold">Brand assets</h2>
      </div>
      <div className="space-y-3">
        {slots.map(s => {
          const url = current[`brand_${s.key}_url`];
          return (
            <div key={s.key} className="flex items-center gap-3" data-testid={`brand-slot-${s.key}`}>
              <div className="w-20 h-12 rounded flex items-center justify-center" style={{ background: "var(--cp-surface-2)", border: "1px solid var(--cp-border)" }}>
                {url ? (
                  <img src={url} alt={s.key} style={{ maxHeight: "100%", maxWidth: "100%", objectFit: "contain" }}/>
                ) : (
                  <span className="text-[9px] opacity-40">empty</span>
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-xs font-bold uppercase">{s.key}</div>
                <div className="text-[10px]" style={{ color: "var(--cp-text-muted)" }}>{s.label}</div>
              </div>
              <label className="text-xs px-3 py-1.5 rounded cursor-pointer hover:opacity-80" style={{ background: "var(--cp-lime)", color: "var(--cp-forest)", fontWeight: 700 }} data-testid={`brand-upload-${s.key}`}>
                Upload
                <input type="file" accept="image/*" className="hidden" onChange={e => upload(s.key, e.target.files?.[0])}/>
              </label>
            </div>
          );
        })}
      </div>
      <div className="text-[10px] mt-3 opacity-60">PNG / SVG / JPEG / WebP, max 5 MB. Transparent backgrounds render best.</div>
    </div>
  );
}

function CreateAdminForm({ onMessage }) {
  const [form, setForm] = useState({ email: "", password: "", display_name: "" });
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const { data } = await api.post("/admin/users/create-admin", form);
      if (data.created) onMessage(`✓ Admin created: ${form.email}`);
      else if (data.promoted) onMessage(`✓ Existing user promoted to admin: ${form.email}`);
      setForm({ email: "", password: "", display_name: "" });
    } catch (e) {
      onMessage(`✗ ${e?.response?.data?.detail || e.message}`);
    }
    setBusy(false);
  };
  return (
    <form onSubmit={submit} className="cp-surface p-4 space-y-2" data-testid="create-admin-form">
      <div className="flex items-center gap-2 mb-2">
        <UserPlus size={16} className="text-cp-lime"/>
        <h2 className="font-extrabold">Create / promote admin</h2>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        <input
          required type="email"
          placeholder="email@example.com"
          value={form.email}
          onChange={e => setForm({ ...form, email: e.target.value })}
          className="px-3 py-2 rounded text-sm"
          style={{ background: "var(--cp-surface-2)", border: "1px solid var(--cp-border)", color: "var(--cp-text)" }}
          data-testid="create-admin-email"
        />
        <input
          type="text"
          placeholder="Display name (optional)"
          value={form.display_name}
          onChange={e => setForm({ ...form, display_name: e.target.value })}
          className="px-3 py-2 rounded text-sm"
          style={{ background: "var(--cp-surface-2)", border: "1px solid var(--cp-border)", color: "var(--cp-text)" }}
          data-testid="create-admin-name"
        />
      </div>
      <input
        required type="password" minLength={8}
        placeholder="Password (min 8 characters)"
        value={form.password}
        onChange={e => setForm({ ...form, password: e.target.value })}
        className="w-full px-3 py-2 rounded text-sm"
        style={{ background: "var(--cp-surface-2)", border: "1px solid var(--cp-border)", color: "var(--cp-text)" }}
        data-testid="create-admin-password"
      />
      <button
        type="submit" disabled={busy}
        className="px-4 py-2 rounded text-sm font-extrabold disabled:opacity-50"
        style={{ background: "var(--cp-lime)", color: "var(--cp-forest)" }}
        data-testid="create-admin-submit"
      >
        {busy ? "Creating…" : "Create / promote"}
      </button>
      <div className="text-[10px] opacity-60">If the email already exists it will be promoted to admin instead of creating a new account.</div>
    </form>
  );
}

export default AdminPanel;


/* ──────────────────────────────────────────────────────────────────────── */
/** PaymentsAdminTab — view PocketFi webhook deliveries that failed signature
 *  verification, and manually credit a user's NGN wallet when a deposit was
 *  confirmed in PocketFi's dashboard but didn't reach the wallet because of
 *  a header/algorithm mismatch. Every manual credit is audited and idempotent
 *  on the PocketFi reference.
 */
function PaymentsAdminTab({ onMessage }) {
  const [failures, setFailures] = useState([]);
  const [loadingF, setLoadingF] = useState(false);
  const [form, setForm] = useState({ email: "", amount_ngn: "", reference: "", reason: "" });
  const [submitting, setSubmitting] = useState(false);

  const loadFailures = async () => {
    setLoadingF(true);
    try {
      const { data } = await api.get("/admin/webhooks/pocketfi/failures?limit=20");
      setFailures(data.failures || []);
    } catch (e) { onMessage(`✗ ${e?.response?.data?.detail || e.message}`); }
    setLoadingF(false);
  };
  useEffect(() => { loadFailures(); /* eslint-disable-next-line */ }, []);

  const submitCredit = async (e) => {
    e.preventDefault();
    if (!form.email || !form.amount_ngn || !form.reference || !form.reason) {
      onMessage("✗ All fields required."); return;
    }
    if (!confirm(`Credit ₦${form.amount_ngn} to ${form.email}?\nReference: ${form.reference}`)) return;
    setSubmitting(true);
    try {
      const { data } = await api.post("/admin/wallet/credit-ngn", {
        email: form.email,
        amount_ngn: parseInt(form.amount_ngn, 10),
        reference: form.reference,
        reason: form.reason,
      });
      if (data.duplicate) {
        onMessage(`⚠ Already credited (idempotent) — tx ${data.transaction_id}`);
      } else {
        onMessage(`✓ Credited ₦${data.amount_credited_ngn} to ${data.email} · new balance ₦${data.new_balance_ngn}`);
        setForm({ email: "", amount_ngn: "", reference: "", reason: "" });
      }
    } catch (err) {
      onMessage(`✗ ${err?.response?.data?.detail || err.message}`);
    }
    setSubmitting(false);
  };

  const prefillFromFailure = (f) => {
    let body = {};
    try { body = JSON.parse(f.raw_body); } catch (_) { /* ignore */ }
    setForm({
      email: body?.customer?.email || "",
      amount_ngn: String(body?.order?.amount || ""),
      reference: body?.transaction?.reference || "",
      reason: `Webhook ${f.reason} — verified deposit manually from PocketFi dashboard`,
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <div className="space-y-3" data-testid="admin-payments">
      <div className="cp-surface p-3" data-testid="admin-pf-credit">
        <h3 className="text-sm font-extrabold mb-2">Manual NGN credit (stuck deposits)</h3>
        <p className="text-[11px] mb-3" style={{ color: "var(--cp-text-muted)" }}>
          Use this when a user's PocketFi deposit reflects in their dashboard but didn't credit our wallet
          (usually a webhook signature mismatch). Idempotent on <b>Reference</b> — re-submitting the same
          reference will not double-credit.
        </p>
        <form onSubmit={submitCredit} className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          <input className="cp-input text-sm" placeholder="User email (e.g. nelsonurhie49@gmail.com)"
                 value={form.email} onChange={e => setForm(f => ({...f, email: e.target.value}))}
                 data-testid="admin-pf-credit-email"/>
          <input className="cp-input text-sm tabular-nums" placeholder="Amount NGN (e.g. 99)" inputMode="numeric"
                 value={form.amount_ngn} onChange={e => setForm(f => ({...f, amount_ngn: e.target.value}))}
                 data-testid="admin-pf-credit-amount"/>
          <input className="cp-input text-sm font-mono" placeholder="Reference (e.g. PFI|260611857730)"
                 value={form.reference} onChange={e => setForm(f => ({...f, reference: e.target.value}))}
                 data-testid="admin-pf-credit-ref"/>
          <input className="cp-input text-sm" placeholder="Reason (audit log)"
                 value={form.reason} onChange={e => setForm(f => ({...f, reason: e.target.value}))}
                 data-testid="admin-pf-credit-reason"/>
          <button type="submit" disabled={submitting}
                  className="cp-btn-primary text-sm font-extrabold sm:col-span-2 disabled:opacity-50"
                  data-testid="admin-pf-credit-submit">
            {submitting ? "Crediting…" : "Credit NGN"}
          </button>
        </form>
      </div>

      <div className="cp-surface" data-testid="admin-pf-failures">
        <div className="px-3 py-2 flex items-center justify-between border-b" style={{ borderColor: "var(--cp-border)" }}>
          <h3 className="text-sm font-extrabold">PocketFi webhook failures (last 20)</h3>
          <button onClick={loadFailures} className="cp-btn-ghost !p-1.5 text-[10px]" data-testid="admin-pf-failures-reload">↻ Reload</button>
        </div>
        {loadingF ? (
          <div className="p-6 text-center text-sm opacity-60">Loading…</div>
        ) : failures.length === 0 ? (
          <div className="p-6 text-center text-sm opacity-60">No failures — webhooks are clean.</div>
        ) : (
          <ul className="divide-y" style={{ borderColor: "var(--cp-border)" }}>
            {failures.map(f => {
              let body = {};
              try { body = JSON.parse(f.raw_body); } catch (_) { /* ignore */ }
              const ref = body?.transaction?.reference;
              const amt = body?.order?.amount;
              const email = body?.customer?.email;
              // Show only signature-ish headers (signature, hmac, hub, etc.)
              const sigHdrs = Object.entries(f.headers || {})
                .filter(([k]) => /sign|hmac|hub|verify/i.test(k));
              return (
                <li key={f.id} className="px-3 py-2 text-xs space-y-1" data-testid={`admin-pf-fail-${f.id}`}>
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <div><span className="opacity-60">Ref:</span> <code className="font-mono">{ref || "—"}</code></div>
                    <div className="tabular-nums">₦{amt ?? "—"} · {email || "—"}</div>
                    <div className="opacity-60">{f.received_at?.slice(0, 19).replace("T", " ")}</div>
                  </div>
                  {sigHdrs.length > 0 ? (
                    <div className="text-[10px] opacity-80">
                      <b>Signature headers observed:</b>
                      {sigHdrs.map(([k, v]) => (
                        <div key={k} className="font-mono break-all">{k}: {String(v).slice(0, 80)}{String(v).length > 80 ? "…" : ""}</div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-[10px] opacity-60">No signature-like header observed (PocketFi sent none).</div>
                  )}
                  <button onClick={() => prefillFromFailure(f)} className="cp-btn-ghost !py-1 !px-2 text-[10px] font-extrabold" data-testid={`admin-pf-prefill-${f.id}`}>
                    → Pre-fill manual credit form
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}

function PlayerSeasonPointsTab({ onMessage }) {
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState({ matches_processed: 0, scanned_players: 0 });
  const [search, setSearch] = useState("");
  const [position, setPosition] = useState("");
  const [busy, setBusy] = useState(false);
  const [sortBy, setSortBy] = useState("season_points");
  const [savingId, setSavingId] = useState(null);

  const load = async () => {
    setBusy(true);
    try {
      const { data } = await api.get("/admin/players/season-points?limit=1500");
      setRows(data.players || []);
      setMeta({ matches_processed: data.matches_processed, scanned_players: data.scanned_players });
    } catch (e) { onMessage?.(e?.response?.data?.detail || "Failed to load"); }
    setBusy(false);
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  const applyPrice = async (player_id, suggested) => {
    setSavingId(player_id);
    try {
      const { data } = await api.patch(`/admin/players/${player_id}/price`, { price: suggested });
      setRows((arr) => arr.map((r) => r.player_id === player_id ? { ...r, price: data.price } : r));
      onMessage?.(`✓ Price set to €${data.price}M for ${player_id}`);
    } catch (e) {
      onMessage?.(e?.response?.data?.detail || "Price update failed");
    }
    setSavingId(null);
  };

  const filtered = rows
    .filter((r) => !search || (r.name || "").toLowerCase().includes(search.toLowerCase()) || (r.team_name || "").toLowerCase().includes(search.toLowerCase()))
    .filter((r) => !position || r.position === position)
    .sort((a, b) => {
      if (sortBy === "season_points") return (b.season_points || 0) - (a.season_points || 0);
      if (sortBy === "ppg") return (b.ppg || 0) - (a.ppg || 0);
      if (sortBy === "price") return (b.price || 0) - (a.price || 0);
      if (sortBy === "delta") return ((b.suggested_price || 0) - (b.price || 0)) - ((a.suggested_price || 0) - (a.price || 0));
      return (a.name || "").localeCompare(b.name || "");
    });

  return (
    <div className="space-y-3" data-testid="admin-player-points">
      <div className="cp-surface p-3 flex flex-wrap items-center gap-3">
        <div className="text-xs flex-1 min-w-[180px]" style={{ color: "var(--cp-text-muted)" }}>
          {meta.matches_processed} finished WC matches · {meta.scanned_players} players scanned
        </div>
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search player or country…" className="cp-input min-w-[200px]" data-testid="pp-search"/>
        <select value={position} onChange={(e) => setPosition(e.target.value)} className="cp-input" data-testid="pp-pos">
          <option value="">All positions</option>
          <option value="GK">GK</option>
          <option value="DEF">DEF</option>
          <option value="MID">MID</option>
          <option value="FWD">FWD</option>
        </select>
        <select value={sortBy} onChange={(e) => setSortBy(e.target.value)} className="cp-input" data-testid="pp-sort">
          <option value="season_points">Sort: Total points</option>
          <option value="ppg">Sort: Points / match</option>
          <option value="delta">Sort: Suggested − Current</option>
          <option value="price">Sort: Current price</option>
          <option value="name">Sort: Name (A–Z)</option>
        </select>
        <button onClick={load} disabled={busy} className="cp-btn-primary" data-testid="pp-refresh">{busy ? "Loading…" : "Refresh"}</button>
      </div>

      <div className="cp-surface overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr style={{ color: "var(--cp-text-muted)" }} className="text-xs">
              <th className="text-left p-2">Player</th>
              <th className="text-left">Country</th>
              <th>Pos</th>
              <th className="text-right">Matches</th>
              <th className="text-right">Total Pts</th>
              <th className="text-right">Pts/Match</th>
              <th className="text-right">Current €M</th>
              <th className="text-right">Suggested €M</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {filtered.slice(0, 600).map((r) => {
              const delta = (r.suggested_price || 0) - (r.price || 0);
              return (
                <tr key={r.player_id} className="border-t" style={{ borderColor: "var(--cp-border)" }} data-testid={`pp-row-${r.player_id}`}>
                  <td className="p-2 font-bold">{r.name}</td>
                  <td className="text-xs">{r.team_name || r.country}</td>
                  <td className="text-center">
                    <span className="cp-pill text-[10px] font-bold" style={{ background: "var(--cp-surface-2)" }}>{r.position}</span>
                  </td>
                  <td className="text-right tabular-nums">{r.matches_played}</td>
                  <td className="text-right tabular-nums font-extrabold" style={{ color: (r.season_points || 0) > 0 ? "var(--cp-lime)" : "var(--cp-text-muted)" }}>{r.season_points}</td>
                  <td className="text-right tabular-nums">{r.ppg}</td>
                  <td className="text-right tabular-nums">{(r.price || 0).toFixed(1)}</td>
                  <td className="text-right tabular-nums">
                    <span style={{ color: delta > 0 ? "#22c55e" : delta < 0 ? "#ef4444" : "var(--cp-text)" }}>
                      {(r.suggested_price || 0).toFixed(1)}
                      {Math.abs(delta) >= 0.1 && (
                        <span className="text-[9px] ml-1 opacity-70">
                          ({delta > 0 ? "+" : ""}{delta.toFixed(1)})
                        </span>
                      )}
                    </span>
                  </td>
                  <td className="text-right pr-2">
                    {Math.abs(delta) >= 0.1 ? (
                      <button
                        disabled={savingId === r.player_id}
                        onClick={() => applyPrice(r.player_id, r.suggested_price)}
                        className="text-[11px] underline opacity-80 hover:opacity-100"
                        data-testid={`pp-apply-${r.player_id}`}
                      >
                        {savingId === r.player_id ? "…" : "Apply"}
                      </button>
                    ) : (
                      <span className="text-[10px] opacity-30">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {filtered.length === 0 && !busy && (
          <div className="p-6 text-center text-sm" style={{ color: "var(--cp-text-muted)" }}>No players match the filter.</div>
        )}
        {filtered.length > 600 && (
          <div className="p-3 text-center text-[11px]" style={{ color: "var(--cp-text-muted)" }}>Showing first 600 of {filtered.length}. Narrow with search/filters.</div>
        )}
      </div>
    </div>
  );
}

