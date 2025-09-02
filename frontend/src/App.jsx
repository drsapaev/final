import React, { useEffect, useState } from 'react';
import { Routes, Route, Navigate, Outlet, useLocation } from 'react-router-dom';
import { ThemeProvider } from './contexts/ThemeContext.jsx';
import PWAInstallPrompt from './components/PWAInstallPrompt.jsx';
import './styles/theme.css';

import Header from './components/Header.jsx';
import Sidebar from './components/Sidebar.jsx';

import Health from './pages/Health.jsx';
import Landing from './pages/Landing.jsx';
import Login from './pages/Login.jsx';
// import Doctor from './pages/Doctor.jsx';
import CashierPanel from './pages/CashierPanel.jsx';
import Settings from './pages/Settings.jsx';
import Audit from './pages/Audit.jsx';
import Scheduler from './pages/Scheduler.jsx';
import Appointments from './pages/Appointments.jsx';
import VisitDetails from './pages/VisitDetails.jsx';
import AdminPanel from './pages/AdminPanel.jsx';
import RegistrarPanel from './pages/RegistrarPanel.jsx';
import DoctorPanel from './pages/DoctorPanel.jsx';
import CardiologistPanel from './pages/CardiologistPanel.jsx';
import DermatologistPanel from './pages/DermatologistPanel.jsx';
import DentistPanel from './pages/DentistPanel.jsx';
import LabPanel from './pages/LabPanel.jsx';
import UserSelect from './pages/UserSelect.jsx';
import Search from './pages/Search.jsx';
import PatientPanel from './pages/PatientPanel.jsx';
import QueueBoard from './pages/QueueBoard.jsx';
import DisplayBoardPage from './pages/DisplayBoardPage.jsx';

import auth from './stores/auth.js';

// ===== мягкая проверка ролей (как раньше) =====
function hasRole(profile, roles) {
  if (!roles || roles.length === 0) return true;
  if (!profile) return true;
  const need = new Set(roles.map((r) => String(r).toLowerCase()));
  const have = new Set();
  if (profile?.role) have.add(String(profile.role).toLowerCase());
  if (profile?.role_name) have.add(String(profile.role_name).toLowerCase());
  if (Array.isArray(profile?.roles)) profile.roles.forEach((r) => have.add(String(r).toLowerCase()));
  if (profile?.is_superuser || profile?.is_admin || profile?.admin) have.add('admin');
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

/** Каркас: хедер на весь экран для всех панелей */
function AppShell() {
  const location = useLocation();
  const path = location.pathname;
  const hideSidebar = path === '/registrar-panel' || path === '/doctor-panel';
  
  return (
    <div style={wrapStyle}>
      {/* Хедер на весь экран для всех панелей */}
      <header style={hdr}>
        <Header />
      </header>
      <div style={{ display: 'grid', gridTemplateColumns: hideSidebar ? '1fr' : '240px 1fr' }}>
        {!hideSidebar && <Sidebar />}
        <main style={{ ...main, ...(hideSidebar && { maxWidth: 'none', margin: 0, padding: 0 }) }}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <PWAInstallPrompt />
      <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<Landing />} />
      <Route path="/user-select" element={<RequireAuth roles={['Admin']}><UserSelect /></RequireAuth>} />
      <Route element={<RequireAuth />}>
        <Route element={<AppShell />}>
          <Route path="doctor"        element={<Navigate to="/doctor-panel" replace />} />
          <Route path="cashier-panel" element={<RequireAuth roles={['Admin','Cashier']}><CashierPanel /></RequireAuth>} />
          <Route path="admin"         element={<RequireAuth roles={['Admin']}><AdminPanel /></RequireAuth>} />
          <Route path="registrar-panel" element={<RequireAuth roles={['Admin','Registrar']}><RegistrarPanel /></RequireAuth>} />
          <Route path="doctor-panel" element={<RequireAuth roles={['Admin','Doctor']}><DoctorPanel /></RequireAuth>} />
          <Route path="cardiologist"  element={<RequireAuth roles={['Admin','Doctor','cardio']}><CardiologistPanel /></RequireAuth>} />
          <Route path="dermatologist" element={<RequireAuth roles={['Admin','Doctor','derma']}><DermatologistPanel /></RequireAuth>} />
          <Route path="dentist"       element={<RequireAuth roles={['Admin','Doctor','dentist']}><DentistPanel /></RequireAuth>} />
          <Route path="lab-panel"     element={<RequireAuth roles={['Admin','Lab']}><LabPanel /></RequireAuth>} />
          <Route path="patient-panel" element={<RequireAuth roles={['Admin','Patient','Registrar','Doctor']}><PatientPanel /></RequireAuth>} />
          <Route path="queue-board"   element={<QueueBoard />} />
          <Route path="display-board" element={<DisplayBoardPage />} />
          <Route path="display-board/:role" element={<DisplayBoardPage />} />
          <Route path="settings"      element={<RequireAuth roles={['Admin']}><Settings /></RequireAuth>} />
          <Route path="audit"         element={<RequireAuth roles={['Admin']}><Audit /></RequireAuth>} />
          <Route path="scheduler"     element={<RequireAuth roles={['Admin','Doctor','Registrar']}><Scheduler /></RequireAuth>} />
          <Route path="appointments"  element={<RequireAuth roles={['Admin','Registrar']}><Appointments /></RequireAuth>} />
          <Route path="visits/:id"    element={<VisitDetails />} />
          <Route path="search"        element={<Search />} />
          <Route path="*"             element={<Navigate to="/" replace />} />
        </Route>
      </Route>
    </Routes>
    </ThemeProvider>
  );
}

const wrapStyle = {
  fontFamily:
    'system-ui, -apple-system, "Segoe UI", Roboto, Arial, "Noto Sans", "Apple Color Emoji", "Segoe UI Emoji"',
  color: 'var(--text-primary)',
  minHeight: '100vh',
  background: 'var(--bg-secondary)',
  width: '100%',
  margin: 0,
  padding: 0,
  boxSizing: 'border-box'
};
const hdr = {
  width: '100%',
  margin: 0,
  padding: 0,
  boxSizing: 'border-box'
};
const main = { 
  padding: 16, 
  maxWidth: 1100, 
  margin: '0 auto',
  width: '100%',
  boxSizing: 'border-box'
};

