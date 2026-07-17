// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { lazy, Suspense, useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { ToastContainer } from 'react-toastify';
import { SpeedInsights } from '@vercel/speed-insights/react';
import { AppProviders } from './providers/AppProviders';
import { ThemeProvider, useTheme } from './contexts/ThemeContext';
import './styles/theme.css';
import './styles/dark-theme-visibility-fix.css';
import './styles/global-fixes.css';
import './theme/macos-tokens.css';
import './styles/macos.css';
import './styles/header-new.css';
import 'react-toastify/dist/ReactToastify.css';
import { MacOSThemeProvider } from './theme/macosTheme.jsx';
import { bootstrapStoredColorScheme } from './theme/colorScheme.js';
import {
  Sidebar,
} from './components/ui/macos';
import HeaderNew from './components/layout/HeaderNew.jsx';
// SW-05 fix: global command palette (Cmd+K)
import { CommandPalette } from './components/common/CommandPalette';
import GlobalNotificationCenter from './components/notifications/GlobalNotificationCenter.jsx';
import Health from './pages/Health.jsx';
import Landing from './pages/Landing.jsx';
import LoginFormStyled from './components/auth/LoginFormStyled.jsx';
import Setup from './pages/Setup.jsx';
import { useSetupStatus } from './hooks/useSetupStatus.js';
import { useBreakpoint } from './hooks/useEnhancedMediaQuery.js';
import auth from './stores/auth.js';
import { ROUTE_REGISTRY } from './routing/routeRegistry.js';
import { ForbiddenPage, LegacyRouteRedirect, NotFoundPage, RouteAccessBoundary, UnauthorizedPage, resolveSetupRedirect } from './routing/routeGuards.jsx';
import { getRouteChromeState } from './routing/routeSelectors.js';
import { sanitizeSpeedInsightsEvent } from './utils/speedInsightsPrivacy.js';

bootstrapStoredColorScheme();

const beforeSendSpeedInsights = (event) => sanitizeSpeedInsightsEvent(event, ROUTE_REGISTRY);

const CashierPanel = lazy(() => import('./pages/CashierPanel.jsx'));
const Settings = lazy(() => import('./pages/Settings.jsx'));
const Audit = lazy(() => import('./pages/Audit.jsx'));
const Scheduler = lazy(() => import('./pages/Scheduler.jsx'));
const Appointments = lazy(() => import('./pages/Appointments.jsx'));
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
const CSSTestPage = lazy(() => import('./pages/CSSTestPage.jsx'));
const PaymentSuccess = lazy(() => import('./pages/PaymentSuccess.jsx'));
const PaymentCancel = lazy(() => import('./pages/PaymentCancel.jsx'));
const PaymentTest = lazy(() => import('./pages/PaymentTest.jsx'));
const MacOSDemoPage = lazy(() => import('./pages/MacOSDemoPage.jsx'));
const ChangePasswordRequired = lazy(() => import('./pages/auth/ChangePasswordRequired.jsx'));
const PatientPickupView = lazy(() => import('./pages/PatientPickupView.jsx'));
const UserProfile = lazy(() => import('./pages/UserProfile.jsx'));
// SW-01 fix: removed ButtonShowcase (dead code, components/buttons/ deleted)
const TelegramManager = lazy(() => import('./components/TelegramManager.jsx'));
const TelegramMiniAppPatientShell = lazy(() => import('./pages/TelegramMiniAppPatientShell.jsx'));
const TelegramSettings = lazy(() => import('./components/admin/TelegramSettings.jsx'));
const AISettings = lazy(() => import('./components/admin/AISettings.jsx'));
const PhoneVerificationManager = lazy(() => import('./components/admin/PhoneVerificationManager.jsx'));
const ActivationSystem = lazy(() => import('./components/admin/ActivationSystem.jsx'));
const AdminDashboard = lazy(() => import('./components/admin/AdminDashboard.jsx'));
const ClinicManagement = lazy(() => import('./components/admin/ClinicManagement.jsx'));
const QueueCabinetManagement = lazy(() => import('./components/admin/QueueCabinetManagement.jsx'));
const AdminDoctors = lazy(() => import('./components/admin/AdminDoctors.jsx'));
const AdminPatients = lazy(() => import('./components/admin/AdminPatients.jsx'));
const AdminAppointments = lazy(() => import('./components/admin/AdminAppointments.jsx'));
const AdminServices = lazy(() => import('./components/admin/AdminServices.jsx'));
const UnifiedFinance = lazy(() => import('./components/admin/UnifiedFinance.jsx'));
const UnifiedSettings = lazy(() => import('./components/admin/UnifiedSettings.jsx'));
const SystemManagement = lazy(() => import('./components/admin/SystemManagement.jsx'));
const CloudPrintingManager = lazy(() => import('./components/admin/CloudPrintingManager.jsx'));
const MedicalEquipmentManager = lazy(() => import('./components/admin/MedicalEquipmentManager.jsx'));
const WebhookManager = lazy(() => import('./components/admin/WebhookManager.jsx'));
const GraphQLExplorer = lazy(() => import('./components/admin/GraphQLExplorer.jsx'));
const UnifiedReports = lazy(() => import('./components/admin/UnifiedReports.jsx'));
const UnifiedNotifications = lazy(() => import('./components/admin/UnifiedNotifications.jsx'));
const UnifiedIntegrations = lazy(() => import('./components/admin/UnifiedIntegrations.jsx'));
const EmailSMSManager = lazy(() => import('./components/notifications/EmailSMSManager.jsx'));
const FileManager = lazy(() => import('./components/files/FileManager.jsx'));
const UnifiedUserManagement = lazy(() => import('./components/admin/UnifiedUserManagement.jsx'));
const AllFreeApproval = lazy(() => import('./components/admin/AllFreeApproval.jsx'));
const IntegrationDemo = lazy(() => import('./components/integration/IntegrationDemo.jsx'));

