import React, { useEffect, useState } from 'react';
import { Routes, Route, Navigate, Outlet, useLocation } from 'react-router-dom';
import { AppProviders } from './providers/AppProviders';
import { PWAInstallPrompt, ConnectionStatus } from './components/pwa';
import { usePWA } from './hooks/usePWA.js';
import './styles/theme.css';
import './styles/dark-theme-visibility-fix.css';

// Временно переключаемся на новый хедер (старый оставляем для сравнения)
import HeaderNew from './components/layout/HeaderNew.jsx';
import Sidebar from './components/layout/Sidebar.jsx';

import Health from './pages/Health.jsx';
import Landing from './pages/Landing.jsx';
import Login from './pages/Login.jsx';
import CashierPanel from './pages/CashierPanel.jsx';
import Settings from './pages/Settings.jsx';
import Audit from './pages/Audit.jsx';
import Scheduler from './pages/Scheduler.jsx';
import Appointments from './pages/Appointments.jsx';
import VisitDetails from './pages/VisitDetails.jsx';
import AdminPanel from './pages/AdminPanel.jsx';
import RegistrarPanel from './pages/RegistrarPanel.jsx';
import DoctorPanel from './pages/DoctorPanel.jsx';
import CardiologistPanelUnified from './pages/CardiologistPanelUnified.jsx';
import DermatologistPanelUnified from './pages/DermatologistPanelUnified.jsx';
import DentistPanelUnified from './pages/DentistPanelUnified.jsx';
import LabPanel from './pages/LabPanel.jsx';
import UserSelect from './pages/UserSelect.jsx';
import Search from './pages/Search.jsx';
import PatientPanel from './pages/PatientPanel.jsx';
import DisplayBoardUnified from './pages/DisplayBoardUnified.jsx';
import AnalyticsPage from './pages/AnalyticsPage.jsx';
import MediLabDemo from './pages/MediLabDemo.jsx';
import QueueJoin from './pages/QueueJoin.jsx';
import PaymentSuccess from './pages/PaymentSuccess.jsx';
import PaymentCancel from './pages/PaymentCancel.jsx';
import PaymentTest from './pages/PaymentTest.jsx';

// Новые компоненты - ПОШАГОВОЕ ДОБАВЛЕНИЕ
import TestComponent from './components/TestComponent.jsx';
import SimpleDashboard from './components/dashboard/SimpleDashboard.jsx';
import SimpleUserManagement from './components/admin/SimpleUserManagement.jsx';
import SimpleEMR from './components/medical/SimpleEMR.jsx';
import SimpleFileManager from './components/SimpleFileManager.jsx';
import LoginFormStyled from './components/auth/LoginFormStyled.jsx'; // Стилизованная версия в стиле системы
import NewComponentsNav from './components/NewComponentsNav.jsx'; // Навигация по новым компонентам

