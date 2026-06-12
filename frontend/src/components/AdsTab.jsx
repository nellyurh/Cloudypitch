import React, { useEffect, useState } from "react";
import api from "../lib/api";
import { Plus, Trash2, Eye, MousePointerClick, ToggleLeft, ToggleRight, Pencil, Save } from "lucide-react";

const PLACEMENTS = [
  { key: "header_banner", label: "Header banner (under sports tabs)" },
  { key: "wc_hub_top", label: "World Cup hub — above hero" },
  { key: "sidebar_right", label: "Right rail sticky (300×250)" },
  { key: "leaderboard_above", label: "Above WC leaderboard widget" },
  { key: "match_list_inline", label: "Between match cards" },
  { key: "predictions_inline", label: "Between prediction rows" },
  { key: "fantasy_sidebar", label: "Fantasy / Build-team sidebar" },
  { key: "mobile_bottom", label: "Mobile sticky bottom bar" },
  { key: "home_bottom_banner", label: "Home bottom banner" },
  { key: "wc_hub_sponsor", label: "WC hub mid-card sponsor" },
  { key: "pool_sponsor", label: "Prize-pool sponsor strip" },
  { key: "interstitial_nav", label: "Interstitial (route change)" },
];

const empty = {
  placement_key: "header_banner",
  network: "direct",
  is_active: true,
  sponsor_name: "",
  sponsor_image_url: "",
  target_url: "",
  starts_at: "",
  ends_at: "",
  weight: 1,
};

