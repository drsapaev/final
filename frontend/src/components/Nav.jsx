import React, { useEffect, useState } from "react";
import { auth } from "../stores/auth.js";
import RoleGate from "./RoleGate.jsx";

export default function Nav({ active = "Health", onNavigate = () => {} }) {
  const [st, setSt] = useState(auth.getState());
  useEffect(() => auth.subscribe(setSt), []);

  const user = st.user;
  const role = user?.role || "Guest";

  const items = [
    { key: "Health", label: "Health", roles: ["Admin","Registrar","Doctor","Lab","Cashier","User"] },
    { key: "Registrar", label: "Регистратура", roles: ["Admin","Registrar"] },
    { key: "Doctor", label: "Врач", roles: ["Admin","Doctor"] },
    { key: "Lab", label: "Лаборатория", roles: ["Admin","Lab"] },
    { key: "Cashier", label: "Касса", roles: ["Admin","Cashier"] },
    { key: "Scheduler", label: "Расписание", roles: ["Admin","Registrar","Doctor"] },
    { key: "Audit", label: "Аудит", roles: ["Admin"] },
    { key: "Activation", label: "Activation", roles: ["Admin"] }, // NEW
    { key: "Settings", label: "Настройки", roles: ["Admin"] },
  ];

  function Button({ item }) {
    const isActive = active === item.key;
    const style = {
      padding: "8px 12px",
      borderRadius: 10,
      border: "1px solid #ddd",
      marginRight: 6,
      cursor: "pointer",
      background: isActive ? "#111" : "#fff",
      color: isActive ? "#fff" : "#111",
    };
    return <button style={style} onClick={() => onNavigate(item.key)}>{item.label}</button>;
  }

  const barStyle = { display: "flex", alignItems: "center", gap: 8, padding: 12, borderBottom: "1px solid #eee", background: "#fafafa", position: "sticky", top: 0, zIndex: 10 };

  return (
    <div style={barStyle}>
      <div style={{ fontWeight: 700, marginRight: 12 }}>Clinic Queue Manager</div>

      <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 6 }}>
        {items.map((it) => (
          <RoleGate key={it.key} roles={it.roles}>
            <Button item={it} />
          </RoleGate>
        ))}
      </div>

      <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
        {user ? (
          <>
            <span style={{ opacity: 0.8 }}>{user.full_name || user.username} · {role}</span>
            <button
              onClick={() => { auth.logout(); onNavigate("Login"); }}
              style={{ padding: "6px 10px", borderRadius: 8, border: "1px solid #ddd", background: "#fff" }}
            >Выйти</button>
          </>
        ) : (
          <button
            onClick={() => onNavigate("Login")}
            style={{ padding: "6px 10px", borderRadius: 8, border: "1px solid #ddd", background: "#fff" }}
          >Войти</button>
        )}
      </div>
    </div>
  );
}