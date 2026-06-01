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

const ADMIN_CONTEXTUAL_ROUTE_IDS = [
  'admin-benefit-settings',
  'admin-wizard-settings',
  'admin-payment-providers',
  'admin-clinic-settings',
  'admin-queue-settings',
  'admin-telegram-settings',
  'admin-display-settings',
  'admin-user-select',
];

const ADMIN_NAV_GROUPING_ROUTE_CONTRACT = {
  'admin-dashboard': { path: '/admin', owner: 'admin.operations', component: 'AdminPanel', entry: 'menu', section: 'Обзор' },
  'admin-analytics': { path: '/admin/analytics', owner: 'admin.analytics', component: 'AnalyticsPage', entry: 'menu', section: 'Обзор' },
  'admin-reports': { path: '/admin/reports', owner: 'admin.reports', component: 'AdminPanel', entry: 'direct', section: 'Обзор' },
  'admin-system': { path: '/admin/system', owner: 'admin.system', component: 'AdminPanel', entry: 'direct', section: 'Операции' },
  'admin-cloud-printing': { path: '/admin/cloud-printing', owner: 'admin.operations', component: 'AdminPanel', entry: 'direct', section: 'Операции' },
  'admin-medical-equipment': { path: '/admin/medical-equipment', owner: 'admin.operations', component: 'AdminPanel', entry: 'direct', section: 'Операции' },
  'admin-webhooks': { path: '/admin/webhooks', owner: 'admin.integrations', component: 'AdminPanel', entry: 'direct', section: 'Интеграции' },
  'admin-graphql-explorer': { path: '/admin/graphql-explorer', owner: 'admin.integrations', component: 'AdminPanel', entry: 'direct', section: 'Интеграции' },
};

