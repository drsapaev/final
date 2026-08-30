// @ts-check
/**
 * PR-UI-16-2 — Deterministic product screenshot pipeline for the Landing page.
 *
 * PURPOSE
 *   Captures REAL application screens (real UI components, real routes, real
 *   render pipeline) against a fully mocked API with deterministic data, and
 *   writes them to `public/landing/screens/*.png` for use on the Landing page
 *   (Hero + Screens showcase, plan §PR-UI-16).
 *
 *   These are genuine captures of the existing product — no fake UI, no
 *   advertising mockups (user-authorized source: "existing application UI +
 *   existing mock API infrastructure + deterministic data", decision Q1=A).
 *
 * REPRODUCIBILITY CONTRACT (plan §PR-UI-16 AC A7)
 *   - Regeneration command:  npm run capture:landing-shots
 *     (runs this spec with CAPTURE_LANDING_SHOTS=1; dev server auto-started
 *     by the Playwright webServer config — no backend needed).
 *   - Mock data source: self-contained fixtures in this file, mirroring the
 *     shapes pinned by e2e/visual-regression.spec.ts (PR-UI-12-4 five
 *     clinical screens + registrar wizard). All names are synthetic
 *     ("Тестов Тест Тестович" — derived from "test"; phone +998900000000)
 *     per the PII policy in AGENTS.md §PII.
 *   - Routes captured (deep links, no dropdown interaction):
 *       /registrar/queue?doctor=1          → QueueTable (canonical DataTable)
 *       /clinical/appointments             → EAT behind the "Расширенная
 *                                             таблица" toggle (canonical)
 *       /clinical/search (query "Тестов")  → patient result cards
 *       /lab                               → lab queue cards
 *       /doctor/dermatology?visitId=501&patientId=101 → EMRContainerV2
 *       /registrar (wizard "Новая запись") → AppointmentWizardV2 step 1
 *   - Viewport: 1440×900, deviceScaleFactor 2 (retina-crisp for the landing
 *     card sizes).
 *   - Theme: LIGHT, pinned via localStorage `colorScheme=light` (fresh
 *     contexts default to light anyway — the init script makes it explicit).
 *   - Language: ru (app default).
 *   - Clock: fixed at 2026-08-29T12:00:00+05:00 via page.clock.install (the
 *     same instant as the PR-UI-12-4 baselines) so date-derived UI (queue
 *     badges, "today" labels) renders identically on any future run date.
 *
 * GATING
 *   Skipped unless CAPTURE_LANDING_SHOTS=1 — never runs in CI's default e2e
 *   sweep (screenshot generation is an explicit, on-demand operation; the
 *   committed PNGs are versioned artifacts, like any other static asset).
 */

import { mkdirSync } from 'fs';
import path from 'path';
import { test } from '@playwright/test';

test.skip(!process.env.CAPTURE_LANDING_SHOTS, 'capture pipeline — run explicitly: npm run capture:landing-shots');

const OUT_DIR = path.resolve(process.cwd(), 'public/landing/screens');
mkdirSync(OUT_DIR, { recursive: true });

// Fixed capture instant — mirrors PR-UI-12-4 baseline policy (date-rollover
// determinism; see the clock note in visual-regression.spec.ts).
const CAPTURE_INSTANT = new Date('2026-08-29T12:00:00+05:00');

// ── mock helpers (same shapes as visual-regression.spec.ts) ────────────────

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

function createToken(profile: { id: number; username: string }): string {
  return createJwt({
    sub: String(profile.id), username: profile.username,
    user_id: profile.id, exp: Math.floor(CAPTURE_INSTANT.getTime() / 1000) + 3600,
  });
}

function jsonResponse(body: unknown): { status: number; contentType: string; body: string } {
  return { status: 200, contentType: 'application/json; charset=utf-8', body: JSON.stringify(body) };
}

const registrarProfile = {
  id: 20, username: 'registrar@example.com', email: 'registrar@example.com',
  full_name: 'Registrar User', role: 'Receptionist', is_active: true, is_superuser: false,
};
const appointmentsProfile = {
  id: 21, username: 'registrar2@example.com', email: 'registrar2@example.com',
  full_name: 'Registrar User', role: 'Registrar', is_active: true, is_superuser: false,
};
const labProfile = {
  id: 40, username: 'lab@clinic.com', email: 'lab@clinic.com',
  full_name: 'Lab User', role: 'Lab', is_active: true, is_superuser: false,
};
const doctorProfile = {
  id: 50, username: 'doctor@clinic.com', email: 'doctor@clinic.com',
  full_name: 'Doctor User', role: 'Doctor', is_active: true, is_superuser: false,
};

