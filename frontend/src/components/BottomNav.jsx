import React from "react";
import { NavLink } from "react-router-dom";
import { Home, Trophy, Target, ShieldCheck, User } from "lucide-react";
import { useAuth } from "../lib/auth";

const ITEMS = [
  { to: "/", label: "Scores", icon: Home, end: true, testid: "bn-scores" },
  { to: "/worldcup", label: "WC 2026", icon: Trophy, testid: "bn-wc" },
  { to: "/predictions", label: "Predict", icon: Target, testid: "bn-predict" },
  { to: "/fantasy", label: "Fantasy", icon: ShieldCheck, testid: "bn-fantasy" },
];

export const BottomNav = () => {
  const { user } = useAuth();
  return (
    <nav
      className="lg:hidden fixed bottom-0 left-0 right-0 z-40"
      style={{ background: "var(--cp-surface)", borderTop: "1px solid var(--cp-border)" }}
      data-testid="bottom-nav"
    >
      <div className="grid grid-cols-5 max-w-screen-sm mx-auto">
        {ITEMS.map(({ to, label, icon: Icon, end, testid }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex flex-col items-center justify-center py-2 text-[10px] font-semibold tracking-wide gap-0.5 ${
                isActive ? "text-cp-lime" : ""
              }`
            }
            style={({ isActive }) => (isActive ? {} : { color: "var(--cp-text-muted)" })}
            data-testid={testid}
          >
            <Icon size={20} />
            <span>{label}</span>
          </NavLink>
        ))}
        <NavLink
          to={user ? "/profile" : "/signin"}
          className={({ isActive }) =>
            `flex flex-col items-center justify-center py-2 text-[10px] font-semibold tracking-wide gap-0.5 ${
              isActive ? "text-cp-lime" : ""
            }`
          }
          style={({ isActive }) => (isActive ? {} : { color: "var(--cp-text-muted)" })}
          data-testid="bn-profile"
        >
          {user ? (
            <span className="cp-logo-circle" style={{ width: 22, height: 22, fontSize: 11 }}>
              {(user.display_name || user.email || "U").slice(0, 1).toUpperCase()}
            </span>
          ) : (
            <User size={20} />
          )}
          <span>{user ? "Me" : "Sign in"}</span>
        </NavLink>
      </div>
    </nav>
  );
};

export default BottomNav;
