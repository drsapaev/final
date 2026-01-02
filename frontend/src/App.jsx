import React, { useEffect, useState, Suspense, lazy } from 'react';
import { Routes, Route, Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { AppProviders } from './providers/AppProviders';
import { PWAInstallPrompt } from './components/pwa';
import { usePWA } from './hooks/usePWA.js';
import { ThemeProvider, useTheme } from './contexts/ThemeContext';
import './styles/theme.css';
import './styles/dark-theme-visibility-fix.css';
import './styles/global-fixes.css';
import './theme/macos-tokens.css';
import './styles/macos.css';
import { MacOSThemeProvider } from './theme/macosTheme.jsx';

// Global color scheme initializer - синхронизировано с ColorSchemeSelector
function initializeColorScheme() {
  const customScheme = localStorage.getItem('customColorScheme');
  const schemeId = localStorage.getItem('activeColorSchemeId');

  if (customScheme === 'true' && schemeId) {
    const root = document.documentElement;
    // Полная нормализация: убираем светлую/тёмную тему и их атрибуты
    document.body.classList.remove('light-theme', 'dark-theme');
    document.documentElement.removeAttribute('data-theme');

    if (schemeId === 'vibrant') {
      // Матовые приглушённые цвета
      root.style.setProperty('--mac-bg-primary', '#6b8db3'); /* Приглушённый синий */
      root.style.setProperty('--mac-bg-secondary', '#7fa899'); /* Приглушённый бирюзовый */
      root.style.setProperty('--mac-accent-blue', '#d4a063'); /* Приглушённый оранжевый */
      root.style.setProperty('--mac-text-primary', '#ffffff');
      root.style.setProperty('--mac-text-secondary', 'rgba(255,255,255,0.92)');
      root.style.setProperty('--mac-gradient-window', 'linear-gradient(135deg, rgba(107, 141, 179, 0.75) 0%, rgba(127, 168, 153, 0.7) 40%, rgba(212, 160, 99, 0.65) 80%), linear-gradient(135deg, rgba(120, 130, 145, 0.3) 0%, rgba(130, 140, 150, 0.25) 100%)');
      root.style.setProperty('--mac-gradient-sidebar', 'linear-gradient(135deg, rgba(100, 130, 165, 0.7) 0%, rgba(115, 155, 140, 0.65) 45%, rgba(200, 150, 90, 0.6) 100%), linear-gradient(135deg, rgba(130, 140, 150, 0.25) 0%, rgba(140, 150, 160, 0.2) 100%)');
      root.style.setProperty('--bg', '#6b8db3');
      root.style.setProperty('--mac-bg-toolbar', 'rgba(30, 35, 45, 0.4)');
      root.style.setProperty('--mac-separator', 'rgba(255,255,255,0.22)');
      root.style.setProperty('--mac-border', 'rgba(255,255,255,0.22)');
      root.style.setProperty('--mac-border-secondary', 'rgba(255,255,255,0.18)');
      root.setAttribute('data-color-scheme', 'vibrant');
    } else if (schemeId === 'glass') {
      // Синхронизировано с macos.css [data-color-scheme="glass"]
      // Улучшенные значения для лучшей видимости карточек
      root.style.setProperty('--mac-bg-primary', 'rgba(50, 55, 65, 0.75)');
      root.style.setProperty('--mac-bg-secondary', 'rgba(60, 65, 75, 0.65)');
      root.style.setProperty('--mac-bg-toolbar', 'rgba(50, 55, 65, 0.85)'); /* Увеличенная непрозрачность для хедера */
      root.style.setProperty('--mac-bg-tertiary', 'rgba(70, 75, 85, 0.55)');
      root.style.setProperty('--mac-accent-blue', 'rgba(0,122,255,0.8)');
      root.style.setProperty('--mac-text-primary', '#f0f1f5');
      root.style.setProperty('--mac-text-secondary', 'rgba(240,240,245,0.9)');
      root.style.setProperty('--mac-border', 'rgba(255, 255, 255, 0.2)');
      root.style.setProperty('--mac-border-secondary', 'rgba(255, 255, 255, 0.15)');
      root.style.setProperty('--mac-blur-light', 'saturate(180%) blur(22px)');
      root.style.setProperty('--surface', 'rgba(255,255,255,0.25)');
      root.style.setProperty('--bg', '#f6f7f9');
      // Очищаем градиент из предыдущих тем
      root.style.setProperty('--mac-gradient-window', 'none');
      // Для стеклянной темы задаём фон и фильтр на html и body
      document.documentElement.style.background = 'rgba(20, 20, 25, 0.3)';
      document.documentElement.style.backdropFilter = 'blur(22px) saturate(160%)';
      document.documentElement.style.webkitBackdropFilter = 'blur(22px) saturate(160%)';
      document.body.style.background = 'rgba(20, 20, 25, 0.3)';
      document.body.style.backdropFilter = 'blur(22px) saturate(160%)';
      document.body.style.webkitBackdropFilter = 'blur(22px) saturate(160%)';
      root.setAttribute('data-color-scheme', 'glass');
    } else if (schemeId === 'gradient') {
      // Синхронизация с предпросмотром в Settings → Gradient
      root.style.setProperty('--mac-bg-primary', '#667eea');
      root.style.setProperty('--mac-bg-secondary', '#764ba2');
      root.style.setProperty('--mac-bg-tertiary', '#8e7cc3');
      root.style.setProperty('--mac-accent-blue', '#f093fb');
      root.style.setProperty('--mac-text-primary', '#ffffff');
      root.style.setProperty('--mac-text-secondary', 'rgba(255,255,255,0.9)');
      root.style.setProperty('--mac-border', 'rgba(255, 255, 255, 0.18)');
      root.style.setProperty('--mac-border-secondary', 'rgba(255, 255, 255, 0.14)');
      root.style.setProperty('--mac-separator', 'rgba(255, 255, 255, 0.16)');
      root.style.setProperty('--mac-gradient-window', 'linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%)');
      root.style.setProperty('--bg', 'transparent');
      // Прозрачные слои для бесшовного градиента
      root.style.setProperty('--mac-bg-toolbar', 'transparent');
      root.style.setProperty('--mac-gradient-sidebar', 'transparent');
      // Сброс эффектов стекла
      document.documentElement.style.background = '';
      document.documentElement.style.backdropFilter = '';
      document.documentElement.style.webkitBackdropFilter = '';
      document.body.style.background = '';
      document.body.style.backdropFilter = '';
      document.body.style.webkitBackdropFilter = '';
      root.setAttribute('data-color-scheme', 'gradient');
    }
  }
}

// Initialize on load
initializeColorScheme();

// macOS UI компоненты
import { Sidebar } from './components/ui/macos';
import HeaderNew from './components/layout/HeaderNew.jsx';

// Статические импорты для критически важных страниц
import Health from './pages/Health.jsx';
import Landing from './pages/Landing.jsx';
import Login from './pages/Login.jsx';
import ButtonShowcase from './components/buttons/ButtonShowcase.jsx';

// Динамические импорты для больших страниц
const CashierPanel = lazy(() => import('./pages/CashierPanel.jsx'));
const Settings = lazy(() => import('./pages/Settings.jsx'));
const Audit = lazy(() => import('./pages/Audit.jsx'));
const Scheduler = lazy(() => import('./pages/Scheduler.jsx'));
const Appointments = lazy(() => import('./pages/Appointments.jsx'));
const VisitDetails = lazy(() => import('./pages/VisitDetails.jsx'));
const AdminPanel = lazy(() => import('./pages/AdminPanel.jsx'));
const RegistrarPanel = lazy(() => import('./pages/RegistrarPanel.jsx'));
const DoctorPanel = lazy(() => import('./pages/DoctorPanel.jsx'));
const CardiologistPanelUnified = lazy(() => import('./pages/CardiologistPanelUnified.jsx'));
const DermatologistPanelUnified = lazy(() => import('./pages/DermatologistPanelUnified.jsx'));
const DentistPanelUnified = lazy(() => import('./pages/DentistPanelUnified.jsx'));
const LabPanel = lazy(() => import('./pages/LabPanel.jsx'));
const UserSelect = lazy(() => import('./pages/UserSelect.jsx'));
const Search = lazy(() => import('./pages/Search.jsx'));
const QueueJoin = lazy(() => import('./pages/QueueJoin.jsx'));
const PatientPanel = lazy(() => import('./pages/PatientPanel.jsx'));
const DisplayBoardUnified = lazy(() => import('./pages/DisplayBoardUnified.jsx'));
const AnalyticsPage = lazy(() => import('./pages/AnalyticsPage.jsx'));
const MediLabDemo = lazy(() => import('./pages/MediLabDemo.jsx'));
const CSSTestPage = lazy(() => import('./pages/CSSTestPage'));
const PaymentSuccess = lazy(() => import('./pages/PaymentSuccess.jsx'));
const PaymentCancel = lazy(() => import('./pages/PaymentCancel.jsx'));
const PaymentTest = lazy(() => import('./pages/PaymentTest.jsx'));
const MacOSDemoPage = lazy(() => import('./pages/MacOSDemoPage.jsx'));
const SecurityPage = lazy(() => import('./pages/SecurityPage.jsx'));
const ChangePasswordRequired = lazy(() => import('./pages/auth/ChangePasswordRequired.jsx'));

// Стилизованные компоненты
import LoginFormStyled from './components/auth/LoginFormStyled.jsx'; // Стилизованная версия в стиле системы

// Скрытые компоненты для интеграции
import TelegramManager from './components/TelegramManager.jsx';
import EmailSMSManager from './components/notifications/EmailSMSManager.jsx';
import TwoFactorManager from './components/security/TwoFactorManager.jsx';
import FileManager from './components/files/FileManager.jsx';
import EMRInterface from './components/medical/EMRInterface.jsx';
import EMRDemo from './pages/EMRDemo.jsx';
import UserManagement from './components/admin/UserManagement.jsx';
import IntegrationDemo from './components/integration/IntegrationDemo.jsx';

import auth from './stores/auth.js';

import logger from './utils/logger';
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
  const [isChecking, setIsChecking] = useState(true);
  const loc = useLocation();

  useEffect(() => {
    // Подписываемся на изменения auth
    const unsubscribe = auth.subscribe(setSt);

    // Проверяем токен при монтировании
    const token = auth.getToken();
    if (token && !st.profile) {
      // Если есть токен, но нет профиля, пытаемся загрузить профиль
      auth.getProfile().then(() => {
        setIsChecking(false);
      }).catch(() => {
        setIsChecking(false);
      });
    } else {
      setIsChecking(false);
    }

    return unsubscribe;
  }, []);

  // Показываем загрузку при проверке
  if (isChecking) {
    return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>Загрузка...</div>;
  }

  // Проверяем токен
  if (!st.token) {
    return <Navigate to="/login" replace state={{ from: loc }} />;
  }

  // Проверяем роли
  if (!hasRole(st.profile, roles)) {
    return <Navigate to="/" replace />;
  }

  return children || <Outlet />;
}