async function installAuth(page: import('@playwright/test').Page, profile: typeof registrarProfile) {
  await page.addInitScript(({ token, profile: p }: { token: string; profile: typeof registrarProfile }) => {
    sessionStorage.setItem('auth_token', token);
    sessionStorage.setItem('refresh_token', token);
    sessionStorage.setItem('auth_profile', JSON.stringify(p));
    sessionStorage.setItem('user', JSON.stringify(p));
    // Pin the capture theme: light (ThemeContext reads localStorage on boot).
    localStorage.setItem('colorScheme', 'light');
  }, { token: createToken(profile), profile });
  // Mock WebSocket to prevent ECONNREFUSED noise (no backend in E2E).
  await page.routeWebSocket('**/*', ws => { ws.close(); });
}

async function shot(page: import('@playwright/test').Page, name: string) {
  await page.screenshot({
    path: path.join(OUT_DIR, name),
    animations: 'disabled',
    caret: 'hide',
  });
  // eslint-disable-next-line no-console
  console.log(`[capture-landing-shots] wrote ${name}`);
}

// Flat queue entry shape (mirrors visual-regression.spec.ts / registrar-time.spec.ts).
const queueEntry = (i: number) => ({
  id: 2000 + i,
  number: i + 1,
  patient_id: 100 + i,
  patient_name: `Тестов Тест Тестович ${i + 1}`,
  patient_phone: '+998900000000',
  queue_number: i + 1,
  queue_time: `2026-08-29T09:${String(i * 3).padStart(2, '0')}:00+05:00`,
  created_at: `2026-08-29T09:${String(i * 3).padStart(2, '0')}:00+05:00`,
  status: i === 0 ? 'called' : 'waiting',
  source: i % 2 === 0 ? 'online' : 'desk',
  payment_status: 'paid',
  payment_type: 'cash',
  cost: 100000,
  services: ['Консультация'],
  service_codes: ['K01'],
  discount_mode: 'none',
  approval_status: null,
  type: 'online_queue',
  record_type: 'online_queue',
  queue_entry_id: 2000 + i,
  department_key: 'cardiology',
  department: 'cardiology',
  session_id: 'sess-1',
});

const queuesTodayResponse = (entries: ReturnType<typeof queueEntry>[]) => jsonResponse({
  queues: [{
    queue_id: 1,
    specialist_id: 1,
    specialist_name: 'Dr Test',
    specialty: 'cardiology',
    cabinet: '12',
    entries,
    stats: { total: entries.length, waiting: entries.length - 1, called: 1, served: 0, online_entries: 0 },
    opened_at: '2026-08-29T09:00:00+05:00',
  }],
  total_queues: 1,
  date: '2026-08-29',
  timezone: 'Asia/Tashkent',
});

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
});

