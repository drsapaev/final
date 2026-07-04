import { describe, expect, it } from 'vitest';
import { renderRouteDocsMarkdown } from '../routeDocsSnapshot.js';
import { resolveSetupRedirect } from '../routeGuards.jsx';
import { ROUTE_REGISTRY, SIDEBAR_PRESETS } from '../routeRegistry.js';
import {
  getCompatibilityRedirects,
  getAdminNavSections,
  getInternalDemoRoutes,
  getLegacyRedirectTarget,
  getProtectedPatientFormsEntryPath,
  getProtectedPatientPaymentEntryPath,
  getProtectedPatientBookingEntryPath,
  getRoleHomeRoute,
  getRouteDocsSnapshot,
  getRouteChromeState,
  isInternalDemoEnabled,
  isRouteAccessibleToProfile,
} from '../routeSelectors.js';

const PRODUCTION_ROLE_HOMES = {
  admin: '/admin',
  registrar: '/registrar',
  lab: '/lab',
  doctor: '/doctor',
  cashier: '/cashier',
  cardio: '/doctor/cardiology',
  derma: '/doctor/dermatology',
  dentist: '/doctor/dentistry',
  patient: '/patient',
};

const AI_SIDEBAR_BADGE = 'Черновик · не медицинское заключение';
const AI_SIDEBAR_ACCESSIBLE_COPY = /черновик, не диагноз, не медицинское заключение/i;

// P-003 fix: 7 of the 8 previously orphaned admin-settings routes are now surfaced
// in the sidebar under the new domain-based sections. Only admin-user-select remains
// nav:false — it is an impersonation tool intended for contextual invocation, not
// sidebar discovery.
const ADMIN_CONTEXTUAL_ROUTE_IDS = [
  'admin-user-select',
];

// P-003 fix: the following routes used to be nav:false entry:'direct' on
// UnifiedSettings — they are now entry:'menu' with domain-based sections. The
// contract below tracks the remaining truly-hidden route only.
const ADMIN_CONTEXTUAL_SETTINGS_DIRECT_ROUTE_IDS = [
  // intentionally empty — all 7 settings routes now visible in the sidebar
];

const ADMIN_NAV_GROUPING_ROUTE_CONTRACT = {
  'admin-dashboard': { path: '/admin', owner: 'admin.operations', component: 'AdminDashboard', entry: 'menu', section: 'Обзор' },
  'admin-analytics': { path: '/admin/analytics', owner: 'admin.analytics', component: 'AnalyticsPage', entry: 'menu', section: 'Обзор' },
  'admin-reports': { path: '/admin/reports', owner: 'admin.reports', component: 'UnifiedReports', entry: 'direct', section: 'Обзор' },
  'admin-system': { path: '/admin/system', owner: 'admin.system', component: 'SystemManagement', entry: 'direct', section: 'Система' },
  'admin-cloud-printing': { path: '/admin/cloud-printing', owner: 'admin.operations', component: 'CloudPrintingManager', entry: 'direct', section: 'Интеграции' },
  'admin-medical-equipment': { path: '/admin/medical-equipment', owner: 'admin.operations', component: 'MedicalEquipmentManager', entry: 'direct', section: 'Интеграции' },
  'admin-webhooks': { path: '/admin/webhooks', owner: 'admin.integrations', component: 'WebhookManager', entry: 'direct', section: 'Интеграции' },
  'admin-graphql-explorer': { path: '/admin/graphql-explorer', owner: 'admin.integrations', component: 'GraphQLExplorer', entry: 'direct', section: 'Интеграции' },
};

const ADMIN_ROUTE_CHROME_HEADING_CONTRACT = {
  'admin-system': { path: '/admin/system', pageTitle: 'Admin System' },
  'admin-cloud-printing': { path: '/admin/cloud-printing', pageTitle: 'Admin Cloud Printing' },
  'admin-medical-equipment': { path: '/admin/medical-equipment', pageTitle: 'Admin Medical Equipment' },
  'admin-webhooks': { path: '/admin/webhooks', pageTitle: 'Вебхуки' },
  'admin-graphql-explorer': { path: '/admin/graphql-explorer', pageTitle: 'Admin GraphQL Explorer' },
};

const ADMIN_MANAGEMENT_ROUTE_CHROME_HEADING_CONTRACT = {
  'admin-users': { path: '/admin/users', pageTitle: 'Admin Users' },
  'admin-doctors': { path: '/admin/doctors', pageTitle: 'Admin Doctors' },
  'admin-services': { path: '/admin/services', pageTitle: 'Admin Services' },
  'admin-queue-cabinet-management': { path: '/admin/queue-cabinet-management', pageTitle: 'Admin Queue Cabinets' },
  'admin-patients': { path: '/admin/patients', pageTitle: 'Admin Patients' },
  'admin-appointments': { path: '/admin/appointments', pageTitle: 'Admin Appointments' },
  'admin-all-free': { path: '/admin/all-free', pageTitle: 'Admin All Free' },
};

