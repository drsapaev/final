import React, { useEffect, useState } from "react";
import { NavLink, useNavigate, useLocation } from "react-router-dom";
import auth, { setProfile } from "../stores/auth.js";
import RoleGate from "./RoleGate.jsx";

export default function Nav() {
  const [st, setSt] = useState(auth.getState());
  const navigate = useNavigate();
  const { pathname } = useLocation();

  useEffect(() => {
    const unsub = auth.subscribe(setSt);
    return () => unsub();
  }, []);

  const user = st.profile || st.user || null;
  const role = user?.role || "Guest";

  // Маршруты приложения — при необходимости синхронизируй с src/App.jsx
  const routes = [
    { key: "Health",     to: "/health",      label: "Health",       roles: ["Admin","Registrar","Doctor","Lab","Cashier","User"] },
    { key: "Registrar",  to: "/registrar",   label: "Регистратура", roles: ["Admin","Registrar"] },
    { key: "Doctor",     to: "/doctor",      label: "Врач",         roles: ["Admin","Doctor"] },
    { key: "Lab",        to: "/lab",         label: "Лаборатория",  roles: ["Admin","Lab"] },
    { key: "Cashier",    to: "/cashier",     label: "Касса",        roles: ["Admin","Cashier"] },
    { key: "Scheduler",  to: "/scheduler",   label: "Расписание",   roles: ["Admin","Registrar","Doctor"] },
    { key: "Audit",      to: "/audit",       label: "Аудит",        roles: ["Admin"] },
    { key: "Activation", to: "/activation",  label: "Activation",   roles: ["Admin"] },
    { key: "Settings",   to: "/settings",    label: "Настройки",    roles: ["Admin"] },
  ];

  const barStyle = {
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: 12,
    borderBottom: "1px solid #eee",
    background: "#fafafa",
    position: "sticky",
    top: 0,
    zIndex: 10,
  };

  const linkBase = {
    padding: "8px 12px",
    borderRadius: 10,
    border: "1px solid #ddd",
    marginRight: 6,
    textDecoration: "none",
  };

  return (
    <div style={barStyle}>
      {/* Заголовок приложения вынесён в AppShell — чтобы не дублировать */}
      <div style={{ fontWeight: 700, marginRight: 12, opacity: 0.85 }} aria-hidden="true"> </div>

      <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 6 }}>
        {routes.map((it) => (
          <RoleGate key={it.key} roles={it.roles}>
            <NavLink
              to={it.to}
              style={({ isActive }) => ({
                ...linkBase,
                background: isActive ? "#111" : "#fff",
                color: isActive ? "#fff" : "#111",
              })}
              aria-current={pathname === it.to ? "page" : undefined}
            >
              {it.label}
            </NavLink>
          </RoleGate>
        ))}
      </div>

      <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
        {user ? (
          <>
            <span style={{ opacity: 0.8 }}>
              {user.full_name || user.username || "Пользователь"} · {role}
            </span>
            <button
              onClick={() => {
                auth.clearToken();
                setProfile(null);
                navigate("/login");
              }}
              style={{ padding: "6px 10px", borderRadius: 8, border: "1px solid #ddd", background: "#fff", cursor: "pointer" }}
            >
              Выйти
            </button>
          </>
        ) : (
          <button
            onClick={() => navigate("/login")}
            style={{ padding: "6px 10px", borderRadius: 8, border: "1px solid #ddd", background: "#fff", cursor: "pointer" }}
          >
            Войти
          </button>
        )}
      </div>
    </div>
  );
}