test.describe('PR-UI-16-2 — Landing product screenshots (deterministic capture)', () => {
  test('queue screen — /registrar/queue (QueueTable, canonical DataTable)', async ({ page }) => {
    await page.clock.install({ time: CAPTURE_INSTANT });
    await installAuth(page, registrarProfile);
    await page.route('**/api/v1/**', async (route) => {
      const { pathname } = new URL(route.request().url());
      if (pathname === '/api/v1/setup/status') { await route.fulfill(jsonResponse({ initialized: true })); return; }
      if (pathname === '/api/v1/auth/me') { await route.fulfill(jsonResponse(registrarProfile)); return; }
      if (pathname === '/api/v1/queue/available-specialists') {
        await route.fulfill(jsonResponse({ specialists: [{ id: 1, doctor_name: 'Dr Test', specialty: 'cardiology', cabinet: '12' }] }));
        return;
      }
      if (pathname === '/api/v1/registrar/queues/today') {
        await route.fulfill(queuesTodayResponse(Array.from({ length: 12 }, (_, i) => queueEntry(i))));
        return;
      }
      if (pathname === '/api/v1/queues/profiles') { await route.fulfill(jsonResponse({ success: true, profiles: [], source: 'database' })); return; }
      if (pathname === '/api/v1/registrar/doctors') { await route.fulfill(jsonResponse({ doctors: [{ id: 1, full_name: 'Dr Test', specialty: 'cardiology', cabinet: '12' }] })); return; }
      if (pathname === '/api/v1/registrar/services') { await route.fulfill(jsonResponse({ services_by_group: {} })); return; }
      if (pathname === '/api/v1/registrar/queue-settings') { await route.fulfill(jsonResponse({ data: { max_queue_size: 25 } })); return; }
      if (pathname === '/api/v1/registrar/departments') { await route.fulfill(jsonResponse({ data: [{ key: 'cardio', title: 'Кардиология', active: true }] })); return; }
      if (pathname === '/api/v1/registrar/appointments' || pathname === '/api/v1/registrar/all-appointments') { await route.fulfill(jsonResponse({ appointments: [], total: 0, has_more: false })); return; }
      if (pathname === '/api/v1/notifications/history/stats') { await route.fulfill(jsonResponse({ recent_activity: [] })); return; }
      await route.fulfill(jsonResponse({ success: true }));
    });

    await page.goto('/registrar/queue?doctor=1');
    await page.locator('.qt-table-container table').first().waitFor({ state: 'visible', timeout: 15000 });
    await page.locator('.qt-table-container').getByText('Тестов Тест Тестович 1').first().waitFor({ state: 'visible', timeout: 15000 });
    await page.waitForTimeout(600);

    await shot(page, 'queue.png');
  });

  test('appointments screen — /clinical/appointments (EAT, canonical table)', async ({ page }) => {
    await page.clock.install({ time: CAPTURE_INSTANT });
    await installAuth(page, appointmentsProfile);
    await page.route('**/api/v1/**', async (route) => {
      const { pathname } = new URL(route.request().url());
      if (pathname === '/api/v1/setup/status') { await route.fulfill(jsonResponse({ initialized: true })); return; }
      if (pathname === '/api/v1/auth/me') { await route.fulfill(jsonResponse(appointmentsProfile)); return; }
      if (pathname === '/api/v1/appointments') {
        await route.fulfill(jsonResponse(Array.from({ length: 15 }, (_, i) => ({
          id: 5000 + i,
          record_type: 'appointment',
          source_type: 'manual',
          appointment_id: 5000 + i,
          patient_id: 200 + i,
          patient_last_name: 'Тестов',
          patient_first_name: 'Тест',
          patient_fio: `Тестов Тест Тестович ${i + 1}`,
          patient_name: `Тестов Тест Тестович ${i + 1}`,
          patient_phone: '+998900000000',
          doctor_id: 1,
          doctor_name: 'Dr Test',
          specialty: 'cardiology',
          appointment_time: `10:${String(i * 4).padStart(2, '0')}`,
          appointment_date: '2026-08-29',
          status: 'scheduled',
          session_id: 'session-1',
          session_color: '#ef4444',
          services_names: ['Консультация кардиолога'],
          available_actions: ['cancel', 'print'],
        }))));
        return;
      }
      if (pathname === '/api/v1/notifications/history/stats') { await route.fulfill(jsonResponse({ recent_activity: [] })); return; }
      await route.fulfill(jsonResponse({ success: true }));
    });

    await page.goto('/clinical/appointments');
    await page.locator('table').first().waitFor({ state: 'visible', timeout: 15000 });
    // Switch to the canonical EAT surface.
    await page.locator('div[role="checkbox"]').filter({ hasText: 'Расширенная таблица' }).first().click();
    await page.locator('.eat-table-scroll table').first().waitFor({ state: 'visible', timeout: 15000 });
    await page.locator('.eat-table-scroll').getByText('Тестов Тест Тестович 1').first().waitFor({ state: 'visible', timeout: 15000 });
    await page.waitForTimeout(600);

    await shot(page, 'appointments.png');
  });

  test('patients screen — /clinical/search (patient result cards)', async ({ page }) => {
    await page.clock.install({ time: CAPTURE_INSTANT });
    await installAuth(page, registrarProfile);
    await page.route('**/api/v1/**', async (route) => {
      const { pathname } = new URL(route.request().url());
      if (pathname === '/api/v1/setup/status') { await route.fulfill(jsonResponse({ initialized: true })); return; }
      if (pathname === '/api/v1/auth/me') { await route.fulfill(jsonResponse(registrarProfile)); return; }
      if (pathname === '/api/v1/patients/') {
        await route.fulfill(jsonResponse(Array.from({ length: 4 }, (_, i) => ({
          id: 300 + i,
          last_name: 'Тестов',
          first_name: 'Тест',
          middle_name: 'Тестович',
          full_name: `Тестов Тест Тестович ${i + 1}`,
          phone: '+998900000000',
          birth_date: '1990-01-01',
          sex: 'male',
          created_at: '2026-01-01T00:00:00Z',
        }))));
        return;
      }
      if (pathname === '/api/v1/notifications/history/stats') { await route.fulfill(jsonResponse({ recent_activity: [] })); return; }
      await route.fulfill(jsonResponse({ success: true }));
    });

    await page.goto('/clinical/search');
    const input = page.getByLabel('Поиск пациентов и визитов');
    await input.waitFor({ state: 'visible', timeout: 15000 });
    await input.fill('Тестов');
    await input.press('Enter');
    await page.getByRole('button', { name: /Открыть пациента/ }).first().waitFor({ state: 'visible', timeout: 15000 });
    await page.waitForTimeout(600);

    await shot(page, 'patients.png');
  });

  test('lab screen — /lab (lab queue cards)', async ({ page }) => {
    await page.clock.install({ time: CAPTURE_INSTANT });
    await installAuth(page, labProfile);
    await page.route('**/api/v1/**', async (route) => {
      const { pathname } = new URL(route.request().url());
      if (pathname === '/api/v1/setup/status') { await route.fulfill(jsonResponse({ initialized: true })); return; }
      if (pathname === '/api/v1/auth/me') { await route.fulfill(jsonResponse(labProfile)); return; }
      if (pathname === '/api/v1/lab/queue/today') {
        await route.fulfill(jsonResponse({
          entries: Array.from({ length: 5 }, (_, i) => ({
            id: 600 + i,
            appointment_id: 600 + i,
            patient_fio: `Тестов Тест Тестович ${i + 1}`,
            patient_id: 400 + i,
            status: i === 0 ? 'in_progress' : 'waiting',
            created_at: '2026-08-29T09:00:00+05:00',
            services: ['Общий анализ крови'],
            queue_number: i + 1,
          })),
          total: 5,
        }));
        return;
      }
      // Bare-array endpoints (mapping over them directly — object wrappers crash).
      if (pathname === '/api/v1/lab/templates') { await route.fulfill(jsonResponse([])); return; }
      if (pathname === '/api/v1/lab/catalog/units') { await route.fulfill(jsonResponse([])); return; }
      if (pathname === '/api/v1/lab/catalog/analytes') { await route.fulfill(jsonResponse([])); return; }
      if (pathname === '/api/v1/notifications/history/stats') { await route.fulfill(jsonResponse({ recent_activity: [] })); return; }
      await route.fulfill(jsonResponse({ success: true }));
    });

    await page.goto('/lab');
    await page.locator('.lqw-root').first().waitFor({ state: 'visible', timeout: 15000 });
    await page.locator('.lqw-root').getByText('Тестов Тест Тестович 1').first().waitFor({ state: 'visible', timeout: 15000 });
    await page.waitForTimeout(600);

    await shot(page, 'lab.png');
  });

  test('EMR screen — dermatology visit view (EMRContainerV2)', async ({ page }) => {
    await page.clock.install({ time: CAPTURE_INSTANT });
    await installAuth(page, doctorProfile);
    const dermaQueueEntry = {
      id: 1001,
      number: 1,
      patient_id: 101,
      patient_fio: 'Тестов Тест Тестович',
      patient_name: 'Тестов Тест Тестович',
      patient_phone: '+998900000000',
      patient_birth_year: 1990,
      services: [{ id: 101, code: 'D001', name: 'Консультация дерматолога', price: 150000 }],
      cost: 150000,
      total_amount: 150000,
      payment_status: 'paid',
      payment_type: 'cash',
      canonical_status: 'queued',
      status: 'queued',
      queue_position: 1,
      queue_tag: 'derma',
      visit_id: 501,
      appointment_date: '2026-08-29',
      appointment_time: '10:00',
      created_at: '2026-08-29T09:00:00+05:00',
      doctor_id: 1,
      doctor_name: 'Dr Test',
      department: 'derma',
      available_actions: ['in_cabinet', 'complete'],
      queue_entry_id: 1001,
      can_start_visit: true,
      record_kind: 'appointment',
      source_kind: 'manual',
    };
    await page.route('**/api/v1/**', async (route) => {
      const { pathname } = new URL(route.request().url());
      if (pathname === '/api/v1/setup/status') { await route.fulfill(jsonResponse({ initialized: true })); return; }
      if (pathname === '/api/v1/auth/me') { await route.fulfill(jsonResponse(doctorProfile)); return; }
      if (pathname === '/api/v1/registrar/queues/today') {
        await route.fulfill(jsonResponse({
          queues: [{
            queue_id: 1,
            specialist_id: 1,
            specialist_name: 'Dr Test',
            specialty: 'derma',
            cabinet: '12',
            entries: [dermaQueueEntry],
            stats: { total: 1, waiting: 1, called: 0, served: 0, online_entries: 0 },
            opened_at: '2026-08-29T09:00:00+05:00',
          }],
          total_queues: 1,
          date: '2026-08-29',
          timezone: 'Asia/Tashkent',
        }));
        return;
      }
      if (pathname === '/api/v1/registrar/services') { await route.fulfill(jsonResponse({ services_by_group: {} })); return; }
      // EMR GET → 404: canonical "new visit" draft (deterministic).
      if (pathname === '/api/v1/v2/emr/501') { await route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'not found' }) }); return; }
      if (pathname === '/api/v1/derma/examinations') { await route.fulfill(jsonResponse({ items: [], data: [] })); return; }
      if (pathname === '/api/v1/derma/procedures') { await route.fulfill(jsonResponse({ items: [], data: [] })); return; }
      if (pathname === '/api/v1/notifications/history/stats') { await route.fulfill(jsonResponse({ recent_activity: [] })); return; }
      await route.fulfill(jsonResponse({ success: true }));
    });

    await page.goto('/doctor/dermatology?visitId=501&patientId=101');
    await page.locator('.emr-v2-container').first().waitFor({ state: 'visible', timeout: 20000 });
    await page.waitForTimeout(800);

    await shot(page, 'emr.png');
  });

  test('registrar wizard — /registrar (AppointmentWizardV2, patient step)', async ({ page }) => {
    await page.clock.install({ time: CAPTURE_INSTANT });
    await installAuth(page, registrarProfile);
    await page.route('**/api/v1/**', async (route) => {
      const { pathname } = new URL(route.request().url());
      if (pathname === '/api/v1/setup/status') { await route.fulfill(jsonResponse({ initialized: true })); return; }
      if (pathname === '/api/v1/auth/me') { await route.fulfill(jsonResponse(registrarProfile)); return; }
      if (pathname === '/api/v1/queues/profiles') {
        await route.fulfill(jsonResponse({
          success: true,
          profiles: [{ key: 'cardiology', title: 'Cardiology', title_ru: 'Кардиология', queue_tags: ['cardiology'], icon: 'Heart', color: '#ef4444', order: 1 }],
          source: 'database',
        }));
        return;
      }
      if (pathname === '/api/v1/registrar/doctors') { await route.fulfill(jsonResponse({ doctors: [{ id: 1, full_name: 'Dr Test', specialty: 'cardiology', cabinet: '12' }] })); return; }
      if (pathname === '/api/v1/registrar/services') { await route.fulfill(jsonResponse({ services_by_group: { cardio: [{ id: 101, code: 'C001', name: 'Консультация кардиолога', price: 150000, requires_doctor: true, is_consultation: true, department_key: 'cardiology' }] } })); return; }
      if (pathname === '/api/v1/registrar/queues/today') {
        await route.fulfill(jsonResponse({ queues: [], total_queues: 0, date: '2026-08-29', timezone: 'Asia/Tashkent' }));
        return;
      }
      if (pathname === '/api/v1/registrar/appointments' || pathname === '/api/v1/registrar/all-appointments') { await route.fulfill(jsonResponse({ appointments: [], total: 0, has_more: false })); return; }
      if (pathname === '/api/v1/notifications/history/stats') { await route.fulfill(jsonResponse({ recent_activity: [] })); return; }
      await route.fulfill(jsonResponse({ success: true }));
    });

    await page.goto('/registrar');
    await page.waitForTimeout(2000);
    // Open the check-in wizard ("Новая запись" = the Patient → Registrar step
    // of the workflow the Landing shows).
    await page.locator('text=Новая запись').first().click();
    await page.waitForTimeout(1500);
    await page.locator('.wizard-progress').first().waitFor({ state: 'visible', timeout: 15000 });
    await page.waitForTimeout(600);

    await shot(page, 'registrar-wizard.png');
  });
});
