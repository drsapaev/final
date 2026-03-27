import fs from 'node:fs';
import path from 'node:path';
import { chromium } from '../../frontend/node_modules/playwright/index.mjs';

const ROOT = 'c:/final/output/playwright';
// Use a CORS-safe dev origin that is allowed by backend defaults.
const FRONTEND_URL = process.env.FRONTEND_URL || 'http://localhost:8080';
const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:18002';
const AUTH_LOGIN_URL = `${BACKEND_URL}/api/v1/authentication/login`;
const DERMA_URL = `${FRONTEND_URL}/dermatologist?tab=appointments`;

fs.mkdirSync(ROOT, { recursive: true });

function saveJson(filename, data) {
  fs.writeFileSync(
    path.join(ROOT, filename),
    JSON.stringify(data, null, 2),
    'utf-8'
  );
}

async function postJson(url, body, headers = {}) {
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...headers
    },
    body: JSON.stringify(body)
  });

  return response;
}

async function getJson(url, token) {
  const response = await fetch(url, {
    headers: {
      Authorization: `Bearer ${token}`
    }
  });

  if (!response.ok) {
    throw new Error(`GET ${url} failed with ${response.status}`);
  }

  return response.json();
}

function normalizeArray(payload) {
  if (Array.isArray(payload)) {
    return payload;
  }
  if (payload && Array.isArray(payload.data)) {
    return payload.data;
  }
  return [];
}

function flattenServices(payload) {
  if (Array.isArray(payload)) {
    return payload;
  }
  if (Array.isArray(payload?.data)) {
    return payload.data;
  }
  if (payload?.services_by_group && typeof payload.services_by_group === 'object') {
    return Object.values(payload.services_by_group).flat();
  }
  if (Array.isArray(payload?.services)) {
    return payload.services;
  }
  return [];
}

function patientDisplayName(patient) {
  return [patient.last_name, patient.first_name, patient.middle_name]
    .filter(Boolean)
    .join(' ')
    .trim();
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function loginAdmin() {
  if (process.env.DERMA_TOKEN) {
    return {
      access_token: process.env.DERMA_TOKEN,
      user: {
        id: 25,
        username: 'derma@example.com',
        full_name: 'Dermatologist User',
        email: 'ahmad.kosmet1@gmail.com',
        role: 'derma',
        is_active: true,
        is_superuser: false
      }
    };
  }

  for (let attempt = 1; attempt <= 4; attempt += 1) {
    const response = await postJson(AUTH_LOGIN_URL, {
      username: 'admin@example.com',
      password: 'admin123'
    });

    if (response.ok) {
      return response.json();
    }

    if (response.status !== 429 || attempt === 4) {
      throw new Error(`Admin login failed with ${response.status}`);
    }

    await sleep(attempt * 5000);
  }
}

async function createDermatologyVisit(actor) {
  const actorToken = process.env.REGISTRAR_TOKEN || actor.access_token;
  const patientsPayload = await getJson(`${BACKEND_URL}/api/v1/patients/?limit=200`, actorToken);
  const patients = normalizeArray(patientsPayload);
  if (!patients.length) {
    throw new Error('No patients available for registrar cart flow');
  }

  const patient = patients.find((item) => item.id === 448) || patients[0];
  const servicesPayload = await getJson(`${BACKEND_URL}/api/v1/registrar/services`, actorToken);
  const services = flattenServices(servicesPayload);
  const service =
    services.find((item) => item.code === 'D01') ||
    services.find((item) => /дерматолог/i.test(item.name || '')) ||
    services.find((item) => /derma/i.test(item.code || ''));

  if (!service) {
    throw new Error('Dermatology service not found');
  }

  const today = new Date().toISOString().slice(0, 10);
  const cartPayload = {
    patient_id: patient.id,
    discount_mode: 'none',
    payment_method: 'cash',
    notes: 'SSOT DERM-01 live verify',
    visits: [
      {
        department: 'dermatology',
        visit_date: today,
        visit_time: '15:30',
        doctor_id: null,
        services: [
          {
            service_id: service.id,
            quantity: 1,
            custom_price: null
          }
        ],
        notes: 'SSOT DERM-01 live verify'
      }
    ]
  };

  const cartResponse = await postJson(
    `${BACKEND_URL}/api/v1/registrar/cart`,
    cartPayload,
    { Authorization: `Bearer ${actorToken}` }
  );

  if (!cartResponse.ok) {
    throw new Error(`Registrar cart failed with ${cartResponse.status}: ${await cartResponse.text()}`);
  }

  const cartResult = await cartResponse.json();
  const queueSnapshot = await getJson(`${BACKEND_URL}/api/v1/registrar/queues/today`, actorToken);
  return {
    actor_user: actor.user || null,
    patient,
    patient_name: patientDisplayName(patient),
    service,
    cart_payload: cartPayload,
    cart_result: cartResult,
    queue_snapshot: queueSnapshot,
    visit_id: cartResult.visit_ids?.[0] ?? cartResult.created_visits?.[0]?.visit_id ?? null
  };
}

async function fetchExamList(patientId, token) {
  return getJson(
    `${BACKEND_URL}/api/v1/derma/examinations?patient_id=${patientId}&limit=10`,
    token
  );
}

const auth = await loginAdmin();
const token = auth.access_token;
const user = {
  id: 25,
  username: 'derma@example.com',
  full_name: 'Dermatologist User',
  email: 'ahmad.kosmet1@gmail.com',
  role: 'derma',
  is_active: true,
  is_superuser: false
};
const createdVisit = await createDermatologyVisit(auth);
saveJson('derma-live-created-visit.json', createdVisit);
const trackedResponses = [];
const browserConsole = [];

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1400 } });

