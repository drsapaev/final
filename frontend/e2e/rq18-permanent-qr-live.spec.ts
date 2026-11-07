/**
 * RQ-18 current-source synthetic acceptance.
 *
 * Covers the current Admin setup flow, explicit publication, permanent QR
 * provision/recovery, anonymous booking to the typed QueueResource owner,
 * and anonymous refusal/reactivation through the same permanent address.
 * All browser contexts are synthetic and ephemeral. No QR/session code,
 * patient input, screenshot, trace, video, or raw response is persisted.
 */
import crypto from 'node:crypto';
import { test, expect, type Browser, type Page, type Response } from '@playwright/test';

test.use({ trace: 'off', screenshot: 'off', video: 'off' });

const ADMIN_USERNAME = process.env.QA_ADMIN_USERNAME || 'admin';
const letters = 'abcdefghij';
const rawSuffix = process.env.QA_SUFFIX || String(Date.now()).slice(-6);
const suffixKey = rawSuffix.toLowerCase()
  .replace(/\d/g, (digit) => letters[Number(digit)] || 'k')
  .replace(/[^a-z]/g, 'k');
const suffixDigits = String(Date.now()).slice(-7);
const profileKey = 'rqqrdir' + suffixKey;
const queueTag = 'rqqrdir' + suffixKey;
const profileTitle = 'SYNTHETIC-RQ18 direction ' + suffixKey;
const serviceName = 'SYNTHETIC-RQ18 service ' + suffixKey;
const resourceName = 'SYNTHETIC-RQ18 resource ' + suffixKey;
const patientName = 'SYNTHETIC-RQ18 patient ' + suffixKey;
const patientPhone = '+99890' + suffixDigits;

type QueueProfileRow = {
  key?: string;
  name?: string;
  title?: string;
  title_ru?: string;
  queue_tags?: string[];
  department_key?: string;
  is_active?: boolean;
  show_on_qr_page?: boolean;
};

type DirectionTarget = {
  owner_type: 'doctor' | 'resource';
  owner_id: number;
  queue_tag: string;
  is_active: boolean;
  eligible_for_new_booking: boolean;
};

type DirectionQueue = {
  daily_queue_id: number;
  queue_tag: string;
  owner_type: 'doctor' | 'resource' | 'unresolved';
  owner_id: number | null;
};

type DirectionRow = {
  profile: { key: string; show_on_qr_page: boolean };
  resolved_mode: 'booking' | 'overview' | 'unresolved';
  configuration_state: 'ready' | 'incomplete' | 'conflict' | 'unavailable';
  effective_availability: 'available' | 'unavailable' | 'conflict';
  public_availability: boolean;
  permanent_address_exists: boolean;
  booking_targets: DirectionTarget[];
  current_day_queues: DirectionQueue[];
};

type DirectionFacts = {
  directions: DirectionRow[];
};

function requiredAdminPassword() {
  const password = process.env.QA_ADMIN_PASSWORD;
  if (!password) throw new Error('QA_ADMIN_PASSWORD is required for the synthetic Admin check.');
  return password;
}

