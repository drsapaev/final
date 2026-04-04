const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const { chromium } = require(path.join(ROOT, 'frontend', 'node_modules', 'playwright'));
const BACKEND_ROOT = path.join(ROOT, 'backend');
const WEB_BASE = 'http://127.0.0.1:5173';
const API_BASE = 'http://127.0.0.1:18000/api/v1';
const OUTPUT_DIR = path.join(ROOT, 'output', 'browser-row-actions');

fs.mkdirSync(OUTPUT_DIR, { recursive: true });

function ts() {
  return new Date().toISOString().replace(/[:.]/g, '-');
}

function writeJson(name, data) {
  const file = path.join(OUTPUT_DIR, name);
  fs.writeFileSync(file, JSON.stringify(data, null, 2), 'utf8');
  return file;
}

function todayTashkent() {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Tashkent',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  }).format(new Date());
}

function mintSession(username) {
  const pythonCode = `
import json
import sys
import urllib.request

sys.path.insert(0, r"${BACKEND_ROOT.replace(/\\/g, '\\\\')}")

from app.core.security import create_access_token

username = sys.argv[1]
token = create_access_token(subject=username, expires_minutes=240)
req = urllib.request.Request(
    "http://127.0.0.1:18000/api/v1/auth/me",
    headers={"Authorization": f"Bearer {token}"},
)
with urllib.request.urlopen(req, timeout=30) as resp:
    profile = json.loads(resp.read().decode("utf-8"))

print(json.dumps({"username": username, "token": token, "profile": profile}, ensure_ascii=False))
`;

  const raw = execFileSync('python', ['-c', pythonCode, username], {
    cwd: ROOT,
    encoding: 'utf8'
  }).trim();

  return JSON.parse(raw);
}

async function apiGetJson(url, token) {
  const response = await fetch(url, {
    headers: {
      Authorization: `Bearer ${token}`
    }
  });
  const text = await response.text();
  let data;
  try {
    data = text ? JSON.parse(text) : null;
  } catch (error) {
    throw new Error(`Failed to parse JSON from ${url}: ${error.message}\n${text.slice(0, 500)}`);
  }
  if (!response.ok) {
    throw new Error(`GET ${url} failed with ${response.status}: ${text.slice(0, 500)}`);
  }
  return data;
}

function normalizeArrayPayload(payload) {
  if (Array.isArray(payload)) {
    return payload;
  }
  if (Array.isArray(payload?.data)) {
    return payload.data;
  }
  if (Array.isArray(payload?.items)) {
    return payload.items;
  }
  if (Array.isArray(payload?.queues)) {
    return payload.queues;
  }
  return [];
}

function getAppointmentSpecialty(row) {
  const department = row?.department;
  if (typeof department === 'string') {
    return department.toLowerCase();
  }
  if (department && typeof department === 'object') {
    return String(department.key || department.name_ru || department.name || '').toLowerCase();
  }
  return String(row?.doctor_specialty || row?.specialty || '').toLowerCase();
}

function isSmokeAppointment(row) {
  return String(row?.notes || '').includes('browser smoke row action');
}

async function createPage(context, session, suffix) {
  const page = await context.newPage();
  await page.addInitScript(
    ({ token, profile }) => {
      localStorage.clear();
      localStorage.setItem('auth_token', token);
      localStorage.setItem('refresh_token', 'browser-smoke-refresh');
      localStorage.setItem('auth_profile', JSON.stringify(profile));
      localStorage.setItem('user', JSON.stringify(profile));
    },
    { token: session.token, profile: session.profile }
  );

  page.on('pageerror', (error) => {
    console.log(`[pageerror:${suffix}] ${error.message}`);
  });

  page.on('console', (message) => {
    if (message.type() === 'error' || message.type() === 'warning') {
      console.log(`[console:${suffix}:${message.type()}] ${message.text()}`);
    }
  });

  return page;
}

