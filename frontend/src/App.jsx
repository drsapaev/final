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
import { Alert, Badge, Button, Card, CardContent, Input, Sidebar, Textarea } from './components/ui/macos';
import HeaderNew from './components/layout/HeaderNew.jsx';
import Health from './pages/Health.jsx';
import Landing from './pages/Landing.jsx';
import LoginFormStyled from './components/auth/LoginFormStyled.jsx';
import Setup from './pages/Setup.jsx';
import { useSetupStatus } from './hooks/useSetupStatus.js';
import { api } from './api/client.js';
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
const EmailSMSManager = lazy(() => import('./components/notifications/EmailSMSManager.jsx'));
const TwoFactorManager = lazy(() => import('./components/security/TwoFactorManager.jsx'));
const FileManager = lazy(() => import('./components/files/FileManager.jsx'));
const UserManagement = lazy(() => import('./components/admin/UserManagement.jsx'));
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
  AdminPanel,
  AnalyticsPage,
  Settings,
  Audit,
  TelegramManager,
  EmailSMSManager,
  UserManagement,
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

const MINI_APP_CAPABILITY_LABELS = {
  appointments: 'Запись',
  forms: 'Анкеты',
  cabinet: 'Кабинет',
  payments: 'Оплаты',
  results: 'Результаты',
};

const MINI_APP_SECTION_ALIASES = {
  appointments: 'appointments',
  doctors: 'appointments',
  forms: 'forms',
  cabinet: 'cabinet',
  payments: 'payments',
  results: 'results',
  documents: 'results',
};

function getTelegramMiniAppInitData() {
  if (typeof window === 'undefined') {
    return '';
  }

  return window.Telegram?.WebApp?.initData || '';
}

function getTelegramMiniAppEntryToken(search) {
  const token = new URLSearchParams(search || '').get('entryToken') || '';
  return token.trim();
}

function getTelegramMiniAppAuthPayload(search, section) {
  const initData = getTelegramMiniAppInitData();
  const selectedSection = section || getTelegramMiniAppSelectedSection(search);
  if (initData) {
    return {
      initData,
      section: selectedSection || undefined,
    };
  }

  const entryToken = getTelegramMiniAppEntryToken(search);
  if (entryToken) {
    return {
      entryToken,
      section: selectedSection || undefined,
    };
  }

  return null;
}

function getTelegramMiniAppSelectedSection(search) {
  const section = new URLSearchParams(search || '').get('section') || '';
  return MINI_APP_SECTION_ALIASES[section.trim().toLowerCase()] || '';
}

