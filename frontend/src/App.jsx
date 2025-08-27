import React, { useEffect, useState } from "react";
import { Routes, Route, Navigate, Outlet, useLocation } from "react-router-dom";

import Nav from "./components/Nav.jsx";

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
import VisitDetails from "./pages/VisitDetails.jsx";

import auth from "./stores/auth.js";

// ===== мягкая проверка ролей (как раньше) =====
function hasRole(profile, roles) {
  if (!roles || roles.length === 0) return true;
  if (!profile) return true;
  const need = new Set(roles.map((r) => String(r).toLowerCase()));
  const have = new Set();
  if (profile?.role) have.add(String(profile.role).toLowerCase());
  if (profile?.role_name) have.add(String(profile.role_name).toLowerCase());
  if (Array.isArray(profile?.roles)) profile.roles.forEach((r) => have.add(String(r).toLowerCase()));
  if (profile?.is_superuser || profile?.is_admin || profile?.admin) have.add("admin");
  for (const n of need) if (have.has(n)) return true;
  if (have.size === 0) return true;
  return false;
}

function RequireAuth({ roles, children }) {
  const [st, setSt] = useState(auth.getState());
  const loc = useLocation();
  useEffect(() => auth.subscribe(setSt), []);
  if (!st.token) return <Navigate to="/login" replace state={{ from: loc }} />;
  if (!hasRole(st.profile, roles)) return <Navigate to="/" replace />;
  return children || <Outlet />;
}

/** Каркас: только Nav, без дублирующего заголовка */
function AppShell() {
  return (
    <div style={wrapStyle}>
      <header style={hdr}>
        <Nav />
      </header>
      <main style={main}>
        <Outlet />
      </main>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<RequireAuth />}>
        <Route element={<AppShell />}>
          <Route index element={<Health />} />
          <Route path="registrar"     element={<RequireAuth roles={["Admin","Registrar"]}><Registrar /></RequireAuth>} />
          <Route path="doctor"        element={<RequireAuth roles={["Admin","Doctor"]}><Doctor /></RequireAuth>} />
          <Route path="lab"           element={<RequireAuth roles={["Admin","Lab"]}><Lab /></RequireAuth>} />
          <Route path="cashier"       element={<RequireAuth roles={["Admin","Cashier"]}><Cashier /></RequireAuth>} />
          <Route path="settings"      element={<RequireAuth roles={["Admin"]}><Settings /></RequireAuth>} />
          <Route path="audit"         element={<RequireAuth roles={["Admin"]}><Audit /></RequireAuth>} />
          <Route path="scheduler"     element={<RequireAuth roles={["Admin","Doctor","Registrar"]}><Scheduler /></RequireAuth>} />
          <Route path="appointments"  element={<RequireAuth roles={["Admin","Registrar"]}><Appointments /></RequireAuth>} />
          <Route path="visits/:id"    element={<VisitDetails />} />
          <Route path="*"             element={<Navigate to="/" replace />} />
        </Route>
      </Route>
    </Routes>
  );
}

const wrapStyle = {
  fontFamily:
    'system-ui, -apple-system, "Segoe UI", Roboto, Arial, "Noto Sans", "Apple Color Emoji", "Segoe UI Emoji"',
  color: "#0f172a",
  minHeight: "100vh",
  background: "#f8fafc",
};
const hdr = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: 12,
  padding: "10px 12px",
  borderBottom: "1px solid #e5e7eb",
  position: "sticky",
  top: 0,
  background: "white",
  zIndex: 10,
};
const main = { padding: 16, maxWidth: 1100, margin: "0 auto" };

