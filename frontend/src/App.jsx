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
import { Sidebar } from './components/ui/macos';
import HeaderNew from './components/layout/HeaderNew.jsx';
import Health from './pages/Health.jsx';
import Landing from './pages/Landing.jsx';
import LoginFormStyled from './components/auth/LoginFormStyled.jsx';
import Setup from './pages/Setup.jsx';
import { useSetupStatus } from './hooks/useSetupStatus.js';
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
const VisitDetails = lazy(() => import('./pages/VisitDetails.jsx'));
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
const SecurityPage = lazy(() => import('./pages/SecurityPage.jsx'));
const ChangePasswordRequired = lazy(() => import('./pages/auth/ChangePasswordRequired.jsx'));
const PatientPickupView = lazy(() => import('./pages/PatientPickupView.jsx'));
const UserProfile = lazy(() => import('./pages/UserProfile.jsx'));
const ButtonShowcase = lazy(() => import('./components/buttons/ButtonShowcase.jsx'));
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
const EmailSMSManager = lazy(() => import('./components/notifications/EmailSMSManager.jsx'));
const TwoFactorManager = lazy(() => import('./components/security/TwoFactorManager.jsx'));
const FileManager = lazy(() => import('./components/files/FileManager.jsx'));
const AdvancedUserManagement = lazy(() => import('./components/admin/AdvancedUserManagement.jsx'));
const UserManagement = lazy(() => import('./components/admin/UserManagement.jsx'));
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
  AdvancedUserManagement,
  UserManagement,
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
  SecurityPage,
  TwoFactorManager,
  VisitDetails,
  PatientPickupView,
  MediLabDemo,
  MacOSDemoPage,
  IntegrationDemo,
  PaymentTest,
  CSSTestPage,
  ButtonShowcase,
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
  UnauthorizedPage,
  ForbiddenPage,
  NotFoundPage,
};

function LoadingScreen() {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', fontSize: '18px' }}>
      Загрузка...
    </div>
  );
}

function AppShell({ children }) {
  const location = useLocation();
  const navigate = useNavigate();
  const { theme } = useTheme();
  const [authState, setAuthState] = useState(() => auth.getState());
  const chrome = getRouteChromeState(location.pathname, location.search, authState.profile);

  useEffect(() => auth.subscribe(setAuthState), []);

  const handleSidebarClick = (item) => {
    if (chrome.sidebarPreset?.navigation === 'query') {
      const params = new URLSearchParams(location.search);
      params.set(chrome.sidebarPreset.queryParam, item.id);
      navigate({ pathname: location.pathname, search: `?${params.toString()}` });
      return;
    }

    if (item.to) {
      navigate(item.to);
    }
  };

  return (
    <div className="app-shell" style={macOSWrapStyle} data-route-id={chrome.route?.id || 'unknown'}>
      {!chrome.hideHeader && (
        <div style={{ padding: '12px', backgroundColor: 'transparent', width: '100%', maxWidth: '100%' }}>
          <HeaderNew />
        </div>
      )}

      <div
        className="app-shell-grid"
        style={{
          display: 'grid',
          gridTemplateColumns: chrome.hideSidebar ? '1fr' : 'auto 1fr',
          gap: '16px',
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
          <div style={{ marginTop: '0', marginLeft: '12px' }}>
            <Sidebar
              items={chrome.sidebarItems}
              activeItem={chrome.activeSidebarItem}
              onItemClick={handleSidebarClick}
              defaultCollapsed={false}
              collapsible
            />
          </div>
        )}

        <main
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
