import type { Page } from '@playwright/test';

const API_PREFIX = '/api/v1';

export interface RoleQaRoute {
  key: string;
  role: string;
  path: string;
  routeId: string;
}

export interface SpecialtyQaRoute extends RoleQaRoute {
  summaryLabel: string;
}

export interface DenyQaRoute {
  key: string;
  role: string;
  path: string;
  deniedRouteId: string;
}

export interface QaProfile {
  id: string;
  username: string;
  email: string;
  full_name: string;
  first_name: string;
  last_name: string;
  role: string;
  role_name: string;
  roles: string[];
  permissions: string[];
  is_admin: boolean;
  is_superuser: boolean;
  qa_harness: boolean;
}

export const AUTHENTICATED_ROLE_QA_ROUTES: RoleQaRoute[] = [
  {
    key: 'admin',
    role: 'Admin',
    path: '/admin',
    routeId: 'admin-dashboard',
  },
  {
    key: 'registrar',
    role: 'Registrar',
    path: '/registrar',
    routeId: 'registrar-home',
  },
  {
    key: 'doctor',
    role: 'Doctor',
    path: '/doctor',
    routeId: 'doctor-home',
  },
  {
    key: 'cashier',
    role: 'Cashier',
    path: '/cashier',
    routeId: 'cashier-home',
  },
  {
    key: 'lab',
    role: 'Lab',
    path: '/lab',
    routeId: 'lab-home',
  },
  {
    key: 'patient',
    role: 'Patient',
    // PR-QA-02: was /patient/payments (routeId patient-payment-entry) — that
    // route is NOT in the registry (routeSelectors falls back to the
    // non-existent path → 404). The canonical patient surface is /patient.
    path: '/patient',
    routeId: 'patient-home',
  },
];

export const AUTHENTICATED_SPECIALTY_QA_ROUTES: SpecialtyQaRoute[] = [
  {
    key: 'doctor-cardiology',
    role: 'Doctor',
    // PR-QA-02: Phase 4+ reduced the sidebar and merged the appointments tab
    // into 'patients'; ?tab=appointments remains a supported back-compat
    // deep link that renders AppointmentsTab with its SummaryBar.
    path: '/doctor/cardiology?tab=appointments',
    routeId: 'doctor-cardiology',
    summaryLabel: 'Сводка записей кардиолога',
  },
  {
    key: 'doctor-dermatology',
    role: 'Doctor',
    path: '/doctor/dermatology?tab=appointments',
    routeId: 'doctor-dermatology',
    summaryLabel: 'Сводка записей дерматолога',
  },
  // PR-QA-02: doctor-dentistry EXCLUDED — appointments assertion is obsolete.
  // Phase 4+ dentistry switch(activeTab) has no 'appointments' case:
  // renderAppointments() (with the Сводка записей стоматолога SummaryBar) is
  // dead code, and ?tab=appointments falls through to the dashboard tab.
  // DentalPatientsTab is a DIFFERENT UI — swapping the anchor would silently
  // change the test's meaning. Replacement acceptance requires a product
  // decision (tracked in the QA audit). Not a Tier-1 candidate until then.
];

export const AUTHENTICATED_UI_QA_ROUTES: Array<RoleQaRoute | SpecialtyQaRoute> = [
  ...AUTHENTICATED_ROLE_QA_ROUTES,
  ...AUTHENTICATED_SPECIALTY_QA_ROUTES,
];

export const AUTHENTICATED_RBAC_DENY_QA_ROUTES: DenyQaRoute[] = [
  {
    key: 'cashier-denied-admin',
    role: 'Cashier',
    path: '/admin',
    deniedRouteId: 'admin-dashboard',
  },
  {
    key: 'doctor-denied-cashier',
    role: 'Doctor',
    path: '/cashier',
    deniedRouteId: 'cashier-home',
  },
  {
    key: 'cashier-denied-lab',
    role: 'Cashier',
    path: '/lab',
    deniedRouteId: 'lab-home',
  },
  {
    key: 'registrar-denied-cardiology',
    role: 'Registrar',
    path: '/doctor/cardiology',
    deniedRouteId: 'doctor-cardiology',
  },
];

