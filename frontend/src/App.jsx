import React, { useEffect, useState } from "react";
import Nav from "./components/Nav.jsx";
import RoleGate from "./components/RoleGate.jsx";

// Pages
import Health from "./pages/Health.jsx";
import Login from "./pages/Login.jsx";
import Registrar from "./pages/Registrar.jsx";
import Doctor from "./pages/Doctor.jsx";
import Lab from "./pages/Lab.jsx";
import Cashier from "./pages/Cashier.jsx";
import Settings from "./pages/Settings.jsx";
import Audit from "./pages/Audit.jsx";
import Scheduler from "./pages/Scheduler.jsx";
import Appointments from "./pages/Appointments.jsx";

import { subscribe, getToken, clearToken, getProfile } from "./stores/auth";

const PAGES = [
  "Health",
  "Registrar",
  "Doctor",
  "Lab",
  "Cashier",
  "Settings",
  "Audit",
  "Scheduler",
  "Appointments",
];

export default function App() {
  const [auth, setAuth] = useState({ token: getToken(), profile: getProfile() });
  const [active, setActive] = useState("Health");

  useEffect(() => {
    const unsub = subscribe((st) => setAuth({ token: st.token, profile: st.profile }));
    return () => unsub();
  }, []);

  if (!auth.token) {
    return wrap(<Login />);
  }

  const page = (() => {
    switch (active) {
      case "Health":
        return <Health />;
      case "Registrar":
        return (
          <RoleGate allow={["Admin", "Registrar"]}>
            <Registrar />
          </RoleGate>
        );
      case "Doctor":
        return (
          <RoleGate allow={["Admin", "Doctor"]}>
            <Doctor />
          </RoleGate>
        );
      case "Lab":
        return (
          <RoleGate allow={["Admin", "Lab"]}>
            <Lab />
          </RoleGate>
        );
      case "Cashier":
        return (
          <RoleGate allow={["Admin", "Cashier"]}>
            <Cashier />
          </RoleGate>
        );
      case "Settings":
        return (
          <RoleGate allow={["Admin"]}>
            <Settings />
          </RoleGate>
        );
      case "Audit":
        return (
          <RoleGate allow={["Admin"]}>
            <Audit />
          </RoleGate>
        );
      case "Scheduler":
        return (
          <RoleGate allow={["Admin", "Doctor", "Registrar"]}>
            <Scheduler />
          </RoleGate>
        );
      case "Appointments":
        return (
          <RoleGate allow={["Admin", "Registrar"]}>
            <Appointments />
          </RoleGate>
        );
      default:
        return <Health />;
    }
  })();

  const profile = auth.profile || {};

  return wrap(
    <>
      <header style={hdr}>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <div style={brand}>Clinic Queue Manager</div>
          <Nav pages={PAGES} active={active} onSelect={setActive} />
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <div style={{ fontSize: 13, opacity: 0.8 }}>
            {profile.full_name || profile.username || "—"} • {profile.role || "User"}
          </div>
          <button onClick={clearToken} style={btn}>Выйти</button>
        </div>
      </header>
      <main style={main}>{page}</main>
    </>
  );
}

function wrap(children) {
  return <div style={wrapStyle}>{children}</div>;
}

const wrapStyle = {
  fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, Arial, "Noto Sans", "Apple Color Emoji", "Segoe UI Emoji"',
  color: "#0f172a",
  minHeight: "100vh",
  background: "#f8fafc",
};

const hdr = {
  display: "flex",
  justifyContent: "space-between",
  gap: 12,
  padding: "10px 12px",
  borderBottom: "1px solid #e5e7eb",
  position: "sticky",
  top: 0,
  background: "white",
};

const brand = { fontWeight: 800, fontSize: 18, marginRight: 8 };

const main = { padding: 16, maxWidth: 1100, margin: "0 auto" };

const btn = { padding: "6px 10px", borderRadius: 6, border: "1px solid #e5e7eb", background: "white", cursor: "pointer" };