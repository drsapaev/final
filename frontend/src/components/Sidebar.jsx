import React from "react";
import { NavLink } from "react-router-dom";
import auth from "../stores/auth.js";

const item = {
  display: "block",
  padding: "8px 10px",
  borderRadius: 8,
  color: "#111",
  textDecoration: "none",
};

export default function Sidebar() {
  const st = auth.getState();
  const profile = st.profile || st.user || {};
  const role = String(profile?.role || profile?.role_name || "").toLowerCase();

  const common = [];

  const byRole = [];
  if (role === "admin") {
    byRole.push(
      { to: "/admin", label: "Админ" },
      { to: "/user-select", label: "Пользователи" },
    );
  }
  if (role === "registrar") {
    byRole.push(
      { to: "/registrar-panel", label: "Панель регистратора" }
    );
  }
  if (role === "doctor") {
    byRole.push(
      { to: "/doctor", label: "Врач" },
      { to: "/doctor-panel", label: "Панель врача" }
    );
  }
  if (role === "lab") {
    byRole.push({ to: "/lab-panel", label: "Лаборатория" });
  }
  if (role === "cashier") {
    byRole.push({ to: "/cashier", label: "Касса" });
  }

  const items = [...byRole, ...common];

  return (
    <aside style={{ width: 240, borderRight: "1px solid #e5e7eb", padding: 12, background: "#fff" }}>
      <div style={{ display: 'grid', gap: 6 }}>
        {items.map(x => (
          <NavLink
            key={x.to}
            to={x.to}
            style={({ isActive }) => ({
              ...item,
              background: isActive ? "#111" : "#fff",
              color: isActive ? "#fff" : "#111",
            })}
          >
            {x.label}
          </NavLink>
        ))}
      </div>
    </aside>
  );
}