// macOS Helper functions
function getPageTitle(path) {
  const titles = {
    '/': 'Dashboard',
    '/admin': 'Admin Panel',
    '/doctor-panel': 'Doctor Panel',
    '/patient-panel': 'Patient Panel',
    '/registrar-panel': 'Registrar Panel',
    '/cashier-panel': 'Cashier Panel',
    '/cardiologist': 'Cardiologist Panel',
    '/dermatologist': 'Dermatologist Panel',
    '/dentist': 'Dentist Panel',
    '/lab-panel': 'Lab Panel',
    '/settings': 'Settings',
    '/analytics': 'Analytics'
  };
  return titles[path] || 'Medical System';
}

function getSidebarItems(path) {
  // Admin panel specific items (из старого AdminPanel)
  if (path.startsWith('/admin')) {
    return [
      { id: 'dashboard', label: 'Dashboard', icon: 'chart.bar' },
      { id: 'analytics', label: 'Analytics', icon: 'chart.bar' }, // ✅ Заменено chart.line.uptrend.xyaxis → chart.bar
      { id: 'wait-time-analytics', label: 'Wait Time Analytics', icon: 'clock' },
      { id: 'ai-analytics', label: 'AI Analytics', icon: 'brain' },
      { id: 'webhooks', label: 'Webhooks', icon: 'globe' },
      { id: 'reports', label: 'Reports', icon: 'file-text' }, // ✅ Заменено doc.text → file-text
      { id: 'system', label: 'System', icon: 'gear' }, // ✅ Заменено server.rack → gear
      { id: 'cloud-printing', label: 'Cloud Printing', icon: 'printer' },
      { id: 'medical-equipment', label: 'Medical Equipment', icon: 'stethoscope' },
      { id: 'dynamic-pricing', label: 'Dynamic Pricing', icon: 'tag' },
      { id: 'billing', label: 'Billing', icon: 'receipt' },
      { id: 'discount-benefits', label: 'Discount Benefits', icon: 'percent' },
      { id: 'graphql-explorer', label: 'GraphQL API', icon: 'database' },
      { id: 'users', label: 'Users', icon: 'users' }, // ✅ Заменено person.2 → users
      { id: 'doctors', label: 'Doctors', icon: 'user-plus' }, // ✅ Заменено person.badge.plus → user-plus
      { id: 'services', label: 'Services', icon: 'list' }, // ✅ Заменено list.bullet → list
      { id: 'patients', label: 'Patients', icon: 'users' }, // ✅ Заменено person.2 → users
      { id: 'appointments', label: 'Appointments', icon: 'calendar' },
      { id: 'all-free', label: 'All Free', icon: 'exclamationmark.triangle' },
      { id: 'benefit-settings', label: 'Benefit Settings', icon: 'gear' },
      { id: 'wizard-settings', label: 'Wizard Settings', icon: 'monitor' }, // ✅ Заменено desktopcomputer → monitor
      { id: 'payment-providers', label: 'Payment Providers', icon: 'creditcard' },
      { id: 'clinic-management', label: 'Clinic Management', icon: 'building' }, // ✅ Заменено building.2 → building
      { id: 'clinic-settings', label: 'Clinic Settings', icon: 'gear' },
      { id: 'queue-settings', label: 'Queue Settings', icon: 'list' }, // ✅ Заменено list.number → list
      { id: 'queue-limits', label: 'Queue Limits', icon: 'shield' },
      { id: 'ai-imaging', label: 'AI Imaging', icon: 'camera' },
      { id: 'treatment-recommendations', label: 'Treatment Recommendations', icon: 'heart' },
      { id: 'drug-interactions', label: 'Drug Interactions', icon: 'pill' },
      { id: 'risk-assessment', label: 'Risk Assessment', icon: 'shield' },
      { id: 'voice-to-text', label: 'Voice to Text', icon: 'mic' },
      { id: 'smart-scheduling', label: 'Smart Scheduling', icon: 'calendar' },
      { id: 'quality-control', label: 'Quality Control', icon: 'checkmark.circle' },
      { id: 'analytics-insights', label: 'Analytics Insights', icon: 'chart.line.uptrend.xyaxis' },
      { id: 'telegram-bot', label: 'Telegram Bot', icon: 'paperplane' },
      { id: 'fcm-notifications', label: 'FCM Notifications', icon: 'bell' },
      { id: 'phone-verification', label: 'Phone Verification', icon: 'phone' },
      { id: 'user-data-transfer', label: 'User Data Transfer', icon: 'arrow.up.arrow.down' },
      { id: 'group-permissions', label: 'Group Permissions', icon: 'person.3' },
      { id: 'user-export', label: 'User Export', icon: 'square.and.arrow.up' },
      { id: 'registrar-notifications', label: 'Registrar Notifications', icon: 'bell.badge' },
      { id: 'ai-settings', label: 'AI Settings', icon: 'brain' },
      { id: 'telegram-settings', label: 'Telegram Settings', icon: 'paperplane' },
      { id: 'display-settings', label: 'Display Settings', icon: 'tv' },
      { id: 'activation', label: 'Activation', icon: 'key' },
      { id: 'finance', label: 'Finance', icon: 'dollarsign.circle' },
      { id: 'security', label: 'Security', icon: 'lock' },
      { id: 'settings', label: 'Settings', icon: 'gear' }
    ];
  }

  // Doctor panel specific items (из старого DoctorPanel)
  if (path === '/doctor-panel') {
    return [
      { id: 'dashboard', label: 'Dashboard', icon: 'chart.bar' },
      { id: 'patients', label: 'Patients', icon: 'person.2' },
      { id: 'appointments', label: 'Appointments', icon: 'calendar' },
      { id: 'ai', label: 'AI Assistant', icon: 'brain' },
      { id: 'reports', label: 'Reports', icon: 'doc.text' }
    ];
  }

  // Patient panel specific items (из старого PatientPanel)
  if (path === '/patient-panel') {
    return [
      { id: 'appointments', label: 'Appointments', icon: 'calendar' },
      { id: 'results', label: 'Test Results', icon: 'doc.text' },
      { id: 'profile', label: 'Profile', icon: 'person' }
    ];
  }

  // Registrar panel specific items (из старого RegistrarPanel)
  if (path === '/registrar-panel') {
    return [
      { id: 'welcome', label: 'Welcome', icon: 'house' },
      { id: 'appointments', label: 'All Appointments', icon: 'calendar' },
      { id: 'cardio', label: 'Cardiology', icon: 'heart' },
      { id: 'echokg', label: 'ECG', icon: 'waveform.path.ecg' },
      { id: 'derma', label: 'Dermatology', icon: 'face.smiling' },
      { id: 'dental', label: 'Dentistry', icon: 'smile' },
      { id: 'lab', label: 'Laboratory', icon: 'testtube.2' },
      { id: 'procedures', label: 'Procedures', icon: 'list' },
      { id: 'queue', label: 'Online Queue', icon: 'list' }
    ];
  }

  // Dentist panel specific items (из старого DentistPanel)
  if (path === '/dentist') {
    return [
      { id: 'dashboard', label: 'Dashboard', icon: 'chart.bar' },
      { id: 'patients', label: 'Patients', icon: 'person.2' },
      { id: 'appointments', label: 'Appointments', icon: 'calendar' },
      { id: 'examinations', label: 'Examinations', icon: 'eye' },
      { id: 'diagnoses', label: 'Diagnoses', icon: 'stethoscope' },
      { id: 'visits', label: 'Visit Protocols', icon: 'doc.text' },
      { id: 'photos', label: 'Photo Archive', icon: 'camera' },
      { id: 'templates', label: 'Templates', icon: 'doc' },
      { id: 'reports', label: 'Reports', icon: 'chart.bar' },
      { id: 'dental-chart', label: 'Dental Chart', icon: 'smile' },
      { id: 'treatment-plans', label: 'Treatment Plans', icon: 'list' },
      { id: 'prosthetics', label: 'Prosthetics', icon: 'smile' },
      { id: 'ai-assistant', label: 'AI Assistant', icon: 'brain' }
    ];
  }

  // Dermatologist panel specific items (из старого DermatologistPanel)
  if (path === '/dermatologist') {
    return [
      { id: 'queue', label: 'Queue', icon: 'person.2' },
      { id: 'appointments', label: 'Appointments', icon: 'calendar' },
      { id: 'visit', label: 'Visit', icon: 'stethoscope' },
      { id: 'patients', label: 'Patients', icon: 'person' },
      { id: 'photos', label: 'Photos', icon: 'camera' },
      { id: 'skin', label: 'Skin Examination', icon: 'eye' },
      { id: 'cosmetic', label: 'Cosmetic', icon: 'sparkles' },
      { id: 'ai', label: 'AI Assistant', icon: 'brain' },
      { id: 'services', label: 'Services', icon: 'scissors' },
      { id: 'history', label: 'History', icon: 'doc.text' }
    ];
  }

  // Cardiologist panel specific items (из старого CardiologistPanel)
  if (path === '/cardiologist') {
    return [
      { id: 'queue', label: 'Queue', icon: 'person.2' },
      { id: 'appointments', label: 'Appointments', icon: 'calendar' },
      { id: 'visit', label: 'Visit', icon: 'heart' },
      { id: 'ecg', label: 'ECG', icon: 'waveform.path.ecg' },
      { id: 'blood', label: 'Blood Tests', icon: 'testtube.2' },
      { id: 'ai', label: 'AI Assistant', icon: 'brain' },
      { id: 'services', label: 'Services', icon: 'stethoscope' },
      { id: 'history', label: 'History', icon: 'doc.text' }
    ];
  }

  // Lab panel specific items (из LabPanel)
  if (path === '/lab-panel') {
    return [
      { id: 'tests', label: 'Tests', icon: 'testtube.2' },
      { id: 'results', label: 'Results', icon: 'chart.bar' },
      { id: 'patients', label: 'Patients', icon: 'person.2' },
      { id: 'appointments', label: 'Appointments', icon: 'calendar' },
      { id: 'reports', label: 'Reports', icon: 'doc.text' }
    ];
  }

  // Cashier panel specific items (из старого CashierPanel)
  if (path === '/cashier-panel') {
    return [
      { id: 'dashboard', label: 'Dashboard', icon: 'chart.bar' },
      { id: 'payments', label: 'Payments', icon: 'creditcard' },
      { id: 'appointments', label: 'Appointments', icon: 'calendar' },
      { id: 'reports', label: 'Reports', icon: 'doc.text' },
      { id: 'settings', label: 'Settings', icon: 'gear' }
    ];
  }

  // Default items for other panels
  const baseItems = [
    { id: 'dashboard', label: 'Dashboard', icon: 'house' },
    { id: 'appointments', label: 'Appointments', icon: 'calendar' },
    { id: 'patients', label: 'Patients', icon: 'person' },
    { id: 'analytics', label: 'Analytics', icon: 'chart.bar' },
    { id: 'settings', label: 'Settings', icon: 'gear' }
  ];

  return baseItems;
}