function getDefaultMiniAppAppointmentDate() {
  const nextDay = new Date();
  nextDay.setDate(nextDay.getDate() + 1);
  const year = nextDay.getFullYear();
  const month = String(nextDay.getMonth() + 1).padStart(2, '0');
  const day = String(nextDay.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function createMiniAppAppointmentPreviewForm() {
  return {
    appointmentDate: getDefaultMiniAppAppointmentDate(),
    appointmentTime: '09:30',
    department: '',
    notes: '',
  };
}

function isMiniAppCapabilityEnabled(capability) {
  return Boolean(
    capability?.create_enabled ||
    capability?.preview_enabled ||
    capability?.read_enabled ||
    capability?.view_enabled ||
    capability?.capture_enabled ||
    capability?.payment_capture_enabled
  );
}

function notifyTelegramMiniAppReady() {
  if (typeof window === 'undefined') {
    return;
  }

  const webApp = window.Telegram?.WebApp;
  if (!webApp) {
    return;
  }

  try {
    webApp.ready?.();
    webApp.expand?.();
  } catch {
    // Telegram WebApp helpers are best-effort browser hints.
  }
}

function TelegramMiniAppPatientShell() {
  const location = useLocation();
  const selectedSection = getTelegramMiniAppSelectedSection(location.search);
  const [state, setState] = useState({
    status: 'checking',
    manifest: null,
    error: null,
  });
  const [appointmentPreviewForm, setAppointmentPreviewForm] = useState(createMiniAppAppointmentPreviewForm);
  const [appointmentPreview, setAppointmentPreview] = useState({
    status: 'idle',
    payload: null,
    error: null,
  });
  const [cabinetSummary, setCabinetSummary] = useState({
    status: 'idle',
    payload: null,
    error: null,
  });

  useEffect(() => {
    let isMounted = true;
    notifyTelegramMiniAppReady();

    const authPayload = getTelegramMiniAppAuthPayload(location.search, selectedSection);
    setCabinetSummary({
      status: selectedSection === 'cabinet' && authPayload ? 'loading' : 'idle',
      payload: null,
      error: null,
    });

    if (!authPayload) {
      setState({
        status: 'unavailable',
        manifest: null,
        error: null,
      });
      return () => {
        isMounted = false;
      };
    }

    api.post('/telegram/mini-app/patient/manifest', authPayload)
      .then((response) => {
        if (!isMounted) return;
        setState({
          status: 'ready',
          manifest: response.data,
          error: null,
        });
        if (selectedSection === 'cabinet') {
          return api.post('/telegram/mini-app/cabinet/summary', authPayload)
            .then((summaryResponse) => {
              if (!isMounted) return;
              setCabinetSummary({
                status: 'ready',
                payload: summaryResponse.data,
                error: null,
              });
            });
        }
        return null;
      })
      .catch(() => {
        if (!isMounted) return;
        setCabinetSummary({
          status: selectedSection === 'cabinet' ? 'error' : 'idle',
          payload: null,
          error: 'Кабинет пациента не загрузился. Откройте ссылку заново из Telegram.',
        });
        setState({
          status: 'error',
          manifest: null,
          error: 'Сессия Mini App не подтверждена',
        });
      });

    return () => {
      isMounted = false;
    };
  }, [location.search, selectedSection]);

  const capabilities = state.manifest?.capabilities || {};
  const capabilityEntries = Object.entries(MINI_APP_CAPABILITY_LABELS);
  const selectedCapability = selectedSection ? capabilities[selectedSection] || {} : null;
  const selectedCapabilityEnabled = isMiniAppCapabilityEnabled(selectedCapability);
  const canPreviewAppointments = Boolean(
    selectedSection === 'appointments' &&
    selectedCapability?.preview_enabled
  );

  const handleAppointmentPreviewFieldChange = (field) => (event) => {
    setAppointmentPreviewForm((current) => ({
      ...current,
      [field]: event.target.value,
    }));
  };

  const handleAppointmentPreviewSubmit = (event) => {
    event.preventDefault();

    const initData = getTelegramMiniAppInitData();
    if (!initData || !appointmentPreviewForm.appointmentDate) {
      setAppointmentPreview({
        status: 'error',
        payload: null,
        error: 'Укажите дату и откройте Mini App из Telegram.',
      });
      return;
    }

    const requestBody = {
      initData,
      appointmentDate: appointmentPreviewForm.appointmentDate,
      appointmentTime: appointmentPreviewForm.appointmentTime || undefined,
      department: appointmentPreviewForm.department.trim() || undefined,
      notes: appointmentPreviewForm.notes.trim() || undefined,
    };

    setAppointmentPreview({
      status: 'loading',
      payload: null,
      error: null,
    });

    api.post('/telegram/mini-app/appointments/preview', requestBody)
      .then((response) => {
        setAppointmentPreview({
          status: 'ready',
          payload: response.data,
          error: null,
        });
      })
      .catch((error) => {
        const reason = error?.response?.data?.detail?.reason || 'preview_failed';
        setAppointmentPreview({
          status: 'error',
          payload: null,
          error: `Черновик записи не подтвержден: ${reason}`,
        });
      });
  };

  const previewAppointment = appointmentPreview.payload?.appointment || null;

  return (
    <div style={miniAppPageStyle}>
      <main style={miniAppMainStyle}>
        <section style={miniAppHeroStyle}>
          <div>
            <p style={miniAppKickerStyle}>Kosmed Clinic</p>
            <h1 style={miniAppTitleStyle}>Mini App пациента</h1>
          </div>
          <Badge
            variant={state.status === 'ready' ? 'success' : 'secondary'}
            size="large"
            style={miniAppStatusBadgeStyle}
          >
            {state.status === 'ready' ? 'Сессия подтверждена' : 'Ожидание сессии'}
          </Badge>
        </section>

        {state.status === 'checking' && (
          <Alert severity="info" style={miniAppNoticeStyle}>Загрузка статуса...</Alert>
        )}

        {state.status === 'unavailable' && (
          <Alert severity="info" style={miniAppNoticeStyle}>
            Сессия Telegram недоступна. Данные пациента не загружаются.
          </Alert>
        )}

        {state.status === 'error' && (
          <Alert severity="error" style={miniAppNoticeStyle}>
            {state.error}
          </Alert>
        )}

        {state.status === 'ready' && (
          <>
            {selectedSection && (
              <Card padding="small" shadow="none" style={miniAppSelectedSectionStyle}>
                <CardContent style={miniAppSelectedSectionContentStyle}>
                  <div>
                    <p style={miniAppKickerStyle}>Открытый раздел</p>
                    <h2 style={miniAppSelectedSectionTitleStyle}>
                      {MINI_APP_CAPABILITY_LABELS[selectedSection]}
                    </h2>
                  </div>
                  <div style={miniAppSelectedSectionStatusStyle}>
                    <Badge
                      variant={selectedCapabilityEnabled ? 'primary' : 'secondary'}
                      size="small"
                    >
                      {selectedCapabilityEnabled ? 'Доступно' : 'Только статус'}
                    </Badge>
                    <p style={miniAppCapabilityTextStyle}>
                      {selectedCapability?.status || 'manifest_only'}
                    </p>
                  </div>
                </CardContent>
              </Card>
            )}

            {selectedSection === 'cabinet' && cabinetSummary.status === 'loading' && (
              <Alert severity="info" style={miniAppNoticeStyle}>
                Кабинет пациента загружается...
              </Alert>
            )}

            {selectedSection === 'cabinet' && cabinetSummary.status === 'error' && (
              <Alert severity="error" style={miniAppNoticeStyle}>
                {cabinetSummary.error}
              </Alert>
            )}

            {selectedSection === 'cabinet' && cabinetSummary.status === 'ready' && (
              <Card padding="small" shadow="none" style={miniAppAppointmentPreviewStyle}>
                <CardContent style={miniAppAppointmentPreviewContentStyle}>
                  <div style={miniAppAppointmentPreviewHeaderStyle}>
                    <div>
                      <p style={miniAppKickerStyle}>Пациент</p>
                      <h2 style={miniAppSelectedSectionTitleStyle}>
                        {cabinetSummary.payload?.patient?.name || 'Пациент'}
                      </h2>
                    </div>
                    <Badge variant="success" size="small">Доступ подтверждён</Badge>
                  </div>
                  <div style={miniAppAppointmentPreviewResultStyle}>
                    <div>
                      <p style={miniAppCapabilityTextStyle}>Визиты</p>
                      <strong>{cabinetSummary.payload?.visits?.length || 0}</strong>
                    </div>
                    <div>
                      <p style={miniAppCapabilityTextStyle}>Очередь</p>
                      <strong>{cabinetSummary.payload?.queue?.length || 0}</strong>
                    </div>
                    <div>
                      <p style={miniAppCapabilityTextStyle}>Долг</p>
                      <strong>{cabinetSummary.payload?.payments?.debt || '0'}</strong>
                    </div>
                    <div>
                      <p style={miniAppCapabilityTextStyle}>Результаты</p>
                      <strong>{cabinetSummary.payload?.reports?.length || 0}</strong>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {canPreviewAppointments && (
              <Card padding="small" shadow="none" style={miniAppAppointmentPreviewStyle}>
                <CardContent style={miniAppAppointmentPreviewContentStyle}>
                  <div style={miniAppAppointmentPreviewHeaderStyle}>
                    <div>
                      <p style={miniAppKickerStyle}>Предварительная проверка</p>
                      <h2 style={miniAppSelectedSectionTitleStyle}>Черновик записи</h2>
                    </div>
                    <Badge variant="secondary" size="small">Без создания</Badge>
                  </div>

                  <form style={miniAppAppointmentFormStyle} onSubmit={handleAppointmentPreviewSubmit}>
                    <div style={miniAppAppointmentFormGridStyle}>
                      <Input
                        type="date"
                        label="Дата"
                        value={appointmentPreviewForm.appointmentDate}
                        onChange={handleAppointmentPreviewFieldChange('appointmentDate')}
                        required
                        style={miniAppAppointmentInputStyle}
                      />
                      <Input
                        type="time"
                        label="Время"
                        value={appointmentPreviewForm.appointmentTime}
                        onChange={handleAppointmentPreviewFieldChange('appointmentTime')}
                        style={miniAppAppointmentInputStyle}
                      />
                      <Input
                        label="Отделение"
                        value={appointmentPreviewForm.department}
                        onChange={handleAppointmentPreviewFieldChange('department')}
                        placeholder="Опционально"
                        maxLength={64}
                        style={miniAppAppointmentInputStyle}
                      />
                    </div>
                    <Textarea
                      label="Заметка для регистратуры"
                      value={appointmentPreviewForm.notes}
                      onChange={handleAppointmentPreviewFieldChange('notes')}
                      placeholder="Без медицинских данных"
                      maxLength={1000}
                      minRows={2}
                    />
                    <Button
                      type="submit"
                      variant="primary"
                      size="small"
                      loading={appointmentPreview.status === 'loading'}
                      disabled={appointmentPreview.status === 'loading'}
                    >
                      Проверить черновик
                    </Button>
                  </form>

                  {appointmentPreview.status === 'error' && (
                    <Alert severity="error" style={miniAppNoticeStyle}>
                      {appointmentPreview.error}
                    </Alert>
                  )}

                  {appointmentPreview.status === 'ready' && previewAppointment && (
                    <div style={miniAppAppointmentPreviewResultStyle}>
                      <div>
                        <p style={miniAppCapabilityTextStyle}>Дата и время</p>
                        <strong>{previewAppointment.appointment_date} {previewAppointment.appointment_time || 'время не указано'}</strong>
                      </div>
                      <div>
                        <p style={miniAppCapabilityTextStyle}>Статус</p>
                        <strong>{previewAppointment.status}</strong>
                      </div>
                      <div>
                        <p style={miniAppCapabilityTextStyle}>Оплата</p>
                        <strong>{previewAppointment.payment_type} / {previewAppointment.payment_currency}</strong>
                      </div>
                      <Badge variant={appointmentPreview.payload?.mutation_allowed ? 'warning' : 'success'} size="small">
                        {appointmentPreview.payload?.preview_only ? 'Только предпросмотр' : 'Требует проверки'}
                      </Badge>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            <section style={miniAppGridStyle}>
              {capabilityEntries.map(([key, label]) => {
                const capability = capabilities[key] || {};
                const enabled = isMiniAppCapabilityEnabled(capability);
                const isSelected = key === selectedSection;
                return (
                  <Card
                    key={key}
                    padding="small"
                    shadow="none"
                    style={{
                      ...miniAppCapabilityStyle,
                      ...(isSelected ? miniAppCapabilitySelectedStyle : {}),
                    }}
                  >
                    <CardContent style={miniAppCapabilityContentStyle}>
                      <div style={miniAppCapabilityHeaderStyle}>
                        <h2 style={miniAppCapabilityTitleStyle}>{label}</h2>
                        <Badge variant={enabled ? 'primary' : 'secondary'} size="small">
                          {enabled ? 'Доступно' : 'Только статус'}
                        </Badge>
                      </div>
                      <p style={miniAppCapabilityTextStyle}>
                        {capability.status || 'manifest_only'}
                      </p>
                    </CardContent>
                  </Card>
                );
              })}
            </section>
          </>
        )}
      </main>
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

const miniAppPageStyle = {
  minHeight: '100vh',
  background: 'var(--mac-bg-page, #f5f7fb)',
  color: 'var(--mac-text-primary, #111827)',
  fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
};

const miniAppMainStyle = {
  width: '100%',
  maxWidth: '720px',
  margin: '0 auto',
  padding: '20px 16px 28px',
  boxSizing: 'border-box',
};

const miniAppHeroStyle = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'flex-start',
  gap: '16px',
  padding: '8px 0 18px',
};

const miniAppKickerStyle = {
  margin: '0 0 6px',
  fontSize: '13px',
  fontWeight: 700,
  color: 'var(--mac-text-secondary, #5f6b7a)',
};

const miniAppTitleStyle = {
  margin: 0,
  fontSize: '28px',
  lineHeight: 1.15,
  fontWeight: 800,
  color: 'var(--mac-text-primary, #111827)',
};

const miniAppStatusBadgeStyle = {
  flexShrink: 0,
  fontWeight: 700,
};

const miniAppNoticeStyle = {
  fontSize: '14px',
  lineHeight: 1.5,
};

const miniAppGridStyle = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(156px, 1fr))',
  gap: '12px',
};

const miniAppSelectedSectionStyle = {
  marginBottom: '12px',
  borderColor: 'rgba(23, 92, 211, 0.28)',
};

const miniAppSelectedSectionContentStyle = {
  display: 'flex',
  alignItems: 'flex-start',
  justifyContent: 'space-between',
  gap: '14px',
  flexWrap: 'wrap',
};

const miniAppSelectedSectionTitleStyle = {
  margin: 0,
  fontSize: '20px',
  lineHeight: 1.25,
  fontWeight: 800,
  color: 'var(--mac-text-primary, #111827)',
};

const miniAppSelectedSectionStatusStyle = {
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'flex-end',
  gap: '8px',
  minWidth: '128px',
};

const miniAppAppointmentPreviewStyle = {
  marginBottom: '12px',
  borderColor: 'rgba(52, 199, 89, 0.26)',
};

const miniAppAppointmentPreviewContentStyle = {
  display: 'flex',
  flexDirection: 'column',
  gap: '14px',
};

const miniAppAppointmentPreviewHeaderStyle = {
  display: 'flex',
  alignItems: 'flex-start',
  justifyContent: 'space-between',
  gap: '14px',
  flexWrap: 'wrap',
};

const miniAppAppointmentFormStyle = {
  display: 'flex',
  flexDirection: 'column',
  gap: '12px',
};

const miniAppAppointmentFormGridStyle = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
  gap: '12px',
};

const miniAppAppointmentInputStyle = {
  width: '100%',
  boxSizing: 'border-box',
};

const miniAppAppointmentPreviewResultStyle = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(132px, 1fr))',
  alignItems: 'center',
  gap: '12px',
  padding: '12px',
  border: '1px solid rgba(52, 199, 89, 0.24)',
  borderRadius: '8px',
  background: 'rgba(52, 199, 89, 0.08)',
  fontSize: '13px',
  color: 'var(--mac-text-primary, #111827)',
};

const miniAppCapabilityStyle = {
  minHeight: '128px',
};

const miniAppCapabilitySelectedStyle = {
  outline: '2px solid rgba(23, 92, 211, 0.18)',
  outlineOffset: '-2px',
};

const miniAppCapabilityContentStyle = {
  minHeight: '104px',
  boxSizing: 'border-box',
  display: 'flex',
  flexDirection: 'column',
  justifyContent: 'space-between',
  gap: '12px',
};

const miniAppCapabilityHeaderStyle = {
  display: 'flex',
  alignItems: 'flex-start',
  justifyContent: 'space-between',
  gap: '10px',
};

const miniAppCapabilityTitleStyle = {
  margin: 0,
  fontSize: '16px',
  lineHeight: 1.25,
  fontWeight: 750,
};

const miniAppCapabilityTextStyle = {
  margin: 0,
  fontSize: '13px',
  lineHeight: 1.4,
  color: 'var(--mac-text-secondary, #5f6b7a)',
  overflowWrap: 'anywhere',
};
