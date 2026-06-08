import React, { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import api from "../lib/api";

const STORAGE_KEY = "cp_popup_dismissed_v";

/** Admin-controllable promo / notice modal.
 *  Shown once per popup_notice.version per device. Admin can re-trigger by
 *  bumping the version from the admin panel.
 */
export const PopupNotice = () => {
  const [notice, setNotice] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/site-config");
        const p = data?.popup_notice;
        if (!p || !p.enabled || !p.title) return;
        const version = String(p.version || 1);
        const dismissed = (() => {
          try { return localStorage.getItem(STORAGE_KEY); } catch (_e) { return null; }
        })();
        if (dismissed === version) return;
        // Small delay so it doesn't slam in the user's face on first paint
        setTimeout(() => setNotice(p), 900);
      } catch (_e) { /* ignore — no popup */ }
    })();
  }, []);

  const close = () => {
    try { localStorage.setItem(STORAGE_KEY, String(notice?.version || 1)); } catch (_e) { /* ignore */ }
    setNotice(null);
  };
  const cta = () => {
    close();
    if (notice?.cta_link) {
      // External links open in same tab to mimic Sofascore-style promo
      if (/^https?:\/\//i.test(notice.cta_link)) window.location.href = notice.cta_link;
      else window.location.assign(notice.cta_link);
    }
  };

  if (!notice) return null;
  return createPortal(
    <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4" data-testid="popup-notice-root">
      <div className="absolute inset-0" style={{ background: "rgba(0,0,0,0.7)" }} onClick={close} data-testid="popup-notice-backdrop"/>
      <div
        className="relative w-full max-w-sm rounded-2xl overflow-hidden animate-fade-in"
        style={{ background: "var(--cp-surface)", border: "1px solid var(--cp-border)", boxShadow: "0 24px 64px rgba(0,0,0,0.6)" }}
        data-testid="popup-notice"
      >
        {notice.image_url ? (
          <div className="w-full" style={{ aspectRatio: "16 / 9", background: "var(--cp-surface-2)" }}>
            <img src={notice.image_url} alt="" className="w-full h-full object-cover" data-testid="popup-notice-image"/>
          </div>
        ) : (
          <div
            className="w-full"
            style={{
              aspectRatio: "16 / 9",
              background: "linear-gradient(135deg, var(--cp-forest), color-mix(in oklab, var(--cp-lime) 70%, var(--cp-forest)))",
            }}
          />
        )}
        <button
          onClick={close}
          className="absolute top-2 right-2 rounded-full p-1.5"
          style={{ background: "rgba(0,0,0,0.55)", color: "#fff" }}
          aria-label="Close"
          data-testid="popup-notice-close"
        >
          <X size={14}/>
        </button>
        <div className="p-5 space-y-3">
          <h2 className="text-lg font-extrabold leading-tight" data-testid="popup-notice-title">{notice.title}</h2>
          {notice.body && (
            <p className="text-sm leading-relaxed" style={{ color: "var(--cp-text-muted)" }} data-testid="popup-notice-body">
              {notice.body}
            </p>
          )}
          <div className="flex items-center justify-end gap-2 pt-1">
            <button onClick={close} className="px-3 py-2 text-xs font-bold rounded" style={{ color: "var(--cp-text-muted)" }} data-testid="popup-notice-maybe">
              Maybe later
            </button>
            {notice.cta_text && notice.cta_link && (
              <button
                onClick={cta}
                className="px-4 py-2 text-xs font-extrabold rounded"
                style={{ background: "var(--cp-lime)", color: "var(--cp-forest)" }}
                data-testid="popup-notice-cta"
              >
                {notice.cta_text}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
};

export default PopupNotice;