function getActiveItem(path) {
  if (path === '/') return 'dashboard';

  // Admin panel - get from URL params
  if (path.startsWith('/admin')) {
    const urlParams = new URLSearchParams(window.location.search);
    const section = urlParams.get('section') || 'dashboard';
    return section;
  }

  // Doctor panel - get from URL params
  if (path === '/doctor-panel') {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('tab') || 'dashboard';
  }

  // Patient panel - get from URL params
  if (path === '/patient-panel') {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('tab') || 'appointments';
  }

  // Registrar panel - get from URL params
  if (path === '/registrar-panel') {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('tab') || 'welcome';
  }

  // Dentist panel - get from URL params
  if (path === '/dentist') {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('tab') || 'dashboard';
  }

  // Dermatologist panel - get from URL params
  if (path === '/dermatologist') {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('tab') || 'queue';
  }

  // Cardiologist panel - get from URL params
  if (path === '/cardiologist') {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('tab') || 'queue';
  }

  // Cashier panel - get from URL params
  if (path === '/cashier-panel') {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('tab') || 'dashboard';
  }

  // Lab panel - get from URL params
  if (path === '/lab-panel') {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('tab') || 'tests';
  }

  // Other panels
  if (path === '/settings') return 'settings';
  if (path === '/analytics') return 'analytics';

  return 'dashboard';
}

