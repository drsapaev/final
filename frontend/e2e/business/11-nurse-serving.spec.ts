/**
 * E2E Business Scenario 11: NURSE-V2 N2-5 — the nurse tablet workspace.
 *
 * Self-contained (mocked API, the fixtures.ts pattern): the Nurse lands
 * on /nurse, the workplace/board flow renders from the N2-3 contract,
 * other roles are denied, and a reload restores the state purely from
 * the server responses (§8). The full 3-scenario browser acceptance
 * against a disposable backend runs as the §15 local gate (documented in
 * the PR body) — this spec pins the same contract in CI.
 */

import { test, expect } from './fixtures';

const WORKPLACES = {
  items: [
    {
      assignment_id: 1,
      queue_resource_id: 10,
      resource_code: 'proc',
      resource_display_name: 'Процедурный кабинет',
      resource_queue_tag: 'tag_proc',
      resource_default_cabinet: '4',
      cabinet_override: null,
      effective_cabinet: '4',
    },
  ],
  total: 1,
};

const BOARD = {
  queue_resource_id: 10,
  resource_queue_tag: 'tag_proc',
  resource_display_name: 'Процедурный кабинет',
  effective_cabinet: '4',
  queue_id: 100,
  queue_day: '2026-09-21T00:00:00Z',
  waiting: [
    {
      id: 11,
      number: 17,
      status: 'waiting',
      priority: 0,
      source: 'desk',
      patient_id: 5,
      patient_name: 'Анна Тестова',
      phone: null,
      queue_time: '2026-09-21T08:00:00Z',
      called_at: null,
      called_by_user_id: null,
      served_by_user_id: null,
      served_at: null,
      visit_id: null,
      is_my_claim: false,
      services: [],
    },
  ],
  active: [],
  my_entry: null,
  late_pending: [],
  counts: { waiting: 1 },
};

// PR-39: the app reads auth_token/auth_profile from sessionStorage —
// seed it there (the authenticated-rbac-deny harness pattern).
const NURSE_PROFILE = { id: 7, role: 'Nurse', email: 'nurse@clinic.com' };

// tokenManager.isTokenValid() parses the JWT payload — a plain string
// token is "malformed" and gets cleared before the first render (the
// authenticatedQa harness pattern: a fake alg:none JWT with exp +1h).
function base64UrlEncode(value: unknown): string {
  return btoa(JSON.stringify(value)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function createQaJwt(role: string): string {
  const nowSeconds = Math.floor(Date.now() / 1000);
  return `${base64UrlEncode({ alg: 'none', typ: 'JWT' })}.${base64UrlEncode({
    sub: `qa_${role.toLowerCase()}`,
    role,
    iat: nowSeconds,
    exp: nowSeconds + 60 * 60,
  })}.qa`;
}

function nurseAuth(page: import('@playwright/test').Page) {
  return page.addInitScript((token: string) => {
    sessionStorage.setItem('auth_token', token);
    sessionStorage.setItem(
      'auth_profile',
      JSON.stringify({ id: 7, role: 'Nurse', email: 'nurse@clinic.com' }),
    );
  }, createQaJwt('Nurse'));
}

function doctorAuth(page: import('@playwright/test').Page) {
  return page.addInitScript((token: string) => {
    sessionStorage.setItem('auth_token', token);
    sessionStorage.setItem(
      'auth_profile',
      JSON.stringify({ id: 8, role: 'Doctor', email: 'doctor@clinic.com' }),
    );
  }, createQaJwt('Doctor'));
}

function mockNurseServing(
  page: import('@playwright/test').Page,
  {
    workplaces = WORKPLACES,
    board = BOARD,
    profile = NURSE_PROFILE,
  }: {
    // The payloads are structural JSON for route.fulfill — the board
    // stays permissive so a handover board (with the N2-5 predicate
    // fields the base BOARD literal does not infer) passes through.
    workplaces?: typeof WORKPLACES;
    board?: Record<string, unknown>;
    profile?: typeof NURSE_PROFILE;
  } = {},
) {
  // ONE handler for the whole API surface (the authenticatedQa pattern):
  // unmocked paths would hit the dev-server proxy and fail ECONNREFUSED
  // without a backend, tripping the session-validation / login redirect.
  return page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    let payload: unknown = {};
    if (path === '/api/v1/nurse/serving/workplaces') {
      payload = workplaces;
    } else if (path === '/api/v1/nurse/serving/draining-executions') {
      payload = { items: [], total: 0 };
    } else if (path.includes('/api/v1/nurse/serving/queue-resources')) {
      payload = board;
    } else if (path === '/api/v1/auth/me') {
      payload = profile;
    } else if (path === '/api/v1/setup/status') {
      payload = { initialized: true };
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(payload),
    });
  });
}