const ADMIN_ROUTE_CHROME_HEADING_CONTRACT = {
  'admin-system': { path: '/admin/system', pageTitle: 'Admin System' },
  'admin-cloud-printing': { path: '/admin/cloud-printing', pageTitle: 'Admin Cloud Printing' },
  'admin-medical-equipment': { path: '/admin/medical-equipment', pageTitle: 'Admin Medical Equipment' },
  'admin-webhooks': { path: '/admin/webhooks', pageTitle: 'Вебхуки' },
  'admin-graphql-explorer': { path: '/admin/graphql-explorer', pageTitle: 'Admin GraphQL Explorer' },
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
    const presetAiItems = Object.values(SIDEBAR_PRESETS)
      .flatMap((preset) => preset.items || [])
      .filter((item) => item.id === 'ai' || item.id === 'ai-assistant');

    expect(presetAiItems).toHaveLength(4);
    presetAiItems.forEach(assertAiSidebarDisclaimer);

    const adminAiRoute = ROUTE_REGISTRY.find((route) => route.id === 'admin-ai-settings');
    assertAiSidebarDisclaimer(adminAiRoute.nav);

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

  it('keeps admin overview, operations, and integrations route sections explicit', () => {
    const adminProfile = { role: 'Admin' };
    const navSections = getAdminNavSections(adminProfile);
    const sectionTitles = navSections.map((section) => section.title);

    expect(sectionTitles).toEqual(['Обзор', 'Управление', 'Операции', 'Интеграции', 'Система']);

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
    const adminProfile = { role: 'Admin' };

    Object.entries(ADMIN_ROUTE_CHROME_HEADING_CONTRACT).forEach(([routeId, expected]) => {
      const route = getRouteById(routeId);
      const chrome = getRouteChromeState(expected.path, '', adminProfile);

      expect(route).toBeTruthy();
      expect(route.layout.pageTitle).toBe(expected.pageTitle);
      expect(route.title).toBeTruthy();
      expect(chrome.pageTitle).toBe(expected.pageTitle);
      expect(chrome.activeSidebarItem).toBe(routeId);
      expect(chrome.pageTitle).not.toBe('AdminPanel');
      expect(chrome.pageTitle).not.toBe('Admin');
    });
  });

  it('keeps admin user routes split between canonical and advanced ownership', () => {
    const adminProfile = { role: 'Admin' };
    const canonicalUsersRoute = getRouteById('admin-users');
    const advancedUsersRoute = getRouteById('admin-advanced-users');

    expect(canonicalUsersRoute).toBeTruthy();
    expect(canonicalUsersRoute.path).toBe('/admin/users');
    expect(canonicalUsersRoute.owner).toBe('admin.users');
    expect(canonicalUsersRoute.entry).toBe('menu');
    expect(canonicalUsersRoute.component).toBe('AdminPanel');
    expect(canonicalUsersRoute.layout.activeSidebarItem).toBe('admin-users');
    expect(isRouteAccessibleToProfile(canonicalUsersRoute, adminProfile)).toBe(true);

    expect(advancedUsersRoute).toBeTruthy();
    expect(advancedUsersRoute.path).toBe('/admin/advanced-users');
    expect(advancedUsersRoute.owner).toBe('admin.users');
    expect(advancedUsersRoute.entry).toBe('direct');
    expect(advancedUsersRoute.component).toBe('AdvancedUserManagement');
    expect(advancedUsersRoute.legacyRedirectFrom).toContain('/advanced-users');
    expect(advancedUsersRoute.layout.activeSidebarItem).toBe('admin-advanced-users');
    expect(isRouteAccessibleToProfile(advancedUsersRoute, adminProfile)).toBe(true);

    expect(canonicalUsersRoute.component).not.toBe(advancedUsersRoute.component);
    expect(canonicalUsersRoute.path).not.toBe(advancedUsersRoute.path);
    expect(getRouteChromeState('/admin/users', '', adminProfile).activeSidebarItem).toBe('admin-users');
    expect(getRouteChromeState('/admin/advanced-users', '', adminProfile).activeSidebarItem).toBe('admin-advanced-users');
  });

  it('keeps admin notification channels separated until routed deliberately', () => {
    const adminProfile = { role: 'Admin' };
    const notificationsRoute = getRouteById('admin-notifications');
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

    expect(publicNotificationPaths.has('/admin/fcm-notifications')).toBe(false);
    expect(publicNotificationPaths.has('/admin/registrar-notifications')).toBe(false);
    expect(publicNotificationComponents.has('UnifiedNotifications')).toBe(false);
  });

  it('keeps admin Telegram operational and settings surfaces explicit', () => {
    const adminProfile = { role: 'Admin' };
    const telegramIntegrationRoute = getRouteById('admin-telegram-integration');
    const telegramSettingsRoute = getRouteById('admin-telegram-settings');
    const routedComponents = new Set(ROUTE_REGISTRY.map((route) => route.component));

    expect(telegramIntegrationRoute).toBeTruthy();
    expect(telegramIntegrationRoute.path).toBe('/admin/integrations/telegram');
    expect(telegramIntegrationRoute.owner).toBe('admin.telegram');
    expect(telegramIntegrationRoute.entry).toBe('menu');
    expect(telegramIntegrationRoute.component).toBe('TelegramManager');
    expect(telegramIntegrationRoute.legacyRedirectFrom).toContain('/telegram-integration');
    expect(telegramIntegrationRoute.layout.activeSidebarItem).toBe('admin-telegram-integration');
    expect(isRouteAccessibleToProfile(telegramIntegrationRoute, adminProfile)).toBe(true);
    expect(getRouteChromeState('/admin/integrations/telegram', '', adminProfile).activeSidebarItem).toBe('admin-telegram-integration');

    expect(telegramSettingsRoute).toBeTruthy();
    expect(telegramSettingsRoute.path).toBe('/admin/telegram-settings');
    expect(telegramSettingsRoute.owner).toBe('admin.telegram');
    expect(telegramSettingsRoute.entry).toBe('direct');
    expect(telegramSettingsRoute.nav).toBe(false);
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

  it('keeps protected patient payment entry authenticated and non-navigational', () => {
    const route = getRouteById('patient-payment-entry');

    expect(route).toBeTruthy();
    expect(getProtectedPatientPaymentEntryPath()).toBe('/patient/payments');
    expect(route.path).toBe('/patient/payments');
    expect(route.auth).toBe('authenticated');
    expect(route.roles).toEqual([]);
    expect(route.nav).toBe(false);
    expect(route.component).toBe('PatientPanel');
    expect(isRouteAccessibleToProfile(route, null)).toBe(false);
    expect(isRouteAccessibleToProfile(route, { role: 'Doctor' })).toBe(true);

    const chrome = getRouteChromeState('/patient/payments', '', { role: 'Doctor' });
    expect(chrome.activeSidebarItem).toBe('payments');
    expect(chrome.hideSidebar).toBe(true);
  });

  it('adds protected patient booking entry as its own route contract', () => {
    const route = getRouteById('patient-booking-entry');

    expect(route).toBeTruthy();
    expect(getProtectedPatientBookingEntryPath()).toBe('/patient/bookings');
    expect(route.path).toBe('/patient/bookings');
    expect(route.auth).toBe('authenticated');
    expect(route.roles).toEqual([]);
    expect(route.nav).toBe(false);
    expect(route.component).toBe('PatientPanel');
    expect(isRouteAccessibleToProfile(route, null)).toBe(false);
    expect(isRouteAccessibleToProfile(route, { role: 'Doctor' })).toBe(true);

    const chrome = getRouteChromeState('/patient/bookings', '', { role: 'Doctor' });
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