function base64UrlEncode(value: unknown) {
  return Buffer.from(JSON.stringify(value))
    .toString('base64')
    .replace(/=/g, '')
    .replace(/\+/g, '-')
    .replace(/\//g, '_');
}

function createQaJwt(profile: QaProfile) {
  const nowSeconds = Math.floor(Date.now() / 1000);
  const header = { alg: 'none', typ: 'JWT' };
  const payload = {
    sub: profile.username,
    role: profile.role,
    roles: profile.roles,
    iat: nowSeconds,
    exp: nowSeconds + 60 * 60,
  };

  return `${base64UrlEncode(header)}.${base64UrlEncode(payload)}.qa`;
}

export function createAuthenticatedQaProfile(role: string): QaProfile {
  const normalizedRole = String(role || 'Admin');
  const isAdmin = normalizedRole === 'Admin';
  const username = `qa_${normalizedRole.toLowerCase()}`;

  return {
    id: `qa-${normalizedRole.toLowerCase()}`,
    username,
    email: `${username}@clinic.local`,
    full_name: `QA ${normalizedRole}`,
    first_name: 'QA',
    last_name: normalizedRole,
    role: normalizedRole,
    role_name: normalizedRole,
    roles: [normalizedRole],
    permissions: isAdmin ? ['*'] : [],
    is_admin: isAdmin,
    is_superuser: isAdmin,
    qa_harness: true,
  };
}

function collectionPayload() {
  return {
    items: [],
    results: [],
    data: [],
    total: 0,
    count: 0,
    success: true,
  };
}

function buildQaApiPayload(pathname: string, profile: QaProfile, method: string) {
  const path = pathname.replace(API_PREFIX, '') || '/';
  const lowerPath = path.toLowerCase();

  if (lowerPath === '/setup/status') {
    return { initialized: true };
  }

  if (lowerPath === '/auth/me' || lowerPath === '/authentication/profile') {
    return profile;
  }

  if (method !== 'GET') {
    return { success: true, id: 'qa-write-disabled' };
  }

  if (lowerPath === '/users/users') {
    return {
      users: [],
      page: 1,
      per_page: 20,
      total: 0,
      total_pages: 0,
      success: true,
    };
  }

  if (lowerPath === '/patients' || lowerPath === '/patients/') {
    return [];
  }

  if (lowerPath === '/admin/appointments') {
    return [];
  }

  if (lowerPath === '/billing/invoices' || lowerPath === '/billing/payments') {
    return [];
  }

  if (lowerPath === '/services' || lowerPath === '/services/categories' || lowerPath === '/services/admin/doctors') {
    return [];
  }

  if (lowerPath === '/departments') {
    return { success: true, data: [], count: 0 };
  }

  if (lowerPath === '/queues/profiles') {
    return { success: true, profiles: [] };
  }

  if (lowerPath === '/webhooks' || lowerPath === '/webhooks/') {
    return { success: true, items: [] };
  }

  if (lowerPath === '/webhooks/system/stats') {
    return {
      success: true,
      total_webhooks: 0,
      active_webhooks: 0,
      recent_24h: {
        total_calls: 0,
        success_rate: 0,
      },
    };
  }

  if (lowerPath.startsWith('/webhooks/') && lowerPath.endsWith('/calls')) {
    return { success: true, items: [] };
  }

  if (lowerPath.includes('summary') || lowerPath.includes('stats') || lowerPath.includes('dashboard')) {
    // collectionPayload() already provides success: true and total: 0 via the spread below.
    return {
      pending: 0,
      completed: 0,
      cancelled: 0,
      by_status: {},
      ...collectionPayload(),
    };
  }

  if (lowerPath.includes('settings') || lowerPath.includes('config') || lowerPath.includes('profile')) {
    // collectionPayload() already provides success: true via the spread below.
    return { ...collectionPayload() };
  }

  return collectionPayload();
}

export async function installAuthenticatedQaHarness(
  page: Page,
  { role }: { role: string }
): Promise<{ token: string; profile: QaProfile }> {
  const profile = createAuthenticatedQaProfile(role);
  const token = createQaJwt(profile);

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const payload = buildQaApiPayload(url.pathname, profile, request.method());

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(payload),
    });
  });

  await page.addInitScript(({ authToken, authProfile }) => {
    // Clear pre-existing session state BEFORE seeding the QA session.
    // Order matters: a sessionStorage.clear() after the setItem calls
    // would wipe the auth_token/auth_profile we just installed, the auth
    // guard would redirect to /login, and every authenticated QA test
    // would fail with expect(page).not.toHaveURL(/\/login$/) (28 failures
    // observed before this fix).
    window.sessionStorage.clear();
    window.localStorage.removeItem('clinic_api_rate_limit_until');
    window.sessionStorage.setItem('auth_token', authToken);
    window.sessionStorage.setItem('auth_profile', JSON.stringify(authProfile));
    window.sessionStorage.setItem('user', JSON.stringify(authProfile));
    window.localStorage.setItem('theme', 'light');
    window.localStorage.setItem('language', 'ru');
  }, { authToken: token, authProfile: profile });

  return { token, profile };
}
