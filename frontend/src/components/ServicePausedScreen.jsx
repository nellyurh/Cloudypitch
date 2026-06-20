import React from "react";
import { Link } from "react-router-dom";
import { ShieldAlert, Trophy, ArrowLeft } from "lucide-react";

/* Full-page shutdown screen used when an admin has paused Fantasy or
 * Predictions. Renders the admin-set reason, a short explainer, and a
 * link out to the leaderboard (which is intentionally still live). */
export default function ServicePausedScreen({
  service, // "fantasy" | "predictions"
  reason,
}) {
  const title = service === "predictions" ? "Predictions paused" : "Fantasy paused";
  const leaderboardHref = service === "predictions" ? "/predictions/leaderboard" : "/leaderboard";
  const friendlyReason = (reason || "").trim() ||
    `${title} are temporarily disabled by an admin. Existing points are frozen — they'll resume the moment we reopen.`;

  return (
    <div className="max-w-2xl mx-auto py-10 px-4" data-testid={`service-paused-${service}`}>
      <div
        className="cp-surface p-6 sm:p-8 text-center relative overflow-hidden"
        style={{
          background:
            "radial-gradient(circle at top, rgba(251,191,36,0.10), transparent 60%), var(--cp-surface)",
          border: "1px solid rgba(251,191,36,0.30)",
        }}
      >
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-full mb-4"
             style={{ background: "rgba(251,191,36,0.15)", border: "1px solid rgba(251,191,36,0.40)" }}>
          <ShieldAlert size={28} className="text-amber-400"/>
        </div>

        <div className="text-[10px] font-extrabold uppercase tracking-[0.25em] text-amber-400 mb-2">
          Service paused
        </div>
        <h1 className="text-2xl sm:text-3xl font-extrabold mb-3" data-testid="service-paused-title">
          {title}
        </h1>

        <div
          className="rounded p-4 text-sm mb-5"
          style={{
            background: "var(--cp-surface-2)",
            border: "1px solid var(--cp-border)",
            color: "var(--cp-text)",
          }}
          data-testid="service-paused-reason"
        >
          {friendlyReason}
        </div>

        <p className="text-xs mb-6" style={{ color: "var(--cp-text-muted)" }}>
          No new entries or points can be earned while this is paused.
          Leaderboards continue to show your standings.
        </p>

        <div className="flex flex-wrap justify-center gap-2">
          <Link
            to={leaderboardHref}
            className="cp-btn-primary text-xs inline-flex items-center gap-1.5"
            data-testid="service-paused-leaderboard-link"
          >
            <Trophy size={14}/> View leaderboard
          </Link>
          <Link
            to="/"
            className="cp-btn-ghost text-xs inline-flex items-center gap-1.5"
            data-testid="service-paused-home-link"
          >
            <ArrowLeft size={14}/> Back to home
          </Link>
        </div>
      </div>
    </div>
  );
}