const ROUTE_COMPONENTS = {
  Landing,
  LoginFormStyled,
  ChangePasswordRequired,
  Health,
  QueueJoin,
  PaymentSuccess,
  PaymentCancel,
  DisplayBoardUnified,
  Setup,
  AnalyticsPage,
  Settings,
  Audit,
  TelegramManager,
  EmailSMSManager,
  UnifiedUserManagement,
  AllFreeApproval,
  FileManager,
  UserSelect,
  RegistrarPanel,
  DoctorPanel,
  CashierPanel,
  LabPanel,
  PatientPanel,
  CardiologistPanelUnified,
  DermatologistPanelUnified,
  DentistPanelUnified,
  Scheduler,
  Appointments,
  Search,
  UserProfile,
  PatientPickupView,
  MediLabDemo,
  MacOSDemoPage,
  IntegrationDemo,
  PaymentTest,
  CSSTestPage,
  // SW-01: ButtonShowcase removed (dead code)
  TelegramMiniAppPatientShell,
  TelegramSettings,
  AISettings,
  PhoneVerificationManager,
  ActivationSystem,
  AdminDashboard,
  ClinicManagement,
  QueueCabinetManagement,
  AdminDoctors,
  AdminPatients,
  AdminAppointments,
  AdminServices,
  UnifiedFinance,
  UnifiedSettings,
  SystemManagement,
  CloudPrintingManager,
  MedicalEquipmentManager,
  WebhookManager,
  GraphQLExplorer,
  UnifiedReports,
  UnifiedNotifications,
  UnifiedIntegrations,
  UnauthorizedPage,
  ForbiddenPage,
  NotFoundPage,
};

function LoadingScreen() {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', fontSize: 'var(--mac-font-size-xl)' }}>
      Загрузка...
    </div>
  );
}

