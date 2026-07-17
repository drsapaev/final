// @ts-check
import { test, expect } from '@playwright/test';

function base64UrlEncode(value) {
  return Buffer.from(JSON.stringify(value))
    .toString('base64')
    .replace(/=/g, '')
    .replace(/\+/g, '-')
    .replace(/\//g, '_');
}

function createJwt(payload) {
  return `${base64UrlEncode({ alg: 'HS256', typ: 'JWT' })}.${base64UrlEncode(payload)}.sig`;
}

const registrarProfile = {
  id: 20,
  username: 'registrar@example.com',
  email: 'registrar@example.com',
  full_name: 'Registrar User',
  role: 'Receptionist',
  is_active: true,
  is_superuser: false,
};

const accessToken = createJwt({
  sub: String(registrarProfile.id),
  username: registrarProfile.username,
  user_id: registrarProfile.id,
  exp: Math.floor(Date.now() / 1000) + 3600,
});

function jsonResponse(body) {
  return {
    status: 200,
    contentType: 'application/json; charset=utf-8',
    body: JSON.stringify(body),
  };
}

test.describe('Registrar queue time rendering', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(({ token, profile }) => {
      // PR-39 / P0-2: tokens migrated from localStorage to sessionStorage
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
          profiles: [
            {
              key: 'cardiology',
              title: 'Cardiology',
              title_ru: 'Кардиология',
              queue_tags: ['cardiology'],
              icon: 'Heart',
              color: '#ef4444',
              order: 1,
            },
          ],
          source: 'database',
        }));
        return;
      }

      if (pathname === '/api/v1/registrar/doctors') {
        await route.fulfill(jsonResponse({
          doctors: [
            {
              id: 1,
              full_name: 'Dr Test',
              specialty: 'cardiology',
              cabinet: '12',
            },
          ],
        }));
        return;
      }

      if (pathname === '/api/v1/registrar/services') {
        await route.fulfill(jsonResponse({
          services_by_group: {
            cardio: [
              { id: 1, name: 'Consultation', service_code: 'K01' },
            ],
          },
        }));
        return;
      }

      if (pathname === '/api/v1/registrar/queue-settings') {
        await route.fulfill(jsonResponse({ data: { max_queue_size: 25 } }));
        return;
      }

      if (pathname === '/api/v1/registrar/departments') {
        await route.fulfill(jsonResponse({
          data: [
            { key: 'cardio', title: 'Кардиология', active: true },
          ],
        }));
        return;
      }

      if (pathname === '/api/v1/registrar/queues/today') {
        await route.fulfill(jsonResponse({
          queues: [
            {
              queue_id: 1,
              specialist_id: 1,
              specialist_name: 'Dr Test',
              specialty: 'cardiology',
              cabinet: '12',
              entries: [
                {
                  id: 101,
                  number: 7,
                  patient_id: 1001,
                  patient_name: 'Time Check Patient',
                  patient_birth_year: 1990,
                  phone: '+998900000000',
                  address: 'Test address',
                  services: ['Consultation'],
                  service_codes: ['K01'],
                  cost: 100000,
                  payment_status: 'paid',
                  payment_type: 'cash',
                  source: 'desk',
                  status: 'waiting',
                  created_at: '2026-04-16T09:31:00+05:00',
                  queue_time: '2026-04-16T09:30:00+05:00',
                  discount_mode: 'none',
                  approval_status: null,
                  type: 'online_queue',
                  record_type: 'online_queue',
                  queue_entry_id: 101,
                  department_key: 'cardiology',
                  department: 'cardiology',
                  session_id: 'sess-1',
                },
              ],
              stats: {
                total: 1,
                waiting: 1,
                called: 0,
                served: 0,
                online_entries: 0,
              },
              opened_at: '2026-04-16T09:00:00+05:00',
            },
          ],
          total_queues: 1,
          date: '2026-04-16',
        }));
        return;
      }

      if (pathname === '/api/v1/messages/conversations') {
        await route.fulfill(jsonResponse({ conversations: [], unread_count: 0 }));
        return;
      }

      if (pathname === '/api/v1/messages/unread') {
        await route.fulfill(jsonResponse({ unread_count: 0 }));
        return;
      }

      if (pathname === '/api/v1/users/me/preferences') {
        await route.fulfill(jsonResponse({}));
        return;
      }

      if (pathname.startsWith('/api/v1/patients/')) {
        await route.fulfill(jsonResponse({}));
        return;
      }

      await route.fulfill(jsonResponse({}));
    });
  });

  test('renders queue_time in clinic timezone for registrar rows', async ({ page }) => {
    await page.goto('/registrar');

    const row = page.locator('tr', { hasText: 'Time Check Patient' }).first();
    await expect(row).toBeVisible({ timeout: 30_000 });
    await expect(row).toContainText('09:30:00');
    await expect(row).not.toContainText('04:30:00');
  });
});