const ADMIN_STANDALONE_MANAGEMENT_COMPONENT_CONTRACT = {
  'admin-services': { path: '/admin/services', owner: 'admin.catalog', component: 'AdminServices', entry: 'direct' },
  'admin-all-free': { path: '/admin/all-free', owner: 'admin.operations', component: 'AllFreeApproval', entry: 'direct' },
};

const ADMIN_CONTEXTUAL_ROUTE_CHROME_HEADING_CONTRACT = {
  'admin-benefit-settings': { path: '/admin/benefit-settings', pageTitle: 'Admin Benefit Settings' },
  'admin-wizard-settings': { path: '/admin/wizard-settings', pageTitle: 'Admin Wizard Settings' },
  'admin-payment-providers': { path: '/admin/payment-providers', pageTitle: 'Admin Payment Providers' },
  'admin-clinic-settings': { path: '/admin/clinic-settings', pageTitle: 'Admin Clinic Settings' },
  'admin-queue-settings': { path: '/admin/queue-settings', pageTitle: 'Admin Queue Settings' },
  'admin-ai-settings': { path: '/admin/ai-settings', pageTitle: 'Admin AI Settings' },
  'admin-telegram-settings': { path: '/admin/telegram-settings', pageTitle: 'Admin Telegram Settings' },
  'admin-display-settings': { path: '/admin/display-settings', pageTitle: 'Admin Display Settings' },
  'admin-security': { path: '/admin/security', pageTitle: 'Admin Security' },
  'admin-user-select': { path: '/admin/user-select', pageTitle: 'Admin User Switcher' },
};

const CLINICAL_CONTEXTUAL_ROUTE_IDS = [
  'clinical-profile',
  'clinical-security',
  'clinical-two-factor',
  'clinical-visit-details',
  'clinical-pickup',
];

function assertAiSidebarDisclaimer(item) {
  expect(item.badge).toBe(AI_SIDEBAR_BADGE);
  expect(item.tooltip).toMatch(AI_SIDEBAR_ACCESSIBLE_COPY);
  expect(item.ariaLabel).toMatch(AI_SIDEBAR_ACCESSIBLE_COPY);
}

function getRouteById(routeId) {
  return ROUTE_REGISTRY.find((route) => route.id === routeId);
}

function assertRouteSpecificChromeHeadings(routeHeadingContract) {
  const adminProfile = { role: 'Admin' };

  Object.entries(routeHeadingContract).forEach(([routeId, expected]) => {
    const route = getRouteById(routeId);
    const chrome = getRouteChromeState(expected.path, '', adminProfile);

    expect(route).toBeTruthy();
    expect(route.layout.pageTitle).toBe(expected.pageTitle);
    expect(route.title).toBeTruthy();
    expect(chrome.pageTitle).toBe(expected.pageTitle);
    expect(chrome.pageTitle).not.toBe('AdminPanel');
    expect(chrome.pageTitle).not.toBe('Admin');

    if (route.layout.activeSidebarItem) {
      expect(chrome.activeSidebarItem).toBe(route.layout.activeSidebarItem);
    }
  });
}

