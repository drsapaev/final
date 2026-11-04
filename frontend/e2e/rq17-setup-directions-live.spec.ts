/**
 * RQ-17 — T18 current Admin setup path for a resource-owned direction.
 *
 * This spec follows the current backend-facts screen and its existing editors.
 * It verifies the canonical Users editor link (there is no second doctor
 * onboarding form in setup), creates a hidden QueueProfile and a doctorless
 * service through their existing Admin screens, then creates and activates a
 * QueueResource through the setup screen's resource view. All rows live only
 * in the owned synthetic staging database and are removed with that project.
 */
import crypto from 'node:crypto';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { test, expect, type Page } from '@playwright/test';

const ADMIN_USERNAME = process.env.QA_ADMIN_USERNAME || 'admin';

function requiredAdminPassword() {
  const password = process.env.QA_ADMIN_PASSWORD;
  if (!password) {
    throw new Error('Set QA_ADMIN_PASSWORD for the synthetic RQ-17 Admin flow.');
  }
  return password;
}

function base32Decode(secret: string): Buffer {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  let bits = '';
  for (const character of secret.replace(/=+$/, '').toUpperCase()) {
    const value = alphabet.indexOf(character);
    if (value < 0) throw new Error('The synthetic Admin 2FA setup returned an invalid TOTP secret.');
    bits += value.toString(2).padStart(5, '0');
  }
  const bytes: number[] = [];
  for (let index = 0; index + 8 <= bits.length; index += 8) {
    bytes.push(Number.parseInt(bits.slice(index, index + 8), 2));
  }
  return Buffer.from(bytes);
}

function totpCode(secret: string, atMs = Date.now()): string {
  const counter = Math.floor(atMs / 1000 / 30);
  const message = Buffer.alloc(8);
  message.writeBigUInt64BE(BigInt(counter));
  const digest = crypto.createHmac('sha1', base32Decode(secret)).update(message).digest();
  const offset = digest[digest.length - 1] & 0x0f;
  const binary = ((digest[offset] & 0x7f) << 24)
    | (digest[offset + 1] << 16)
    | (digest[offset + 2] << 8)
    | digest[offset + 3];
  return String(binary % 1_000_000).padStart(6, '0');
}

async function loginAdminWithRequiredTwoFactor(page: Page) {
  await page.goto('/login');
  await page.locator('input[name="username"]').fill(ADMIN_USERNAME);
  await page.locator('input[name="password"]').fill(requiredAdminPassword());

  const loginResponsePromise = page.waitForResponse((response) => {
    const pathname = new URL(response.url()).pathname;
    return response.request().method() === 'POST' && pathname.endsWith('/authentication/login');
  });
  await page.getByRole('button', { name: /Войти|Sign in|Log in/i }).click();
  const loginResponse = await loginResponsePromise;
  expect(loginResponse.ok(), 'synthetic Admin password login should succeed').toBeTruthy();
  const loginData = await loginResponse.json() as Record<string, unknown>;

  if (loginData.requires_2fa_setup === true) {
    const setupWizard = page.locator('.twofactor-setup-auth');
    await expect(setupWizard).toBeVisible();

    const setupResponsePromise = page.waitForResponse((response) => {
      const pathname = new URL(response.url()).pathname;
      return response.request().method() === 'POST' && pathname.endsWith('/2fa/setup');
    });
    await setupWizard.getByRole('button', { name: /Далее|Next/i }).click();
    const setupResponse = await setupResponsePromise;
    expect(setupResponse.ok(), 'normal Admin TOTP enrollment should succeed').toBeTruthy();
    const setupData = await setupResponse.json() as { secret_key?: unknown };
    const secret = typeof setupData.secret_key === 'string' ? setupData.secret_key : '';
    expect(secret.length, '2FA enrollment must return a TOTP secret').toBeGreaterThan(0);

    await setupWizard.getByRole('button', { name: /Далее|Next/i }).click();
    await setupWizard.getByLabel('2FA verification code').fill(totpCode(secret));
    await setupWizard.getByRole('button', { name: /Подтвердить|Confirm/i }).click();
    await expect(setupWizard.getByRole('button', { name: /Готово|Завершить|Finish|Done/i })).toBeVisible();
    await setupWizard.getByRole('button', { name: /Готово|Завершить|Finish|Done/i }).click();
    await expect(setupWizard).toHaveCount(0);
    return;
  }

  if (loginData.requires_2fa === true) {
    const secret = process.env.QA_ADMIN_TOTP_SECRET;
    if (!secret) {
      throw new Error('Admin already has 2FA; set QA_ADMIN_TOTP_SECRET for this synthetic staging run.');
    }
    const verifyPanel = page.locator('.twofactor-verify-auth');
    await expect(verifyPanel).toBeVisible();
    await verifyPanel.getByLabel('Authenticator code').fill(totpCode(secret));
    await verifyPanel.getByRole('button', { name: /Проверить|Подтвердить|Verify|Confirm/i }).click();
    await expect(verifyPanel).toHaveCount(0);
    return;
  }

  throw new Error('Admin login did not require 2FA; refusing to continue without the normal Admin security flow.');
}

