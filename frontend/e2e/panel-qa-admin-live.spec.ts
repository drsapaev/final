import fs from 'node:fs';
import path from 'node:path';
import { test, expect } from '@playwright/test';

const rootDir = path.resolve(process.cwd(), '..');
const artifactsDir = path.join(rootDir, 'output', 'playwright');
const idFile = path.join(artifactsDir, 'admin-live-ids.json');

const storageState = path.join(artifactsDir, 'admin-storage.json');
const suffix = process.env.QA_SUFFIX || String(Date.now()).slice(-6);
const patientPhoneDigits = process.env.QA_PATIENT_PHONE || `90${suffix}1`;
const patientPhone = `+998 ${patientPhoneDigits.slice(0, 2)} ${patientPhoneDigits.slice(2, 5)} ${patientPhoneDigits.slice(5, 7)} ${patientPhoneDigits.slice(7, 9)}`;
const patientEmail = `qa_admin_patient_${suffix}@clinic.uz`;
const patientLastName = 'Админ';
const patientFirstName = 'Пациент';
const patientMiddleName = 'Поток';
const serviceCode = process.env.QA_SERVICE_CODE || `L${suffix.slice(-2)}`;
const serviceName = `QA Lab Service ${suffix}`;

function readIds() {
  if (!fs.existsSync(idFile)) {
    return {};
  }
  return JSON.parse(fs.readFileSync(idFile, 'utf8'));
}

function writeIds(patch) {
  const current = readIds();
  const next = { ...current, ...patch };
  fs.writeFileSync(idFile, JSON.stringify(next, null, 2), 'utf8');
}

test.describe.configure({ mode: 'serial' });

test.use({
  baseURL: 'http://localhost:5173',
  storageState,
  viewport: { width: 1440, height: 1200 }
});

test('ADM-05 create patient from admin patients UI', async ({ page }) => {
  page.on('console', (msg) => {
    if (msg.text().includes('/api/v1/patients') || msg.type() === 'error') {
      console.log(`BROWSER_${msg.type().toUpperCase()}: ${msg.text()}`);
    }
  });
  page.on('pageerror', (error) => {
    console.log(`PAGEERROR: ${error.message}`);
  });
  page.on('response', (response) => {
    if (response.url().includes('/api/v1/patients')) {
      console.log(`PATIENTS_RESPONSE ${response.status()} ${response.url()}`);
    }
  });

  await page.goto('/admin?section=patients');
  await page.waitForLoadState('networkidle');

  await expect(page.getByRole('heading', { name: 'Управление пациентами' })).toBeVisible();
  if (await page.getByRole('heading', { name: 'Ошибка загрузки пациентов' }).isVisible().catch(() => false)) {
    await page.screenshot({
      path: path.join(artifactsDir, 'admin-patients-error-state.png'),
      fullPage: true
    });
    throw new Error('Admin patients section entered error state before create/search flow');
  }
  await page.getByRole('button', { name: 'Добавить пациента' }).first().click();

  const form = page.locator('form').last();
  await form.getByPlaceholder('Иванов', { exact: true }).fill(patientLastName);
  await form.getByPlaceholder('Иван', { exact: true }).fill(patientFirstName);
  await form.getByPlaceholder('Иванович', { exact: true }).fill(patientMiddleName);
  await form.locator('input[type="date"]').first().fill('1990-01-15');
  await form.locator('select').first().selectOption('female');
  await form.getByPlaceholder('+998 90 123 45 67', { exact: true }).first().fill(patientPhone);
  await form.getByPlaceholder('ivan@example.com', { exact: true }).fill(patientEmail);
  await form.getByPlaceholder('г. Ташкент, ул. Навои, д. 1', { exact: true }).fill('г. Ташкент, QA street, 15');
  await form.getByRole('button', { name: 'Добавить пациента' }).last().click();

  await expect(page.getByRole('button', { name: 'Добавить пациента' }).first()).toBeVisible();
  await page.getByPlaceholder('Поиск пациентов...').fill(patientLastName);
  await expect(page.getByText(`${patientLastName} ${patientFirstName} ${patientMiddleName}`).first()).toBeVisible({ timeout: 15000 });

  await page.screenshot({
    path: path.join(artifactsDir, 'admin-patient-after-create.png'),
    fullPage: true
  });

  writeIds({
    suffix,
    patient: {
      email: patientEmail,
      phone: patientPhone,
      lastName: patientLastName,
      firstName: patientFirstName
    }
  });
});

test('ADM-06 create service from admin services UI', async ({ page }) => {
  await page.goto('/admin?section=services');
  await page.waitForLoadState('networkidle');

  await expect(page.getByRole('heading', { name: 'Справочник услуг' })).toBeVisible();
  await page.getByRole('button', { name: 'Добавить услугу' }).click();

  const form = page.locator('form').last();
  await form.locator('input[type="text"]').first().fill(serviceName);
  await form.getByPlaceholder('K01').fill(serviceCode);
  await form.locator('select').first().selectOption('7');
  await form.locator('input[type="number"]').first().fill('17000');
  await form.locator('input[type="number"]').nth(1).fill('20');

  await page.getByRole('button', { name: 'Очередь' }).click();
  await form.locator('select').first().selectOption('lab');

  await form.getByRole('button', { name: 'Сохранить' }).click();

  await expect(page.getByText('Услуга создана')).toBeVisible({ timeout: 15000 });
  await page.getByPlaceholder('Введите название услуги...').fill(serviceName);
  await expect(page.getByText(serviceName)).toBeVisible({ timeout: 15000 });

  await page.screenshot({
    path: path.join(artifactsDir, 'admin-service-after-create.png'),
    fullPage: true
  });

  writeIds({
    suffix,
    service: {
      name: serviceName,
      code: serviceCode,
      queueTag: 'lab',
      categoryId: 7
    }
  });
});
