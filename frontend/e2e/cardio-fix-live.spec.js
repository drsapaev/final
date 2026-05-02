import fs from 'node:fs';
import path from 'node:path';
import { test, expect } from '@playwright/test';

const rootDir = path.resolve(process.cwd(), '..');
const artifactsDir = path.join(rootDir, 'output', 'playwright');
const storageStateFile = path.join(artifactsDir, 'cardio-storage.json');

function readCardioAuth() {
  const storageState = JSON.parse(fs.readFileSync(storageStateFile, 'utf8'));
  const appOrigin = storageState.origins.find((origin) => origin.origin === 'http://localhost:5173');
  const localStorageItems = new Map((appOrigin?.localStorage || []).map((item) => [item.name, item.value]));
  return {
    auth_token: localStorageItems.get('auth_token'),
    user: localStorageItems.get('user'),
    auth_profile: localStorageItems.get('auth_profile'),
    theme: localStorageItems.get('theme') || 'dark',
    language: localStorageItems.get('language') || 'ru'
  };
}

test.describe.configure({ mode: 'serial' });

test.use({
  baseURL: 'http://localhost:5175',
  viewport: { width: 1440, height: 1200 }
});

test('CARD-01/CARD-02 live fix on temp 5175/18001 stack', async ({ page }) => {
  const auth = readCardioAuth();
  const networkUrls = [];
  const interpretation = `Playwright CARD-01 ${Date.now()}`;

  page.on('request', (request) => {
    networkUrls.push(request.url());
  });

  await page.addInitScript((payload) => {
    if (window.location.origin === 'http://localhost:5175') {
      Object.entries(payload).forEach(([key, value]) => {
        if (value) {
          window.localStorage.setItem(key, value);
        }
      });
    }
  }, auth);

  const patientResponsePromise = page.waitForResponse((response) => response.url().includes('/api/v1/patients/444') && response.status() === 200);
  const bloodListResponsePromise = page.waitForResponse((response) => response.url().includes('/api/v1/cardio/blood-tests?patient_id=444') && response.status() === 200);

  await page.goto('/cardiologist?patientId=444&tab=appointments');
  await page.waitForLoadState('networkidle');
  await patientResponsePromise;
  await bloodListResponsePromise;

  await expect(page.getByText('Записи к кардиологу')).toBeVisible();

  await page.getByText(/Blood Tests|Анализы/, { exact: true }).first().click();
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1000);
  await expect(page.getByText('Анализы крови')).toBeVisible();

  await expect(page.getByText('Нет данных анализов')).toHaveCount(0);
  await page.getByRole('button', { name: /Новый анализ|New analysis/i }).click();
  await page.waitForLoadState('networkidle');

  const numericInputs = page.locator('input[type="number"]');
  await numericInputs.nth(0).fill('182');
  await numericInputs.nth(2).fill('101');
  await numericInputs.nth(4).fill('92');
  await page.getByPlaceholder('Интерпретация результатов анализов').fill(interpretation);
  await page.getByRole('button', { name: 'Сохранить анализ' }).click();

  await page.waitForTimeout(1500);
  await page.waitForLoadState('networkidle');
  await expect(page.getByText(interpretation)).toBeVisible({ timeout: 15000 });

  await page.getByText(/History|История/, { exact: true }).first().click();
  await page.waitForLoadState('networkidle');
  await expect(page.getByText('Хронология записей пациента')).toBeVisible();
  await expect(page.getByText('Нет данных по ЭКГ или анализам крови')).toHaveCount(0);
  await expect(page.getByText('Анализ крови — 2026-03-21').first()).toBeVisible({ timeout: 15000 });

  fs.writeFileSync(
    path.join(artifactsDir, 'cardio-fix-live-network.json'),
    JSON.stringify(networkUrls, null, 2),
    'utf8'
  );

  await page.screenshot({
    path: path.join(artifactsDir, 'cardio-fix-live-history.png'),
    fullPage: true
  });

  expect(networkUrls.some((url) => url.includes('localhost:18001/api/v1/cardio/blood-tests'))).toBeTruthy();
  expect(networkUrls.some((url) => url.includes('localhost:18000/api/v1/cardio/blood-tests'))).toBeFalsy();
});