describe('route contract invariants', () => {
  it('keeps route ids unique and canonical paths singular', () => {
    const ids = new Set();
    const paths = new Set();

    ROUTE_REGISTRY.forEach((route) => {
      expect(ids.has(route.id)).toBe(false);
      expect(paths.has(route.path)).toBe(false);
      ids.add(route.id);
      paths.add(route.path);
    });
  });

  it('keeps admin routes under /admin', () => {
    ROUTE_REGISTRY.filter((route) => route.group === 'admin').forEach((route) => {
      expect(route.path.startsWith('/admin')).toBe(true);
    });
  });

  it('keeps admin routes off the legacy AdminPanel component owner', () => {
    const legacyAdminPanelRoutes = ROUTE_REGISTRY.filter(
      (route) => route.group === 'admin' && route.component === 'AdminPanel'
    );

    expect(legacyAdminPanelRoutes).toEqual([]);
  });

  it('keeps internal demo routes out of navigation', () => {
    getInternalDemoRoutes().forEach((route) => {
      expect(route.nav).toBe(false);
    });
  });

  it('keeps internal demo routes disabled unless explicitly enabled', () => {
    const demoRoute = getInternalDemoRoutes()[0];

    expect(isInternalDemoEnabled()).toBe(false);
    expect(isRouteAccessibleToProfile(demoRoute, { role: 'Admin' }, { internalDemoEnabled: false })).toBe(false);
    expect(isRouteAccessibleToProfile(demoRoute, { role: 'Admin' }, { internalDemoEnabled: true })).toBe(true);
  });

  it('does not assign roles to public routes', () => {
    ROUTE_REGISTRY.filter((route) => route.auth === 'public').forEach((route) => {
      expect(route.roles).toEqual([]);
    });
  });

  it('does not expose callback routes in navigation', () => {
    ROUTE_REGISTRY.filter((route) => route.surface === 'callback').forEach((route) => {
      expect(route.nav).toBe(false);
    });
  });

  it('requires at least one role for every role-scoped route', () => {
    ROUTE_REGISTRY.filter((route) => route.auth === 'role-scoped').forEach((route) => {
      expect(route.roles.length).toBeGreaterThan(0);
    });
  });

  it('assigns exactly one canonical home route per production role', () => {
    Object.entries(PRODUCTION_ROLE_HOMES).forEach(([role, expectedPath]) => {
      expect(getRoleHomeRoute(role)).toBe(expectedPath);
    });
  });

  it('supports specialist username home overrides when backend role is generic', () => {
    expect(getRoleHomeRoute({ username: 'cardio@example.com', role: 'Doctor' })).toBe('/doctor/cardiology');
    expect(getRoleHomeRoute({ username: 'derma@example.com', role: 'Doctor' })).toBe('/doctor/dermatology');
    expect(getRoleHomeRoute({ username: 'dentist@example.com', role: 'Doctor' })).toBe('/doctor/dentistry');
  });

  it('keeps compatibility aliases separate from canonical paths', () => {
    const canonicalPaths = new Set(ROUTE_REGISTRY.map((route) => route.path));

    getCompatibilityRedirects().forEach((redirect) => {
      expect(canonicalPaths.has(redirect.aliasPath)).toBe(false);
    });
  });

  it('labels AI sidebar navigation as draft support, not a diagnosis', () => {
    // P-010 fix: presets may use either flat `items` or grouped `sections`.
    // Flatten both to find all AI-related items across every preset.
    const allPresetItems = Object.values(SIDEBAR_PRESETS).flatMap((preset) => {
      const flatItems = preset.items || [];
      const sectionItems = Array.isArray(preset.sections)
        ? preset.sections.flatMap((section) => section.items || [])
        : [];
      return [...flatItems, ...sectionItems];
    });
    const presetAiItems = allPresetItems.filter(
      (item) => item.id === 'ai' || item.id === 'ai-assistant'
    );

    expect(presetAiItems).toHaveLength(4);
    presetAiItems.forEach(assertAiSidebarDisclaimer);

    const adminAiRoute = ROUTE_REGISTRY.find((route) => route.id === 'admin-ai-settings');
    assertAiSidebarDisclaimer(adminAiRoute.nav);
    expect(adminAiRoute.component).toBe('AISettings');
    expect(adminAiRoute.component).not.toBe('AdminPanel');

    const adminChrome = getRouteChromeState('/admin/ai-settings', '', { role: 'Admin' });
    const adminAiItem = adminChrome.sidebarItems.find((item) => item.id === 'admin-ai-settings');

    assertAiSidebarDisclaimer(adminAiItem);
  });

  it('keeps admin contextual routes registered and out of admin sidebar navigation', () => {
    const adminProfile = { role: 'Admin' };
    const adminChrome = getRouteChromeState('/admin', '', adminProfile);
    const adminSidebarIds = new Set(adminChrome.sidebarItems.map((item) => item.id));
    const adminSidebarTargets = new Set(adminChrome.sidebarItems.map((item) => item.to));

    ADMIN_CONTEXTUAL_ROUTE_IDS.forEach((routeId) => {
      const route = getRouteById(routeId);

      expect(route).toBeTruthy();
      expect(route.group).toBe('admin');
      expect(route.nav).toBe(false);
      expect(isRouteAccessibleToProfile(route, adminProfile)).toBe(true);
      expect(adminSidebarIds.has(route.id)).toBe(false);
      expect(adminSidebarTargets.has(route.path)).toBe(false);
    });
  });

  it('keeps hidden contextual settings routes on UnifiedSettings direct ownership', () => {
    const adminProfile = { role: 'Admin' };

    ADMIN_CONTEXTUAL_SETTINGS_DIRECT_ROUTE_IDS.forEach((routeId) => {
      const route = getRouteById(routeId);

      expect(route).toBeTruthy();
      expect(route.nav).toBe(false);
      expect(route.entry).toBe('direct');
      expect(route.component).toBe('UnifiedSettings');
      expect(route.component).not.toBe('AdminPanel');
      expect(isRouteAccessibleToProfile(route, adminProfile)).toBe(true);
    });
  });

  it('keeps admin overview, operations, and integrations route sections explicit', () => {
    const adminProfile = { role: 'Admin' };
    const navSections = getAdminNavSections(adminProfile);
    const sectionTitles = navSections.map((section) => section.title);

    // P-003 fix: 'Настройки' section added to surface 7 previously orphaned
    // admin-settings routes (benefit-settings, wizard-settings, payment-providers,
    // clinic-settings, queue-settings, telegram-settings, display-settings).
    expect(sectionTitles).toEqual(['Обзор', 'Пациенты и запись', 'Финансы', 'Клиника и очередь', 'Коммуникации', 'Система', 'Интеграции']);

    Object.entries(ADMIN_NAV_GROUPING_ROUTE_CONTRACT).forEach(([routeId, expected]) => {
      const route = getRouteById(routeId);
      const chrome = getRouteChromeState(expected.path, '', adminProfile);
      const navSection = navSections.find((section) => section.title === expected.section);

      expect(route).toBeTruthy();
      expect(route.path).toBe(expected.path);
      expect(route.owner).toBe(expected.owner);
      expect(route.component).toBe(expected.component);
      expect(route.entry).toBe(expected.entry);
      expect(route.nav.section).toBe(expected.section);
      expect(route.layout.activeSidebarItem).toBe(routeId);
      expect(chrome.activeSidebarItem).toBe(routeId);
      expect(isRouteAccessibleToProfile(route, adminProfile)).toBe(true);
      expect(navSection.items.some((item) => item.id === routeId)).toBe(true);
    });
  });

  it('keeps operations and integrations routes on route-specific chrome headings', () => {
    assertRouteSpecificChromeHeadings(ADMIN_ROUTE_CHROME_HEADING_CONTRACT);
  });

  it('keeps management routes on route-specific chrome headings', () => {
    assertRouteSpecificChromeHeadings(ADMIN_MANAGEMENT_ROUTE_CHROME_HEADING_CONTRACT);
  });

  it('keeps standalone admin management routes on direct component owners', () => {
    const adminProfile = { role: 'Admin' };

    Object.entries(ADMIN_STANDALONE_MANAGEMENT_COMPONENT_CONTRACT).forEach(([routeId, expected]) => {
      const route = getRouteById(routeId);

      expect(route).toBeTruthy();
      expect(route.path).toBe(expected.path);
      expect(route.owner).toBe(expected.owner);
      expect(route.component).toBe(expected.component);
      expect(route.component).not.toBe('AdminPanel');
      expect(route.entry).toBe(expected.entry);
      expect(route.layout.activeSidebarItem).toBe(routeId);
      expect(isRouteAccessibleToProfile(route, adminProfile)).toBe(true);
    });
  });

  it('keeps contextual admin routes on route-specific chrome headings', () => {
    assertRouteSpecificChromeHeadings(ADMIN_CONTEXTUAL_ROUTE_CHROME_HEADING_CONTRACT);
  });

  it('keeps admin user management on the canonical UnifiedUserManagement route', () => {
    // P1 architectural fix (Sprint 3): admin-advanced-users route was removed
    // (20-line AdvancedUserManagement stub duplicated admin-users which routes
    // to UnifiedUserManagement that renders UserManagement underneath).
    // /admin/advanced-users and /advanced-users now 404 — bookmarks should be
    // updated to /admin/users.
    const adminProfile = { role: 'Admin' };
    const canonicalUsersRoute = getRouteById('admin-users');

    expect(canonicalUsersRoute).toBeTruthy();
    expect(canonicalUsersRoute.path).toBe('/admin/users');
    expect(canonicalUsersRoute.owner).toBe('admin.users');
    expect(canonicalUsersRoute.entry).toBe('menu');
    expect(canonicalUsersRoute.component).toBe('UnifiedUserManagement');
    expect(canonicalUsersRoute.layout.activeSidebarItem).toBe('admin-users');
    expect(isRouteAccessibleToProfile(canonicalUsersRoute, adminProfile)).toBe(true);
    expect(getRouteChromeState('/admin/users', '', adminProfile).activeSidebarItem).toBe('admin-users');

    // admin-advanced-users route no longer exists
    expect(getRouteById('admin-advanced-users')).toBeUndefined();
  });

  it('keeps admin notification channels separated, with UnifiedNotifications routed for push', () => {
    // Step 3 wire-in: UnifiedNotifications (FCM + Registrar tabs) is now routed
    // on /admin/push-notifications. Email/SMS stays on /admin/notifications via
    // EmailSMSManager. No separate FCM/registrar routes — they are tabs inside
    // UnifiedNotifications.
    const adminProfile = { role: 'Admin' };
    const notificationsRoute = getRouteById('admin-notifications');
    const pushNotificationsRoute = getRouteById('admin-push-notifications');
    const publicNotificationPaths = new Set(ROUTE_REGISTRY.map((route) => route.path));
    const publicNotificationComponents = new Set(ROUTE_REGISTRY.map((route) => route.component));

    expect(notificationsRoute).toBeTruthy();
    expect(notificationsRoute.path).toBe('/admin/notifications');
    expect(notificationsRoute.owner).toBe('admin.notifications');
    expect(notificationsRoute.entry).toBe('menu');
    expect(notificationsRoute.component).toBe('EmailSMSManager');
    expect(notificationsRoute.legacyRedirectFrom).toContain('/notifications');
    expect(notificationsRoute.layout.activeSidebarItem).toBe('admin-notifications');
    expect(isRouteAccessibleToProfile(notificationsRoute, adminProfile)).toBe(true);
    expect(getRouteChromeState('/admin/notifications', '', adminProfile).activeSidebarItem).toBe('admin-notifications');

    expect(pushNotificationsRoute).toBeTruthy();
    expect(pushNotificationsRoute.path).toBe('/admin/push-notifications');
    expect(pushNotificationsRoute.component).toBe('UnifiedNotifications');
    expect(pushNotificationsRoute.owner).toBe('admin.notifications');
    expect(isRouteAccessibleToProfile(pushNotificationsRoute, adminProfile)).toBe(true);
    expect(getRouteChromeState('/admin/push-notifications', '', adminProfile).activeSidebarItem).toBe('admin-push-notifications');

    expect(publicNotificationPaths.has('/admin/fcm-notifications')).toBe(false);
    expect(publicNotificationPaths.has('/admin/registrar-notifications')).toBe(false);
    expect(publicNotificationComponents.has('UnifiedNotifications')).toBe(true);
  });

  it('keeps admin phone verification on its direct route owner', () => {
    const adminProfile = { role: 'Admin' };
    const phoneVerificationRoute = getRouteById('admin-phone-verification');

    expect(phoneVerificationRoute).toBeTruthy();
    expect(phoneVerificationRoute.path).toBe('/admin/phone-verification');
    expect(phoneVerificationRoute.owner).toBe('admin.integrations');
    expect(phoneVerificationRoute.entry).toBe('direct');
    expect(phoneVerificationRoute.component).toBe('PhoneVerificationManager');
    expect(phoneVerificationRoute.component).not.toBe('AdminPanel');
    expect(phoneVerificationRoute.layout.activeSidebarItem).toBe('admin-phone-verification');
    expect(isRouteAccessibleToProfile(phoneVerificationRoute, adminProfile)).toBe(true);
    expect(getRouteChromeState('/admin/phone-verification', '', adminProfile).activeSidebarItem).toBe('admin-phone-verification');
  });

  it('keeps admin activation on its direct route owner', () => {
    const adminProfile = { role: 'Admin' };
    const activationRoute = getRouteById('admin-activation');

    expect(activationRoute).toBeTruthy();
    expect(activationRoute.path).toBe('/admin/activation');
    expect(activationRoute.owner).toBe('admin.licensing');
    expect(activationRoute.entry).toBe('menu');
    expect(activationRoute.component).toBe('ActivationSystem');
    expect(activationRoute.component).not.toBe('AdminPanel');
    expect(activationRoute.legacyRedirectFrom).toContain('/activation');
    expect(activationRoute.layout.activeSidebarItem).toBe('admin-activation');
    expect(isRouteAccessibleToProfile(activationRoute, adminProfile)).toBe(true);
    expect(getRouteChromeState('/admin/activation', '', adminProfile).activeSidebarItem).toBe('admin-activation');
  });

  it('keeps admin finance on its direct route owner', () => {
    const adminProfile = { role: 'Admin' };
    const financeRoute = getRouteById('admin-finance');

    expect(financeRoute).toBeTruthy();
    expect(financeRoute.path).toBe('/admin/finance');
    expect(financeRoute.owner).toBe('admin.billing');
    expect(financeRoute.entry).toBe('direct');
    expect(financeRoute.component).toBe('UnifiedFinance');
    expect(financeRoute.component).not.toBe('AdminPanel');
    expect(financeRoute.layout.activeSidebarItem).toBe('admin-finance');
    expect(isRouteAccessibleToProfile(financeRoute, adminProfile)).toBe(true);
    expect(getRouteChromeState('/admin/finance', '', adminProfile).activeSidebarItem).toBe('admin-finance');
  });

  it('keeps admin doctors on its direct route owner', () => {
    const adminProfile = { role: 'Admin' };
    const doctorsRoute = getRouteById('admin-doctors');

    expect(doctorsRoute).toBeTruthy();
    expect(doctorsRoute.path).toBe('/admin/doctors');
    expect(doctorsRoute.owner).toBe('admin.users');
    expect(doctorsRoute.entry).toBe('direct');
    expect(doctorsRoute.component).toBe('AdminDoctors');
    expect(doctorsRoute.component).not.toBe('AdminPanel');
    expect(doctorsRoute.nav.sidebar).toBe(true);
    expect(doctorsRoute.layout.activeSidebarItem).toBe('admin-doctors');
    expect(isRouteAccessibleToProfile(doctorsRoute, adminProfile)).toBe(true);
    expect(getRouteChromeState('/admin/doctors', '', adminProfile).activeSidebarItem).toBe('admin-doctors');
  });

  it('keeps admin patients on its direct route owner', () => {
    const adminProfile = { role: 'Admin' };
    const patientsRoute = getRouteById('admin-patients');

    expect(patientsRoute).toBeTruthy();
    expect(patientsRoute.path).toBe('/admin/patients');
    expect(patientsRoute.owner).toBe('admin.patients');
    expect(patientsRoute.entry).toBe('direct');
    expect(patientsRoute.component).toBe('AdminPatients');
    expect(patientsRoute.component).not.toBe('AdminPanel');
    expect(patientsRoute.nav.sidebar).toBe(true);
    expect(patientsRoute.layout.activeSidebarItem).toBe('admin-patients');
    expect(isRouteAccessibleToProfile(patientsRoute, adminProfile)).toBe(true);
    expect(getRouteChromeState('/admin/patients', '', adminProfile).activeSidebarItem).toBe('admin-patients');
  });

  it('keeps admin appointments on its direct route owner', () => {
    const adminProfile = { role: 'Admin' };
    const appointmentsRoute = getRouteById('admin-appointments');

    expect(appointmentsRoute).toBeTruthy();
    expect(appointmentsRoute.path).toBe('/admin/appointments');
    expect(appointmentsRoute.owner).toBe('admin.scheduling');
    expect(appointmentsRoute.entry).toBe('direct');
    expect(appointmentsRoute.component).toBe('AdminAppointments');
    expect(appointmentsRoute.component).not.toBe('AdminPanel');
    expect(appointmentsRoute.nav.sidebar).toBe(true);
    expect(appointmentsRoute.layout.activeSidebarItem).toBe('admin-appointments');
    expect(isRouteAccessibleToProfile(appointmentsRoute, adminProfile)).toBe(true);
    expect(getRouteChromeState('/admin/appointments', '', adminProfile).activeSidebarItem).toBe('admin-appointments');
  });

  it('keeps admin clinic management on its direct route owner', () => {
    const adminProfile = { role: 'Admin' };
    const clinicManagementRoute = getRouteById('admin-clinic-management');

    expect(clinicManagementRoute).toBeTruthy();
    expect(clinicManagementRoute.path).toBe('/admin/clinic-management');
    expect(clinicManagementRoute.owner).toBe('admin.operations');
    expect(clinicManagementRoute.entry).toBe('direct');
    expect(clinicManagementRoute.component).toBe('ClinicManagement');
    expect(clinicManagementRoute.component).not.toBe('AdminPanel');
    expect(clinicManagementRoute.nav.sidebar).toBe(true);
    expect(clinicManagementRoute.layout.activeSidebarItem).toBe('admin-clinic-management');
    expect(isRouteAccessibleToProfile(clinicManagementRoute, adminProfile)).toBe(true);
    expect(getRouteChromeState('/admin/clinic-management', '', adminProfile).activeSidebarItem).toBe('admin-clinic-management');
  });

  it('keeps admin queue cabinets on their direct route owner', () => {
    const adminProfile = { role: 'Admin' };
    const queueCabinetRoute = getRouteById('admin-queue-cabinet-management');

    expect(queueCabinetRoute).toBeTruthy();
    expect(queueCabinetRoute.path).toBe('/admin/queue-cabinet-management');
    expect(queueCabinetRoute.owner).toBe('admin.queue');
    expect(queueCabinetRoute.entry).toBe('direct');
    expect(queueCabinetRoute.component).toBe('QueueCabinetManagement');
    expect(queueCabinetRoute.component).not.toBe('AdminPanel');
    expect(queueCabinetRoute.nav.sidebar).toBe(true);
    expect(queueCabinetRoute.layout.activeSidebarItem).toBe('admin-queue-cabinet-management');
    expect(isRouteAccessibleToProfile(queueCabinetRoute, adminProfile)).toBe(true);
    expect(getRouteChromeState('/admin/queue-cabinet-management', '', adminProfile).activeSidebarItem).toBe('admin-queue-cabinet-management');
  });

  it('keeps admin clinic settings surfaced in the Настройки section (P-003 fix)', () => {
    const adminProfile = { role: 'Admin' };
    const clinicSettingsRoute = getRouteById('admin-clinic-settings');

    expect(clinicSettingsRoute).toBeTruthy();
    expect(clinicSettingsRoute.path).toBe('/admin/clinic-settings');
    expect(clinicSettingsRoute.owner).toBe('admin.settings');
    // P-003 fix: previously entry:'direct' + nav:false — orphan route unreachable
    // from the sidebar. Now entry:'menu' with nav.sidebar:true under 'Настройки'.
    expect(clinicSettingsRoute.entry).toBe('menu');
    expect(clinicSettingsRoute.nav).not.toBe(false);
    expect(clinicSettingsRoute.nav.sidebar).toBe(true);
    expect(clinicSettingsRoute.nav.section).toBe('Клиника и очередь');
    expect(clinicSettingsRoute.component).toBe('UnifiedSettings');
    expect(clinicSettingsRoute.component).not.toBe('AdminPanel');
    expect(clinicSettingsRoute.layout.activeSidebarItem).toBe('admin-clinic-settings');
    expect(isRouteAccessibleToProfile(clinicSettingsRoute, adminProfile)).toBe(true);
    expect(getRouteChromeState('/admin/clinic-settings', '?section=clinic-settings', adminProfile).pageTitle).toBe('Admin Clinic Settings');
  });

  it('keeps admin Telegram settings as the canonical sidebar surface, integration as direct-only', () => {
    // P1 architectural fix (Sprint 3): admin-telegram-integration demoted to
    // entry:'direct' + nav:false to remove duplicate Telegram sidebar entry.
    // admin-telegram-settings (Настройки section) is the canonical surface.
    const adminProfile = { role: 'Admin' };
    const telegramIntegrationRoute = getRouteById('admin-telegram-integration');
    const telegramSettingsRoute = getRouteById('admin-telegram-settings');
    const routedComponents = new Set(ROUTE_REGISTRY.map((route) => route.component));

    expect(telegramIntegrationRoute).toBeTruthy();
    expect(telegramIntegrationRoute.path).toBe('/admin/integrations/telegram');
    expect(telegramIntegrationRoute.owner).toBe('admin.telegram');
    expect(telegramIntegrationRoute.entry).toBe('direct');
    expect(telegramIntegrationRoute.nav).toBe(false);
    expect(telegramIntegrationRoute.component).toBe('TelegramManager');
    expect(telegramIntegrationRoute.legacyRedirectFrom).toContain('/telegram-integration');
    expect(telegramIntegrationRoute.layout.activeSidebarItem).toBe('admin-telegram-integration');
    expect(isRouteAccessibleToProfile(telegramIntegrationRoute, adminProfile)).toBe(true);
    expect(getRouteChromeState('/admin/integrations/telegram', '', adminProfile).activeSidebarItem).toBe('admin-telegram-integration');

    expect(telegramSettingsRoute).toBeTruthy();
    expect(telegramSettingsRoute.path).toBe('/admin/telegram-settings');
    expect(telegramSettingsRoute.owner).toBe('admin.telegram');
    // P-003 fix: previously entry:'direct' + nav:false. Now visible under 'Настройки'.
    expect(telegramSettingsRoute.entry).toBe('menu');
    expect(telegramSettingsRoute.nav).not.toBe(false);
    expect(telegramSettingsRoute.nav.sidebar).toBe(true);
    expect(telegramSettingsRoute.nav.section).toBe('Коммуникации');
    expect(telegramSettingsRoute.component).toBe('TelegramSettings');
    expect(isRouteAccessibleToProfile(telegramSettingsRoute, adminProfile)).toBe(true);

    expect(routedComponents.has('UnifiedTelegramManagement')).toBe(false);
  });

  it('keeps clinical contextual routes registered and out of default sidebar navigation', () => {
    const doctorProfile = { role: 'Doctor' };
    const clinicalChrome = getRouteChromeState('/clinical/search', '', doctorProfile);
    const clinicalSidebarIds = new Set(clinicalChrome.sidebarItems.map((item) => item.id));
    const clinicalSidebarTargets = new Set(clinicalChrome.sidebarItems.map((item) => item.to));

    CLINICAL_CONTEXTUAL_ROUTE_IDS.forEach((routeId) => {
      const route = getRouteById(routeId);

      expect(route).toBeTruthy();
      expect(route.group).toBe('clinical');
      expect(route.nav).toBe(false);
      expect(isRouteAccessibleToProfile(route, doctorProfile)).toBe(true);
      expect(clinicalSidebarIds.has(route.id)).toBe(false);
      expect(clinicalSidebarTargets.has(route.path)).toBe(false);
    });
  });

  it('keeps doctor route sidebars visible and query-tab driven', () => {
    const doctorProfile = { role: 'Doctor' };
    const doctorChrome = getRouteChromeState('/doctor', '?tab=queue', doctorProfile);
    const cardiologyChrome = getRouteChromeState('/doctor/cardiology', '?tab=visit', doctorProfile);
    const dermatologyChrome = getRouteChromeState('/doctor/dermatology', '?tab=skin', doctorProfile);
    const dentistryChrome = getRouteChromeState('/doctor/dentistry', '?tab=dental-chart', doctorProfile);

    expect(doctorChrome.hideSidebar).toBe(false);
    expect(doctorChrome.sidebarPreset?.queryParam).toBe('tab');
    expect(doctorChrome.activeSidebarItem).toBe('queue');
    expect(doctorChrome.sidebarItems.map((item) => item.id)).toEqual([
      'dashboard',
      'patients',
      'appointments',
      'queue',
      'ai',
      'reports',
    ]);

    [
      [cardiologyChrome, 'visit'],
      [dermatologyChrome, 'skin'],
      [dentistryChrome, 'dental-chart'],
    ].forEach(([chrome, activeItem]) => {
      expect(chrome.hideSidebar).toBe(false);
      expect(chrome.fullscreen).toBe(true);
      expect(chrome.sidebarPreset?.queryParam).toBe('tab');
      expect(chrome.activeSidebarItem).toBe(activeItem);
      expect(chrome.sidebarItems.length).toBeGreaterThan(0);
    });
  });

  it('keeps route-derived admin and default sidebar targets backed by canonical routes', () => {
    const canonicalPaths = new Set(ROUTE_REGISTRY.map((route) => route.path));
    const routeDerivedSidebarItems = [
      ...getRouteChromeState('/admin', '', { role: 'Admin' }).sidebarItems,
      ...getRouteChromeState('/clinical/search', '', { role: 'Doctor' }).sidebarItems,
    ];

    expect(routeDerivedSidebarItems.length).toBeGreaterThan(0);
    routeDerivedSidebarItems.forEach((item) => {
      expect(item.to).toBeTruthy();
      expect(canonicalPaths.has(item.to)).toBe(true);
    });
  });

  it('keeps protected patient payment entry restricted to Patient role (P-002 fix)', () => {
    const route = getRouteById('patient-payment-entry');

    expect(route).toBeTruthy();
    expect(getProtectedPatientPaymentEntryPath()).toBe('/patient/payments');
    expect(route.path).toBe('/patient/payments');
    // P-002 fix: previously auth:'authenticated' + roles:[] allowed ANY logged-in
    // staff member to open patient payment pages, exposing patient financial data.
    // Now restricted to Patient role only.
    expect(route.auth).toBe('role-scoped');
    expect(route.roles).toEqual(['Patient']);
    expect(route.nav).toBe(false);
    expect(route.component).toBe('PatientPanel');
    expect(isRouteAccessibleToProfile(route, null)).toBe(false);
    expect(isRouteAccessibleToProfile(route, { role: 'Doctor' })).toBe(false);
    expect(isRouteAccessibleToProfile(route, { role: 'Patient' })).toBe(true);

    const chrome = getRouteChromeState('/patient/payments', '', { role: 'Patient' });
    expect(chrome.activeSidebarItem).toBe('payments');
    expect(chrome.hideSidebar).toBe(true);
  });

  it('adds protected patient booking entry as its own route contract (P-002 fix)', () => {
    const route = getRouteById('patient-booking-entry');

    expect(route).toBeTruthy();
    expect(getProtectedPatientBookingEntryPath()).toBe('/patient/bookings');
    expect(route.path).toBe('/patient/bookings');
    // P-002 fix: same hardening as patient-payment-entry.
    expect(route.auth).toBe('role-scoped');
    expect(route.roles).toEqual(['Patient']);
    expect(route.nav).toBe(false);
    expect(route.component).toBe('PatientPanel');
    expect(isRouteAccessibleToProfile(route, null)).toBe(false);
    expect(isRouteAccessibleToProfile(route, { role: 'Doctor' })).toBe(false);
    expect(isRouteAccessibleToProfile(route, { role: 'Patient' })).toBe(true);

    const chrome = getRouteChromeState('/patient/bookings', '', { role: 'Patient' });
    expect(chrome.activeSidebarItem).toBe('appointments');
    expect(chrome.hideSidebar).toBe(true);
  });

  it('keeps protected patient forms entry as query-route fallback', () => {
    const route = getRouteById('patient-forms-entry');

    expect(getProtectedPatientFormsEntryPath()).toBe('/patient?tab=forms');
    expect(route).toBeFalsy();
  });
});