async function waitForText(page, text, timeout = 15000) {
  await page.locator(`text=${text}`).first().waitFor({ state: 'visible', timeout });
}

async function closeOverlay(page) {
  try {
    await page.keyboard.press('Escape');
    await page.waitForTimeout(300);
  } catch (error) {
    console.log(`[closeOverlay] escape failed: ${error.message}`);
  }
}

async function searchTableRow(page, patientName) {
  const search = page.locator('input[placeholder="Поиск"], input[placeholder*="Поиск"], input[placeholder="Search"], input[placeholder*="Search"]').first();
  await search.waitFor({ state: 'visible', timeout: 15000 });
  await search.fill('');
  await search.fill(patientName);
  await page.waitForTimeout(500);
  const row = page.locator('table tbody tr').filter({ hasText: patientName }).first();
  await row.waitFor({ state: 'visible', timeout: 15000 });
  return row;
}

async function clickRowButton(row, title) {
  const button = row.locator(`button[title="${title}"]`).first();
  await button.waitFor({ state: 'visible', timeout: 15000 });
  await button.click();
}

async function screenshot(page, name) {
  const file = path.join(OUTPUT_DIR, `${ts()}-${name}.png`);
  await page.screenshot({ path: file, fullPage: true });
  return file;
}

async function runRegistrarSmoke(context, session, registrarRow) {
  const page = await createPage(context, session, 'registrar');
  const screenshots = [];
  const registrarDate = registrarRow?.appointment_date || registrarRow?.created_at?.slice?.(0, 10) || '';

  await page.goto(`${WEB_BASE}/registrar-panel${registrarDate ? `?date=${registrarDate}` : ''}`, { waitUntil: 'domcontentloaded' });

  const row = await searchTableRow(page, registrarRow.patient_fio || registrarRow.patient_name);
  screenshots.push(await screenshot(page, 'registrar-row-visible'));

  await clickRowButton(row, 'Просмотр');
  await waitForText(page, 'Регистрация пациента');
  screenshots.push(await screenshot(page, 'registrar-view-open'));
  await closeOverlay(page);

  await clickRowButton(row, 'Редактировать');
  await waitForText(page, 'Регистрация пациента');
  screenshots.push(await screenshot(page, 'registrar-edit-open'));
  await closeOverlay(page);

  const callResponsePromise = page.waitForResponse((response) =>
    response.request().method() === 'POST'
      && response.url().includes('/registrar/queue/')
      && response.url().includes('/start-visit')
  );
  await clickRowButton(row, 'Вызвать');
  const callResponse = await callResponsePromise;
  screenshots.push(await screenshot(page, 'registrar-call-after'));

  await clickRowButton(row, 'Печать');
  await waitForText(page, 'Печать документа');
  screenshots.push(await screenshot(page, 'registrar-print-open'));
  await closeOverlay(page);

  await clickRowButton(row, 'Еще');
  await waitForText(page, 'Отменить');
  await page.getByText('Отменить', { exact: true }).last().click();
  await waitForText(page, 'Отменить запись');
  screenshots.push(await screenshot(page, 'registrar-cancel-open'));
  await closeOverlay(page);

  const rowAfter = await searchTableRow(page, registrarRow.patient_fio || registrarRow.patient_name);
  const statusText = await rowAfter.textContent();

  return {
    page: 'registrar-panel',
    patient: registrarRow.patient_fio || registrarRow.patient_name,
    callStatus: callResponse.status,
    rowTextAfterCall: statusText,
    screenshots
  };
}

