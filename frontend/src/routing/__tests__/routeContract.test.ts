// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { describe, expect, it } from 'vitest';
import { renderRouteDocsMarkdown } from '../routeDocsSnapshot.ts';
import { resolveSetupRedirect } from '../routeGuards.tsx';
import { ROUTE_REGISTRY, SIDEBAR_PRESETS } from '../routeRegistry.ts';
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
} from '../routeSelectors.ts';

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
  // IA PR-2: 5 integration routes demoted to nav:false (tabs inside UnifiedIntegrations hub)
  'admin-integrations': { path: '/admin/integrations', owner: 'admin.integrations', component: 'UnifiedIntegrations', entry: 'menu', section: 'Система' },
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
