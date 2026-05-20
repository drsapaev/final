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

const MINI_APP_CAPABILITY_SAFETY_FLAGS = [
  ['contains_medical_data', 'medical data', 'no medical data'],
  ['contains_payment_provider_data', 'provider payloads', 'no provider payloads'],
  ['contains_passport_data', 'passport data', 'no passport data'],
  ['contains_billing_records', 'billing records', 'no billing records'],
  ['contains_amounts', 'amounts present', 'no amounts'],
  ['contains_payment_records', 'payment records', 'no payment records'],
  ['contains_provider_payloads', 'provider payloads', 'no provider payloads'],
  ['contains_medical_results', 'medical results', 'no medical results'],
  ['contains_lab_values', 'lab values', 'no lab values'],
  ['contains_report_records', 'report records', 'no report records'],
  ['contains_file_urls', 'file URLs', 'no file URLs'],
  ['contains_pdfs', 'PDFs present', 'no PDFs'],
  ['contains_diagnoses', 'diagnoses', 'no diagnoses'],
];

function getTelegramMiniAppInitData() {
  if (typeof window === 'undefined') {
    return '';
  }

  return window.Telegram?.WebApp?.initData || '';
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

function buildMiniAppAppointmentRequestBody(initData, form) {
  return {
    initData,
    appointmentDate: form.appointmentDate,
    appointmentTime: form.appointmentTime || undefined,
    department: form.department.trim() || undefined,
    notes: form.notes.trim() || undefined,
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

function getMiniAppCapabilitySafetyBadges(capability) {
  if (!capability) {
    return [];
  }

  return MINI_APP_CAPABILITY_SAFETY_FLAGS
    .filter(([key]) => Object.prototype.hasOwnProperty.call(capability, key))
    .map(([key, unsafeLabel, safeLabel]) => {
      const unsafe = Boolean(capability[key]);
      return {
        key,
        label: unsafe ? unsafeLabel : safeLabel,
        variant: unsafe ? 'warning' : 'success',
      };
    });
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
  const [appointmentCreate, setAppointmentCreate] = useState({
    status: 'idle',
    payload: null,
    error: null,
  });
  const [formsManifest, setFormsManifest] = useState({
    status: 'idle',
    payload: null,
    error: null,
  });
  const [cabinetManifest, setCabinetManifest] = useState({
    status: 'idle',
    payload: null,
    error: null,
  });
  const [paymentsManifest, setPaymentsManifest] = useState({
    status: 'idle',
    payload: null,
    error: null,
  });
  const [resultsManifest, setResultsManifest] = useState({
    status: 'idle',
    payload: null,
    error: null,
  });

  useEffect(() => {
    let isMounted = true;
    notifyTelegramMiniAppReady();

    const initData = getTelegramMiniAppInitData();
    if (!initData) {
      setState({
        status: 'unavailable',
        manifest: null,
        error: null,
      });
      return () => {
        isMounted = false;
      };
    }

    api.post('/telegram/mini-app/patient/manifest', { initData })
      .then((response) => {
        if (!isMounted) return;
        setState({
          status: 'ready',
          manifest: response.data,
          error: null,
        });
      })
      .catch(() => {
        if (!isMounted) return;
        setState({
          status: 'error',
          manifest: null,
          error: 'Сессия Mini App не подтверждена',
        });
      });

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    let isMounted = true;

    if (state.status !== 'ready' || selectedSection !== 'forms') {
      setFormsManifest({
        status: 'idle',
        payload: null,
        error: null,
      });
      return () => {
        isMounted = false;
      };
    }

    const initData = getTelegramMiniAppInitData();
    if (!initData) {
      setFormsManifest({
        status: 'error',
        payload: null,
        error: 'РЎРµСЃСЃРёСЏ Mini App РЅРµ РїРѕРґС‚РІРµСЂР¶РґРµРЅР°',
      });
      return () => {
        isMounted = false;
      };
    }

    setFormsManifest({
      status: 'loading',
      payload: null,
      error: null,
    });

    api.post('/telegram/mini-app/forms/manifest', { initData })
      .then((response) => {
        if (!isMounted) return;
        setFormsManifest({
          status: 'ready',
          payload: response.data,
          error: null,
        });
      })
      .catch((error) => {
        if (!isMounted) return;
        const reason = error?.response?.data?.detail?.reason || 'forms_manifest_failed';
        setFormsManifest({
          status: 'error',
          payload: null,
          error: `РђРЅРєРµС‚С‹ РЅРµ РґРѕСЃС‚СѓРїРЅС‹: ${reason}`,
        });
      });

    return () => {
      isMounted = false;
    };
  }, [selectedSection, state.status]);

  useEffect(() => {
    let isMounted = true;

    if (state.status !== 'ready' || selectedSection !== 'cabinet') {
      setCabinetManifest({
        status: 'idle',
        payload: null,
        error: null,
      });
      return () => {
        isMounted = false;
      };
    }

    const initData = getTelegramMiniAppInitData();
    if (!initData) {
      setCabinetManifest({
        status: 'error',
        payload: null,
        error: 'Mini App session is not confirmed.',
      });
      return () => {
        isMounted = false;
      };
    }

    setCabinetManifest({
      status: 'loading',
      payload: null,
      error: null,
    });

    api.post('/telegram/mini-app/cabinet/manifest', { initData })
      .then((response) => {
        if (!isMounted) return;
        setCabinetManifest({
          status: 'ready',
          payload: response.data,
          error: null,
        });
      })
      .catch((error) => {
        if (!isMounted) return;
        const reason = error?.response?.data?.detail?.reason || 'cabinet_manifest_failed';
        setCabinetManifest({
          status: 'error',
          payload: null,
          error: `Patient cabinet is unavailable: ${reason}`,
        });
      });

    return () => {
      isMounted = false;
    };
  }, [selectedSection, state.status]);

  useEffect(() => {
    let isMounted = true;

    if (state.status !== 'ready' || selectedSection !== 'payments') {
      setPaymentsManifest({
        status: 'idle',
        payload: null,
        error: null,
      });
      return () => {
        isMounted = false;
      };
    }

    const initData = getTelegramMiniAppInitData();
    if (!initData) {
      setPaymentsManifest({
        status: 'error',
        payload: null,
        error: 'Mini App session is not confirmed.',
      });
      return () => {
        isMounted = false;
      };
    }

    setPaymentsManifest({
      status: 'loading',
      payload: null,
      error: null,
    });

    api.post('/telegram/mini-app/payments/manifest', { initData })
      .then((response) => {
        if (!isMounted) return;
        setPaymentsManifest({
          status: 'ready',
          payload: response.data,
          error: null,
        });
      })
      .catch((error) => {
        if (!isMounted) return;
        const reason = error?.response?.data?.detail?.reason || 'payments_manifest_failed';
        setPaymentsManifest({
          status: 'error',
          payload: null,
          error: `Patient payments are unavailable: ${reason}`,
        });
      });

    return () => {
      isMounted = false;
    };
  }, [selectedSection, state.status]);

  useEffect(() => {
    let isMounted = true;

    if (state.status !== 'ready' || selectedSection !== 'results') {
      setResultsManifest({
        status: 'idle',
        payload: null,
        error: null,
      });
      return () => {
        isMounted = false;
      };
    }

    const initData = getTelegramMiniAppInitData();
    if (!initData) {
      setResultsManifest({
        status: 'error',
        payload: null,
        error: 'Mini App session is not confirmed.',
      });
      return () => {
        isMounted = false;
      };
    }

    setResultsManifest({
      status: 'loading',
      payload: null,
      error: null,
    });

    api.post('/telegram/mini-app/results/manifest', { initData })
      .then((response) => {
        if (!isMounted) return;
        setResultsManifest({
          status: 'ready',
          payload: response.data,
          error: null,
        });
      })
      .catch((error) => {
        if (!isMounted) return;
        const reason = error?.response?.data?.detail?.reason || 'results_manifest_failed';
        setResultsManifest({
          status: 'error',
          payload: null,
          error: `Patient results are unavailable: ${reason}`,
        });
      });

    return () => {
      isMounted = false;
    };
  }, [selectedSection, state.status]);

  const capabilities = state.manifest?.capabilities || {};
  const capabilityEntries = Object.entries(MINI_APP_CAPABILITY_LABELS);
  const selectedCapability = selectedSection ? capabilities[selectedSection] || {} : null;
  const selectedCapabilityEnabled = isMiniAppCapabilityEnabled(selectedCapability);
  const selectedCapabilitySafetyBadges = getMiniAppCapabilitySafetyBadges(selectedCapability);
  const canPreviewAppointments = Boolean(
    selectedSection === 'appointments' &&
    selectedCapability?.preview_enabled
  );
  const canShowFormsManifest = Boolean(
    selectedSection === 'forms' &&
    selectedCapability?.manifest_endpoint
  );
  const canShowCabinetManifest = Boolean(
    selectedSection === 'cabinet' &&
    selectedCapability?.manifest_endpoint
  );
  const canShowPaymentsManifest = Boolean(
    selectedSection === 'payments' &&
    selectedCapability?.manifest_endpoint
  );
  const canShowResultsManifest = Boolean(
    selectedSection === 'results' &&
    selectedCapability?.manifest_endpoint
  );

  const handleAppointmentPreviewFieldChange = (field) => (event) => {
    setAppointmentPreviewForm((current) => ({
      ...current,
      [field]: event.target.value,
    }));
    setAppointmentPreview({
      status: 'idle',
      payload: null,
      error: null,
    });
    setAppointmentCreate({
      status: 'idle',
      payload: null,
      error: null,
    });
  };

  const handleAppointmentPreviewSubmit = (event) => {
    event.preventDefault();

    const initData = getTelegramMiniAppInitData();
    if (!initData || !appointmentPreviewForm.appointmentDate) {
      setAppointmentPreview({
        status: 'error',
        payload: null,
        error: 'РЈРєР°Р¶РёС‚Рµ РґР°С‚Сѓ Рё РѕС‚РєСЂРѕР№С‚Рµ Mini App РёР· Telegram.',
      });
      return;
    }

    const requestBody = buildMiniAppAppointmentRequestBody(initData, appointmentPreviewForm);

    setAppointmentPreview({
      status: 'loading',
      payload: null,
      error: null,
    });
    setAppointmentCreate({
      status: 'idle',
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
          error: `Р§РµСЂРЅРѕРІРёРє Р·Р°РїРёСЃРё РЅРµ РїРѕРґС‚РІРµСЂР¶РґРµРЅ: ${reason}`,
        });
      });
  };

  const handleAppointmentCreate = () => {
    const initData = getTelegramMiniAppInitData();
    if (!initData || !appointmentPreviewForm.appointmentDate) {
      setAppointmentCreate({
        status: 'error',
        payload: null,
        error: 'Open Mini App from Telegram and preview the appointment date first.',
      });
      return;
    }

    const requestBody = buildMiniAppAppointmentRequestBody(initData, appointmentPreviewForm);

    setAppointmentCreate({
      status: 'loading',
      payload: null,
      error: null,
    });

    api.post('/telegram/mini-app/appointments', requestBody)
      .then((response) => {
        setAppointmentCreate({
          status: 'ready',
          payload: response.data,
          error: null,
        });
      })
      .catch((error) => {
        const reason = error?.response?.data?.detail?.reason || 'create_failed';
        setAppointmentCreate({
          status: 'error',
          payload: null,
          error: `Appointment was not created: ${reason}`,
        });
      });
  };

  const previewAppointment = appointmentPreview.payload?.appointment || null;
  const formsManifestItems = formsManifest.payload?.forms || [];
  const cabinetManifestSections = cabinetManifest.payload?.sections || [];
  const paymentsManifestSections = paymentsManifest.payload?.sections || [];
  const resultsManifestSections = resultsManifest.payload?.sections || [];

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
                    {selectedCapabilitySafetyBadges.length > 0 && (
                      <div style={miniAppSelectedSectionSafetyStyle}>
                        {selectedCapabilitySafetyBadges.map((badge) => (
                          <Badge key={badge.key} variant={badge.variant} size="small">
                            {badge.label}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}

            {canShowCabinetManifest && (
              <Card padding="small" shadow="none" style={miniAppCabinetManifestStyle}>
                <CardContent style={miniAppFormsManifestContentStyle}>
                  <div style={miniAppAppointmentPreviewHeaderStyle}>
                    <div>
                      <p style={miniAppKickerStyle}>Patient cabinet</p>
                      <h2 style={miniAppSelectedSectionTitleStyle}>Read-only status</h2>
                    </div>
                    <Badge variant="secondary" size="small">No records or edits</Badge>
                  </div>

                  {cabinetManifest.status === 'loading' && (
                    <Alert severity="info" style={miniAppNoticeStyle}>
                      Loading cabinet status...
                    </Alert>
                  )}

                  {cabinetManifest.status === 'error' && (
                    <Alert severity="error" style={miniAppNoticeStyle}>
                      {cabinetManifest.error}
                    </Alert>
                  )}

                  {cabinetManifest.status === 'ready' && (
                    <>
                      <div style={miniAppFormsSummaryStyle}>
                        <Badge variant={cabinetManifest.payload?.cabinet_enabled ? 'primary' : 'secondary'} size="small">
                          {cabinetManifest.payload?.cabinet_enabled ? 'cabinet on' : 'cabinet planned'}
                        </Badge>
                        <Badge variant="secondary" size="small">
                          {cabinetManifest.payload?.read_enabled ? 'read on' : 'read off'}
                        </Badge>
                        <Badge variant="secondary" size="small">
                          {cabinetManifest.payload?.mutation_enabled ? 'mutation on' : 'mutation off'}
                        </Badge>
                      </div>

                      <section style={miniAppFormsGridStyle}>
                        {cabinetManifestSections.map((section) => (
                          <div key={section.key || section.title} style={miniAppCabinetManifestItemStyle}>
                            <div>
                              <h3 style={miniAppFormManifestTitleStyle}>{section.title || section.key}</h3>
                              <p style={miniAppCapabilityTextStyle}>{section.status || 'planned'}</p>
                            </div>
                            <div style={miniAppFormManifestBadgeRowStyle}>
                              <Badge variant="secondary" size="small">
                                {section.read_enabled ? 'read on' : 'read off'}
                              </Badge>
                              <Badge variant="secondary" size="small">
                                {section.write_enabled ? 'write on' : 'write off'}
                              </Badge>
                              <Badge variant={section.contains_medical_data ? 'warning' : 'success'} size="small">
                                {section.contains_medical_data ? 'medical data' : 'no medical data'}
                              </Badge>
                              <Badge variant={section.contains_passport_data ? 'warning' : 'success'} size="small">
                                {section.contains_passport_data ? 'passport data' : 'no passport data'}
                              </Badge>
                              <Badge variant={section.contains_billing_records ? 'warning' : 'success'} size="small">
                                {section.contains_billing_records ? 'billing records' : 'no billing records'}
                              </Badge>
                            </div>
                          </div>
                        ))}
                      </section>
                    </>
                  )}
                </CardContent>
              </Card>
            )}

            {canShowPaymentsManifest && (
              <Card padding="small" shadow="none" style={miniAppPaymentsManifestStyle}>
                <CardContent style={miniAppFormsManifestContentStyle}>
                  <div style={miniAppAppointmentPreviewHeaderStyle}>
                    <div>
                      <p style={miniAppKickerStyle}>Patient payments</p>
                      <h2 style={miniAppSelectedSectionTitleStyle}>Manifest only</h2>
                    </div>
                    <Badge variant="secondary" size="small">No amounts or charges</Badge>
                  </div>

                  {paymentsManifest.status === 'loading' && (
                    <Alert severity="info" style={miniAppNoticeStyle}>
                      Loading payment status...
                    </Alert>
                  )}

                  {paymentsManifest.status === 'error' && (
                    <Alert severity="error" style={miniAppNoticeStyle}>
                      {paymentsManifest.error}
                    </Alert>
                  )}

                  {paymentsManifest.status === 'ready' && (
                    <>
                      <div style={miniAppFormsSummaryStyle}>
                        <Badge variant={paymentsManifest.payload?.payments_enabled ? 'primary' : 'secondary'} size="small">
                          {paymentsManifest.payload?.payments_enabled ? 'payments on' : 'payments planned'}
                        </Badge>
                        <Badge variant="secondary" size="small">
                          {paymentsManifest.payload?.read_enabled ? 'read on' : 'read off'}
                        </Badge>
                        <Badge variant="secondary" size="small">
                          {paymentsManifest.payload?.payment_capture_enabled ? 'capture on' : 'capture off'}
                        </Badge>
                        <Badge variant="secondary" size="small">
                          {paymentsManifest.payload?.provider_redirect_enabled ? 'provider redirect on' : 'provider redirect off'}
                        </Badge>
                        <Badge variant={paymentsManifest.payload?.contains_amounts ? 'warning' : 'success'} size="small">
                          {paymentsManifest.payload?.contains_amounts ? 'amounts present' : 'no amounts'}
                        </Badge>
                        <Badge variant={paymentsManifest.payload?.contains_payment_records ? 'warning' : 'success'} size="small">
                          {paymentsManifest.payload?.contains_payment_records ? 'payment records' : 'no payment records'}
                        </Badge>
                        <Badge variant={paymentsManifest.payload?.contains_provider_payloads ? 'warning' : 'success'} size="small">
                          {paymentsManifest.payload?.contains_provider_payloads ? 'provider payloads' : 'no provider payloads'}
                        </Badge>
                      </div>

                      <section style={miniAppFormsGridStyle}>
                        {paymentsManifestSections.map((section) => (
                          <div key={section.key || section.title} style={miniAppPaymentsManifestItemStyle}>
                            <div>
                              <h3 style={miniAppFormManifestTitleStyle}>{section.title || section.key}</h3>
                              <p style={miniAppCapabilityTextStyle}>{section.status || 'planned'}</p>
                            </div>
                            <div style={miniAppFormManifestBadgeRowStyle}>
                              <Badge variant="secondary" size="small">
                                {section.read_enabled ? 'read on' : 'read off'}
                              </Badge>
                              <Badge variant="secondary" size="small">
                                {section.payment_enabled ? 'payment on' : 'payment off'}
                              </Badge>
                              <Badge variant={section.contains_amounts ? 'warning' : 'success'} size="small">
                                {section.contains_amounts ? 'amounts present' : 'no amounts'}
                              </Badge>
                              <Badge variant={section.contains_payment_records ? 'warning' : 'success'} size="small">
                                {section.contains_payment_records ? 'payment records' : 'no payment records'}
                              </Badge>
                              <Badge variant={section.contains_provider_payloads ? 'warning' : 'success'} size="small">
                                {section.contains_provider_payloads ? 'provider payloads' : 'no provider payloads'}
                              </Badge>
                            </div>
                          </div>
                        ))}
                      </section>
                    </>
                  )}
                </CardContent>
              </Card>
            )}

            {canShowResultsManifest && (
              <Card padding="small" shadow="none" style={miniAppResultsManifestStyle}>
                <CardContent style={miniAppFormsManifestContentStyle}>
                  <div style={miniAppAppointmentPreviewHeaderStyle}>
                    <div>
                      <p style={miniAppKickerStyle}>Patient results</p>
                      <h2 style={miniAppSelectedSectionTitleStyle}>Manifest only</h2>
                    </div>
                    <Badge variant="secondary" size="small">No reports or files</Badge>
                  </div>

                  {resultsManifest.status === 'loading' && (
                    <Alert severity="info" style={miniAppNoticeStyle}>
                      Loading result status...
                    </Alert>
                  )}

                  {resultsManifest.status === 'error' && (
                    <Alert severity="error" style={miniAppNoticeStyle}>
                      {resultsManifest.error}
                    </Alert>
                  )}

                  {resultsManifest.status === 'ready' && (
                    <>
                      <div style={miniAppFormsSummaryStyle}>
                        <Badge variant={resultsManifest.payload?.results_enabled ? 'primary' : 'secondary'} size="small">
                          {resultsManifest.payload?.results_enabled ? 'results on' : 'results planned'}
                        </Badge>
                        <Badge variant="secondary" size="small">
                          {resultsManifest.payload?.view_enabled ? 'view on' : 'view off'}
                        </Badge>
                        <Badge variant="secondary" size="small">
                          {resultsManifest.payload?.download_enabled ? 'download on' : 'download off'}
                        </Badge>
                        <Badge variant={resultsManifest.payload?.contains_pdfs ? 'warning' : 'success'} size="small">
                          {resultsManifest.payload?.contains_pdfs ? 'PDFs present' : 'no PDFs'}
                        </Badge>
                      </div>

                      <section style={miniAppFormsGridStyle}>
                        {resultsManifestSections.map((section) => (
                          <div key={section.key || section.title} style={miniAppResultsManifestItemStyle}>
                            <div>
                              <h3 style={miniAppFormManifestTitleStyle}>{section.title || section.key}</h3>
                              <p style={miniAppCapabilityTextStyle}>{section.status || 'planned'}</p>
                            </div>
                            <div style={miniAppFormManifestBadgeRowStyle}>
                              <Badge variant="secondary" size="small">
                                {section.view_enabled ? 'view on' : 'view off'}
                              </Badge>
                              <Badge variant="secondary" size="small">
                                {section.download_enabled ? 'download on' : 'download off'}
                              </Badge>
                              <Badge variant={section.contains_medical_results ? 'warning' : 'success'} size="small">
                                {section.contains_medical_results ? 'medical results' : 'no medical results'}
                              </Badge>
                              <Badge variant={section.contains_lab_values ? 'warning' : 'success'} size="small">
                                {section.contains_lab_values ? 'lab values' : 'no lab values'}
                              </Badge>
                              <Badge variant={section.contains_report_records ? 'warning' : 'success'} size="small">
                                {section.contains_report_records ? 'report records' : 'no report records'}
                              </Badge>
                              <Badge variant={section.contains_file_urls ? 'warning' : 'success'} size="small">
                                {section.contains_file_urls ? 'file URLs' : 'no file URLs'}
                              </Badge>
                              <Badge variant={section.contains_diagnoses ? 'warning' : 'success'} size="small">
                                {section.contains_diagnoses ? 'diagnoses' : 'no diagnoses'}
                              </Badge>
                            </div>
                          </div>
                        ))}
                      </section>
                    </>
                  )}
                </CardContent>
              </Card>
            )}

            {canShowFormsManifest && (
              <Card padding="small" shadow="none" style={miniAppFormsManifestStyle}>
                <CardContent style={miniAppFormsManifestContentStyle}>
                  <div style={miniAppAppointmentPreviewHeaderStyle}>
                    <div>
                      <p style={miniAppKickerStyle}>Р—Р°С‰РёС‰РµРЅРЅС‹Рµ Р°РЅРєРµС‚С‹</p>
                      <h2 style={miniAppSelectedSectionTitleStyle}>РЎС‚Р°С‚СѓСЃ С„РѕСЂРј</h2>
                    </div>
                    <Badge variant="secondary" size="small">Р‘РµР· РІРІРѕРґР° РґР°РЅРЅС‹С…</Badge>
                  </div>

                  {formsManifest.status === 'loading' && (
                    <Alert severity="info" style={miniAppNoticeStyle}>
                      Р—Р°РіСЂСѓР·РєР° СЃС‚Р°С‚СѓСЃР° Р°РЅРєРµС‚...
                    </Alert>
                  )}

                  {formsManifest.status === 'error' && (
                    <Alert severity="error" style={miniAppNoticeStyle}>
                      {formsManifest.error}
                    </Alert>
                  )}

                  {formsManifest.status === 'ready' && (
                    <>
                      <div style={miniAppFormsSummaryStyle}>
                        <Badge variant={formsManifest.payload?.forms_enabled ? 'primary' : 'secondary'} size="small">
                          {formsManifest.payload?.forms_enabled ? 'РђРЅРєРµС‚С‹ РґРѕСЃС‚СѓРїРЅС‹' : 'РђРЅРєРµС‚С‹ РїРѕРєР° РїР»Р°РЅРёСЂСѓСЋС‚СЃСЏ'}
                        </Badge>
                        <Badge variant="secondary" size="small">
                          {formsManifest.payload?.capture_enabled ? 'Р’РІРѕРґ РІРєР»СЋС‡РµРЅ' : 'Р’РІРѕРґ РѕС‚РєР»СЋС‡РµРЅ'}
                        </Badge>
                        <Badge variant="secondary" size="small">
                          {formsManifest.payload?.submission_enabled ? 'РћС‚РїСЂР°РІРєР° РІРєР»СЋС‡РµРЅР°' : 'РћС‚РїСЂР°РІРєР° РѕС‚РєР»СЋС‡РµРЅР°'}
                        </Badge>
                      </div>

                      <section style={miniAppFormsGridStyle}>
                        {formsManifestItems.map((form) => (
                          <div key={form.key || form.title} style={miniAppFormManifestItemStyle}>
                            <div>
                              <h3 style={miniAppFormManifestTitleStyle}>{form.title || form.key}</h3>
                              <p style={miniAppCapabilityTextStyle}>{form.status || 'planned'}</p>
                            </div>
                            <div style={miniAppFormManifestBadgeRowStyle}>
                              <Badge variant="secondary" size="small">
                                {form.capture_enabled ? 'capture on' : 'capture off'}
                              </Badge>
                              <Badge variant="secondary" size="small">
                                {form.submission_enabled ? 'submit on' : 'submit off'}
                              </Badge>
                              <Badge variant={form.contains_medical_data ? 'warning' : 'success'} size="small">
                                {form.contains_medical_data ? 'medical data' : 'no medical data'}
                              </Badge>
                              <Badge variant={form.contains_passport_data ? 'warning' : 'success'} size="small">
                                {form.contains_passport_data ? 'passport data' : 'no passport data'}
                              </Badge>
                            </div>
                          </div>
                        ))}
                      </section>
                    </>
                  )}
                </CardContent>
              </Card>
            )}

            {canPreviewAppointments && (
              <Card padding="small" shadow="none" style={miniAppAppointmentPreviewStyle}>
                <CardContent style={miniAppAppointmentPreviewContentStyle}>
                  <div style={miniAppAppointmentPreviewHeaderStyle}>
                    <div>
                      <p style={miniAppKickerStyle}>РџСЂРµРґРІР°СЂРёС‚РµР»СЊРЅР°СЏ РїСЂРѕРІРµСЂРєР°</p>
                      <h2 style={miniAppSelectedSectionTitleStyle}>Р§РµСЂРЅРѕРІРёРє Р·Р°РїРёСЃРё</h2>
                    </div>
                    <Badge variant="secondary" size="small">Р‘РµР· СЃРѕР·РґР°РЅРёСЏ</Badge>
                  </div>

                  <div style={miniAppFormsSummaryStyle}>
                    <Badge variant="secondary" size="small">
                      {selectedCapability?.preview_enabled ? 'preview on' : 'preview off'}
                    </Badge>
                    <Badge variant={selectedCapability?.contains_medical_data ? 'warning' : 'success'} size="small">
                      {selectedCapability?.contains_medical_data ? 'medical data' : 'no medical data'}
                    </Badge>
                    <Badge variant={selectedCapability?.contains_payment_provider_data ? 'warning' : 'success'} size="small">
                      {selectedCapability?.contains_payment_provider_data ? 'provider payloads' : 'no provider payloads'}
                    </Badge>
                  </div>

                  <form style={miniAppAppointmentFormStyle} onSubmit={handleAppointmentPreviewSubmit}>
                    <div style={miniAppAppointmentFormGridStyle}>
                      <Input
                        type="date"
                        label="Р”Р°С‚Р°"
                        value={appointmentPreviewForm.appointmentDate}
                        onChange={handleAppointmentPreviewFieldChange('appointmentDate')}
                        required
                        style={miniAppAppointmentInputStyle}
                      />
                      <Input
                        type="time"
                        label="Р’СЂРµРјСЏ"
                        value={appointmentPreviewForm.appointmentTime}
                        onChange={handleAppointmentPreviewFieldChange('appointmentTime')}
                        style={miniAppAppointmentInputStyle}
                      />
                      <Input
                        label="РћС‚РґРµР»РµРЅРёРµ"
                        value={appointmentPreviewForm.department}
                        onChange={handleAppointmentPreviewFieldChange('department')}
                        placeholder="РћРїС†РёРѕРЅР°Р»СЊРЅРѕ"
                        maxLength={64}
                        style={miniAppAppointmentInputStyle}
                      />
                    </div>
                    <Textarea
                      label="Р—Р°РјРµС‚РєР° РґР»СЏ СЂРµРіРёСЃС‚СЂР°С‚СѓСЂС‹"
                      value={appointmentPreviewForm.notes}
                      onChange={handleAppointmentPreviewFieldChange('notes')}
                      placeholder="Р‘РµР· РјРµРґРёС†РёРЅСЃРєРёС… РґР°РЅРЅС‹С…"
                      maxLength={1000}
                      minRows={2}
                    />
                    <Button
                      type="submit"
                      variant="primary"
                      size="small"
                      loading={appointmentPreview.status === 'loading'}
                      disabled={appointmentPreview.status === 'loading' || appointmentCreate.status === 'loading'}
                    >
                      РџСЂРѕРІРµСЂРёС‚СЊ С‡РµСЂРЅРѕРІРёРє
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
                        <p style={miniAppCapabilityTextStyle}>Р”Р°С‚Р° Рё РІСЂРµРјСЏ</p>
                        <strong>{previewAppointment.appointment_date} {previewAppointment.appointment_time || 'РІСЂРµРјСЏ РЅРµ СѓРєР°Р·Р°РЅРѕ'}</strong>
                      </div>
                      <div>
                        <p style={miniAppCapabilityTextStyle}>РЎС‚Р°С‚СѓСЃ</p>
                        <strong>{previewAppointment.status}</strong>
                      </div>
                      <div>
                        <p style={miniAppCapabilityTextStyle}>РћРїР»Р°С‚Р°</p>
                        <strong>{previewAppointment.payment_type} / {previewAppointment.payment_currency}</strong>
                      </div>
                      <Badge variant={appointmentPreview.payload?.mutation_allowed ? 'warning' : 'success'} size="small">
                        {appointmentPreview.payload?.preview_only ? 'РўРѕР»СЊРєРѕ РїСЂРµРґРїСЂРѕСЃРјРѕС‚СЂ' : 'РўСЂРµР±СѓРµС‚ РїСЂРѕРІРµСЂРєРё'}
                      </Badge>
                    </div>
                  )}

                  {appointmentPreview.status === 'ready' && previewAppointment && selectedCapability?.create_enabled && (
                    <div style={miniAppAppointmentCreateActionStyle}>
                      <Button
                        type="button"
                        variant="primary"
                        size="small"
                        loading={appointmentCreate.status === 'loading'}
                        disabled={appointmentCreate.status === 'loading' || appointmentCreate.status === 'ready'}
                        onClick={handleAppointmentCreate}
                      >
                        Create appointment
                      </Button>
                      <Badge variant={appointmentCreate.status === 'ready' ? 'success' : 'secondary'} size="small">
                        {appointmentCreate.status === 'ready' ? 'created' : 'creates one scheduled visit'}
                      </Badge>
                    </div>
                  )}

                  {appointmentCreate.status === 'error' && (
                    <Alert severity="error" style={miniAppNoticeStyle}>
                      {appointmentCreate.error}
                    </Alert>
                  )}

                  {appointmentCreate.status === 'ready' && (
                    <Alert severity="success" style={miniAppNoticeStyle}>
                      Appointment request accepted. The clinic will continue the visit workflow in the protected system.
                    </Alert>
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

const miniAppSelectedSectionSafetyStyle = {
  display: 'flex',
  flexWrap: 'wrap',
  justifyContent: 'flex-end',
  gap: '6px',
  maxWidth: '360px',
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

const miniAppAppointmentCreateActionStyle = {
  display: 'flex',
  alignItems: 'center',
  flexWrap: 'wrap',
  gap: '8px',
};

const miniAppFormsManifestStyle = {
  marginBottom: '12px',
  borderColor: 'rgba(88, 86, 214, 0.24)',
};

const miniAppCabinetManifestStyle = {
  marginBottom: '12px',
  borderColor: 'rgba(0, 122, 255, 0.24)',
};

const miniAppPaymentsManifestStyle = {
  marginBottom: '12px',
  borderColor: 'rgba(255, 149, 0, 0.26)',
};

const miniAppResultsManifestStyle = {
  marginBottom: '12px',
  borderColor: 'rgba(52, 199, 89, 0.26)',
};

const miniAppFormsManifestContentStyle = {
  display: 'flex',
  flexDirection: 'column',
  gap: '14px',
};

const miniAppFormsSummaryStyle = {
  display: 'flex',
  alignItems: 'center',
  flexWrap: 'wrap',
  gap: '8px',
};

const miniAppFormsGridStyle = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(164px, 1fr))',
  gap: '12px',
};

const miniAppFormManifestItemStyle = {
  display: 'flex',
  flexDirection: 'column',
  justifyContent: 'space-between',
  gap: '14px',
  minHeight: '132px',
  padding: '12px',
  border: '1px solid rgba(88, 86, 214, 0.22)',
  borderRadius: '8px',
  background: 'rgba(88, 86, 214, 0.07)',
};

const miniAppCabinetManifestItemStyle = {
  ...miniAppFormManifestItemStyle,
  border: '1px solid rgba(0, 122, 255, 0.22)',
  background: 'rgba(0, 122, 255, 0.07)',
};

const miniAppPaymentsManifestItemStyle = {
  ...miniAppFormManifestItemStyle,
  border: '1px solid rgba(255, 149, 0, 0.24)',
  background: 'rgba(255, 149, 0, 0.08)',
};

const miniAppResultsManifestItemStyle = {
  ...miniAppFormManifestItemStyle,
  border: '1px solid rgba(52, 199, 89, 0.24)',
  background: 'rgba(52, 199, 89, 0.08)',
};

const miniAppFormManifestTitleStyle = {
  margin: '0 0 6px',
  fontSize: '15px',
  lineHeight: 1.25,
  fontWeight: 750,
  color: 'var(--mac-text-primary, #111827)',
};

const miniAppFormManifestBadgeRowStyle = {
  display: 'flex',
  flexWrap: 'wrap',
  gap: '6px',
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