function AppShell({ children }) {
  const location = useLocation();
  const navigate = useNavigate();
  const { theme } = useTheme();
  const { isMobile } = useBreakpoint();
  const [authState, setAuthState] = useState(() => auth.getState());
  const chrome = getRouteChromeState(location.pathname, location.search, authState.profile);
  const compactSidebar = isMobile && !chrome.hideSidebar;

  // P-018 fix: allow mobile users to expand the sidebar via a hamburger toggle.
  // Previously App.jsx:225 set collapsible={!compactSidebar} which hard-disabled
  // expand on mobile — leaving users to tap icons with no visible labels.
  // mobileSidebarExpanded now lets the user toggle the sidebar open/closed on
  // narrow viewports; auto-collapse on route change for predictability.
  const [mobileSidebarExpanded, setMobileSidebarExpanded] = useState(false);

  // Auto-collapse the expanded mobile sidebar whenever the route changes,
  // so navigating to a new section doesn't leave the sidebar blocking content.
  useEffect(() => {
    setMobileSidebarExpanded(false);
  }, [location.pathname, location.search]);

  useEffect(() => auth.subscribe(setAuthState), []);

  const handleSidebarClick = (item) => {
    if (chrome.sidebarPreset?.navigation === 'query') {
      const params = new URLSearchParams(location.search);
      params.set(chrome.sidebarPreset.queryParam, item.id);
      navigate({ pathname: location.pathname, search: `?${params.toString()}` });
      // Collapse after navigation on mobile
      if (compactSidebar) setMobileSidebarExpanded(false);
      return;
    }

    if (item.to) {
      navigate(item.to);
      if (compactSidebar) setMobileSidebarExpanded(false);
    }
  };

  return (
    <div className="app-shell" style={macOSWrapStyle} data-route-id={chrome.route?.id || 'unknown'}>
      {/* PR-49: skip-to-content link for keyboard users — bypasses header + sidebar */}
      <a
        href="#main-content"
        className="skip-to-content-link"
        style={{
          position: 'absolute',
          top: '-100px',
          left: '8px',
          zIndex: 9999,
          padding: '8px 16px',
          backgroundColor: 'var(--mac-accent-blue, #007aff)',
          color: '#fff',
          borderRadius: 'var(--mac-radius-md)',
          textDecoration: 'none',
          fontSize: '14px',
          fontWeight: 600,
          transition: 'top 200ms ease',
        }}
        onFocus={(e) => { e.currentTarget.style.top = '8px'; }}
        onBlur={(e) => { e.currentTarget.style.top = '-100px'; }}
      >
        Перейти к содержимому
      </a>
      {!chrome.hideHeader && (
        <div style={{ padding: 'var(--mac-spacing-3)', backgroundColor: 'transparent', width: '100%', maxWidth: '100%' }}>
          <HeaderNew />
        </div>
      )}

      <div
        className="app-shell-grid"
        style={{
          display: 'grid',
          // P-018 fix: when mobile sidebar is expanded, give it the full
          // expanded width (220px) instead of the 72px compact column.
          gridTemplateColumns: chrome.hideSidebar ? '1fr' : (compactSidebar && !mobileSidebarExpanded) ? '72px minmax(0, 1fr)' : (compactSidebar && mobileSidebarExpanded) ? '220px minmax(0, 1fr)' : 'auto minmax(0, 1fr)',
          gap: compactSidebar ? '8px' : '16px',
          flex: 1,
          minHeight: 0,
          width: '100%',
          maxWidth: '100%',
          overflowX: 'hidden',
          overflowY: 'auto',
          padding: chrome.hideHeader ? '0' : '0 0 16px 0',
        }}
      >
        {!chrome.hideSidebar && (
          <div style={{ marginTop: '0', marginLeft: compactSidebar ? '4px' : '12px', minWidth: 0, position: 'relative' }}>
            {/* P-018 fix: hamburger toggle button visible only on mobile, lets
                the user expand the sidebar to see labels (previously impossible
                because collapsible was hard-disabled on compactSidebar). */}
            {compactSidebar && (
              <button
                type="button"
                onClick={() => setMobileSidebarExpanded((v) => !v)}
                aria-label={mobileSidebarExpanded ? 'Свернуть меню' : 'Развернуть меню'}
                aria-expanded={mobileSidebarExpanded}
                title={mobileSidebarExpanded ? 'Свернуть меню' : 'Развернуть меню'}
                style={{
                  position: 'absolute',
                  top: '8px',
                  right: '8px',
                  zIndex: 10,
                  width: '28px',
                  height: '28px',
                  borderRadius: 'var(--mac-radius-md)',
                  border: '1px solid var(--mac-border, rgba(0,0,0,0.1))',
                  backgroundColor: 'var(--mac-bg-secondary, rgba(0,0,0,0.04))',
                  color: 'var(--mac-text-primary)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  padding: 0,
                }}
              >
                {/* Inline hamburger / chevron icon (3 horizontal lines when collapsed, X when expanded) */}
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
                  {mobileSidebarExpanded ? (
                    <>
                      <line x1="3" y1="3" x2="11" y2="11" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                      <line x1="11" y1="3" x2="3" y2="11" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                    </>
                  ) : (
                    <>
                      <line x1="2" y1="4" x2="12" y2="4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                      <line x1="2" y1="7" x2="12" y2="7" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                      <line x1="2" y1="10" x2="12" y2="10" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                    </>
                  )}
                </svg>
              </button>
            )}
            <Sidebar
              items={chrome.sidebarItems}
              // P-010 fix: pass sectioned structure to Sidebar for grouped rendering.
              sections={chrome.sidebarSections}
              activeItem={chrome.activeSidebarItem}
              onItemClick={handleSidebarClick}
              // When mobile+expanded → show full sidebar (labels visible).
              // When mobile+collapsed → compact icons-only (default).
              // When desktop → defer to Sidebar's internal collapse logic.
              collapsed={compactSidebar ? !mobileSidebarExpanded : undefined}
              defaultCollapsed={compactSidebar ? !mobileSidebarExpanded : undefined}
              collapsible={!compactSidebar}
            />
          </div>
        )}

        {/* PR-49: mobile sidebar overlay — when sidebar is expanded on mobile,
            render a semi-transparent backdrop that closes the sidebar on click.
            Previously the sidebar pushed content right (no overlay), which is
            non-standard and makes it hard to dismiss on touch devices. */}
        {compactSidebar && mobileSidebarExpanded && (
          <div
            onClick={() => setMobileSidebarExpanded(false)}
            onKeyDown={(e) => { if (e.key === 'Escape' || e.key === 'Enter') setMobileSidebarExpanded(false); }}
            aria-label="Закрыть меню"
            role="button"
            tabIndex={-1}
            style={{
              position: 'fixed',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              backgroundColor: 'rgba(0, 0, 0, 0.4)',
              zIndex: 5,
              cursor: 'pointer',
            }}
          />
        )}

        <main
          id="main-content"
          className={`app-main${chrome.hideSidebar || chrome.fullscreen ? ' app-main--frameless' : ''}`}
          style={{
            ...macOSMainStyle,
            ...(theme === 'light' && { boxShadow: 'none' }),
            ...(chrome.hideSidebar && {
              background: 'transparent',
              border: 'none',
              borderRadius: 0,
              boxShadow: 'none',
              maxWidth: 'none',
              margin: 0,
              padding: 0,
            }),
            ...(chrome.fullscreen && {
              maxWidth: 'none',
              margin: 0,
              border: 'none',
              borderRadius: 0,
              boxShadow: 'none',
              background: 'transparent',
              padding: 0,
            }),
          }}
        >
          {children}
        </main>
      </div>
      {/* SW-05 fix: global command palette — Cmd+K / Ctrl+K to open */}
      <CommandPalette profile={authState.profile} navigate={navigate} />
      {/* Global notification center — controlled by header bell via context */}
      <GlobalNotificationCenter />
    </div>
  );
}