// Скрытые компоненты для интеграции
import TelegramManager from './components/TelegramManager.jsx';
import EmailSMSManager from './components/notifications/EmailSMSManager.jsx';
import TwoFactorManager from './components/security/TwoFactorManager.jsx';
import FileManager from './components/files/FileManager.jsx';
import EMRInterface from './components/medical/EMRInterface.jsx';
import UserManagement from './components/admin/UserManagement.jsx';
import IntegrationDemo from './components/integration/IntegrationDemo.jsx';

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
  const hideSidebar = path === '/registrar-panel' || 
                     path === '/doctor-panel' || 
                     path === '/cashier-panel' || 
                     path.startsWith('/admin');
  
  return (
    <div style={wrapStyle}>
      {/* Хедер на весь экран для всех панелей (новая версия) */}
      <header style={hdr}>
        <HeaderNew />
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

// Внутренний компонент с PWA логикой
function AppContent() {
  const { shouldShowInstallPrompt } = usePWA();

  return (
    <>
      <ConnectionStatus />
      {shouldShowInstallPrompt() && <PWAInstallPrompt />}
      <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/new-login" element={<LoginFormStyled />} />
      <Route path="/components" element={<NewComponentsNav />} />
      <Route path="/health" element={<Health />} />
      <Route path="/" element={<Landing />} />
      <Route path="/medilab-demo" element={<MediLabDemo />} />
      <Route path="/medilab-demo/dashboard" element={<MediLabDemo />} />
      <Route path="/medilab-demo/patients" element={<MediLabDemo />} />
      <Route path="/medilab-demo/appointments" element={<MediLabDemo />} />
      <Route path="/medilab-demo/staff-schedule" element={<MediLabDemo />} />
      <Route path="/user-select" element={<RequireAuth roles={['Admin']}><UserSelect /></RequireAuth>} />
      <Route path="/queue/join" element={<QueueJoin />} />
      <Route path="/payment/success" element={<PaymentSuccess />} />
      <Route path="/payment/cancel" element={<PaymentCancel />} />
      <Route path="/payment/test" element={<PaymentTest />} />
      <Route element={<RequireAuth />}>
        <Route element={<AppShell />}>

          <Route path="cashier-panel" element={<RequireAuth roles={['Admin','Cashier']}><CashierPanel /></RequireAuth>} />
          <Route path="admin" element={<RequireAuth roles={['Admin']}><AdminPanel /></RequireAuth>} />
          <Route path="admin/analytics" element={<RequireAuth roles={['Admin']}><AdminPanel /></RequireAuth>} />
          <Route path="admin/users" element={<RequireAuth roles={['Admin']}><AdminPanel /></RequireAuth>} />
          <Route path="admin/doctors" element={<RequireAuth roles={['Admin']}><AdminPanel /></RequireAuth>} />
          <Route path="admin/services" element={<RequireAuth roles={['Admin']}><AdminPanel /></RequireAuth>} />
          <Route path="admin/patients" element={<RequireAuth roles={['Admin']}><AdminPanel /></RequireAuth>} />
          <Route path="admin/appointments" element={<RequireAuth roles={['Admin']}><AdminPanel /></RequireAuth>} />
          <Route path="admin/clinic-management" element={<RequireAuth roles={['Admin']}><AdminPanel /></RequireAuth>} />
          <Route path="admin/clinic-settings" element={<RequireAuth roles={['Admin']}><AdminPanel /></RequireAuth>} />
          <Route path="admin/queue-settings" element={<RequireAuth roles={['Admin']}><AdminPanel /></RequireAuth>} />
          <Route path="admin/ai-settings" element={<RequireAuth roles={['Admin']}><AdminPanel /></RequireAuth>} />
          <Route path="admin/telegram-settings" element={<RequireAuth roles={['Admin']}><AdminPanel /></RequireAuth>} />
          <Route path="admin/display-settings" element={<RequireAuth roles={['Admin']}><AdminPanel /></RequireAuth>} />
          <Route path="admin/activation" element={<RequireAuth roles={['Admin']}><AdminPanel /></RequireAuth>} />
          <Route path="admin/finance" element={<RequireAuth roles={['Admin']}><AdminPanel /></RequireAuth>} />
          <Route path="admin/reports" element={<RequireAuth roles={['Admin']}><AdminPanel /></RequireAuth>} />
          <Route path="admin/settings" element={<RequireAuth roles={['Admin']}><AdminPanel /></RequireAuth>} />
          <Route path="admin/security" element={<RequireAuth roles={['Admin']}><AdminPanel /></RequireAuth>} />
          <Route path="registrar-panel" element={<RequireAuth roles={['Admin','Registrar']}><RegistrarPanel /></RequireAuth>} />
          <Route path="doctor-panel" element={<RequireAuth roles={['Admin','Doctor']}><DoctorPanel /></RequireAuth>} />
          <Route path="cardiologist" element={<RequireAuth roles={['Admin','Doctor','cardio']}><CardiologistPanelUnified /></RequireAuth>} />
          <Route path="dermatologist" element={<RequireAuth roles={['Admin','Doctor','derma']}><DermatologistPanelUnified /></RequireAuth>} />
          <Route path="dentist"       element={<RequireAuth roles={['Admin','Doctor','dentist']}><DentistPanelUnified /></RequireAuth>} />
          <Route path="lab-panel"     element={<RequireAuth roles={['Admin','Lab']}><LabPanel /></RequireAuth>} />
          <Route path="patient-panel" element={<RequireAuth roles={['Admin','Patient','Registrar','Doctor']}><PatientPanel /></RequireAuth>} />
          <Route path="queue-board"   element={<DisplayBoardUnified />} />
          <Route path="display-board" element={<DisplayBoardUnified />} />
          <Route path="display-board/:role" element={<DisplayBoardUnified />} />
          <Route path="settings"      element={<RequireAuth roles={['Admin']}><Settings /></RequireAuth>} />
          <Route path="audit"         element={<RequireAuth roles={['Admin']}><Audit /></RequireAuth>} />
          <Route path="scheduler"     element={<RequireAuth roles={['Admin','Doctor','Registrar']}><Scheduler /></RequireAuth>} />
          <Route path="appointments"  element={<RequireAuth roles={['Admin','Registrar']}><Appointments /></RequireAuth>} />
          <Route path="analytics"     element={<RequireAuth roles={['Admin']}><AnalyticsPage /></RequireAuth>} />
          <Route path="visits/:id"    element={<VisitDetails />} />
          <Route path="search"        element={<Search />} />
          
          {/* Новые маршруты для созданных компонентов - ПОШАГОВОЕ ДОБАВЛЕНИЕ */}
          <Route path="test"           element={<TestComponent />} />
          <Route path="simple-dashboard" element={<SimpleDashboard />} />
          <Route path="simple-users"   element={<SimpleUserManagement />} />
          <Route path="simple-emr"     element={<SimpleEMR />} />
          <Route path="simple-files"   element={<SimpleFileManager />} />
          
          {/* Интегрированные скрытые компоненты */}
          <Route path="advanced-users"     element={<RequireAuth roles={['Admin']}><UserManagement /></RequireAuth>} />
          <Route path="advanced-emr"       element={<RequireAuth roles={['Admin','Doctor','Nurse']}><EMRInterface /></RequireAuth>} />
          <Route path="file-management"    element={<RequireAuth roles={['Admin','Doctor','Nurse']}><FileManager /></RequireAuth>} />
          <Route path="notifications"     element={<RequireAuth roles={['Admin']}><EmailSMSManager /></RequireAuth>} />
          <Route path="telegram-integration" element={<RequireAuth roles={['Admin']}><TelegramManager /></RequireAuth>} />
          <Route path="security-settings" element={<RequireAuth roles={['Admin','Doctor','Nurse']}><TwoFactorManager /></RequireAuth>} />
          
          {/* Демо интеграции */}
          <Route path="integration-demo"   element={<IntegrationDemo />} />
          
          <Route path="*"             element={<Navigate to="/" replace />} />
        </Route>
      </Route>
    </Routes>
    </>
  );
}

// Основной компонент App
export default function App() {
  return (
    <AppProviders>
      <AppContent />
    </AppProviders>
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