function base32Decode(secret: string): Buffer {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  let bits = '';
  for (const character of secret.replace(/=+$/, '').toUpperCase()) {
    const value = alphabet.indexOf(character);
    if (value < 0) throw new Error('The synthetic Admin 2FA secret is invalid.');
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
  markRq18Phase('admin-login-navigation');
  await page.goto('/login');
  markRq18Phase('admin-login-fields');
  await page.locator('input[name="username"]').fill(ADMIN_USERNAME);
  await page.locator('input[name="password"]').fill(requiredAdminPassword());

  const loginResponsePromise = page.waitForResponse((response) => {
    const pathname = new URL(response.url()).pathname;
    return response.request().method() === 'POST'
      && pathname.endsWith('/authentication/login');
  }, { timeout: 30_000 });
  markRq18Phase('admin-login-submit');
  await page.getByRole('button', { name: /Войти|Sign in|Log in|Tizimga kirish/i }).click();
  markRq18Phase('admin-login-response');
  const loginResponse = await loginResponsePromise;
  if (!loginResponse.ok()) throw new Error('Synthetic Admin password login failed.');
  const loginData = await loginResponse.json() as {
    requires_2fa_setup?: boolean;
    requires_2fa?: boolean;
  };

  if (loginData.requires_2fa_setup === true) {
    markRq18Phase('admin-totp-enrollment');
    const setupWizard = page.locator('.twofactor-setup-auth');
    await expect(setupWizard).toBeVisible();
    const setupResponsePromise = page.waitForResponse((response) => {
      const pathname = new URL(response.url()).pathname;
      return response.request().method() === 'POST' && pathname.endsWith('/2fa/setup');
    }, { timeout: 30_000 });
    markRq18Phase('admin-totp-setup-request');
    await setupWizard.getByRole('button', { name: /Далее|Next|Keyingi/i }).click();
    markRq18Phase('admin-totp-setup-clicked');
    const setupResponse = await setupResponsePromise;
    if (!setupResponse.ok()) throw new Error('Normal Admin TOTP enrollment failed.');
    const setupPayload = await setupResponse.json() as { secret_key?: unknown };
    const secret = typeof setupPayload.secret_key === 'string' ? setupPayload.secret_key : '';
    if (!secret) throw new Error('Normal Admin TOTP enrollment returned no usable secret.');

    await setupWizard.getByRole('button', { name: /Далее|Next|Keyingi/i }).click();
    markRq18Phase('admin-totp-code-step');
    const verifyInput = setupWizard.locator('#tfsw-code');
    const finishButton = setupWizard.getByRole('button', { name: /Готово|Завершить|Finish|Done|Yakunlash/i });
    const verifyButton = setupWizard.getByRole('button', { name: /Подтвердить|Confirm|Tasdiqlash/i });
    markRq18Phase('admin-totp-fill-code');
    await expect(verifyInput).toBeVisible();
    await verifyInput.fill(totpCode(secret));
    const verifyResponsePromise = page.waitForResponse((response) => {
      const pathname = new URL(response.url()).pathname;
      return response.request().method() === 'POST' && pathname.endsWith('/2fa/verify-setup');
    }, { timeout: 30_000 }).catch(() => null);
    markRq18Phase('admin-totp-submit-code');
    await verifyButton.click();
    markRq18Phase('admin-totp-verification-response');
    const verifyResponse = await verifyResponsePromise;
    if (!verifyResponse || !verifyResponse.ok()) {
      throw new Error('Normal Admin TOTP verification request failed.');
    }
    const verifyPayload = await verifyResponse.json() as { success?: unknown };
    if (verifyPayload.success !== true) throw new Error('Normal Admin TOTP verification did not succeed.');
    markRq18Phase('admin-totp-verification-passed');
    await expect(finishButton).toBeVisible({ timeout: 20_000 });
    await finishButton.click();
    await expect(setupWizard).toHaveCount(0);
    return;
  }

  if (loginData.requires_2fa === true) {
    markRq18Phase('admin-totp-login');
    const secret = process.env.QA_ADMIN_TOTP_SECRET;
    if (!secret) throw new Error('QA_ADMIN_TOTP_SECRET is required for an already-enrolled synthetic Admin.');
    const verifyPanel = page.locator('.twofactor-verify-auth');
    await expect(verifyPanel).toBeVisible();
    const verifyInput = verifyPanel.getByLabel('Authenticator code');
    const verifyButton = verifyPanel.getByRole('button', { name: /Проверить|Подтвердить|Verify|Confirm|Tekshirish|Tasdiqlash/i });
    for (let attempt = 0; attempt < 4; attempt += 1) {
      await verifyInput.fill(totpCode(secret));
      await verifyButton.click();
      if (!(await verifyPanel.isVisible().catch(() => false))) return;
      await page.waitForTimeout(1000);
    }
    throw new Error('Normal Admin TOTP login did not complete.');
  }

  throw new Error('Admin login did not require the configured 2FA flow.');
}

function isGetResponseForPath(response: Response, suffixPath: string) {
  return response.request().method() === 'GET'
    && new URL(response.url()).pathname.endsWith(suffixPath);
}

async function readAdminDirections(
  page: Page,
  profile: string,
  day?: string,
): Promise<DirectionFacts> {
  const params = new URLSearchParams({ section: 'checklist', profile });
  if (day) params.set('day', day);
  const responsePromise = page.waitForResponse((response) => {
    if (!isGetResponseForPath(response, '/queue/admin/directions')) return false;
    return !day || new URL(response.url()).searchParams.get('day') === day;
  }, { timeout: 30_000 }).catch(() => null);
  try {
    await page.goto('/admin/setup-directions?' + params.toString());
  } catch {
    throw new Error('Admin directions screen navigation failed.');
  }
  const response = await responsePromise;
  if (!response || !response.ok()) {
    throw new Error('Admin directions read model did not return the requested clinic-day facts.');
  }
  await expect(page.getByTestId('setup-directions-heading')).toBeVisible();
  const payload = await response.json() as DirectionFacts;
  if (!Array.isArray(payload.directions)) {
    throw new Error('Admin directions response did not contain a directions list.');
  }
  return payload;
}

function directionByKey(facts: DirectionFacts, key: string): DirectionRow {
  const direction = facts.directions.find((item) => item.profile.key === key);
  if (!direction) throw new Error('Admin directions read model omitted the synthetic profile.');
  return direction;
}

function serviceQueueTagOptions(profiles: QueueProfileRow[]) {
  const options: Array<{ value: string; profileKey: string }> = [];
  const seen = new Set<string>();
  for (const profile of profiles) {
    if (!profile || profile.is_active === false || !profile.key) continue;
    const tags = (profile.queue_tags || []).map((tag) => String(tag ?? '').trim()).filter(Boolean);
    for (const value of (tags.length ? tags : [profile.key.trim()])) {
      if (value && !seen.has(value)) {
        seen.add(value);
        options.push({ value, profileKey: profile.key });
      }
    }
  }
  return options;
}

async function createHiddenQueueProfile(page: Page) {
  markRq18Phase('queue-profile-setup-navigation');
  await page.goto('/admin/setup-directions');
  const links = page.getByTestId('setup-editor-links');
  await expect(links).toBeVisible();
  await links.locator('a[href*="servicesTab=queue-profiles"]').click();
  await expect(page).toHaveURL(/servicesTab=queue-profiles/);
  markRq18Phase('queue-profile-list');
  await page.getByRole('button', { name: /Добавить|Add|Қосу|Қўшиш|Qoʻshish/i }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  markRq18Phase('queue-profile-dialog');
  const keyInput = dialog.locator('#queue-profile-key');
  await expect(keyInput).toHaveAttribute('pattern', '[a-z_]+');
  await keyInput.fill(profileKey);
  const profileKeyIsValid = await keyInput.evaluate((input) => (input as HTMLInputElement).checkValidity());
  if (!profileKeyIsValid) {
    throw new Error('Synthetic QueueProfile key does not satisfy the current form validation.');
  }
  await dialog.locator('#queue-profile-title-en').fill(profileTitle);
  await dialog.locator('#queue-profile-title-ru').fill(profileTitle);
  await dialog.locator('#queue-profile-tags').fill(queueTag);
  markRq18Phase('queue-profile-fields-ready');

  const createResponsePromise = page.waitForResponse((response) => {
    const pathname = new URL(response.url()).pathname;
    return response.request().method() === 'POST' && pathname.endsWith('/queues/profiles');
  });
  markRq18Phase('queue-profile-submit');
  await dialog.getByRole('button', { name: /Создать вкладку очереди|Create queue tab|Navbat yorligʻini yaratish/i }).click();
  const createResponse = await createResponsePromise;
  markRq18Phase('queue-profile-created');
  if (!createResponse.ok()) throw new Error('Synthetic QueueProfile creation failed.');
  const createdPayload = createResponse.request().postDataJSON() as { show_on_qr_page?: unknown } | null;
  if (!createdPayload || createdPayload.show_on_qr_page !== false) {
    throw new Error('New QueueProfile was not created hidden by default.');
  }
  await expect(dialog).toHaveCount(0);
  await expect(page.getByRole('row').filter({ hasText: profileTitle })).toHaveCount(1);
  markRq18Phase('queue-profile-row-visible');
}

async function readProfiles(page: Page): Promise<QueueProfileRow[]> {
  const profilesPromise = page.waitForResponse((response) =>
    isGetResponseForPath(response, '/queues/profiles'));
  await page.goto('/admin/services?servicesTab=catalog');
  const response = await profilesPromise;
  if (!response.ok()) throw new Error('Service Catalog could not read QueueProfiles.');
  const payload = await response.json() as { profiles?: QueueProfileRow[] };
  return Array.isArray(payload.profiles) ? payload.profiles : [];
}

async function createDoctorlessService(page: Page, profiles: QueueProfileRow[]) {
  await page.getByRole('button', { name: /Добавить услугу|Add service|Xizmat qoʻshish/i }).first().click();
  const editor = page.getByRole('heading', { name: /Добавление услуги|Add service|Xizmat qoʻshish/i }).locator('..');
  const form = editor.locator('form').last();
  await expect(form).toBeVisible();
  await form.locator('input[type="text"]').first().fill(serviceName);

  const categorySelect = form.locator('.mac-select').first().getByRole('button');
  await categorySelect.click();
  const categories = page.getByRole('listbox').getByRole('option');
  const categoryCount = await categories.count();
  if (categoryCount === 0) {
    throw new Error('Synthetic Service Catalog has no selectable category.');
  }
  await categories.first().click();

  await editor.getByRole('button', { name: /Очередь|Queue|Navbat/i }).click();
  const queueTagSelect = form.locator('.mac-select').first().getByRole('button');
  await queueTagSelect.click();
  const options = serviceQueueTagOptions(profiles);
  const optionIndex = options.findIndex((option) => option.profileKey === profileKey
    && option.value === queueTag);
  if (optionIndex < 0) throw new Error('Synthetic profile queue tag was not offered to the Service Catalog.');
  const visibleOptions = page.getByRole('listbox').getByRole('option');
  await expect(visibleOptions).toHaveCount(options.length + 1);
  await visibleOptions.nth(optionIndex + 1).click();

  await editor.getByRole('button', { name: /Опции|Options|Parametrlar/i }).click();
  const requiresDoctor = form.getByRole('checkbox', { name: /Требует врача|Doctor required|Vrach talab qiladi/i });
  await expect(requiresDoctor).not.toBeChecked();

  const createResponsePromise = page.waitForResponse((response) => {
    const pathname = new URL(response.url()).pathname;
    return response.request().method() === 'POST' && /\/services\/?$/.test(pathname);
  });
  await form.getByRole('button', { name: /Сохранить услугу|Сохранить|Save service|Save|Saqlash/i }).click();
  const createResponse = await createResponsePromise;
  if (!createResponse.ok()) throw new Error('Synthetic doctorless Service creation failed.');
  const body = createResponse.request().postDataJSON() as {
    queue_tag?: string;
    doctor_id?: number | null;
    requires_doctor?: boolean;
  } | null;
  if (!body || body.queue_tag !== queueTag || body.doctor_id != null || body.requires_doctor !== false) {
    throw new Error('Synthetic Service did not preserve the expected doctorless queue mapping.');
  }
  await expect(page.getByText(serviceName, { exact: true })).toBeVisible();
}

async function createAndActivateQueueResource(page: Page): Promise<number> {
  await page.goto('/admin/setup-directions?section=resources');
  await expect(page.getByTestId('setup-directions-heading')).toBeVisible();
  await page.getByTestId('setup-view-resources').click();
  await page.getByTestId('qr-resource-create-toggle').click();
  const form = page.getByTestId('qr-resource-create-form');
  await expect(form).toBeVisible();
  await page.getByTestId('qr-resource-tag-select').click();
  const choice = page.getByRole('listbox').getByRole('option').filter({ hasText: queueTag });
  await expect(choice).toHaveCount(1);
  await choice.click();
  await page.getByTestId('qr-resource-display-name-input').fill(resourceName);
  await page.getByTestId('qr-resource-submit').click();

  const row = page.locator('[data-testid^="qr-resource-row-"]').filter({ hasText: resourceName });
  await expect(row).toHaveCount(1, { timeout: 20_000 });
  await expect(row.getByTestId('qr-resource-badge-draft')).toBeVisible();
  await row.locator('[data-testid^="qr-resource-toggle-"]').click();
  await expect(row.getByTestId('qr-resource-badge-active')).toBeVisible({ timeout: 20_000 });
  const idText = (await row.getAttribute('data-testid'))?.replace('qr-resource-row-', '') || '';
  const resourceId = Number(idText);
  if (!Number.isInteger(resourceId) || resourceId <= 0) {
    throw new Error('Created QueueResource did not expose its persisted numeric ID.');
  }
  return resourceId;
}

async function publishQueueProfile(page: Page) {
  await page.goto('/admin/services?servicesTab=queue-profiles');
  const row = page.getByRole('row').filter({ hasText: profileTitle });
  await expect(row).toHaveCount(1);
  await row.getByRole('button', {
    name: /для настройки QR-публикации|Edit profile .* to manage QR publication|QR жарияланымын баптау үшін .* профилін өңдеу|profilining QR e’lonini sozlash uchun tahrirlash|профилининг QR эълонини созлаш учун таҳрирлаш/i,
  }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  const visibility = dialog.getByRole('checkbox', {
    name: /Показывать профиль на QR-странице|Show profile on QR page|Профильді QR бетінде көрсету|Profilni QR sahifasida koʻrsatish|Профилни QR саҳифасида кўрсатиш/i,
  });
  await expect(visibility).not.toBeChecked();
  await visibility.click();
  const updateResponsePromise = page.waitForResponse((response) => {
    const pathname = new URL(response.url()).pathname;
    return response.request().method() === 'PUT' && pathname.endsWith('/queues/profiles/' + profileKey);
  });
  await dialog.getByRole('button', { name: /Сохранить вкладку очереди|Сохранить|Save|Navbat yorligʻini saqlash|Saqlash/i }).click();
  const updateResponse = await updateResponsePromise;
  if (!updateResponse.ok()) throw new Error('Explicit QueueProfile publication failed.');
  const body = updateResponse.request().postDataJSON() as { show_on_qr_page?: unknown } | null;
  if (!body || body.show_on_qr_page !== true) {
    throw new Error('Explicit QueueProfile publication was not sent as a separate action.');
  }
  await expect(dialog).toHaveCount(0);
}

async function openPermanentQrBlock(page: Page) {
  const row = page.getByTestId('setup-checklist-row-' + queueTag);
  await expect(row).toBeVisible({ timeout: 20_000 });
  await row.getByTestId('setup-qr-expand-' + queueTag).click();
  const block = row.getByTestId('setup-qr-block-' + queueTag);
  await expect(block).toBeVisible();
  return block;
}

function countDirectionStartRequests(page: Page) {
  const count = { value: 0 };
  page.on('request', (request) => {
    if (request.method() !== 'POST') return;
    try {
      const pathname = new URL(request.url()).pathname;
      if (/\/queue\/public\/[^/]+\/start-session$/.test(pathname)) count.value += 1;
    } catch {
      // Malformed URLs are not recorded or printed.
    }
  });
  return count;
}

async function openPublicAddress(
  browser: Browser,
  origin: string,
  publicCode: string,
  recordAssetPage: (page: Page) => void,
): Promise<{
  context: Awaited<ReturnType<Browser['newContext']>>;
  page: Page;
  startCount: { value: number };
  status: number;
  targetDate: string | null;
}> {
  const context = await browser.newContext({ baseURL: origin });
  const page = await context.newPage();
  recordAssetPage(page);
  const startCount = countDirectionStartRequests(page);
  const responsePromise = page.waitForResponse((response) => {
    if (response.request().method() !== 'POST') return false;
    const pathname = new URL(response.url()).pathname;
    return /\/queue\/public\/[^/]+\/start-session$/.test(pathname);
  }, { timeout: 30_000 }).catch(() => null);
  try {
    await page.goto('/q/' + publicCode, { waitUntil: 'domcontentloaded' });
  } catch {
    await context.close().catch(() => undefined);
    throw new Error('Anonymous permanent QR navigation failed.');
  }
  const response = await responsePromise;
  if (!response) {
    await context.close().catch(() => undefined);
    throw new Error('Anonymous permanent QR did not request exactly one short session.');
  }
  let targetDate: string | null = null;
  if (response.ok()) {
    const payload = await response.json() as { target_date?: unknown };
    if (typeof payload.target_date === 'string') targetDate = payload.target_date;
  }
  return {
    context,
    page,
    startCount,
    status: response.status(),
    targetDate,
  };
}

async function waitForPublicForm(page: Page) {
  const patientNameInput = page.locator('#queue-patient-name');
  if (!(await patientNameInput.isVisible().catch(() => false))) {
    // A permanent direction opens the info step first. The current QueueJoin
    // flow requires an explicit continue before rendering the patient form.
    markRq18Phase('public-info-step');
    const continueButton = page.getByRole('button', {
      name: /Продолжить|Continue|Davom etish|Давом этиш|Жалғастыру/i,
    });
    await expect(continueButton).toBeVisible({ timeout: 30_000 });
    await continueButton.click();
    markRq18Phase('public-info-continued');
  }
  await expect(patientNameInput).toBeVisible({ timeout: 30_000 });
  await expect(page.locator('#queue-phone')).toBeVisible();
}

async function setSyntheticProfileArchived(page: Page, archived: boolean) {
  markRq18Phase('profile-lifecycle-navigation');
  await page.goto('/admin/services?servicesTab=queue-profiles');
  const row = page.locator('tr').filter({ hasText: profileTitle });
  await expect(row).toHaveCount(1, { timeout: 30_000 });
  markRq18Phase('profile-lifecycle-row-visible');
  const archiveName = /Архивировать профиль|Archive profile|profilini arxivlash|профилини архивлаш|профилін мұрағаттау/i;
  const restoreName = /Восстановить профиль|Restore profile|profilini arxivdan tiklash|профилини архивдан тиклаш|профилін мұрағаттан қалпына келтіру/i;
  const action = row.getByRole('button', { name: archived ? archiveName : restoreName });
  const expected = row.getByRole('button', { name: archived ? restoreName : archiveName });
  const responsePromise = page.waitForResponse((response) => {
    const pathname = new URL(response.url()).pathname;
    return response.request().method() === 'PUT'
      && pathname.endsWith('/queues/profiles/' + profileKey);
  }, { timeout: 30_000 }).catch(() => null);
  markRq18Phase(archived ? 'profile-archive-action' : 'profile-restore-action');
  await action.click();
  const response = await responsePromise;
  if (!response || !response.ok()) {
    throw new Error(archived
      ? 'Synthetic QueueProfile could not be archived through the Admin control.'
      : 'Synthetic QueueProfile could not be restored through the Admin control.');
  }
  await expect(expected).toBeVisible({ timeout: 30_000 });
}

function markRq18Phase(phase: string) {
  // Static phase labels only: never include patient input, QR codes, tokens, or URLs.
  process.stdout.write('RQ18_PHASE=' + phase + '\n');
}

function createServedAssetRecorder() {
  const hashesByOriginAndPath = new Map<string, Set<string>>();
  const pending: Promise<void>[] = [];
  const captureFailures = new Set<string>();
  const notModifiedResponses = new Set<string>();

  const recordPage = (assetPage: Page) => {
    assetPage.on('response', (response) => {
      const resourceType = response.request().resourceType();
      if (resourceType !== 'script' && resourceType !== 'stylesheet') return;

      let url: URL;
      try {
        url = new URL(response.url());
      } catch {
        captureFailures.add('invalid-static-response-url');
        return;
      }
      if (!url.pathname.startsWith('/assets/') && url.pathname !== '/sw.js') return;

      const key = url.origin + url.pathname;
      if (response.status() === 304) {
        notModifiedResponses.add(key);
        return;
      }
      if (response.status() !== 200) {
        captureFailures.add(key);
        return;
      }

      pending.push(response.body().then((body) => {
        const digest = crypto.createHash('sha256').update(body).digest('hex');
        const hashes = hashesByOriginAndPath.get(key) || new Set<string>();
        hashes.add(digest);
        hashesByOriginAndPath.set(key, hashes);
      }).catch(() => {
        captureFailures.add(key);
      }));
    });
  };

  const reportForOrigin = async (expectedOrigin: string) => {
    await Promise.all(pending);
    if (Array.from(captureFailures).some((key) => key === 'invalid-static-response-url'
        || key.startsWith(expectedOrigin + '/'))) {
      throw new Error('One or more same-run static asset responses could not be hashed.');
    }
    if (Array.from(notModifiedResponses).some((key) => key.startsWith(expectedOrigin + '/')
        && !hashesByOriginAndPath.has(key))) {
      throw new Error('A cached static asset had no earlier response hash in this run.');
    }

    const records = Array.from(hashesByOriginAndPath.entries())
      .filter(([key]) => key.startsWith(expectedOrigin + '/'))
      .map(([key, hashes]) => {
        if (hashes.size !== 1) {
          throw new Error('A served static asset returned conflicting content in one browser run.');
        }
        return { path: key.slice(expectedOrigin.length), sha256: Array.from(hashes)[0] };
      })
      .sort((left, right) => left.path.localeCompare(right.path));

    if (records.length === 0) {
      throw new Error('No same-origin JavaScript or CSS assets were captured.');
    }

    process.stdout.write('RQ18_ASSET_SHA256_COUNT=' + records.length + '\n');
    for (const record of records) {
      process.stdout.write('RQ18_ASSET_SHA256=' + record.path + ' ' + record.sha256 + '\n');
    }
  };

  return { recordPage, reportForOrigin };
}

test('RQ-18: current permanent QR booking and archive/reactivation lifecycle', async ({ browser, page }) => {
  test.setTimeout(600_000);
  page.setDefaultTimeout(30_000);
  page.setDefaultNavigationTimeout(30_000);
  const servedAssets = createServedAssetRecorder();
  servedAssets.recordPage(page);
  let pageErrors = 0;
  page.on('pageerror', () => { pageErrors += 1; });
  markRq18Phase('admin-login');
  await loginAdminWithRequiredTwoFactor(page);
  markRq18Phase('admin-setup-page');
  await page.goto('/admin/setup-directions');
  await expect(page.getByTestId('setup-directions-heading')).toBeVisible();
  const appOrigin = new URL(page.url()).origin;

  markRq18Phase('create-hidden-profile');
  await createHiddenQueueProfile(page);
  const profiles = await readProfiles(page);
  if (!profiles.some((profile) => profile.key === profileKey && profile.is_active !== false)) {
    throw new Error('New synthetic QueueProfile was not present in the Service Catalog.');
  }
  markRq18Phase('create-service');
  await createDoctorlessService(page, profiles);
  markRq18Phase('create-and-activate-resource');
  const resourceId = await createAndActivateQueueResource(page);

  markRq18Phase('verify-hidden-resource-target');
  let facts = await readAdminDirections(page, profileKey);
  let direction = directionByKey(facts, profileKey);
  const initialTarget = direction.booking_targets.filter((target) =>
    target.owner_type === 'resource'
      && target.owner_id === resourceId
      && target.queue_tag === queueTag
      && target.is_active
      && target.eligible_for_new_booking);
  if (direction.resolved_mode !== 'booking'
      || direction.effective_availability !== 'available'
      || direction.public_availability
      || direction.profile.show_on_qr_page
      || initialTarget.length !== 1) {
    throw new Error('Hidden synthetic direction did not resolve to one available resource target.');
  }

  markRq18Phase('publish-profile');
  await publishQueueProfile(page);
  facts = await readAdminDirections(page, profileKey);
  direction = directionByKey(facts, profileKey);
  if (!direction.public_availability
      || !direction.profile.show_on_qr_page
      || direction.configuration_state !== 'ready'
      || direction.booking_targets.length !== 1
      || direction.booking_targets[0].owner_type !== 'resource'
      || direction.booking_targets[0].owner_id !== resourceId
      || direction.booking_targets[0].queue_tag !== queueTag) {
    throw new Error('Published direction did not expose the expected ready resource target.');
  }

  markRq18Phase('provision-permanent-address');
  const initialQrBlock = await openPermanentQrBlock(page);
  const createButton = initialQrBlock.getByTestId('setup-qr-provision-' + queueTag);
  await expect(createButton).toBeVisible({ timeout: 30_000 });
  const provisionResponsePromise = page.waitForResponse((response) => {
    const pathname = new URL(response.url()).pathname;
    return response.request().method() === 'POST'
      && pathname.includes('/public-address/provision');
  }, { timeout: 30_000 }).catch(() => null);
  await createButton.click();
  const provisionResponse = await provisionResponsePromise;
  if (!provisionResponse || !provisionResponse.ok()) {
    throw new Error('Permanent QR address provisioning failed.');
  }
  const provisionPayload = await provisionResponse.json() as { public_code?: unknown };
  const publicCode = typeof provisionPayload.public_code === 'string'
    ? provisionPayload.public_code.toLowerCase()
    : '';
  if (!/^[a-z0-9]{12}$/.test(publicCode)) {
    throw new Error('Permanent QR provisioning returned an invalid address shape.');
  }
  const renderedUrl = await initialQrBlock.getByTestId('setup-qr-url-' + queueTag).textContent() || '';
  let firstPath = '';
  try {
    firstPath = new URL(renderedUrl).pathname;
  } catch {
    throw new Error('Admin QR block did not render a valid permanent address.');
  }
  if (firstPath !== '/q/' + publicCode) {
    throw new Error('Admin QR block and permanent-address response did not identify the same route.');
  }

  await page.reload();
  const restoredBlock = await openPermanentQrBlock(page);
  const showButton = restoredBlock.getByTestId('setup-qr-show-' + queueTag);
  await expect(showButton).toBeVisible({ timeout: 30_000 });
  await showButton.click();
  const restoredUrl = await restoredBlock.getByTestId('setup-qr-url-' + queueTag).textContent() || '';
  let restoredPath = '';
  try {
    restoredPath = new URL(restoredUrl).pathname;
  } catch {
    throw new Error('Saved permanent QR address could not be recovered after reload.');
  }
  if (restoredPath !== firstPath) {
    throw new Error('Reloaded permanent QR did not restore the same address.');
  }
  const restoredQrText = await restoredBlock.textContent() || '';
  if (/\bTTL\b|expires|истекает|действует до/i.test(restoredQrText)) {
    throw new Error('Permanent QR block describes the address as expiring.');
  }

  let bookingTargetDate = '';
  markRq18Phase('anonymous-booking-and-resource-ownership');
  const booking = await openPublicAddress(browser, appOrigin, publicCode, servedAssets.recordPage);
  try {
    if (booking.status !== 200 || booking.startCount.value !== 1) {
      throw new Error('Available permanent QR did not open exactly one anonymous short session.');
    }
    markRq18Phase('anonymous-session-open');
    bookingTargetDate = booking.targetDate || '';
    if (!/^\d{4}-\d{2}-\d{2}$/.test(bookingTargetDate)) {
      throw new Error('Public short-session response did not return its target clinic day.');
    }
    await expect(booking.page.locator('.qj-main-header').getByText(profileTitle, { exact: true })).toBeVisible();
    markRq18Phase('anonymous-direction-title');
    await waitForPublicForm(booking.page);
    markRq18Phase('anonymous-form-visible');
    await booking.page.locator('#queue-patient-name').fill(patientName);
    await booking.page.locator('#queue-phone').fill(patientPhone);
    markRq18Phase('anonymous-form-filled');
    const submitButton = booking.page.locator('form.qj-form button[type="submit"]');
    await expect(submitButton).toBeEnabled();
    markRq18Phase('anonymous-submit-enabled');
    await submitButton.click();
    markRq18Phase('anonymous-submit-clicked');
    await expect(booking.page.locator('#queue-join-success-title')).toBeVisible({ timeout: 30_000 });
    markRq18Phase('anonymous-success-title');
    await expect(booking.page.locator('.qj-success-number')).toHaveText(/№\s*\d+/);
    markRq18Phase('anonymous-success-number');

    facts = await readAdminDirections(page, profileKey, bookingTargetDate);
    direction = directionByKey(facts, profileKey);
    const routedQueue = direction.current_day_queues.filter((queue) =>
      queue.queue_tag === queueTag
        && queue.owner_type === 'resource'
        && queue.owner_id === resourceId);
    if (routedQueue.length !== 1) {
      throw new Error('Completed anonymous booking was not visible under the expected resource-owned day queue.');
    }
    markRq18Phase('anonymous-resource-ownership-confirmed');
  } finally {
    await booking.context.close().catch(() => undefined);
  }

  markRq18Phase('reopen-permanent-address');
  const reopen = await openPublicAddress(browser, appOrigin, publicCode, servedAssets.recordPage);
  try {
    if (reopen.status !== 200 || reopen.startCount.value !== 1) {
      throw new Error('Reopening the permanent QR did not create one fresh short session.');
    }
    await waitForPublicForm(reopen.page);
  } finally {
    await reopen.context.close().catch(() => undefined);
  }

  markRq18Phase('deactivate-resource-preserving-current-queue');
  await page.goto('/admin/setup-directions?section=resources');
  await expect(page.getByTestId('setup-directions-heading')).toBeVisible();
  await page.getByTestId('setup-view-resources').click();
  let resourceRow = page.locator('[data-testid^="qr-resource-row-"]').filter({ hasText: resourceName });
  await expect(resourceRow.getByTestId('qr-resource-badge-active')).toBeVisible();
  await resourceRow.locator('[data-testid^="qr-resource-toggle-"]').click();
  await expect(resourceRow.getByTestId('qr-resource-badge-draft')).toBeVisible({ timeout: 20_000 });

  // Read the same day created by the public session: when the link targets a
  // future clinic day, today's Admin view is a different queue snapshot.
  facts = await readAdminDirections(page, profileKey, bookingTargetDate);
  direction = directionByKey(facts, profileKey);
  markRq18Phase('inactive-resource-facts-loaded');
  const resourceTargets = direction.booking_targets.filter((target) =>
    target.owner_type === 'resource'
      && target.owner_id === resourceId
      && target.queue_tag === queueTag);
  const retainedResourceQueue = resourceTargets.filter((target) =>
    !target.is_active && target.eligible_for_new_booking);
  const currentResourceQueueCount = direction.current_day_queues.filter((queue) =>
    queue.owner_type === 'resource'
      && queue.owner_id === resourceId
      && queue.queue_tag === queueTag).length;
  if (retainedResourceQueue.length !== 1
      || currentResourceQueueCount !== 1
      || !direction.permanent_address_exists) {
    throw new Error(
      'Inactive-resource facts mismatch: '
      + `public=${direction.public_availability}; address=${direction.permanent_address_exists}; `
      + `resource_targets=${resourceTargets.length}; inactive_eligible=${retainedResourceQueue.length}; `
      + `current_resource_queues=${currentResourceQueueCount}.`,
    );
  }
  markRq18Phase('inactive-resource-existing-queue-preserved');

  facts = await readAdminDirections(page, profileKey);
  direction = directionByKey(facts, profileKey);
  if (direction.public_availability || !direction.permanent_address_exists) {
    throw new Error('Inactive resource remained selectable for new clinic-day bookings or lost its permanent address.');
  }
  markRq18Phase('inactive-resource-clinic-day-booking-closed');

  await setSyntheticProfileArchived(page, true);
  markRq18Phase('archive-published-profile');
  facts = await readAdminDirections(page, profileKey);
  direction = directionByKey(facts, profileKey);
  if (direction.public_availability || !direction.permanent_address_exists) {
    throw new Error('QueueProfile archival did not close public booking while preserving the permanent QR address.');
  }

  const archived = await openPublicAddress(browser, appOrigin, publicCode, servedAssets.recordPage);
  try {
    if (archived.status !== 404 || archived.startCount.value !== 1) {
      throw new Error('Archived direction did not fail closed through the anonymous start-session route.');
    }
    await expect(archived.page.getByTestId('qj-direction-unavailable')).toBeVisible({ timeout: 20_000 });
    const refusalText = await archived.page.getByTestId('qj-direction-unavailable').textContent() || '';
    if (refusalText.includes(queueTag) || refusalText.includes(publicCode)) {
      throw new Error('Anonymous refusal exposed internal direction details.');
    }
  } finally {
    await archived.context.close().catch(() => undefined);
  }

  markRq18Phase('reactivate-resource');
  await page.goto('/admin/setup-directions?section=resources');
  await page.getByTestId('setup-view-resources').click();
  resourceRow = page.locator('[data-testid^="qr-resource-row-"]').filter({ hasText: resourceName });
  await expect(resourceRow.getByTestId('qr-resource-badge-draft')).toBeVisible();
  await resourceRow.locator('[data-testid^="qr-resource-toggle-"]').click();
  await expect(resourceRow.getByTestId('qr-resource-badge-active')).toBeVisible({ timeout: 20_000 });

  await setSyntheticProfileArchived(page, false);
  markRq18Phase('restore-published-profile');
  facts = await readAdminDirections(page, profileKey);
  direction = directionByKey(facts, profileKey);
  const restoredResourceTarget = direction.booking_targets.filter((target) =>
    target.owner_type === 'resource'
      && target.owner_id === resourceId
      && target.queue_tag === queueTag
      && target.is_active
      && target.eligible_for_new_booking);
  if (direction.effective_availability !== 'available'
      || !direction.public_availability
      || restoredResourceTarget.length !== 1
      || !direction.permanent_address_exists) {
    throw new Error('Resource and profile restoration did not restore availability for the same permanent QR address.');
  }

  const reactivated = await openPublicAddress(browser, appOrigin, publicCode, servedAssets.recordPage);
  try {
    if (reactivated.status !== 200 || reactivated.startCount.value !== 1) {
      throw new Error('Reactivated permanent QR did not open a fresh anonymous short session.');
    }
    await waitForPublicForm(reactivated.page);
  } finally {
    await reactivated.context.close().catch(() => undefined);
  }

  markRq18Phase('completed');
  if (pageErrors !== 0) throw new Error('Unexpected uncaught Admin browser errors were observed.');
  await servedAssets.reportForOrigin(appOrigin);
});