async function runLabSmoke(context, session, queueEntry, templateName) {
  const page = await createPage(context, session, 'lab');
  const screenshots = [];

  await page.goto(`${WEB_BASE}/lab-panel`, { waitUntil: 'domcontentloaded' });
  await waitForText(page, 'Очередь лаборатории');

  const queueButton = page.getByRole('button', { name: 'Открыть в редакторе', exact: true }).first();
  await queueButton.waitFor({ state: 'visible', timeout: 15000 });
  await queueButton.click();
  await waitForText(page, 'Редактор лабораторного бланка');
  screenshots.push(await screenshot(page, 'lab-reports-open-from-queue'));

  await page.getByRole('button', { name: 'Шаблоны', exact: true }).click();
  await waitForText(page, 'Редактор бланка');
  const templateCard = page.getByRole('button', { name: new RegExp(templateName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')) }).first();
  if (await templateCard.count()) {
    await templateCard.waitFor({ state: 'visible', timeout: 15000 });
    await templateCard.click();
  } else {
    const anyTemplateCard = page.locator('button').filter({ hasText: /HbA1c|Malassezia|Testosterone|Гликированный|Тестостерон/ }).first();
    await anyTemplateCard.waitFor({ state: 'visible', timeout: 15000 });
    await anyTemplateCard.click();
  }
  await page.waitForTimeout(500);
  screenshots.push(await screenshot(page, 'lab-template-selected'));

  return {
    page: 'lab-panel',
    queuePatient: queueEntry.patient_fio || queueEntry.patient_name || queueEntry.patient?.full_name || 'unknown',
    template: templateName,
    screenshots
  };
}

async function runSpecialtySmoke(context, session, route, title, targetRow, patientCardNames = []) {
  const page = await createPage(context, session, route.replace(/[\/?]/g, '-'));
  const screenshots = [];
  const patientName = targetRow ? (targetRow.patient_fio || targetRow.patient_name) : null;

  await page.goto(`${WEB_BASE}${route}`, { waitUntil: 'domcontentloaded' });
  await waitForText(page, title);

  const appointmentsTab = page.getByRole('button', { name: /Appointments|Записи|Приемы|Appointments/i }).first();
  await appointmentsTab.click().catch(() => {});
  await page.waitForTimeout(1200);

  let row = null;
  if (patientName) {
    try {
      row = await searchTableRow(page, patientName);
      screenshots.push(await screenshot(page, `${route.replace(/\//g, '-')}-appointments-visible`));
    } catch (error) {
      screenshots.push(await screenshot(page, `${route.replace(/\//g, '-')}-appointments-empty`));
      return {
        page: route,
        patient: patientName,
        screenshots,
        status: 'empty',
        error: `row not found for ${patientName}: ${error.message}`
      };
    }
  } else {
    screenshots.push(await screenshot(page, `${route.replace(/\//g, '-')}-appointments-no-target`));
  }

  try {
    await clickRowButton(row, 'Просмотр');
    await waitForText(page, 'Регистрация пациента');
    screenshots.push(await screenshot(page, `${route.replace(/\//g, '-')}-view-open`));
    await closeOverlay(page);
  } catch (error) {
    screenshots.push(await screenshot(page, `${route.replace(/\//g, '-')}-view-missed`));
  }

  try {
    await clickRowButton(row, 'Редактировать');
    await waitForText(page, 'Регистрация пациента');
    screenshots.push(await screenshot(page, `${route.replace(/\//g, '-')}-edit-open`));
    await closeOverlay(page);
  } catch (error) {
    screenshots.push(await screenshot(page, `${route.replace(/\//g, '-')}-edit-missed`));
  }

  let callResponseStatus = null;
  try {
    const callResponsePromise = page.waitForResponse((response) =>
      response.request().method() === 'POST'
        && response.url().includes('/registrar/queue/')
        && response.url().includes('/start-visit')
    ).catch(() => null);
    await clickRowButton(row, 'Вызвать');
    const timeoutPromise = page.waitForTimeout(5000).then(() => null);
    const callResponse = await Promise.race([callResponsePromise, timeoutPromise]);
    if (callResponse) {
      callResponseStatus = callResponse.status();
    }
  } catch (error) {
    screenshots.push(await screenshot(page, `${route.replace(/\//g, '-')}-call-missed`));
  }

  try {
    await clickRowButton(row, 'Печать');
    await waitForText(page, 'Печать документа');
    screenshots.push(await screenshot(page, `${route.replace(/\//g, '-')}-print-open`));
    await closeOverlay(page);
  } catch (error) {
    screenshots.push(await screenshot(page, `${route.replace(/\//g, '-')}-print-missed`));
  }

  try {
    await clickRowButton(row, 'Еще');
    await waitForText(page, 'Отменить');
    await page.getByText('Отменить', { exact: true }).last().click();
    await waitForText(page, 'Отменить запись');
    screenshots.push(await screenshot(page, `${route.replace(/\//g, '-')}-cancel-open`));
    await closeOverlay(page);
  } catch (error) {
    screenshots.push(await screenshot(page, `${route.replace(/\//g, '-')}-cancel-missed`));
  }

  if (route === '/cardiologist') {
    await page.getByRole('button', { name: /visit|Прием|Приём/i }).first().click().catch(() => {});
    await page.waitForTimeout(700);
    await waitForText(page, 'Электронная медицинская карта').catch(() => {});
    screenshots.push(await screenshot(page, 'cardiologist-visit-open'));

    await page.getByRole('button', { name: /history|История/i }).first().click().catch(() => {});
    await page.waitForTimeout(700);
    screenshots.push(await screenshot(page, 'cardiologist-history-open'));
  }

  if (route === '/dermatologist') {
    await page.getByRole('button', { name: /patients|Пациенты/i }).first().click().catch(() => {});
    await page.waitForTimeout(700);
    const firstPatientCard = page.getByRole('button', { name: /Осмотр|Процедура|Просмотр|Открыть|Запись/i }).first();
    if (await firstPatientCard.count()) {
      await firstPatientCard.click().catch(() => {});
      await page.waitForTimeout(500);
      screenshots.push(await screenshot(page, 'dermatologist-patient-action-open'));
    }
    await page.getByRole('button', { name: /history|История/i }).first().click().catch(() => {});
    await page.waitForTimeout(700);
    screenshots.push(await screenshot(page, 'dermatologist-history-open'));
  }

  if (route === '/dentist') {
    await page.getByRole('button', { name: /patients|Пациенты/i }).first().click().catch(() => {});
    await page.waitForTimeout(700);
    const firstProtocolCard = page.getByRole('button', { name: /Создать протокол|Открыть архив|Открыть план|Открыть схему|Открыть/i }).first();
    if (await firstProtocolCard.count()) {
      await firstProtocolCard.click().catch(() => {});
      await page.waitForTimeout(500);
      screenshots.push(await screenshot(page, 'dentist-patient-card-open'));
      await closeOverlay(page);
    }

    await page.getByRole('button', { name: /visits|visit|Протокол визита|Визит/i }).first().click().catch(() => {});
    await page.waitForTimeout(700);
    screenshots.push(await screenshot(page, 'dentist-visits-open'));

    await page.getByRole('button', { name: /history|История/i }).first().click().catch(() => {});
    await page.waitForTimeout(700);
    screenshots.push(await screenshot(page, 'dentist-history-open'));
  }

  return {
    page: route,
    patient: patientName,
    callStatus: callResponseStatus,
    screenshots
  };
}

async function main() {
  const adminSession = mintSession('admin@example.com');
  const registrarSession = mintSession('registrar@example.com');
  const labSession = mintSession('lab@example.com');
  const cardioSession = mintSession('cardio@example.com');
  const dermaSession = mintSession('derma@example.com');
  const dentistSession = mintSession('dentist@example.com');

  const registrarAppointments = normalizeArrayPayload(
    await apiGetJson(`${API_BASE}/registrar/all-appointments?limit=500`, registrarSession.token)
  );
  const labQueues = normalizeArrayPayload(
    await apiGetJson(`${API_BASE}/registrar/queues/today`, labSession.token)
  );

  const queueRows = registrarAppointments.filter((row) => {
    const specialty = getAppointmentSpecialty(row);
    return ['waiting', 'queued', 'confirmed', 'scheduled'].includes(String(row.status || '').toLowerCase())
      && (specialty.includes('cardio') || specialty.includes('derma') || specialty.includes('dentist') || specialty.includes('stomatology') || specialty.includes('lab') || specialty.includes('laboratory') || specialty.includes('cardiology') || specialty.includes('dermatology'));
  });

  const smokeAppointments = registrarAppointments.filter(isSmokeAppointment);

  const registrarRow = smokeAppointments.find((row) => String(row.patient_id) === '81')
    || smokeAppointments.find((row) => String(row.patient_fio || row.patient_name || '').includes('Финальный Тест Тестович'))
    || registrarAppointments.find((row) => ['waiting', 'queued', 'confirmed', 'scheduled', 'pending_confirmation'].includes(String(row.status || '').toLowerCase()))
    || registrarAppointments[0]
    || { patient_fio: 'unknown' };

  const cardioRow = smokeAppointments.find((row) => getAppointmentSpecialty(row).includes('cardio'))
    || queueRows.find((row) => getAppointmentSpecialty(row).includes('cardio'))
    || registrarAppointments.find((row) => getAppointmentSpecialty(row).includes('cardio'))
    || registrarRow;

  const dermaRow = smokeAppointments.find((row) => getAppointmentSpecialty(row).includes('derma'))
    || queueRows.find((row) => getAppointmentSpecialty(row).includes('derma'))
    || registrarAppointments.find((row) => getAppointmentSpecialty(row).includes('derma'))
    || registrarRow;

  const dentistRow = smokeAppointments.find((row) => getAppointmentSpecialty(row).includes('dent') || getAppointmentSpecialty(row).includes('stomat'))
    || queueRows.find((row) => getAppointmentSpecialty(row).includes('dent') || getAppointmentSpecialty(row).includes('stomat'))
    || registrarAppointments.find((row) => getAppointmentSpecialty(row).includes('dent') || getAppointmentSpecialty(row).includes('stomat'))
    || registrarRow;

  const labQueue = labQueues.find((queue) => ['lab', 'laboratory'].includes(String(queue.specialty || '').toLowerCase()))
    || labQueues[0]
    || null;
  const labQueueEntry = labQueue?.entries?.find((entry) => ['waiting', 'called', 'confirmed', 'pending'].includes(String(entry.status || '').toLowerCase()))
    || labQueue?.entries?.[0]
    || null;

  const labTemplates = normalizeArrayPayload(
    await apiGetJson(`${API_BASE}/lab/templates`, labSession.token).catch(async () => {
      return await apiGetJson(`${API_BASE}/lab/report-templates`, labSession.token);
    })
  );
  const firstTemplateName = labTemplates[0]?.name || labTemplates[0]?.template_name || 'Шаблон';

  const context = await chromium.launch({ headless: true });
  const browserContext = await context.newContext({ viewport: { width: 1600, height: 1200 } });

  const results = [];
  try {
    results.push(await runRegistrarSmoke(browserContext, registrarSession, registrarRow));
    results.push(await runLabSmoke(browserContext, labSession, labQueueEntry || {}, firstTemplateName));
    results.push(await runSpecialtySmoke(browserContext, cardioSession, '/cardiologist', 'Записи к кардиологу', cardioRow));
    results.push(await runSpecialtySmoke(browserContext, dermaSession, '/dermatologist', 'Записи к дерматологу', dermaRow));
    results.push(await runSpecialtySmoke(browserContext, dentistSession, '/dentist', 'Записи к стоматологу', dentistRow));
  } finally {
    await browserContext.close();
    await context.close();
  }

  const report = {
    generated_at: new Date().toISOString(),
    results,
    note: 'Row-action smoke completed in headless Chromium with real auth tokens and live data.'
  };

  const reportFile = writeJson(`browser-row-actions-report-${ts()}.json`, report);
  console.log(JSON.stringify(report, null, 2));
  console.log(`Report written to ${reportFile}`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