page.on('response', async (response) => {
  if (
    response.url().includes('/api/v1/derma/') ||
    response.url().includes('/api/v1/registrar/queues/today') ||
    response.url().includes('/api/v1/registrar/all-appointments')
  ) {
    trackedResponses.push({
      url: response.url(),
      status: response.status(),
      method: response.request().method()
    });
  }
});

page.on('console', (message) => {
  browserConsole.push({
    type: message.type(),
    text: message.text()
  });
});

try {
  await page.goto(`${FRONTEND_URL}/login`, { waitUntil: 'domcontentloaded' });
  await page.evaluate(({ tokenValue, userValue }) => {
    window.localStorage.setItem('auth_token', tokenValue);
    window.localStorage.setItem('access_token', tokenValue);
    window.localStorage.setItem('user', JSON.stringify(userValue));
    window.localStorage.setItem('auth_profile', JSON.stringify(userValue));
    window.localStorage.setItem('theme', 'light');
    window.localStorage.setItem('language', 'ru');
  }, { tokenValue: token, userValue: user });

  await page.goto(DERMA_URL, { waitUntil: 'domcontentloaded' });
  await page.getByRole('heading', { name: 'Записи к дерматологу' }).waitFor({ timeout: 20000 });
  await page.waitForTimeout(3000);
  await page.screenshot({ path: path.join(ROOT, 'derma-live-appointments.png'), fullPage: true });

  const initialSnapshot = await page.evaluate(() => {
    const badges = Array.from(document.querySelectorAll('[class*="badge"], button, span'))
      .map((node) => node.textContent?.trim())
      .filter(Boolean)
      .filter((text) =>
        text.includes('Всего:') ||
        text.includes('Ожидают:') ||
        text.includes('Вызваны:') ||
        text.includes('Приняты:')
      );
    const rows = Array.from(document.querySelectorAll('tbody tr')).map((row) =>
      row.textContent?.trim()
    );
    return {
      url: window.location.href,
      authTokenPresent: Boolean(window.localStorage.getItem('auth_token')),
      rows,
      badges
    };
  });
  saveJson('derma-live-initial-snapshot.json', {
    initialSnapshot,
    trackedResponses,
    browserConsole
  });

  const row = page.locator('tr').filter({ hasText: createdVisit.patient_name }).first();
  let appointmentsRowVisible = true;
  try {
    await row.waitFor({ timeout: 8000 });
  } catch (error) {
    appointmentsRowVisible = false;
    await page.getByRole('button', { name: 'Обновить' }).click();
    await page.waitForTimeout(5000);
    await page.screenshot({ path: path.join(ROOT, 'derma-live-appointments-refresh.png'), fullPage: true });
  }

  if (appointmentsRowVisible) {
    await row.click();
  } else {
    await page.goto(`${FRONTEND_URL}/dermatologist?patientId=${createdVisit.patient.id}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(4000);
    await page.getByRole('button', { name: 'Visit' }).click();
  }
  await page.getByRole('heading', { name: `Прием пациента: ${createdVisit.patient_name}` }).waitFor({ timeout: 20000 });
  await page.screenshot({ path: path.join(ROOT, 'derma-live-visit.png'), fullPage: true });

  await page.getByRole('button', { name: 'Skin Examination' }).click();
  await page.getByRole('heading', { name: 'Осмотры кожи' }).waitFor({ timeout: 10000 });
  await page.getByRole('button', { name: 'Новый осмотр' }).click();

  await page.locator('input[type="date"]').fill('2026-03-21');
  await page.locator('select').first().selectOption('combination');
  await page.getByRole('textbox', { name: 'Хорошее, удовлетворительное, проблемное' }).fill('Умеренная сухость и чувствительность');
  await page.getByRole('textbox', { name: 'Акне, пигментация, родинки' }).fill('Локальная эритема на щеках');
  await page.getByRole('textbox', { name: 'Диагноз' }).fill('Чувствительная комбинированная кожа');
  await page.getByRole('textbox', { name: 'План лечения и рекомендации' }).fill('Мягкий уход, SPF, контроль через 2 недели');

  const saveResponsePromise = page.waitForResponse(
    (response) => response.request().method() === 'POST' && response.url().endsWith('/api/v1/derma/examinations'),
    { timeout: 20000 }
  );

  await page.getByRole('button', { name: 'Сохранить осмотр' }).click();
  const saveResponse = await saveResponsePromise;
  const savePayload = await saveResponse.json();

  await page.getByText('Осмотр кожи сохранен успешно').waitFor({ timeout: 10000 });
  await page.getByText('Диагноз: Чувствительная комбинированная кожа').first().waitFor({ timeout: 10000 });
  await page.screenshot({ path: path.join(ROOT, 'derma-live-skin-after-save.png'), fullPage: true });

  await page.getByRole('button', { name: 'History' }).click();
  await page.getByRole('heading', { name: 'История приемов и процедур' }).waitFor({ timeout: 10000 });
  await page.getByText('📋 Чувствительная комбинированная кожа').first().waitFor({ timeout: 10000 });
  await page.screenshot({ path: path.join(ROOT, 'derma-live-history-after-save.png'), fullPage: true });

  await page.getByRole('button', { name: 'Skin Examination' }).click();
  await page.getByText('Диагноз: Чувствительная комбинированная кожа').first().waitFor({ timeout: 10000 });
  await page.screenshot({ path: path.join(ROOT, 'derma-live-skin-reopen.png'), fullPage: true });

  const apiData = await fetchExamList(savePayload.patient_id, token);
  const verification = {
    frontend_url: FRONTEND_URL,
    backend_url: BACKEND_URL,
    user,
    created_visit: createdVisit,
    appointments_row_visible: appointmentsRowVisible,
    save_status: saveResponse.status(),
    save_payload: savePayload,
    api_exam_count: apiData.length,
    api_latest_exam_id: apiData[0]?.id ?? null,
    tracked_responses: trackedResponses
  };

  saveJson('derma-live-verification.json', verification);
  console.log(JSON.stringify(verification, null, 2));
} catch (error) {
  saveJson('derma-live-failure.json', {
    error: {
      name: error?.name || 'Error',
      message: error?.message || String(error)
    },
    trackedResponses,
    browserConsole
  });
  throw error;
} finally {
  await browser.close();
}