describe('redirect and setup policies', () => {
  it('redirects legacy clinical urls to canonical destinations', () => {
    expect(getLegacyRedirectTarget('/registrar-panel')?.targetPath).toBe('/registrar');
    expect(getLegacyRedirectTarget('/settings')?.targetPath).toBe('/admin/settings');
    expect(getLegacyRedirectTarget('/payment/test')?.targetPath).toBe('/internal-demo/payment-test');
  });

  it('applies setup precedence without loops', () => {
    expect(resolveSetupRedirect('/admin', false)).toBe('/setup');
    expect(resolveSetupRedirect('/clinical/search', false)).toBe('/setup');
    expect(resolveSetupRedirect('/queue/join', false)).toBe(null);
    expect(resolveSetupRedirect('/setup', true)).toBe('/login');
    expect(resolveSetupRedirect('/login', true)).toBe(null);
  });
});

describe('docs snapshot', () => {
  it('publishes canonical routing documentation from the registry', () => {
    const snapshot = getRouteDocsSnapshot();
    const markdown = renderRouteDocsMarkdown(snapshot);

    expect(snapshot.groups.admin.some((route) => route.path === '/admin/settings')).toBe(true);
    expect(snapshot.groups.clinical.some((route) => route.path === '/clinical/profile')).toBe(true);
    expect(markdown).toContain('Compatibility Redirects');
    expect(markdown).toContain('/registrar');
    expect(markdown).toContain('/admin/settings');
  });
});