test.describe('Business: NURSE-V2 N2-5 tablet', () => {
  test('Nurse lands on /nurse and sees the station board', async ({ page }) => {
    await nurseAuth(page);
    await mockNurseServing(page);
    await page.goto('/nurse');
    await page.waitForLoadState('networkidle');
    await expect(page.getByText('Процедурный кабинет')).toBeVisible();
    await expect(page.getByText('Анна Тестова')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Вызвать следующего' })).toBeVisible();
  });

  test('zero workplaces: the empty state, no queue or patient data', async ({ page }) => {
    await nurseAuth(page);
    await mockNurseServing(page, { workplaces: { items: [], total: 0 } });
    await page.goto('/nurse');
    await page.waitForLoadState('networkidle');
    await expect(page.getByText('Нет назначенного рабочего места')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Вызвать следующего' })).toHaveCount(0);
  });

  test('reload restores the current patient from the server state (§8)', async ({ page }) => {
    await nurseAuth(page);
    await mockNurseServing(page);
    await page.goto('/nurse');
    await page.waitForLoadState('networkidle');
    await expect(page.getByText('Анна Тестова')).toBeVisible();
    await page.reload();
    await page.waitForLoadState('networkidle');
    // the restored board comes from the GETs, not from any cached UI state
    await expect(page.getByText('Анна Тестова')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Вызвать следующего' })).toBeVisible();
  });

  test('D1 handover: a server-proven actionable entry renders [Принять пациента]', async ({ page }) => {
    await nurseAuth(page);
    // The claim owner's assignment is GONE — the server marks the
    // orphaned called entry actionable for the signed-in nurse.
    const handoverBoard = {
      ...BOARD,
      waiting: [],
      counts: { waiting: 0 },
      active: [
        {
          ...BOARD.waiting[0],
          id: 42,
          number: 42,
          status: 'called',
          patient_name: 'Ольга Передача',
          called_by_user_id: 999,
          is_my_claim: false,
          claim_owner_assignment_active: false,
          actionable_by_current_user: true,
        },
      ],
      my_entry: null,
    };
    await mockNurseServing(page, { board: handoverBoard });
    await page.goto('/nurse');
    await page.waitForLoadState('networkidle');
    await expect(page.getByText('Ольга Передача')).toBeVisible();
    await expect(
      page.getByText(/Сотрудник, вызвавший пациента, недоступен/),
    ).toBeVisible();
    await expect(page.getByRole('button', { name: 'Принять пациента' })).toBeVisible();
    // An owner-gone entry is NOT a foreign read-only row.
    await expect(page.getByText('Обслуживается другим сотрудником')).toHaveCount(0);
  });

  test('Doctor is denied on /nurse (Nurse-only route)', async ({ page }) => {
    await doctorAuth(page);
    await mockNurseServing(page, {
      profile: { id: 8, role: 'Doctor', email: 'doctor@clinic.com' },
    });
    await page.goto('/nurse');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('body')).toContainText('403');
    await expect(page.getByText('Процедурный кабинет')).toHaveCount(0);
  });
});