function getHeaderActions(path) {
  // Import Icon component
  const Icon = ({ name, size = 16 }) => (
    <span style={{ fontSize: `${size}px` }}>{name}</span>
  );

  // Patient Panel actions
  if (path === '/patient-panel') {
    return (
      <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
        <button style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '8px 12px',
          backgroundColor: 'var(--mac-bg-secondary)',
          border: '1px solid var(--mac-border)',
          borderRadius: 'var(--mac-radius-sm)',
          color: 'var(--mac-text-primary)',
          fontSize: '13px',
          cursor: 'pointer',
          transition: 'all var(--mac-duration-normal) var(--mac-ease)'
        }}>
          <Icon name="📅" size={14} />
          Appointments
        </button>
        <button style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '8px 12px',
          backgroundColor: 'var(--mac-bg-secondary)',
          border: '1px solid var(--mac-border)',
          borderRadius: 'var(--mac-radius-sm)',
          color: 'var(--mac-text-primary)',
          fontSize: '13px',
          cursor: 'pointer',
          transition: 'all var(--mac-duration-normal) var(--mac-ease)'
        }}>
          <Icon name="📋" size={14} />
          Test Results
        </button>
        <button style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '8px 12px',
          backgroundColor: 'var(--mac-bg-secondary)',
          border: '1px solid var(--mac-border)',
          borderRadius: 'var(--mac-radius-sm)',
          color: 'var(--mac-text-primary)',
          fontSize: '13px',
          cursor: 'pointer',
          transition: 'all var(--mac-duration-normal) var(--mac-ease)'
        }}>
          <Icon name="👤" size={14} />
          Profile
        </button>
      </div>
    );
  }

  // Doctor Panel actions
  if (path === '/doctor-panel') {
    return (
      <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
        <button style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '8px 12px',
          backgroundColor: 'var(--mac-bg-secondary)',
          border: '1px solid var(--mac-border)',
          borderRadius: 'var(--mac-radius-sm)',
          color: 'var(--mac-text-primary)',
          fontSize: '13px',
          cursor: 'pointer',
          transition: 'all var(--mac-duration-normal) var(--mac-ease)'
        }}>
          <Icon name="🔔" size={14} />
          Notifications
        </button>
        <button style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '8px 12px',
          backgroundColor: 'var(--mac-bg-secondary)',
          border: '1px solid var(--mac-border)',
          borderRadius: 'var(--mac-radius-sm)',
          color: 'var(--mac-text-primary)',
          fontSize: '13px',
          cursor: 'pointer',
          transition: 'all var(--mac-duration-normal) var(--mac-ease)'
        }}>
          <Icon name="🤖" size={14} />
          AI Assistant
        </button>
        <button style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '8px 12px',
          backgroundColor: 'var(--mac-bg-secondary)',
          border: '1px solid var(--mac-border)',
          borderRadius: 'var(--mac-radius-sm)',
          color: 'var(--mac-text-primary)',
          fontSize: '13px',
          cursor: 'pointer',
          transition: 'all var(--mac-duration-normal) var(--mac-ease)'
        }}>
          <Icon name="🚪" size={14} />
          Logout
        </button>
      </div>
    );
  }

  // Registrar Panel actions
  if (path === '/registrar-panel') {
    return (
      <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
        <button style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '8px 12px',
          backgroundColor: 'var(--mac-bg-secondary)',
          border: '1px solid var(--mac-border)',
          borderRadius: 'var(--mac-radius-sm)',
          color: 'var(--mac-text-primary)',
          fontSize: '13px',
          cursor: 'pointer',
          transition: 'all var(--mac-duration-normal) var(--mac-ease)'
        }}>
          <Icon name="➕" size={14} />
          New Appointment
        </button>
        <button style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '8px 12px',
          backgroundColor: 'var(--mac-bg-secondary)',
          border: '1px solid var(--mac-border)',
          borderRadius: 'var(--mac-radius-sm)',
          color: 'var(--mac-text-primary)',
          fontSize: '13px',
          cursor: 'pointer',
          transition: 'all var(--mac-duration-normal) var(--mac-ease)'
        }}>
          <Icon name="📋" size={14} />
          Queue Management
        </button>
        <button style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '8px 12px',
          backgroundColor: 'var(--mac-bg-secondary)',
          border: '1px solid var(--mac-border)',
          borderRadius: 'var(--mac-radius-sm)',
          color: 'var(--mac-text-primary)',
          fontSize: '13px',
          cursor: 'pointer',
          transition: 'all var(--mac-duration-normal) var(--mac-ease)'
        }}>
          <Icon name="🏠" size={14} />
          Home
        </button>
        <button style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '8px 12px',
          backgroundColor: 'var(--mac-bg-secondary)',
          border: '1px solid var(--mac-border)',
          borderRadius: 'var(--mac-radius-sm)',
          color: 'var(--mac-text-primary)',
          fontSize: '13px',
          cursor: 'pointer',
          transition: 'all var(--mac-duration-normal) var(--mac-ease)'
        }}>
          <Icon name="📊" size={14} />
          Online Queue
        </button>
        <button style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '8px 12px',
          backgroundColor: 'var(--mac-bg-secondary)',
          border: '1px solid var(--mac-border)',
          borderRadius: 'var(--mac-radius-sm)',
          color: 'var(--mac-text-primary)',
          fontSize: '13px',
          cursor: 'pointer',
          transition: 'all var(--mac-duration-normal) var(--mac-ease)'
        }}>
          <Icon name="🚪" size={14} />
          Logout
        </button>
      </div>
    );
  }

  // Dermatologist Panel actions
  if (path === '/dermatologist') {
    return (
      <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
        <button style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '8px 12px',
          backgroundColor: 'var(--mac-bg-secondary)',
          border: '1px solid var(--mac-border)',
          borderRadius: 'var(--mac-radius-sm)',
          color: 'var(--mac-text-primary)',
          fontSize: '13px',
          cursor: 'pointer',
          transition: 'all var(--mac-duration-normal) var(--mac-ease)'
        }}>
          <Icon name="⚙️" size={14} />
          Settings
        </button>
        <button style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '8px 12px',
          backgroundColor: 'var(--mac-bg-secondary)',
          border: '1px solid var(--mac-border)',
          borderRadius: 'var(--mac-radius-sm)',
          color: 'var(--mac-text-primary)',
          fontSize: '13px',
          cursor: 'pointer',
          transition: 'all var(--mac-duration-normal) var(--mac-ease)'
        }}>
          <Icon name="🚪" size={14} />
          Logout
        </button>
      </div>
    );
  }

  // Cardiologist Panel actions
  if (path === '/cardiologist') {
    return (
      <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
        <button style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '8px 12px',
          backgroundColor: 'var(--mac-bg-secondary)',
          border: '1px solid var(--mac-border)',
          borderRadius: 'var(--mac-radius-sm)',
          color: 'var(--mac-text-primary)',
          fontSize: '13px',
          cursor: 'pointer',
          transition: 'all var(--mac-duration-normal) var(--mac-ease)'
        }}>
          <Icon name="⚙️" size={14} />
          Settings
        </button>
        <button style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '8px 12px',
          backgroundColor: 'var(--mac-bg-secondary)',
          border: '1px solid var(--mac-border)',
          borderRadius: 'var(--mac-radius-sm)',
          color: 'var(--mac-text-primary)',
          fontSize: '13px',
          cursor: 'pointer',
          transition: 'all var(--mac-duration-normal) var(--mac-ease)'
        }}>
          <Icon name="🚪" size={14} />
          Logout
        </button>
      </div>
    );
  }

  // Cashier Panel actions
  if (path === '/cashier-panel') {
    return (
      <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
        <button style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '8px 12px',
          backgroundColor: 'var(--mac-bg-secondary)',
          border: '1px solid var(--mac-border)',
          borderRadius: 'var(--mac-radius-sm)',
          color: 'var(--mac-text-primary)',
          fontSize: '13px',
          cursor: 'pointer',
          transition: 'all var(--mac-duration-normal) var(--mac-ease)'
        }}>
          <Icon name="📅" size={14} />
          Today
        </button>
        <button style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '8px 12px',
          backgroundColor: 'var(--mac-bg-secondary)',
          border: '1px solid var(--mac-border)',
          borderRadius: 'var(--mac-radius-sm)',
          color: 'var(--mac-text-primary)',
          fontSize: '13px',
          cursor: 'pointer',
          transition: 'all var(--mac-duration-normal) var(--mac-ease)'
        }}>
          <Icon name="📤" size={14} />
          Export
        </button>
        <button style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '8px 12px',
          backgroundColor: 'var(--mac-bg-secondary)',
          border: '1px solid var(--mac-border)',
          borderRadius: 'var(--mac-radius-sm)',
          color: 'var(--mac-text-primary)',
          fontSize: '13px',
          cursor: 'pointer',
          transition: 'all var(--mac-duration-normal) var(--mac-ease)'
        }}>
          <Icon name="⚙️" size={14} />
          Settings
        </button>
        <button style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '8px 12px',
          backgroundColor: 'var(--mac-bg-secondary)',
          border: '1px solid var(--mac-border)',
          borderRadius: 'var(--mac-radius-sm)',
          color: 'var(--mac-text-primary)',
          fontSize: '13px',
          cursor: 'pointer',
          transition: 'all var(--mac-duration-normal) var(--mac-ease)'
        }}>
          <Icon name="🚪" size={14} />
          Logout
        </button>
      </div>
    );
  }

  // Admin Panel actions
  if (path.startsWith('/admin')) {
    return (
      <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
        <button style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '8px 12px',
          backgroundColor: 'var(--mac-bg-secondary)',
          border: '1px solid var(--mac-border)',
          borderRadius: 'var(--mac-radius-sm)',
          color: 'var(--mac-text-primary)',
          fontSize: '13px',
          cursor: 'pointer',
          transition: 'all var(--mac-duration-normal) var(--mac-ease)'
        }}>
          <Icon name="📊" size={14} />
          Analytics
        </button>
        <button style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '8px 12px',
          backgroundColor: 'var(--mac-bg-secondary)',
          border: '1px solid var(--mac-border)',
          borderRadius: 'var(--mac-radius-sm)',
          color: 'var(--mac-text-primary)',
          fontSize: '13px',
          cursor: 'pointer',
          transition: 'all var(--mac-duration-normal) var(--mac-ease)'
        }}>
          <Icon name="🔔" size={14} />
          Notifications
        </button>
        <button style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '8px 12px',
          backgroundColor: 'var(--mac-bg-secondary)',
          border: '1px solid var(--mac-border)',
          borderRadius: 'var(--mac-radius-sm)',
          color: 'var(--mac-text-primary)',
          fontSize: '13px',
          cursor: 'pointer',
          transition: 'all var(--mac-duration-normal) var(--mac-ease)'
        }}>
          <Icon name="⚙️" size={14} />
          Settings
        </button>
        <button style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '8px 12px',
          backgroundColor: 'var(--mac-bg-secondary)',
          border: '1px solid var(--mac-border)',
          borderRadius: 'var(--mac-radius-sm)',
          color: 'var(--mac-text-primary)',
          fontSize: '13px',
          cursor: 'pointer',
          transition: 'all var(--mac-duration-normal) var(--mac-ease)'
        }}>
          <Icon name="🚪" size={14} />
          Logout
        </button>
      </div>
    );
  }

  // Lab Panel actions
  if (path === '/lab-panel') {
    return (
      <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
        <button style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '8px 12px',
          backgroundColor: 'var(--mac-bg-secondary)',
          border: '1px solid var(--mac-border)',
          borderRadius: 'var(--mac-radius-sm)',
          color: 'var(--mac-text-primary)',
          fontSize: '13px',
          cursor: 'pointer',
          transition: 'all var(--mac-duration-normal) var(--mac-ease)'
        }}>
          <Icon name="🧪" size={14} />
          New Test
        </button>
        <button style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '8px 12px',
          backgroundColor: 'var(--mac-bg-secondary)',
          border: '1px solid var(--mac-border)',
          borderRadius: 'var(--mac-radius-sm)',
          color: 'var(--mac-text-primary)',
          fontSize: '13px',
          cursor: 'pointer',
          transition: 'all var(--mac-duration-normal) var(--mac-ease)'
        }}>
          <Icon name="📊" size={14} />
          Results
        </button>
        <button style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '8px 12px',
          backgroundColor: 'var(--mac-bg-secondary)',
          border: '1px solid var(--mac-border)',
          borderRadius: 'var(--mac-radius-sm)',
          color: 'var(--mac-text-primary)',
          fontSize: '13px',
          cursor: 'pointer',
          transition: 'all var(--mac-duration-normal) var(--mac-ease)'
        }}>
          <Icon name="⚙️" size={14} />
          Settings
        </button>
        <button style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '8px 12px',
          backgroundColor: 'var(--mac-bg-secondary)',
          border: '1px solid var(--mac-border)',
          borderRadius: 'var(--mac-radius-sm)',
          color: 'var(--mac-text-primary)',
          fontSize: '13px',
          cursor: 'pointer',
          transition: 'all var(--mac-duration-normal) var(--mac-ease)'
        }}>
          <Icon name="🚪" size={14} />
          Logout
        </button>
      </div>
    );
  }

  return null;
}

