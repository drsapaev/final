import React from "react";
import { getProfile } from "../stores/auth.js";

/**
 * Ограничивает доступ по ролям.
 * Поддерживает оба пропса: `allow` и `roles` (алиасы).
 *
 * Props:
 *  - allow?: string[]
 *  - roles?: string[]        // алиас allow
 *  - fallback?: ReactNode    // что показать при запрете (по умолчанию — предупреждающий бокс)
 *  - children
 */
export default function RoleGate({ allow = [], roles, fallback, children }) {
  const profile = getProfile() || {};
  const role = (profile.role || "").trim();

  const need = Array.isArray(roles) ? roles : allow;
  const ok = !need || need.length === 0 || need.includes(role);

  if (ok) return children;

  if (fallback !== undefined) return fallback;

  return (
    <div style={box}>
      <div style={cap}>Доступ ограничен</div>
      <div>
        Ваша роль: <b>{role || "—"}</b>. Требуется одна из:{" "}
        <code>{(need || []).join(", ")}</code>
      </div>
    </div>
  );
}

const box = {
  border: "1px solid #fecaca",
  background: "#fef2f2",
  color: "#7f1d1d",
  borderRadius: 8,
  padding: 12,
};
const cap = { fontWeight: 700, marginBottom: 6, fontSize: 14 };