const letters = 'abcdefghij';
const suffix = (process.env.QA_SUFFIX || String(Date.now()).slice(-6))
  .toLowerCase()
  .replace(/\d/g, (digit) => letters[Number(digit)] || 'k')
  .replace(/[^a-z]/g, 'k');
const resourceTag = `rqres${suffix}`;
const profileKey = `rq_${suffix}`;
const profileTitle = `Synthetic RQ-17 direction ${suffix}`;
const serviceName = `Synthetic RQ-17 service ${suffix}`;
const resourceName = `Synthetic RQ-17 resource ${suffix}`;

test('current setup screen supports resource-only setup without creating another doctor', async ({ page }) => {
  test.setTimeout(240_000);
  const verifyServedFrontend = process.env.T18_VERIFY_SERVED_FRONTEND === '1';
  const expectedOrigin = process.env.PLAYWRIGHT_BASE_URL
    ? new URL(process.env.PLAYWRIGHT_BASE_URL).origin
    : null;
  if (verifyServedFrontend && !expectedOrigin) {
    throw new Error('T18 served frontend verification requires PLAYWRIGHT_BASE_URL.');
  }
  const servedAssets = new Map<string, Promise<Buffer>>();
  if (verifyServedFrontend && expectedOrigin) {
    page.on('response', (response) => {
      const assetUrl = new URL(response.url());
      if (assetUrl.origin !== expectedOrigin || response.status() !== 200) return;
      if (!/^\/assets\/(?:index-[^/]+\.(?:js|css)|AdminSetupDirections-[^/]+\.js)$/.test(assetUrl.pathname)) return;
      servedAssets.set(assetUrl.pathname, response.body());
    });
  }

  await loginAdminWithRequiredTwoFactor(page);

  await page.goto('/admin/setup-directions');
  await expect(page.getByTestId('setup-directions-heading')).toBeVisible();
  const editorLinks = page.getByTestId('setup-editor-links');
  await expect(editorLinks).toBeVisible();
  await expect(page.locator('[data-testid^="setup-wizard-"]')).toHaveCount(0);
  await expect(editorLinks.locator('a[href*="servicesTab=queue-profiles"]')).toHaveCount(1);
  await expect(editorLinks.locator('a[href*="servicesTab=catalog"]')).toHaveCount(1);
  await expect(editorLinks.locator('a[href*="/admin/users"]')).toHaveCount(1);

  // Create an unpublished profile through the canonical profile editor.
  await editorLinks.locator('a[href*="servicesTab=queue-profiles"]').click();
  await expect(page).toHaveURL(/servicesTab=queue-profiles/);
  await page.getByRole('button', { name: /Добавить|Add/i }).click();
  const profileDialog = page.getByRole('dialog');
  await expect(profileDialog).toBeVisible();
  const profileKeyInput = profileDialog.locator('#queue-profile-key');
  await expect(profileKeyInput).toHaveAttribute('pattern', '[a-z_]+');
  expect(profileKey).toMatch(/^[a-z_]+$/);
  await profileKeyInput.fill(profileKey);
  await profileDialog.locator('#queue-profile-title-en').fill(profileTitle);
  await profileDialog.locator('#queue-profile-title-ru').fill(profileTitle);
  await profileDialog.locator('#queue-profile-tags').fill(resourceTag);
  await profileDialog.getByRole('button', { name: /Создать вкладку очереди|Create queue tab/i }).click();
  await expect(profileDialog).toHaveCount(0);
  await expect(page.getByText(profileTitle).first()).toBeVisible();

  // Create a service with a real category and the new profile tag, leaving
  // the optional doctor empty and requires_doctor at its false default.
  await page.goto('/admin/setup-directions');
  await expect(page.getByTestId('setup-editor-links')).toBeVisible();
  await page.getByTestId('setup-editor-links').locator('a[href*="servicesTab=catalog"]').click();
  await expect(page).toHaveURL(/servicesTab=catalog/);
  const emptyServices = page.getByRole('region', { name: 'Услуги не найдены' });
  await expect(emptyServices).toBeVisible();
  await emptyServices.getByRole('button', { name: /Добавить услугу|Add service/i }).click();
  const serviceEditor = page.getByRole('heading', { name: /Добавление услуги|Add service/i }).locator('..');
  const serviceForm = serviceEditor.locator('form').last();
  await expect(serviceForm).toBeVisible();
  await serviceForm.locator('input[type="text"]').first().fill(serviceName);

  const categorySelect = serviceForm.locator('.mac-select').first().getByRole('button');
  await categorySelect.click();
  const categoryOptions = page.getByRole('listbox').getByRole('option');
  const categoryOptionCount = await categoryOptions.count();
  const hasServiceCategory = categoryOptionCount > 1;
  if (hasServiceCategory) {
    await categoryOptions.nth(1).click();
  } else {
    await expect(categoryOptions).toHaveCount(1);
    await expect(categoryOptions.first()).toHaveText(/Выберите категорию|Select category/i);
    await categoryOptions.first().click();
  }

  const queueTab = serviceEditor.getByRole('button', { name: /Очередь|Queue/i });
  await expect(queueTab).toBeVisible();
  await queueTab.click();
  const queueTagSelect = serviceForm.locator('.mac-select').first().getByRole('button');
  await queueTagSelect.click();
  const resourceTagOption = page.getByRole('listbox').getByRole('option').filter({ hasText: profileTitle });
  await expect(resourceTagOption).toHaveCount(1);
  await resourceTagOption.click();

  const optionsTab = serviceEditor.getByRole('button', { name: /Опции|Options/i });
  await expect(optionsTab).toBeVisible();
  await optionsTab.click();
  await expect(serviceForm.getByRole('checkbox', { name: /Требует врача|Doctor required/i })).not.toBeChecked();
  const serviceCreateResponsePromise = page.waitForResponse((response) => {
    const pathname = new URL(response.url()).pathname;
    return response.request().method() === 'POST' && /\/services\/?$/.test(pathname);
  });
  await serviceForm.getByRole('button', { name: /Сохранить услугу|Сохранить|Save service|Save/i }).click();
  const serviceCreateResponse = await serviceCreateResponsePromise;
  expect(serviceCreateResponse.ok(), 'doctorless synthetic service should be saved').toBeTruthy();
  const servicePayload = serviceCreateResponse.request().postDataJSON() as Record<string, unknown>;
  expect(servicePayload).toMatchObject({
    queue_tag: resourceTag,
    doctor_id: null,
    requires_doctor: false,
  });
  if (!hasServiceCategory) {
    expect(servicePayload.category_id).toBeNull();
  }
  await expect(page.getByText(serviceName).first()).toBeVisible();

  // The current setup screen owns the resource view; create a draft first,
  // then activate it through the normal eligibility gate.
  await page.goto('/admin/setup-directions');
  await expect(page.getByTestId('setup-directions-heading')).toBeVisible();
  await page.getByTestId('setup-view-resources').click();
  await page.getByTestId('qr-resource-create-toggle').click();
  await expect(page.getByTestId('qr-resource-create-form')).toBeVisible();
  await page.getByTestId('qr-resource-tag-select').click();
  const resourceTagChoice = page.getByRole('listbox').getByRole('option').filter({ hasText: resourceTag });
  await expect(resourceTagChoice).toHaveCount(1);
  await resourceTagChoice.click();
  await page.getByTestId('qr-resource-display-name-input').fill(resourceName);
  await page.getByTestId('qr-resource-submit').click();

  const resourceRow = page.locator('[data-testid^="qr-resource-row-"]').filter({ hasText: resourceName });
  await expect(resourceRow).toHaveCount(1, { timeout: 15_000 });
  await expect(resourceRow.getByTestId('qr-resource-badge-draft')).toBeVisible();
  await resourceRow.locator('[data-testid^="qr-resource-toggle-"]').click();
  await expect(resourceRow.getByTestId('qr-resource-badge-active')).toBeVisible({ timeout: 15_000 });

  // The backend read model must resolve exactly one booking target, owned by
  // the QueueResource. A doctor target would contradict this doctorless path.
  await page.getByTestId('setup-view-checklist').click();
  const directionRow = page.getByTestId(`setup-checklist-row-${resourceTag}`);
  await expect(directionRow).toBeVisible({ timeout: 20_000 });
  const targets = directionRow.getByTestId('setup-direction-targets');
  await expect(targets).toBeVisible();
  await expect(targets.locator('li')).toHaveCount(1);
  await expect(targets).toContainText(resourceName);
  await expect(targets).toContainText(/ресурс|resource/i);
  await expect(targets).not.toContainText(/врач|doctor/i);

  if (verifyServedFrontend) {
    const assetDirectory = process.env.T18_SERVED_ASSET_DIR;
    expect(assetDirectory, 'staging runner must provide an owned asset evidence directory').toBeTruthy();
    const requiredAssetPatterns = [
      /\/assets\/index-[^/]+\.js$/,
      /\/assets\/index-[^/]+\.css$/,
      /\/assets\/AdminSetupDirections-[^/]+\.js$/,
    ];
    const requiredAssets = requiredAssetPatterns.map((pattern) =>
      Array.from(servedAssets.entries()).find(([assetPath]) => pattern.test(assetPath))
    );
    expect(requiredAssets.every(Boolean), 'entry JS, entry CSS, and AdminSetupDirections chunk must be served').toBeTruthy();

    await mkdir(assetDirectory!, { recursive: true });
    const assetManifest = [] as Array<{ path: string; file: string; sha256: string }>;
    for (const asset of requiredAssets) {
      if (!asset) continue;
      const [assetPath, servedBodyPromise] = asset;
      const servedBody = await servedBodyPromise;
      const servedHash = crypto.createHash('sha256').update(servedBody).digest('hex');
      const file = path.basename(assetPath);
      await writeFile(path.join(assetDirectory!, file), servedBody);
      assetManifest.push({ path: assetPath, file, sha256: servedHash });
    }
    await writeFile(
      path.join(assetDirectory!, 'manifest.json'),
      JSON.stringify({ assets: assetManifest }, null, 2),
      'utf8',
    );
  }
});