AppShell.propTypes = {
  children: PropTypes.node,
};

function RouteRenderer({ route }) {
  const Component = ROUTE_COMPONENTS[route.component];

  if (!Component) {
    return <NotFoundPage />;
  }

  let element = <Component />;
  element = <RouteAccessBoundary route={route}>{element}</RouteAccessBoundary>;

  if (route.shell === 'app-shell') {
    element = <AppShell>{element}</AppShell>;
  }

  return element;
}

RouteRenderer.propTypes = {
  route: PropTypes.shape({
    id: PropTypes.string.isRequired,
    component: PropTypes.string.isRequired,
    shell: PropTypes.string,
  }).isRequired,
};

function AppContent() {
  const location = useLocation();
  const setupStatus = useSetupStatus();

  if (setupStatus.isLoading && location.pathname !== '/health') {
    return <LoadingScreen />;
  }

  if (!setupStatus.error) {
    const redirectTarget = resolveSetupRedirect(location.pathname, setupStatus.initialized);
    if (redirectTarget && redirectTarget !== location.pathname) {
      return <Navigate to={redirectTarget} replace />;
    }
  }

  return (
    <>
      <Suspense fallback={<LoadingScreen />}>
        <Routes>
          {ROUTE_REGISTRY.map((route) => (
            <Route
              key={route.id}
              path={route.path}
              element={<RouteRenderer route={route} />}
            />
          ))}

          {ROUTE_REGISTRY.flatMap((route) =>
            (route.legacyRedirectFrom || []).map((legacyPath) => (
              <Route
                key={`${route.id}:${legacyPath}`}
                path={legacyPath}
                element={<LegacyRouteRedirect />}
              />
            ))
          )}

          <Route path="*" element={<Navigate to="/not-found" replace />} />
        </Routes>
      </Suspense>
    </>
  );
}

export default function App() {
  return (
    <MacOSThemeProvider>
      <ThemeProvider>
        <AppProviders>
          <AppContent />
          <ToastContainer
            position="bottom-right"
            autoClose={4000}
            newestOnTop
            closeOnClick
            pauseOnHover
            draggable
            theme="colored"
          />
          <SpeedInsights beforeSend={beforeSendSpeedInsights} />
        </AppProviders>
      </ThemeProvider>
    </MacOSThemeProvider>
  );
}

const macOSWrapStyle = {
  fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
  background: 'transparent',
  minHeight: '100vh',
  color: 'var(--mac-text-primary)',
  width: '100%',
  margin: 0,
  padding: 0,
  boxSizing: 'border-box',
  display: 'flex',
  flexDirection: 'column',
};

const macOSMainStyle = {
  flex: 1,
  maxWidth: '100%',
  margin: 0,
  width: '100%',
  minWidth: 0,
  boxSizing: 'border-box',
  overflow: 'auto',
  position: 'relative',
  isolation: 'isolate',
};