/** Каркас: macOS Header и Sidebar для всех панелей */
function AppShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const path = location.pathname;
  const { theme } = useTheme(); // Добавляем доступ к теме

  // Переприменяем кастомную схему при навигации между страницами
  useEffect(() => {
    const reapplyCustomScheme = () => {
      const customScheme = localStorage.getItem('customColorScheme');
      const schemeId = localStorage.getItem('activeColorSchemeId');
      if (customScheme === 'true' && schemeId) {
        initializeColorScheme();
      }
    };

    // Применить сразу при монтировании и при изменении location
    reapplyCustomScheme();

    // Слушать события изменения цветовой схемы
    const handleSchemeChange = () => reapplyCustomScheme();
    window.addEventListener('colorSchemeChanged', handleSchemeChange);
    // Восстановление после блокировки/фонового режима/перезагрузки из BFCache
    const handleVisibilityOrFocus = () => reapplyCustomScheme();
    document.addEventListener('visibilitychange', handleVisibilityOrFocus);
    window.addEventListener('focus', handleVisibilityOrFocus);
    window.addEventListener('pageshow', handleVisibilityOrFocus);

    return () => {
      window.removeEventListener('colorSchemeChanged', handleSchemeChange);
      document.removeEventListener('visibilitychange', handleVisibilityOrFocus);
      window.removeEventListener('focus', handleVisibilityOrFocus);
      window.removeEventListener('pageshow', handleVisibilityOrFocus);
    };
  }, [location.pathname]);

  const hideSidebar = path === '/registrar-panel' ||
    path === '/doctor-panel' ||
    path === '/cashier-panel';

  // Полноэкранный режим для специализированных панелей
  const isFullscreen = path === '/cardiologist' || path === '/dermatologist' || path === '/dentist';

  // Скрыть хедер для лендинга
  const hideHeader = path === '/';

  return (
    <div style={macOSWrapStyle}>
      {/* macOS Header - скрыт для лендинга */}
      {!hideHeader && (
        <div style={{
          padding: '12px 12px 12px 12px', // Отступы: 12px сверху, 12px по бокам и снизу
          backgroundColor: 'transparent',
          width: '100vw'
        }}>
          <HeaderNew />
        </div>
      )}

      <div style={{
        display: 'grid', // Используем CSS Grid для правильного распределения пространства
        gridTemplateColumns: hideSidebar ? '1fr' : 'auto 1fr', // auto для сайдбара, 1fr для контента
        gap: '16px', // Возвращаем gap для правильных отступов между сайдбаром и контентом
        marginTop: hideHeader ? '0' : '0px',
        flex: 1,
        minHeight: 0,
        width: '100vw',
        overflowX: 'hidden', // Скрываем горизонтальную прокрутку
        overflowY: 'auto', // Разрешаем вертикальную прокрутку
        padding: hideHeader ? '0' : '0 0 16px 0' // Убираем боковые отступы, только нижний
      }}>
        {!hideSidebar && (
          <div style={{
            marginTop: '0', // Сохраняем выравнивание с хедером
            marginLeft: '12px' // Отступ от левого края экрана
          }}>
            <Sidebar
              items={getSidebarItems(path)}
              activeItem={getActiveItem(path)}
              onItemClick={(item) => {
                // Special handling for different panels
                if (path.startsWith('/admin')) {
                  const params = new URLSearchParams(location.search);
                  params.set('section', item.id);
                  navigate({ pathname: location.pathname, search: `?${params.toString()}` });
                } else if (path === '/doctor-panel') {
                  const params = new URLSearchParams(location.search);
                  params.set('tab', item.id);
                  navigate({ pathname: location.pathname, search: `?${params.toString()}` });
                } else if (path === '/patient-panel') {
                  const params = new URLSearchParams(location.search);
                  params.set('tab', item.id);
                  navigate({ pathname: location.pathname, search: `?${params.toString()}` });
                } else if (path === '/registrar-panel') {
                  const params = new URLSearchParams(location.search);
                  params.set('tab', item.id);
                  navigate({ pathname: location.pathname, search: `?${params.toString()}` });
                } else if (path === '/dentist') {
                  const params = new URLSearchParams(location.search);
                  params.set('tab', item.id);
                  navigate({ pathname: location.pathname, search: `?${params.toString()}` });
                } else if (path === '/dermatologist') {
                  const params = new URLSearchParams(location.search);
                  params.set('tab', item.id);
                  navigate({ pathname: location.pathname, search: `?${params.toString()}` });
                } else if (path === '/cardiologist') {
                  const params = new URLSearchParams(location.search);
                  params.set('tab', item.id);
                  navigate({ pathname: location.pathname, search: `?${params.toString()}` });
                } else if (path === '/cashier-panel') {
                  const params = new URLSearchParams(location.search);
                  params.set('tab', item.id);
                  navigate({ pathname: location.pathname, search: `?${params.toString()}` });
                } else if (path === '/lab-panel') {
                  const params = new URLSearchParams(location.search);
                  params.set('tab', item.id);
                  navigate({ pathname: location.pathname, search: `?${params.toString()}` });
                }
                // Other navigation logic will be handled by router
              }}
              header="Medical System"
              style={{
                background: 'var(--mac-gradient-sidebar)',
                borderRight: '1px solid var(--mac-separator)',
                borderRadius: 'var(--mac-radius-md)',
                backdropFilter: 'var(--mac-blur-light)',
                WebkitBackdropFilter: 'var(--mac-blur-light)'
              }}
            />
          </div>
        )}

        <main style={{
          ...macOSMainStyle,
          marginTop: '0', // Убираем top margin, gap Grid обеспечит выравнивание
          ...(theme === 'light' && {
            boxShadow: '0 2px 8px rgba(0, 0, 0, 0.06)' // Добавляем тень для светлой темы
          }),
          ...(hideSidebar && { maxWidth: 'none', margin: 0, padding: 0 }),
          ...(isFullscreen && {
            maxWidth: 'none',
            margin: 0,
            padding: 0,
            width: '100%',
            minWidth: '100%',
            overflow: 'visible'
          })
        }}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}

