// @ts-check
/**
 * E2E synthetic scenario (#3808 / CR-01 / REG-FE-025):
 * force-majeure preview + confirmation on the Registrar worklist.
 *
 * Covers the regression contract end-to-end through the real UI:
 * 1. A doctor-owned row (queue_owner_kind='doctor', no legacy doctor
 *    fields) opens the modal targeting queue_owner_id, the row's canonical
 *    day AND the row's daily_queue_id; the preview request carries the SAME
 *    specialist_id + target_date + daily_queue_id that the mutation will
 *    carry (round 2 P1: the backend targets exactly that queue instead of
 *    resolving the specialist onto a shared registry surface).
 * 2. Typing ПОДТВЕРЖДАЮ + a reason only enables the destructive action
 *    after the (mocked) dry-run preview succeeds; the transfer POST is
 *    bound to the previewed specialist + date + queue.
 * 3. A resource-owned row with an incidental legacy doctor_id never
 *    opens the modal — the action is visibly unavailable instead of
 *    silently retargeting doctor 3's whole queue.
 *
 * All API calls are mocked — no backend needed.
 */

import { test, expect } from '@playwright/test';

function base64UrlEncode(value: unknown): string {
  return Buffer.from(JSON.stringify(value))
    .toString('base64')
    .replace(/=/g, '')
    .replace(/\+/g, '-')
    .replace(/\//g, '_');
}

function createJwt(payload: Record<string, unknown>): string {
  return `${base64UrlEncode({ alg: 'HS256', typ: 'JWT' })}.${base64UrlEncode(payload)}.sig`;
}

const registrarProfile = {
  id: 20,
  username: 'registrar@example.com',
  email: 'registrar@example.com',
  full_name: 'Registrar User',
  role: 'Registrar',
  is_active: true,
  is_superuser: false,
};

const accessToken = createJwt({
  sub: String(registrarProfile.id),
  username: registrarProfile.username,
  user_id: registrarProfile.id,
  exp: Math.floor(Date.now() / 1000) + 3600,
});

function localDateString(): string {
  const now = new Date();
  const yyyy = now.getFullYear();
  const mm = String(now.getMonth() + 1).padStart(2, '0');
  const dd = String(now.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}

function jsonResponse(body: unknown): { status: number; contentType: string; body: string } {
  return {
    status: 200,
    contentType: 'application/json; charset=utf-8',
    body: JSON.stringify(body),
  };
}

const DOCTOR_OWNED_PATIENT = 'Пациент Докторов';
const RESOURCE_OWNED_PATIENT = 'Пациент Ресурсов';

test.describe('Registrar force majeure (#3808 REG-FE-025)', () => {
  const targetDate = localDateString();

  /** Captured preview URLs and mutation bodies (asserted by the tests). */
  let previewUrls: string[] = [];
  let transferBodies: Record<string, unknown>[] = [];

  test.beforeEach(async ({ page }) => {
    previewUrls = [];
    transferBodies = [];

    await page.addInitScript(({ token, profile }) => {
      sessionStorage.setItem('auth_token', token);
      sessionStorage.setItem('refresh_token', token);
      sessionStorage.setItem('auth_profile', JSON.stringify(profile));
      sessionStorage.setItem('user', JSON.stringify(profile));
    }, { token: accessToken, profile: registrarProfile });

    await page.route('**/api/v1/**', async (route) => {
      const url = new URL(route.request().url());
      const { pathname } = url;

      if (pathname === '/api/v1/setup/status') {
        await route.fulfill(jsonResponse({ initialized: true }));
        return;
      }

      if (pathname === '/api/v1/auth/me') {
        await route.fulfill(jsonResponse(registrarProfile));
        return;
      }

      if (pathname === '/api/v1/queues/profiles') {
        await route.fulfill(jsonResponse({
          success: true,
          profiles: [{
            key: 'cardiology',
            title: 'Cardiology',
            title_ru: 'Кардиология',
            queue_tags: ['cardiology'],
            icon: 'Heart',
            color: '#ef4444',
            order: 1,
          }],
          source: 'database',
        }));
        return;
      }

      if (pathname === '/api/v1/registrar/doctors') {
        await route.fulfill(jsonResponse({
          doctors: [{
            id: 3,
            full_name: 'Dr Owner',
            specialty: 'cardiology',
            cabinet: '12',
          }],
        }));
        return;
      }

      if (pathname === '/api/v1/registrar/services') {
        await route.fulfill(jsonResponse({
          services_by_group: {
            cardio: [{
              id: 101,
              code: 'C001',
              name: 'Консультация кардиолога',
              price: 150000,
              requires_doctor: true,
            }],
          },
        }));
        return;
      }

      if (pathname === '/api/v1/registrar/queues/today') {
        // Read-model rows: the doctor-owned row carries NO legacy doctor
        // fields; the resource-owned row carries an INCIDENTAL doctor_id.
        await route.fulfill(jsonResponse({
          date: targetDate,
          queues: [{
            specialty: 'Кардиология',
            queue_tag: 'cardiology',
            queue_number: 1,
            specialist_name: 'Dr Owner',
            entries: [
              {
                id: 101,
                patient_id: 51,
                patient_name: DOCTOR_OWNED_PATIENT,
                phone: '+998901234567',
                status: 'waiting',
                canonical_status: 'waiting',
                queue_owner_kind: 'doctor',
                queue_owner_id: 3,
                daily_queue_id: 41,
                record_date: targetDate,
                cost: 150000,
                services: [],
              },
              {
                id: 102,
                patient_id: 52,
                patient_name: RESOURCE_OWNED_PATIENT,
                phone: '+998901234568',
                status: 'waiting',
                canonical_status: 'waiting',
                queue_owner_kind: 'resource',
                queue_owner_id: 7,
                daily_queue_id: 12,
                record_date: targetDate,
                cost: 90000,
                services: [],
                // incidental legacy field: must NEVER become the target
                doctor_id: 3,
                doctor_name: 'Dr Incidental',
              },
            ],
          }],
        }));
        return;
      }

      if (pathname === '/api/v1/force-majeure/pending-entries') {
        previewUrls.push(url.search);
        await route.fulfill(jsonResponse([
          { id: 1, number: 1, patient_name: 'A A', total_amount: 50000, status: 'waiting' },
          { id: 2, number: 2, patient_name: 'B B', total_amount: 25000, status: 'waiting' },
        ]));
        return;
      }

      if (pathname === '/api/v1/force-majeure/transfer') {
        transferBodies.push(route.request().postDataJSON() as Record<string, unknown>);
        await route.fulfill(jsonResponse({ success: true, transferred: 2 }));
        return;
      }

      if (pathname === '/api/v1/notifications/history/stats') {
        await route.fulfill(jsonResponse({ recent_activity: [] }));
        return;
      }

      // Default: empty success
      await route.fulfill(jsonResponse({ success: true }));
    });
  });

  test('doctor-owned row: preview binds specialist + date, confirmation sends the same target', async ({ page }) => {
    await page.goto('/registrar');

    // The per-entry (non-aggregated) rows live on the specialty tab; the
    // default "все отделения" tab shows patient aggregates without owner
    // facts, where the action is deliberately unavailable (see below).
    const cardioTab = page.getByRole('tab', { name: 'Кардиология' });
    await expect(cardioTab).toBeVisible({ timeout: 20000 });
    await cardioTab.click();

    // The doctor-owned read-model row renders (no legacy doctor fields).
    const doctorRow = page.locator('tr', { hasText: DOCTOR_OWNED_PATIENT }).first();
    await expect(doctorRow).toBeVisible({ timeout: 20000 });

    // Open the row context menu and pick force majeure.
    await doctorRow.locator('[aria-label="Еще"]').click();
    const menuItem = page.locator('.context-menu button', { hasText: 'Форс-мажор' });
    await expect(menuItem).toBeVisible();
    await menuItem.click();

    // The modal opens.
    const dialog = page.locator('[role="dialog"]');
    await expect(dialog).toBeVisible();

    // The preview (dry run) is bound to the canonical owner + row day + queue.
    await expect
      .poll(() => previewUrls.length, { timeout: 10000 })
      .toBeGreaterThanOrEqual(1);
    expect(previewUrls[0]).toContain('specialist_id=3');
    expect(previewUrls[0]).toContain(`target_date=${targetDate}`);
    expect(previewUrls[0]).toContain('daily_queue_id=41');

    // The dry-run card shows the previewed entries.
    await expect(page.getByText('2 записей')).toBeVisible({ timeout: 10000 });

    // Fill reason + confirmation phrase.
    await page.locator('[aria-label="Force majeure reason"]').fill('Затопление кабинета');
    await page.locator('[placeholder="ПОДТВЕРЖДАЮ"]').fill('ПОДТВЕРЖДАЮ');

    // The destructive action is enabled after the successful preview.
    const transferButton = page.getByRole('button', { name: 'Перенести', exact: true });
    await expect(transferButton).toBeEnabled();
    await transferButton.click();

    // The mutation carries the SAME specialist + date + queue as the preview.
    await expect
      .poll(() => transferBodies.length, { timeout: 10000 })
      .toBeGreaterThanOrEqual(1);
    expect(transferBodies[0]).toMatchObject({
      specialist_id: 3,
      target_date: targetDate,
      daily_queue_id: 41,
      reason: 'Затопление кабинета',
      send_notifications: true,
    });
  });

  test('resource-owned row: force majeure is visibly unavailable, never retargeted to the incidental doctor', async ({ page }) => {
    await page.goto('/registrar');

    const cardioTab = page.getByRole('tab', { name: 'Кардиология' });
    await expect(cardioTab).toBeVisible({ timeout: 20000 });
    await cardioTab.click();

    const resourceRow = page.locator('tr', { hasText: RESOURCE_OWNED_PATIENT }).first();
    await expect(resourceRow).toBeVisible({ timeout: 20000 });

    await resourceRow.locator('[aria-label="Еще"]').click();
    const menuItem = page.locator('.context-menu button', { hasText: 'Форс-мажор' });
    await expect(menuItem).toBeVisible();
    await menuItem.click();

    // No modal opens: the unambiguous-doctor contract is not satisfied.
    await page.waitForTimeout(500);
    await expect(page.locator('[role="dialog"]')).toHaveCount(0);

    // No preview was requested either (no silent retargeting).
    expect(previewUrls).toHaveLength(0);

    // The registrar sees WHY the action is unavailable.
    await expect(page.getByText('Форс-мажор доступен только', { exact: false })).toBeVisible({ timeout: 10000 });
  });
});