export const AdsTab = ({ onMessage }) => {
  const [ads, setAds] = useState([]);
  const [draft, setDraft] = useState(empty);
  const [editingId, setEditingId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [adSenseSlots, setAdSenseSlots] = useState([]);
  const [adSenseDraft, setAdSenseDraft] = useState({ placement_key: "header_banner", ad_slot: "" });
  const [publisherId, setPublisherId] = useState("");

  const load = async () => {
    try {
      const [a1, a2] = await Promise.all([
        api.get("/ads/placements"),
        api.get("/ads/adsense-slots"),
      ]);
      setAds(a1.data.placements || []);
      setAdSenseSlots(a2.data.slots || []);
      setPublisherId(a2.data.publisher_id || "");
    } catch (e) {
      onMessage?.(`✗ ${e?.response?.data?.detail || e.message}`);
    }
  };
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [a1, a2] = await Promise.all([
          api.get("/ads/placements"),
          api.get("/ads/adsense-slots"),
        ]);
        if (cancelled) return;
        setAds(a1.data.placements || []);
        setAdSenseSlots(a2.data.slots || []);
        setPublisherId(a2.data.publisher_id || "");
      } catch (_e) { /* ignore */ }
    })();
    return () => { cancelled = true; };
  }, []);

  const submit = async (e) => {
    e?.preventDefault?.();
    setBusy(true);
    try {
      const payload = {
        ...draft,
        weight: Number(draft.weight) || 1,
        starts_at: draft.starts_at || null,
        ends_at: draft.ends_at || null,
      };
      if (editingId) {
        await api.patch(`/ads/placements/${editingId}`, payload);
        onMessage?.("✓ Ad updated");
      } else {
        await api.post("/ads/placements", payload);
        onMessage?.("✓ Ad created");
      }
      setDraft(empty); setEditingId(null);
      load();
    } catch (e2) {
      onMessage?.(`✗ ${e2?.response?.data?.detail || e2.message}`);
    }
    setBusy(false);
  };

  const startEdit = (ad) => {
    setEditingId(ad.id);
    setDraft({
      placement_key: ad.placement_key, network: ad.network, is_active: ad.is_active,
      sponsor_name: ad.sponsor_name || "", sponsor_image_url: ad.sponsor_image_url || "",
      target_url: ad.target_url || "", starts_at: ad.starts_at || "", ends_at: ad.ends_at || "",
      weight: ad.weight || 1,
    });
  };

  const toggleActive = async (ad) => {
    try {
      await api.patch(`/ads/placements/${ad.id}`, { ...ad, is_active: !ad.is_active });
      load();
    } catch (e) { onMessage?.(`✗ ${e?.response?.data?.detail || e.message}`); }
  };

  const remove = async (ad) => {
    if (!window.confirm(`Delete ad "${ad.sponsor_name || ad.placement_key}"?`)) return;
    try { await api.delete(`/ads/placements/${ad.id}`); load(); }
    catch (e) { onMessage?.(`✗ ${e?.response?.data?.detail || e.message}`); }
  };

  const saveSlot = async (e) => {
    e?.preventDefault?.();
    if (!adSenseDraft.ad_slot) return;
    try {
      await api.post("/ads/adsense-slots", adSenseDraft);
      onMessage?.("✓ AdSense slot saved");
      setAdSenseDraft({ placement_key: "header_banner", ad_slot: "" });
      load();
    } catch (e2) { onMessage?.(`✗ ${e2?.response?.data?.detail || e2.message}`); }
  };
  const removeSlot = async (placement_key) => {
    try { await api.delete(`/ads/adsense-slots/${placement_key}`); load(); }
    catch (e) { onMessage?.(`✗ ${e?.response?.data?.detail || e.message}`); }
  };

  return (
    <div className="space-y-4 max-w-5xl" data-testid="admin-ads">
      {/* AdSense status */}
      <div className="cp-surface p-4" data-testid="adsense-status">
        <h2 className="font-extrabold mb-1">Google AdSense</h2>
        <div className="text-[11px] opacity-60 mb-2">
          Publisher: <code className="text-cp-lime">{publisherId || "(not configured — set ADSENSE_PUBLISHER_ID in backend env)"}</code>
        </div>
        <div className="text-[11px] opacity-60 mb-3">
          Auto Ads fill any placement with no direct sponsor. To pin a <b>specific</b> AdSense slot to a placement, paste a slot ID below.
        </div>
        <form onSubmit={saveSlot} className="flex flex-wrap items-end gap-2">
          <div>
            <label className="text-[10px] uppercase tracking-widest opacity-60 block">Placement</label>
            <select className="cp-input text-sm" value={adSenseDraft.placement_key} onChange={e => setAdSenseDraft(s => ({ ...s, placement_key: e.target.value }))} data-testid="adsense-placement">
              {PLACEMENTS.map(p => <option key={p.key} value={p.key}>{p.label}</option>)}
            </select>
          </div>
          <div>
            <label className="text-[10px] uppercase tracking-widest opacity-60 block">Ad slot ID</label>
            <input className="cp-input text-sm w-40" placeholder="e.g. 1234567890" value={adSenseDraft.ad_slot} onChange={e => setAdSenseDraft(s => ({ ...s, ad_slot: e.target.value }))} data-testid="adsense-slot"/>
          </div>
          <button className="cp-btn-primary !py-2" type="submit" data-testid="adsense-save"><Save size={14}/> Save slot</button>
        </form>
        {adSenseSlots.length > 0 && (
          <div className="mt-3 text-xs">
            <div className="opacity-60 mb-1">Configured slots:</div>
            <ul className="space-y-1">
              {adSenseSlots.map(s => (
                <li key={s.placement_key} className="flex items-center gap-2">
                  <code className="text-cp-lime">{s.placement_key}</code>
                  <code className="opacity-70">slot {s.ad_slot}</code>
                  <button onClick={() => removeSlot(s.placement_key)} className="text-rose-400 hover:underline ml-auto"><Trash2 size={12}/></button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Direct sponsor form */}
      <div className="cp-surface p-4">
        <h2 className="font-extrabold mb-3 flex items-center gap-2">
          <Plus size={16} className="text-cp-lime"/> {editingId ? "Edit sponsor ad" : "Create sponsor ad"}
        </h2>
        <form onSubmit={submit} className="grid grid-cols-1 md:grid-cols-2 gap-2" data-testid="ads-form">
          <div className="md:col-span-2">
            <label className="text-[10px] uppercase tracking-widest opacity-60 block">Placement</label>
            <select className="cp-input text-sm w-full" value={draft.placement_key} onChange={e => setDraft({ ...draft, placement_key: e.target.value })} data-testid="ad-placement">
              {PLACEMENTS.map(p => <option key={p.key} value={p.key}>{p.label}</option>)}
            </select>
          </div>
          <input className="cp-input text-sm" placeholder="Sponsor name (e.g. Acme Corp)" value={draft.sponsor_name} onChange={e => setDraft({ ...draft, sponsor_name: e.target.value })} data-testid="ad-sponsor"/>
          <input className="cp-input text-sm" type="number" min="1" max="10" placeholder="Rotation weight (1–10)" value={draft.weight} onChange={e => setDraft({ ...draft, weight: e.target.value })} data-testid="ad-weight"/>
          <input className="cp-input text-sm md:col-span-2" placeholder="Image URL (1200×120 banner recommended)" value={draft.sponsor_image_url} onChange={e => setDraft({ ...draft, sponsor_image_url: e.target.value })} data-testid="ad-image"/>
          <input className="cp-input text-sm md:col-span-2" placeholder="Click-through URL" value={draft.target_url} onChange={e => setDraft({ ...draft, target_url: e.target.value })} data-testid="ad-link"/>
          <input className="cp-input text-sm" type="datetime-local" value={draft.starts_at?.slice(0, 16) || ""} onChange={e => setDraft({ ...draft, starts_at: e.target.value ? `${e.target.value}:00Z` : "" })} data-testid="ad-starts"/>
          <input className="cp-input text-sm" type="datetime-local" value={draft.ends_at?.slice(0, 16) || ""} onChange={e => setDraft({ ...draft, ends_at: e.target.value ? `${e.target.value}:00Z` : "" })} data-testid="ad-ends"/>
          <label className="text-xs font-bold inline-flex items-center gap-2 cursor-pointer md:col-span-2">
            <input type="checkbox" checked={draft.is_active} onChange={e => setDraft({ ...draft, is_active: e.target.checked })} data-testid="ad-active"/>
            Active immediately (uncheck to draft)
          </label>
          <div className="md:col-span-2 flex gap-2">
            <button type="submit" disabled={busy} className="cp-btn-primary disabled:opacity-50" data-testid="ad-submit">
              {busy ? "Saving…" : editingId ? "Update ad" : "Create ad"}
            </button>
            {editingId && (
              <button type="button" onClick={() => { setEditingId(null); setDraft(empty); }} className="cp-btn-ghost">Cancel</button>
            )}
          </div>
        </form>
      </div>

      {/* Existing ads table */}
      <div className="cp-surface overflow-x-auto">
        <table className="w-full text-xs" data-testid="ads-table">
          <thead>
            <tr style={{ background: "var(--cp-surface-2)" }}>
              <th className="px-3 py-2 text-left">Sponsor</th>
              <th className="px-3 py-2 text-left">Placement</th>
              <th className="px-3 py-2">Weight</th>
              <th className="px-3 py-2"><Eye size={12} className="inline"/></th>
              <th className="px-3 py-2"><MousePointerClick size={12} className="inline"/></th>
              <th className="px-3 py-2">Window</th>
              <th className="px-3 py-2">Active</th>
              <th className="px-3 py-2 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {ads.length === 0 && (
              <tr><td colSpan={8} className="px-3 py-4 text-center" style={{ color: "var(--cp-text-muted)" }}>No sponsor ads yet — create one above. AdSense Auto Ads will keep filling slots in the meantime.</td></tr>
            )}
            {ads.map(ad => (
              <tr key={ad.id} className="border-t" style={{ borderColor: "var(--cp-border)" }} data-testid={`ad-row-${ad.id}`}>
                <td className="px-3 py-2 font-bold">{ad.sponsor_name || "—"}</td>
                <td className="px-3 py-2"><code className="text-cp-lime">{ad.placement_key}</code></td>
                <td className="px-3 py-2 text-center tabular-nums">{ad.weight || 1}</td>
                <td className="px-3 py-2 text-center tabular-nums">{ad.impressions || 0}</td>
                <td className="px-3 py-2 text-center tabular-nums">{ad.clicks || 0}</td>
                <td className="px-3 py-2 text-[10px] opacity-60">
                  {(ad.starts_at || "—").slice(0, 10)} → {(ad.ends_at || "∞").slice(0, 10)}
                </td>
                <td className="px-3 py-2 text-center">
                  <button onClick={() => toggleActive(ad)} className="hover:scale-110 transition" data-testid={`ad-toggle-${ad.id}`}>
                    {ad.is_active ? <ToggleRight size={20} className="text-cp-lime"/> : <ToggleLeft size={20} className="opacity-50"/>}
                  </button>
                </td>
                <td className="px-3 py-2 text-right">
                  <button onClick={() => startEdit(ad)} className="cp-btn-ghost !p-1.5 mr-1" title="Edit" data-testid={`ad-edit-${ad.id}`}><Pencil size={12}/></button>
                  <button onClick={() => remove(ad)} className="cp-btn-ghost !p-1.5 text-rose-400" title="Delete" data-testid={`ad-delete-${ad.id}`}><Trash2 size={12}/></button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <PropellerZonesPanel onMessage={onMessage}/>
    </div>
  );
};

// ─── PropellerAds zone manager ──────────────────────────────────────────
const PropellerZonesPanel = ({ onMessage }) => {
  const [rows, setRows] = useState([]);
  const [draft, setDraft] = useState({
    placement_key: "header_banner",
    zone_id: "",
    snippet_html: "",
    width: 300,
    height: 250,
    format: "banner",
    is_active: true,
  });
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      const { data } = await api.get("/ads/propellerads-zones");
      setRows(data.zones || []);
    } catch (e) { onMessage?.(e?.response?.data?.detail || "Failed to load Propeller zones"); }
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  const save = async () => {
    setBusy(true);
    try {
      await api.post("/ads/propellerads-zones", draft);
      onMessage?.(`✓ Saved ${draft.placement_key} (${draft.format})`);
      load();
    } catch (e) { onMessage?.(e?.response?.data?.detail || "Save failed"); }
    setBusy(false);
  };

  const remove = async (z) => {
    if (!confirm(`Delete Propeller zone for ${z.placement_key} (${z.format})?`)) return;
    try {
      await api.delete(`/ads/propellerads-zones/${z.placement_key}?format=${z.format}`);
      onMessage?.("✓ Deleted");
      load();
    } catch (e) { onMessage?.(e?.response?.data?.detail || "Delete failed"); }
  };

  return (
    <div className="cp-surface p-4 mt-4" data-testid="propeller-zones-panel">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div>
          <h3 className="font-extrabold flex items-center gap-2">🛰 PropellerAds zones</h3>
          <div className="text-[11px]" style={{ color: "var(--cp-text-muted)" }}>
            Paste the full snippet PropellerAds gives you per zone (the <code>&lt;script&gt;...&lt;/script&gt;</code> block). Without the snippet, nothing renders.
          </div>
        </div>
      </div>

      <PropellerSiteVerification onMessage={onMessage}/>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2 mb-3">
        <select value={draft.placement_key} onChange={(e) => setDraft({...draft, placement_key: e.target.value})} className="cp-input" data-testid="pa-placement">
          {PLACEMENTS.map((p) => <option key={p.key} value={p.key}>{p.label}</option>)}
        </select>
        <select value={draft.format} onChange={(e) => setDraft({...draft, format: e.target.value})} className="cp-input" data-testid="pa-format">
          <option value="banner">Banner (inline)</option>
          <option value="popunder">Popunder (interstitial)</option>
          <option value="push">Push notification</option>
          <option value="native">Native</option>
        </select>
        <input value={draft.zone_id} onChange={(e) => setDraft({...draft, zone_id: e.target.value})} placeholder="Zone ID (e.g. 29626230)" className="cp-input" data-testid="pa-zone-id"/>
        <input type="number" value={draft.width} onChange={(e) => setDraft({...draft, width: parseInt(e.target.value) || 0})} placeholder="Width" className="cp-input" data-testid="pa-width"/>
        <input type="number" value={draft.height} onChange={(e) => setDraft({...draft, height: parseInt(e.target.value) || 0})} placeholder="Height" className="cp-input" data-testid="pa-height"/>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={draft.is_active} onChange={(e) => setDraft({...draft, is_active: e.target.checked})} data-testid="pa-active"/> Active
        </label>
      </div>
      <textarea
        value={draft.snippet_html}
        onChange={(e) => setDraft({...draft, snippet_html: e.target.value})}
        rows={4}
        placeholder='Paste full PropellerAds snippet here, e.g.&#10;<script async data-cfasync="false" src="//pl12345.profitablerate.com/invoke.js"></script>&#10;<div id="container-xxx"></div>'
        className="cp-input w-full font-mono text-[11px]"
        data-testid="pa-snippet"
      />
      <div className="flex items-center gap-2 mt-2">
        <button onClick={save} disabled={busy} className="cp-btn-primary" data-testid="pa-save">{busy ? "Saving…" : "Save / upsert"}</button>
      </div>

      <table className="w-full text-sm mt-4">
        <thead>
          <tr style={{ color: "var(--cp-text-muted)" }} className="text-xs">
            <th className="text-left p-2">Placement</th>
            <th>Format</th>
            <th>Zone</th>
            <th>Size</th>
            <th>Snippet?</th>
            <th>Active</th>
            <th>Impressions</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((z) => (
            <tr key={`${z.placement_key}-${z.format}`} className="border-t" style={{ borderColor: "var(--cp-border)" }} data-testid={`pa-row-${z.placement_key}-${z.format}`}>
              <td className="p-2 text-xs">{z.placement_key}</td>
              <td className="text-center text-xs">{z.format}</td>
              <td className="text-center tabular-nums text-xs">{z.zone_id || "—"}</td>
              <td className="text-center text-xs">{z.width}×{z.height}</td>
              <td className="text-center">{z.snippet_html ? "✓" : "—"}</td>
              <td className="text-center">{z.is_active ? "✓" : "✗"}</td>
              <td className="text-center tabular-nums text-xs">{z.impressions || 0}</td>
              <td className="text-right pr-2">
                <button onClick={() => setDraft(z)} className="text-[11px] underline opacity-80 hover:opacity-100 mr-2" data-testid={`pa-edit-${z.placement_key}-${z.format}`}>Edit</button>
                <button onClick={() => remove(z)} className="text-[11px] text-rose-400 underline opacity-80 hover:opacity-100" data-testid={`pa-del-${z.placement_key}-${z.format}`}>Delete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length === 0 && (
        <div className="p-4 text-center text-xs" style={{ color: "var(--cp-text-muted)" }}>No Propeller zones configured yet.</div>
      )}
    </div>
  );
};

// ─── Site-level verification (Multitag) ─────────────────────────────────
const PropellerSiteVerification = ({ onMessage }) => {
  const [head, setHead] = useState("");
  const [files, setFiles] = useState([]);
  const [fname, setFname] = useState("");
  const [fcontent, setFcontent] = useState("");
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      const { data } = await api.get("/ads/propellerads-site");
      setHead(data.verification_head || "");
      setFiles(data.verification_files || []);
    } catch (_e) { /* may not exist yet */ }
  };
  useEffect(() => { load(); }, []);

  const saveHead = async () => {
    setBusy(true);
    try {
      await api.post("/ads/propellerads-site", { verification_head: head });
      onMessage?.("✓ Verification snippet saved — now click Verify on PropellerAds");
    } catch (e) { onMessage?.(e?.response?.data?.detail || "Save failed"); }
    setBusy(false);
  };

  const saveFile = async () => {
    if (!fname || !fcontent) { onMessage?.("Filename and content are required"); return; }
    setBusy(true);
    try {
      const { data } = await api.post("/ads/propellerads-file", { filename: fname, content: fcontent });
      onMessage?.(`✓ Saved — served at ${window.location.origin}${data.served_at}`);
      setFname(""); setFcontent("");
      load();
    } catch (e) { onMessage?.(e?.response?.data?.detail || "Save failed"); }
    setBusy(false);
  };

  const removeFile = async (fn) => {
    if (!confirm(`Delete verification file /${fn}?`)) return;
    try {
      await api.delete(`/ads/propellerads-file/${fn}`);
      onMessage?.(`✓ Removed /${fn}`);
      load();
    } catch (e) { onMessage?.(e?.response?.data?.detail || "Delete failed"); }
  };

  return (
    <div className="rounded p-3 mb-4 border" style={{ background: "var(--cp-surface-2)", borderColor: "var(--cp-border)" }} data-testid="propeller-site-verify">
      <div className="text-xs font-extrabold mb-1">🔐 PropellerAds Multitag verification</div>
      <div className="text-[10px] mb-2" style={{ color: "var(--cp-text-muted)" }}>
        Use either method PropellerAds lets you pick — both are wired up here.
      </div>

      {/* Method 1: HEAD snippet */}
      <div className="mb-2">
        <div className="text-[10px] font-bold mb-1">A. Paste the meta/script PropellerAds gave you (injected into &lt;head&gt; on every page)</div>
        <textarea
          value={head}
          onChange={(e) => setHead(e.target.value)}
          rows={3}
          placeholder={'<meta name="propeller" content="abc123...">\nor\n<script type="text/javascript">...</script>'}
          className="cp-input w-full font-mono text-[11px]"
          data-testid="pa-verify-head"
        />
        <button onClick={saveHead} disabled={busy} className="cp-btn-primary mt-1" data-testid="pa-verify-head-save">{busy ? "Saving…" : "Save head snippet"}</button>
      </div>

      {/* Method 2: file upload */}
      <div className="mt-3 pt-3 border-t" style={{ borderColor: "var(--cp-border)" }}>
        <div className="text-[10px] font-bold mb-1">B. Upload a verification file (root URL — e.g. /propeller-1234.html)</div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mb-2">
          <input value={fname} onChange={(e) => setFname(e.target.value)} placeholder="filename (e.g. propeller-abc.html)" className="cp-input font-mono text-[11px]" data-testid="pa-verify-file-name"/>
          <button onClick={saveFile} disabled={busy} className="cp-btn-primary" data-testid="pa-verify-file-save">{busy ? "Saving…" : "Save & serve at /filename"}</button>
        </div>
        <textarea
          value={fcontent}
          onChange={(e) => setFcontent(e.target.value)}
          rows={3}
          placeholder="Paste the exact body content PropellerAds gave you for the file"
          className="cp-input w-full font-mono text-[11px]"
          data-testid="pa-verify-file-content"
        />
        {files.length > 0 && (
          <div className="mt-2 space-y-1">
            {files.map((f) => (
              <div key={f.filename} className="flex items-center justify-between text-[11px] py-1 px-2 rounded" style={{ background: "var(--cp-surface)" }}>
                <a href={`/${f.filename}`} target="_blank" rel="noreferrer" className="font-mono underline" data-testid={`pa-verify-file-link-${f.filename}`}>/{f.filename}</a>
                <button onClick={() => removeFile(f.filename)} className="text-rose-400 underline" data-testid={`pa-verify-file-del-${f.filename}`}>Remove</button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default AdsTab;