// Внутренний компонент с PWA логикой
function AppContent() {
  // Безопасный вызов PWA хука с fallback
  let shouldShowInstallPrompt = () => false;

  try {
    const pwa = usePWA();
    shouldShowInstallPrompt = pwa.shouldShowInstallPrompt;
  } catch (error) {
    logger.warn('PWA hook failed in AppContent, using fallback:', error);
  }

  return (
    <>
      {shouldShowInstallPrompt() && <PWAInstallPrompt />}
      <Suspense fallback={<div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', fontSize: '18px' }}>Загрузка...</div>}>
        <Routes>
          <Route path="/login" element={<LoginFormStyled />} />
          <Route path="/old-login" element={<Login />} />
          <Route path="/change-password-required" element={<ChangePasswordRequired />} />
          <Route path="/health" element={<Health />} />
          <Route path="/" element={<Landing />} />
          <Route path="/medilab-demo" element={<MediLabDemo />} />
          <Route path="/macos-demo" element={<MacOSDemoPage />} />
          {/* Test pages - Admin only (security fix) */}
          <Route path="/css-test" element={<RequireAuth roles={['Admin']}><CSSTestPage /></RequireAuth>} />
          <Route path="/buttons" element={<RequireAuth roles={['Admin']}><ButtonShowcase /></RequireAuth>} />
          <Route path="/medilab-demo/dashboard" element={<MediLabDemo />} />
          <Route path="/medilab-demo/patients" element={<MediLabDemo />} />
          <Route path="/medilab-demo/appointments" element={<MediLabDemo />} />
          <Route path="/medilab-demo/staff-schedule" element={<MediLabDemo />} />
          <Route path="/user-select" element={<RequireAuth roles={['Admin']}><UserSelect /></RequireAuth>} />
          <Route path="/queue/join" element={<QueueJoin />} />
          <Route path="/queue/join/:token" element={<QueueJoin />} />
          <Route path="/pwa/queue" element={<QueueJoin />} />
          <Route path="/payment/success" element={<PaymentSuccess />} />
          <Route path="/payment/cancel" element={<PaymentCancel />} />
          {/* Payment test - Admin only (security fix) */}
          <Route path="/payment/test" element={<RequireAuth roles={['Admin']}><PaymentTest /></RequireAuth>} />
          <Route element={<RequireAuth />}>
            <Route element={<AppShell />}>
              <Route path="cashier-panel" element={<RequireAuth roles={['Admin', 'Cashier']}><CashierPanel /></RequireAuth>} />
              <Route path="admin" element={<RequireAuth roles={['Admin']}><AdminPanel /></RequireAuth>} />
              <Route path="admin/analytics" element={<RequireAuth roles={['Admin']}><AdminPanel /></RequireAuth>} />
              <Route path="admin/users" element={<RequireAuth roles={['Admin']}><AdminPanel /></RequireAuth>} />
              <Route path="admin/doctors" element={<RequireAuth roles={['Admin']}><AdminPanel /></RequireAuth>} />
              <Route path="admin/services" element={<RequireAuth roles={['Admin']}><AdminPanel /></RequireAuth>} />
              <Route path="admin/patients" element={<RequireAuth roles={['Admin']}><AdminPanel /></RequireAuth>} />
              <Route path="admin/appointments" element={<RequireAuth roles={['Admin']}><AdminPanel /></RequireAuth>} />
              <Route path="admin/all-free" element={<RequireAuth roles={['Admin']}><AdminPanel /></RequireAuth>} />
              <Route path="admin/benefit-settings" element={<RequireAuth roles={['Admin']}><AdminPanel /></RequireAuth>} />
              <Route path="admin/wizard-settings" element={<RequireAuth roles={['Admin']}><AdminPanel /></RequireAuth>} />
              <Route path="admin/payment-providers" element={<RequireAuth roles={['Admin']}><AdminPanel /></RequireAuth>} />
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
              <Route path="registrar-panel" element={<RequireAuth roles={['Admin', 'Registrar', 'Receptionist']}><RegistrarPanel /></RequireAuth>} />
              <Route path="doctor-panel" element={<RequireAuth roles={['Admin', 'Doctor']}><DoctorPanel /></RequireAuth>} />
              <Route path="cardiologist" element={<RequireAuth roles={['Admin', 'Doctor', 'cardio']}><CardiologistPanelUnified /></RequireAuth>} />
              <Route path="dermatologist" element={<RequireAuth roles={['Admin', 'Doctor', 'derma']}><DermatologistPanelUnified /></RequireAuth>} />
              <Route path="dentist" element={<RequireAuth roles={['Admin', 'Doctor', 'dentist']}><DentistPanelUnified /></RequireAuth>} />
              <Route path="lab-panel" element={<RequireAuth roles={['Admin', 'Lab']}><LabPanel /></RequireAuth>} />
              <Route path="patient-panel" element={<RequireAuth roles={['Admin', 'Patient', 'Registrar', 'Receptionist', 'Doctor']}><PatientPanel /></RequireAuth>} />
              <Route path="queue-board" element={<DisplayBoardUnified />} />
              <Route path="display-board" element={<DisplayBoardUnified />} />
              <Route path="display-board/:role" element={<DisplayBoardUnified />} />
              <Route path="settings" element={<RequireAuth roles={['Admin']}><Settings /></RequireAuth>} />
              <Route path="security" element={<RequireAuth><SecurityPage /></RequireAuth>} />
              <Route path="audit" element={<RequireAuth roles={['Admin']}><Audit /></RequireAuth>} />
              <Route path="scheduler" element={<RequireAuth roles={['Admin', 'Doctor', 'Registrar', 'Receptionist']}><Scheduler /></RequireAuth>} />
              <Route path="appointments" element={<RequireAuth roles={['Admin', 'Registrar', 'Receptionist']}><Appointments /></RequireAuth>} />
              <Route path="analytics" element={<RequireAuth roles={['Admin']}><AnalyticsPage /></RequireAuth>} />
              {/* Visit details - Medical staff only (security fix - contains PHI) */}
              <Route path="visits/:id" element={<RequireAuth roles={['Admin', 'Doctor', 'Registrar', 'Receptionist', 'cardio', 'derma', 'dentist']}><VisitDetails /></RequireAuth>} />
              {/* Search - Medical staff only (security fix) */}
              <Route path="search" element={<RequireAuth roles={['Admin', 'Doctor', 'Registrar', 'Receptionist', 'cardio', 'derma', 'dentist']}><Search /></RequireAuth>} />

              {/* Интегрированные скрытые компоненты */}
              <Route path="advanced-users" element={<RequireAuth roles={['Admin']}><UserManagement /></RequireAuth>} />
              <Route path="advanced-emr" element={<RequireAuth roles={['Admin', 'Doctor', 'Nurse']}><EMRInterface /></RequireAuth>} />
              {/* EMR Demo - Medical staff only (security fix - contains PHI) */}
              <Route path="emr-demo" element={<RequireAuth roles={['Admin', 'Doctor', 'cardio', 'derma', 'dentist']}><EMRDemo /></RequireAuth>} />
              <Route path="file-management" element={<RequireAuth roles={['Admin', 'Doctor', 'Nurse']}><FileManager /></RequireAuth>} />
              <Route path="notifications" element={<RequireAuth roles={['Admin']}><EmailSMSManager /></RequireAuth>} />
              <Route path="telegram-integration" element={<RequireAuth roles={['Admin']}><TelegramManager /></RequireAuth>} />
              <Route path="security-settings" element={<RequireAuth roles={['Admin', 'Doctor', 'Nurse']}><TwoFactorManager /></RequireAuth>} />

              {/* Демо интеграции - Admin only (security fix) */}
              <Route path="integration-demo" element={<RequireAuth roles={['Admin']}><IntegrationDemo /></RequireAuth>} />

              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Route>
        </Routes>
      </Suspense>
    </>
  );
}

// Основной компонент App
export default function App() {
  return (
    <MacOSThemeProvider>
      <ThemeProvider>
        <AppProviders>
          <AppContent />
        </AppProviders>
      </ThemeProvider>
    </MacOSThemeProvider>
  );
}

const macOSWrapStyle = {
  fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
  background: 'var(--mac-gradient-window)',
  minHeight: '100vh',
  color: 'var(--mac-text-primary)',
  width: '100%',
  margin: 0,
  padding: 0,
  boxSizing: 'border-box',
  display: 'flex',
  flexDirection: 'column'
};

const macOSMainStyle = {
  flex: 1,
  maxWidth: '100%', // Убираем фиксированную ширину, позволяем CSS Grid управлять размером
  margin: '0', // Убираем центрирование, так как CSS Grid управляет позиционированием
  width: '100%',
  minWidth: 0, // Добавляем minWidth для правильной работы flex
  boxSizing: 'border-box',
  overflow: 'auto'
};
