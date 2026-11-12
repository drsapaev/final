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
import { createServer } from 'node:http';
import {
  expect,
  request,
  test,
  type APIRequestContext,
  type Browser,
  type BrowserContext,
  type Page,
  type Request,
  type Response,
} from '@playwright/test';

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
const servedAssetDrainByPage = new WeakMap<Page, () => Promise<void>>();
const servedAssetDiagnosticsByPage = new WeakMap<Page, () => string>();

async function withServedAssetDiagnostics<T>(page: Page, operation: () => Promise<T>): Promise<T> {
  try {
    return await operation();
  } catch (error) {
    const diagnostics = servedAssetDiagnosticsByPage.get(page);
    if (diagnostics) process.stdout.write('RQ18_CAPTURE_DIAGNOSTICS=' + diagnostics() + '\n');
    throw error;
  }
}

async function gotoWithServedAssetDrain(
  page: Page,
  url: string,
  options?: Parameters<Page['goto']>[1],
) {
  await servedAssetDrainByPage.get(page)?.();
  return withServedAssetDiagnostics(page, () => page.goto(url, options));
}

async function reloadWithServedAssetDrain(
  page: Page,
  options?: Parameters<Page['reload']>[0],
) {
  await servedAssetDrainByPage.get(page)?.();
  return withServedAssetDiagnostics(page, () => page.reload(options));
}

async function goBackWithServedAssetDrain(page: Page) {
  await servedAssetDrainByPage.get(page)?.();
  return withServedAssetDiagnostics(page, () => page.goBack());
}

async function goForwardWithServedAssetDrain(page: Page) {
  await servedAssetDrainByPage.get(page)?.();
  return withServedAssetDiagnostics(page, () => page.goForward());
}

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
  await gotoWithServedAssetDrain(page, '/login');
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
  await gotoWithServedAssetDrain(page, '/admin/setup-directions?' + params.toString());
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

type QueueProfileLinkCounts = Record<string, number>;

async function readQueueProfileLinkCounts(page: Page, targetProfileKey: string) {
  const result = await page.evaluate(async (key) => {
    const token = sessionStorage.getItem('auth_token');
    const response = await fetch(`/api/v1/queues/profiles/${encodeURIComponent(key)}/impact-preview`, {
      cache: 'no-store',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    const body = await response.json().catch(() => null) as {
      profile?: { key?: string };
      links?: QueueProfileLinkCounts;
    } | null;
    return { status: response.status, profileKey: body?.profile?.key, links: body?.links || null };
  }, targetProfileKey);
  if (result.status !== 200 || result.profileKey !== targetProfileKey || !result.links) {
    throw new Error('QueueProfile impact preview could not confirm persisted service links.');
  }
  return result.links;
}

async function readPersistedDoctorlessService(page: Page, serviceId: number) {
  const result = await page.evaluate(async (id) => {
    const token = sessionStorage.getItem('auth_token');
    const response = await fetch(`/api/v1/services/${id}`, {
      cache: 'no-store',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    const service = await response.json().catch(() => null) as {
      id?: number;
      queue_tag?: string | null;
      doctor_id?: number | null;
      requires_doctor?: boolean | null;
    } | null;
    return { status: response.status, service };
  }, serviceId);
  const service = result.service;
  if (result.status !== 200
      || service?.id !== serviceId
      || service.queue_tag == null
      || service.doctor_id != null
      || service.requires_doctor !== false) {
    throw new Error('The created doctorless Service could not be reread with its persisted queue binding.');
  }
  return service;
}

async function createHiddenQueueProfile(page: Page) {
  markRq18Phase('queue-profile-setup-navigation');
  await gotoWithServedAssetDrain(page, '/admin/setup-directions');
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
  await gotoWithServedAssetDrain(page, '/admin/services?servicesTab=catalog');
  const response = await profilesPromise;
  if (!response.ok()) throw new Error('Service Catalog could not read QueueProfiles.');
  const payload = await response.json() as { profiles?: QueueProfileRow[] };
  return Array.isArray(payload.profiles) ? payload.profiles : [];
}

async function createDoctorlessService(
  page: Page,
  profiles: QueueProfileRow[],
  target: { profileKey: string; queueTag: string; serviceName: string } = {
    profileKey,
    queueTag,
    serviceName,
  },
): Promise<{ serviceId: number; initialServiceLinks: number }> {
  const initialLinks = await readQueueProfileLinkCounts(page, target.profileKey);
  const initialServiceLinks = initialLinks.services;
  if (!Number.isInteger(initialServiceLinks) || initialServiceLinks < 0) {
    throw new Error('QueueProfile impact preview returned an invalid initial service-link count.');
  }

  await page.getByRole('button', { name: /Добавить услугу|Add service|Xizmat qoʻshish/i }).first().click();
  const editor = page.getByRole('heading', { name: /Добавление услуги|Add service|Xizmat qoʻshish/i }).locator('..');
  const form = editor.locator('form').last();
  await expect(form).toBeVisible();
  await form.locator('input[type="text"]').first().fill(target.serviceName);

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
  const optionIndex = options.findIndex((option) => option.profileKey === target.profileKey
    && option.value === target.queueTag);
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
  if (!body || body.queue_tag !== target.queueTag || body.doctor_id != null || body.requires_doctor !== false) {
    throw new Error('Synthetic Service did not preserve the expected doctorless queue mapping.');
  }
  const created = await createResponse.json() as { id?: number };
  if (!Number.isInteger(created.id) || (created.id ?? 0) <= 0) {
    throw new Error('Synthetic Service creation response did not expose its persisted ID.');
  }
  const serviceId = created.id as number;
  const persistedService = await readPersistedDoctorlessService(page, serviceId);
  if (persistedService.queue_tag !== target.queueTag) {
    throw new Error('The created Service was not persisted with the selected QueueProfile tag.');
  }
  const updatedLinks = await readQueueProfileLinkCounts(page, target.profileKey);
  if (updatedLinks.services !== initialServiceLinks + 1) {
    throw new Error('The exact new Service did not add one persisted link to its target QueueProfile.');
  }
  await expect(page.getByText(target.serviceName, { exact: true })).toBeVisible();
  return { serviceId, initialServiceLinks };
}

function clinicTodayTashkent(): string {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Tashkent',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date());
  const value = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${value.year}-${value.month}-${value.day}`;
}

async function verifyT18SpecialistsNavigation(page: Page) {
  const key = 'specialists';
  const day = clinicTodayTashkent();
  markRq18Phase('t18-specialists-catalog');
  const profiles = await readProfiles(page);
  if (!profiles.some((profile) => profile.key === key)) {
    throw new Error('The migrated synthetic QueueProfile specialists was not present in the Admin catalog.');
  }

  const specialistsService = `SYNTHETIC-RQ18 profile guard ${suffixKey}`;
  const createdSpecialistsService = await createDoctorlessService(page, profiles, {
    profileKey: key,
    queueTag: 'cardiology',
    serviceName: specialistsService,
  });

  markRq18Phase('t18-specialists-queue-profiles-route');
  await gotoWithServedAssetDrain(page, '/admin/services?servicesTab=queue-profiles');
  await expect(page.getByRole('heading', {
    name: /Вкладки регистратуры|Queue profiles|Кезек профильдері|Registratura yorliqlari|Навбат профиллари/i,
  }).first()).toBeVisible({ timeout: 30_000 });
  const specialistsKeyCell = page.locator('tbody code').getByText(key, { exact: true });
  await expect(specialistsKeyCell).toHaveCount(1);
  const specialistsRow = specialistsKeyCell.locator('xpath=ancestor::tr');
  await expect(specialistsRow).toHaveCount(1);

  markRq18Phase('t18-specialists-cabinet-route');
  await gotoWithServedAssetDrain(page, '/admin/queue-cabinet-management');
  await expect(page.getByRole('heading', {
    name: /Кабинеты очередей|Queue cabinets|Кезек кабинеттері|Navbat kabinetlari|Навбат кабинетлари/i,
  }).first()).toBeVisible({ timeout: 30_000 });

  markRq18Phase('t18-specialists-settings-route');
  await gotoWithServedAssetDrain(page, '/admin/queue-settings');
  await expect(page.getByRole('heading', {
    name: /Настройки очередей|Queue settings|Navbat sozlamalari/i,
  }).first()).toBeVisible({ timeout: 30_000 });

  markRq18Phase('t18-specialists-selected-profile');
  const facts = await readAdminDirections(page, key, day);
  directionByKey(facts, key);
  await expect(page.getByTestId('setup-editor-links')).toBeVisible();
  await expect.poll(() => new URL(page.url()).searchParams.get('profile')).toBe(key);
  await expect.poll(() => new URL(page.url()).searchParams.get('day')).toBe(day);

  markRq18Phase('t18-specialists-editor-return');
  await page.getByTestId('setup-editor-links').locator('a[href*="servicesTab=queue-profiles"]').click();
  const assertReturnContext = async (tab: 'catalog' | 'queue-profiles') => {
    await expect.poll(() => new URL(page.url()).searchParams.get('servicesTab')).toBe(tab);
    const params = new URL(page.url()).searchParams;
    if (params.get('setupReturn') !== 'queue-directions-v1'
        || params.get('setupSection') !== 'checklist'
        || params.get('setupProfile') !== key
        || params.get('setupDay') !== day) {
      throw new Error('Typed setup return context lost the selected specialists profile or clinic day.');
    }
    await expect(page.getByTestId('queue-setup-return-link')).toBeVisible();
  };
  await assertReturnContext('queue-profiles');

  const tabs = page.locator('.admin-services-tab-bar button');
  await expect(tabs).toHaveCount(2);
  await tabs.nth(0).click();
  await assertReturnContext('catalog');
  await tabs.nth(1).click();
  await assertReturnContext('queue-profiles');

  markRq18Phase('t18-specialists-reload-history');
  await reloadWithServedAssetDrain(page);
  await assertReturnContext('queue-profiles');
  await goBackWithServedAssetDrain(page);
  await assertReturnContext('catalog');
  await goForwardWithServedAssetDrain(page);
  await assertReturnContext('queue-profiles');
  await page.getByTestId('queue-setup-return-link').click();
  await expect(page.getByTestId('setup-directions-heading')).toBeVisible();
  await expect.poll(() => new URL(page.url()).searchParams.get('profile')).toBe(key);
  await expect.poll(() => new URL(page.url()).searchParams.get('day')).toBe(day);

  markRq18Phase('t18-specialists-delete-guard-preview');
  await gotoWithServedAssetDrain(page, '/admin/services?servicesTab=queue-profiles');
  await expect(specialistsRow).toHaveCount(1);
  const persistedService = await readPersistedDoctorlessService(page, createdSpecialistsService.serviceId);
  const impactLinks = await readQueueProfileLinkCounts(page, key);
  const linkCount = Object.values(impactLinks).reduce((total, value) => total + value, 0);
  if (persistedService.queue_tag !== 'cardiology'
      || impactLinks.services !== createdSpecialistsService.initialServiceLinks + 1
      || linkCount < 1) {
    throw new Error('The specialists delete-guard check lacks a verified persisted Service binding created by this run.');
  }

  const deleteResponsePromise = page.waitForResponse((response) => {
    return response.request().method() === 'DELETE'
      && new URL(response.url()).pathname.endsWith('/queues/profiles/' + key);
  }, { timeout: 30_000 });
  await specialistsRow.getByRole('button').last().click();
  const deleteDialog = page.getByRole('dialog');
  await expect(deleteDialog).toBeVisible();
  await deleteDialog.getByRole('button', { name: /Удалить|Delete|Жою|O‘chirish|O'chirish|Ўчириш/i }).last().click();
  const deleteResponse = await deleteResponsePromise;
  if (deleteResponse.status() !== 409) {
    throw new Error('The linked specialists QueueProfile delete guard did not return HTTP 409.');
  }
  const deletePayload = await deleteResponse.json() as { detail?: { reason?: string } };
  if (deletePayload.detail?.reason !== 'profile_has_significant_links') {
    throw new Error('The specialists QueueProfile delete was blocked for an unexpected reason.');
  }
  await expect(specialistsRow).toHaveCount(1);
  process.stdout.write('RQ18_T18_10=PASS\n');
}

async function createAndActivateQueueResource(page: Page): Promise<number> {
  await gotoWithServedAssetDrain(page, '/admin/setup-directions?section=resources');
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
  await gotoWithServedAssetDrain(page, '/admin/services?servicesTab=queue-profiles');
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
  servedAssets: ReturnType<typeof createServedAssetRecorder>,
): Promise<{
  context: Awaited<ReturnType<Browser['newContext']>>;
  page: Page;
  startCount: { value: number };
  status: number;
  targetDate: string | null;
}> {
  const context = await browser.newContext({ baseURL: origin });
  const page = await context.newPage();
  await servedAssets.recordPage(page);
  const startCount = countDirectionStartRequests(page);
  const responsePromise = page.waitForResponse((response) => {
    if (response.request().method() !== 'POST') return false;
    const pathname = new URL(response.url()).pathname;
    return /\/queue\/public\/[^/]+\/start-session$/.test(pathname);
  }, { timeout: 30_000 }).catch(() => null);
  try {
    await gotoWithServedAssetDrain(page, '/q/' + publicCode, { waitUntil: 'domcontentloaded' });
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

async function setSyntheticProfileArchived(
  page: Page,
  archived: boolean,
) {
  markRq18Phase('profile-lifecycle-navigation');
  await gotoWithServedAssetDrain(page, '/admin/services?servicesTab=queue-profiles');
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

type NavigationAbortEvidence = {
  frameId?: string;
  loaderId: string;
  hadMatchingHash: boolean;
};

type MainFrameLoaderEvidence = {
  mainFrameId: string | null;
  mainFrameLoaderId: string | null;
  supersededMainLoaderIds: ReadonlySet<string>;
};

function isCdpNavigationAbortCandidate(
  failure: { errorText: string; canceled?: boolean },
  request: { frameId?: string; loaderId: string },
  mainFrameId: string | null,
) {
  return failure.errorText === 'net::ERR_ABORTED'
    && failure.canceled === true
    && request.frameId === mainFrameId
    && request.loaderId.length > 0;
}

function isVerifiedSupersededMainFrameAbort(
  aborted: NavigationAbortEvidence,
  state: MainFrameLoaderEvidence,
) {
  return aborted.hadMatchingHash
    && aborted.frameId !== undefined
    && aborted.frameId === state.mainFrameId
    && aborted.loaderId !== state.mainFrameLoaderId
    && state.supersededMainLoaderIds.has(aborted.loaderId);
}

function createServedAssetRecorder(options: { drainTimeoutMs?: number } = {}) {
  const drainTimeoutMs = options.drainTimeoutMs ?? 30_000;
  type BrowserBodyReadFailure =
    | 'cdp-body-evicted'
    | 'cdp-body-unavailable'
    | 'cdp-resource-unavailable'
    | 'context-closed'
    | 'read-failed';
  type BrowserBodyRead = { ok: true; bytes: Buffer } | { ok: false; reason: BrowserBodyReadFailure };

  const bodyReadFailureCode = (error: unknown): BrowserBodyReadFailure => {
    const message = error instanceof Error ? error.message : '';
    if (/was evicted!$/i.test(message)) return 'cdp-body-evicted';
    if (message === 'Response body is unavailable') return 'cdp-body-unavailable';
    if (message.includes('No resource with given identifier found')) return 'cdp-resource-unavailable';
    if (message.includes('Target page, context or browser has been closed')) return 'context-closed';
    return 'read-failed';
  };

  const capturedAssetHashes = new Map<string, string>();
  const captureFailures = new Map<string, string>();
  const pendingCaptures = new Set<Promise<void>>();
  type AssetReference = { key: string; path: string };
  type PendingNavigationAbort = NavigationAbortEvidence & {
    asset: AssetReference;
  };
  type PageCaptureState = {
    activeRequests: Map<Request, AssetReference>;
    cdpActiveRequestIds: Set<string>;
    cdpActiveRequestPaths: Map<string, string>;
    browserAbortedByKey: Map<string, number>;
    browserFinishedByKey: Map<string, number>;
    cdpFinishedByKey: Map<string, number>;
    responseBodies: Map<Request, { status: number; body: Promise<BrowserBodyRead> }>;
    pending: Set<Promise<void>>;
    mainFrameId: string | null;
    mainFrameLoaderId: string | null;
    supersededMainLoaderIds: Set<string>;
    pendingNavigationAborts: PendingNavigationAbort[];
    bodyReadStats: {
      bodyReadStarted: number;
      bodyReadCompleted: number;
      bodyReadFailed: number;
    };
    usesCdp: boolean;
  };
  const pageCaptureStates = new Map<Page, PageCaptureState>();

  const incrementCount = (counts: Map<string, number>, key: string) => {
    counts.set(key, (counts.get(key) || 0) + 1);
  };

  const formatCaptureDiagnostics = (state: PageCaptureState) => {
    const pendingPaths = new Set([
      ...Array.from(state.activeRequests.values(), (asset) => asset.path),
      ...state.cdpActiveRequestPaths.values(),
    ]);
    const pendingPathHashes = Array.from(pendingPaths)
      .map((path) => crypto.createHash('sha256').update(path).digest('hex').slice(0, 16))
      .sort();
    return [
      'active=' + state.activeRequests.size,
      'cdp=' + state.cdpActiveRequestIds.size,
      'pendingCaptures=' + state.pending.size,
      'bodyReadStarted=' + state.bodyReadStats.bodyReadStarted,
      'bodyReadCompleted=' + state.bodyReadStats.bodyReadCompleted,
      'bodyReadFailed=' + state.bodyReadStats.bodyReadFailed,
      'pendingPathHashes=' + (pendingPathHashes.join(',') || 'none'),
    ].join(' ');
  };

  const recordHash = (asset: AssetReference, bytes: Buffer) => {
    const sha256 = crypto.createHash('sha256').update(bytes).digest('hex');
    const previous = capturedAssetHashes.get(asset.key);
    if (previous && previous !== sha256) {
      captureFailures.set(asset.key, 'multiple-browser-response-bodies');
      return;
    }
    capturedAssetHashes.set(asset.key, sha256);
  };

  const recordPage = async (assetPage: Page) => {
    const assetKeyFor = (rawUrl: string, resourceType: string): AssetReference | null => {
      let url: URL;
      try {
        url = new URL(rawUrl);
      } catch {
        return null;
      }
      if (url.pathname !== '/sw.js'
          && (!url.pathname.startsWith('/assets/')
            || (resourceType !== 'script' && resourceType !== 'stylesheet'))) return null;
      return { key: url.origin + url.pathname, path: url.pathname };
    };

    const cdpAssetKeyFor = (rawUrl: string, resourceType?: string): AssetReference | null => {
      let pathname: string;
      try {
        pathname = new URL(rawUrl).pathname;
      } catch {
        return null;
      }
      const normalizedType = resourceType?.toLowerCase();
      if (normalizedType === 'script' || normalizedType === 'stylesheet') {
        return assetKeyFor(rawUrl, normalizedType);
      }
      if (pathname === '/sw.js' || /\.m?js$/i.test(pathname)) return assetKeyFor(rawUrl, 'script');
      if (/\.css$/i.test(pathname)) return assetKeyFor(rawUrl, 'stylesheet');
      return null;
    };

    const browser = assetPage.context().browser();
    const cdpSession = browser?.browserType().name() === 'chromium'
      ? await assetPage.context().newCDPSession(assetPage)
      : null;
    const state: PageCaptureState = {
      activeRequests: new Map<Request, { key: string; path: string }>(),
      cdpActiveRequestIds: new Set<string>(),
      cdpActiveRequestPaths: new Map<string, string>(),
      browserAbortedByKey: new Map<string, number>(),
      browserFinishedByKey: new Map<string, number>(),
      cdpFinishedByKey: new Map<string, number>(),
      responseBodies: new Map<Request, { status: number; body: Promise<BrowserBodyRead> }>(),
      pending: new Set<Promise<void>>(),
      mainFrameId: null,
      mainFrameLoaderId: null,
      supersededMainLoaderIds: new Set<string>(),
      pendingNavigationAborts: [],
      bodyReadStats: {
        bodyReadStarted: 0,
        bodyReadCompleted: 0,
        bodyReadFailed: 0,
      },
      usesCdp: cdpSession !== null,
    };
    pageCaptureStates.set(assetPage, state);
    servedAssetDrainByPage.set(assetPage, () => waitForPage(assetPage));
    const diagnostics = () => formatCaptureDiagnostics(state);
    servedAssetDiagnosticsByPage.set(assetPage, diagnostics);

    const addPendingCapture = (capture: Promise<void>) => {
      state.pending.add(capture);
      pendingCaptures.add(capture);
      void capture.then(() => {
        state.pending.delete(capture);
        pendingCaptures.delete(capture);
      });
    };

    if (cdpSession) {
      const cdpAssets = new Map<string, {
        asset: AssetReference;
        frameId?: string;
        loaderId: string;
        status?: number;
      }>();
      cdpSession.on('Page.frameNavigated', (event) => {
        const frame = event.frame;
        if (frame.parentId) return;
        if (state.mainFrameId && state.mainFrameId !== frame.id) return;
        const previousLoaderId = state.mainFrameLoaderId;
        if (previousLoaderId && previousLoaderId !== frame.loaderId) {
          state.supersededMainLoaderIds.add(previousLoaderId);
        }
        state.mainFrameId = frame.id;
        state.mainFrameLoaderId = frame.loaderId;
      });
      cdpSession.on('Network.requestWillBeSent', (event) => {
        const asset = cdpAssetKeyFor(event.request.url, event.type);
        if (!asset) return;
        cdpAssets.set(event.requestId, {
          asset,
          frameId: event.frameId,
          loaderId: event.loaderId,
          status: event.redirectResponse?.status,
        });
        state.cdpActiveRequestIds.add(event.requestId);
        state.cdpActiveRequestPaths.set(event.requestId, asset.path);
      });
      cdpSession.on('Network.responseReceived', (event) => {
        const asset = assetKeyFor(event.response.url, event.type.toLowerCase());
        if (!asset) return;
        cdpAssets.set(event.requestId, {
          asset,
          frameId: event.frameId,
          loaderId: event.loaderId,
          status: event.response.status,
        });
        state.cdpActiveRequestIds.add(event.requestId);
        state.cdpActiveRequestPaths.set(event.requestId, asset.path);
      });
      cdpSession.on('Network.loadingFinished', (event) => {
        const cdpAsset = cdpAssets.get(event.requestId);
        if (!cdpAsset) return;
        cdpAssets.delete(event.requestId);
        state.cdpActiveRequestIds.delete(event.requestId);
        state.cdpActiveRequestPaths.delete(event.requestId);
        incrementCount(state.cdpFinishedByKey, cdpAsset.asset.key);

        if (cdpAsset.status !== 200) {
          captureFailures.set(cdpAsset.asset.key, 'http-' + (cdpAsset.status ?? 'unknown'));
          return;
        }

        // Chromium can discard Playwright Response bodies for resources loaded
        // later in a busy page. Read the completed response through CDP before
        // its Network request id is evicted, without pausing the response
        // pipeline or relying on a second HTTP request.
        state.bodyReadStats.bodyReadStarted += 1;
        const capture = (async () => {
          try {
            const responseBody = await cdpSession.send('Network.getResponseBody', {
              requestId: event.requestId,
            });
            const bytes = responseBody.base64Encoded
              ? Buffer.from(responseBody.body, 'base64')
              : Buffer.from(responseBody.body, 'utf8');
            state.bodyReadStats.bodyReadCompleted += 1;
            recordHash(cdpAsset.asset, bytes);
          } catch (error: unknown) {
            state.bodyReadStats.bodyReadFailed += 1;
            captureFailures.set(
              cdpAsset.asset.key,
              'browser-cdp-response-body-unavailable-' + bodyReadFailureCode(error),
            );
          }
        })();
        addPendingCapture(capture);
      });
      cdpSession.on('Network.loadingFailed', (event) => {
        const cdpAsset = cdpAssets.get(event.requestId);
        if (!cdpAsset) return;
        cdpAssets.delete(event.requestId);
        state.cdpActiveRequestIds.delete(event.requestId);
        state.cdpActiveRequestPaths.delete(event.requestId);
        if (isCdpNavigationAbortCandidate(event, cdpAsset, state.mainFrameId)) {
          state.pendingNavigationAborts.push({
            asset: cdpAsset.asset,
            frameId: cdpAsset.frameId,
            loaderId: cdpAsset.loaderId,
            hadMatchingHash: capturedAssetHashes.has(cdpAsset.asset.key),
          });
        } else {
          captureFailures.set(cdpAsset.asset.key, 'request-failed');
        }
      });
      await cdpSession.send('Page.enable');
      const frameTree = await cdpSession.send('Page.getFrameTree');
      state.mainFrameId = frameTree.frameTree.frame.id;
      state.mainFrameLoaderId = frameTree.frameTree.frame.loaderId;
      await cdpSession.send('Network.enable');
      await cdpSession.send('Network.setCacheDisabled', { cacheDisabled: true });
      assetPage.once('close', () => {
        void cdpSession.detach().catch(() => undefined);
      });
    }

    assetPage.on('request', (browserRequest) => {
      const asset = assetKeyFor(browserRequest.url(), browserRequest.resourceType());
      if (asset) state.activeRequests.set(browserRequest, asset);
    });

    assetPage.on('response', (browserResponse) => {
      const browserRequest = browserResponse.request();
      if (state.usesCdp || !state.activeRequests.has(browserRequest)) return;

      // Non-Chromium browsers have no CDP Network.getResponseBody path. Read
      // Playwright's actual browser response immediately and convert rejection
      // into a safe reason before it can become unhandled.
      state.bodyReadStats.bodyReadStarted += 1;
      const body = browserResponse.body().then<BrowserBodyRead, BrowserBodyRead>(
        (bytes) => {
          state.bodyReadStats.bodyReadCompleted += 1;
          return { ok: true, bytes };
        },
        (error: unknown) => {
          state.bodyReadStats.bodyReadFailed += 1;
          return { ok: false, reason: bodyReadFailureCode(error) };
        },
      );
      state.responseBodies.set(browserRequest, {
        status: browserResponse.status(),
        body,
      });
    });

    assetPage.on('requestfinished', (browserRequest) => {
      const asset = state.activeRequests.get(browserRequest);
      if (!asset) return;
      state.activeRequests.delete(browserRequest);
      incrementCount(state.browserFinishedByKey, asset.key);
      const responseBody = state.responseBodies.get(browserRequest);
      state.responseBodies.delete(browserRequest);
      if (state.usesCdp) return;

      const capture = (async () => {
        if (!responseBody) {
          captureFailures.set(asset.key, 'browser-response-unavailable');
          return;
        }
        if (responseBody.status !== 200) {
          captureFailures.set(asset.key, 'http-' + responseBody.status);
          return;
        }

        const result = await responseBody.body;
        if (!result.ok) {
          captureFailures.set(asset.key, 'browser-response-body-unavailable-' + result.reason);
          return;
        }

        recordHash(asset, result.bytes);
      })();
      addPendingCapture(capture);
    });

    assetPage.on('requestfailed', (browserRequest) => {
      const asset = state.activeRequests.get(browserRequest);
      if (!asset) return;
      state.activeRequests.delete(browserRequest);
      state.responseBodies.delete(browserRequest);
      const failure = browserRequest.failure()?.errorText;
      if (!cdpSession || failure !== 'net::ERR_ABORTED') {
        captureFailures.set(asset.key, 'request-failed');
        return;
      }
      // Chromium may classify a navigation cancellation as ERR_ABORTED. Keep
      // it pending until CDP proves the main-frame loader was superseded by a
      // committed navigation; unmatched aborts fail closed.
      incrementCount(state.browserAbortedByKey, asset.key);
    });
  };

  const waitForPage = async (assetPage: Page) => {
    const state = pageCaptureStates.get(assetPage);
    if (!state) return;
    const deadline = Date.now() + drainTimeoutMs;
    while (state.activeRequests.size > 0 || state.cdpActiveRequestIds.size > 0 || state.pending.size > 0) {
      if (Date.now() >= deadline) {
        const diagnostics = servedAssetDiagnosticsByPage.get(assetPage);
        const diagnosticSummary = diagnostics ? diagnostics() : formatCaptureDiagnostics(state);
        process.stdout.write('RQ18_CAPTURE_DIAGNOSTICS=' + diagnosticSummary + '\n');
        throw new Error('Timed out waiting for browser-served asset bodies to settle '
          + '(' + diagnosticSummary + ').');
      }
      await new Promise((resolve) => setTimeout(resolve, 25));
    }
  };

  const reportForOrigin = async (expectedOrigin: string) => {
    await Promise.all(Array.from(pageCaptureStates.keys(), waitForPage));
    while (pendingCaptures.size > 0) await Promise.all(Array.from(pendingCaptures));
    const origin = new URL(expectedOrigin).origin;
    for (const state of pageCaptureStates.values()) {
      const verifiedNavigationAbortCounts = new Map<string, number>();
      for (const aborted of state.pendingNavigationAborts) {
        if (!isVerifiedSupersededMainFrameAbort(aborted, state)) {
          captureFailures.set(aborted.asset.key, 'request-failed');
        } else {
          incrementCount(verifiedNavigationAbortCounts, aborted.asset.key);
        }
      }
      for (const [key, browserAbortCount] of state.browserAbortedByKey) {
        if (browserAbortCount > (verifiedNavigationAbortCounts.get(key) || 0)) {
          captureFailures.set(key, 'request-failed');
        }
      }
    }
    const finishedCounts = new Map<string, { browser: number; cdp: number }>();
    for (const state of pageCaptureStates.values()) {
      if (!state.usesCdp) continue;
      for (const key of new Set([...state.browserFinishedByKey.keys(), ...state.cdpFinishedByKey.keys()])) {
        const counts = finishedCounts.get(key) || { browser: 0, cdp: 0 };
        counts.browser += state.browserFinishedByKey.get(key) || 0;
        counts.cdp += state.cdpFinishedByKey.get(key) || 0;
        finishedCounts.set(key, counts);
      }
    }
    for (const [key, counts] of finishedCounts) {
      if (key.startsWith(origin + '/') && counts.browser !== counts.cdp) {
        captureFailures.set(key, 'browser-cdp-finished-count-mismatch');
      }
    }
    const failures = Array.from(captureFailures.entries())
      .filter(([key]) => key.startsWith(origin + '/'))
      .map(([key, reason]) => {
        const path = key.slice(origin.length);
        return path + ':' + reason;
      })
      .sort();
    if (failures.length > 0) {
      throw new Error('Browser-served asset bodies could not be verified: ' + failures.join(', '));
    }
    const records = Array.from(capturedAssetHashes.entries())
      .filter(([key]) => key.startsWith(origin + '/'))
      .map(([key, sha256]) => ({ path: key.slice(origin.length), sha256 }))
      .sort((left, right) => left.path.localeCompare(right.path));
    const browserAssetPaths = records
      .map((record) => record.path)
      .filter((path) => path.startsWith('/assets/'));
    if (browserAssetPaths.length === 0) {
      throw new Error('No same-origin JavaScript or CSS assets were captured.');
    }

    process.stdout.write('RQ18_BROWSER_ASSET_PATH_COUNT=' + browserAssetPaths.length + '\n');
    process.stdout.write('RQ18_ASSET_SHA256_COUNT=' + records.length + '\n');
    for (const record of records) {
      process.stdout.write('RQ18_ASSET_SHA256=' + record.path + ' ' + record.sha256 + '\n');
    }
    process.stdout.write('RQ18_BROWSER_SW_CAPTURED=' + (records.some((record) => record.path === '/sw.js') ? '1' : '0') + '\n');
    return records;
  };

  return { recordPage, waitForPage, reportForOrigin };
}

test('RQ-18 provenance hashes the browser response body before navigation cancels it', async ({ browser }) => {
  test.setTimeout(60_000);
  const probePath = `/assets/rq18-browser-response-${suffixKey}.js`;
  const browserBody = `/*${'x'.repeat(1024 * 1024)}*/\nwindow.__rq18BrowserResponse = '${suffixKey}';`;
  const independentBody = `window.__rq18IndependentResponse = '${suffixKey}';`;
  const browserHash = crypto.createHash('sha256').update(browserBody).digest('hex');
  const server = createServer((incoming, outgoing) => {
    outgoing.statusCode = 200;
    if (incoming.url === '/' || incoming.url === '/after-capture') {
      outgoing.setHeader('content-type', 'text/html; charset=utf-8');
      outgoing.end('<!doctype html><html><head></head><body></body></html>');
      return;
    }
    if (incoming.url === probePath || incoming.url === probePath + '?independent=1') {
      outgoing.setHeader('content-type', 'application/javascript; charset=utf-8');
      outgoing.setHeader('cache-control', 'no-store');
      if (incoming.url === probePath) {
        outgoing.flushHeaders();
        outgoing.write(browserBody.slice(0, 1024));
        setTimeout(() => outgoing.end(browserBody.slice(1024)), 200);
      } else {
        outgoing.end(independentBody);
      }
      return;
    }
    outgoing.statusCode = 404;
    outgoing.end();
  });
  await new Promise<void>((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolve);
  });
  const address = server.address();
  if (!address || typeof address === 'string') {
    await new Promise<void>((resolve) => server.close(() => resolve()));
    throw new Error('Could not start local browser-byte regression server.');
  }
  const origin = `http://127.0.0.1:${address.port}`;
  const probeUrl = new URL(probePath, origin).toString();
  let context: BrowserContext | undefined;
  let independentRequest: APIRequestContext | undefined;

  try {
    context = await browser.newContext({ serviceWorkers: 'block' });
    const page = await context.newPage();
    const servedAssets = createServedAssetRecorder();
    await servedAssets.recordPage(page);
    independentRequest = await request.newContext();
    await gotoWithServedAssetDrain(page, origin, { waitUntil: 'domcontentloaded' });
    const requestBrowserProbeScript = async () => {
      const browserResponsePromise = page.waitForResponse((response) => response.url() === probeUrl);
      await page.evaluate((url) => {
        const script = document.createElement('script');
        script.src = url;
        document.head.append(script);
      }, probeUrl);
      const browserResponse = await browserResponsePromise;
      expect(browserResponse.status()).toBe(200);
    };
    await requestBrowserProbeScript();
    await gotoWithServedAssetDrain(page, new URL('/after-capture', origin).toString(), {
      waitUntil: 'domcontentloaded',
    });
    await goBackWithServedAssetDrain(page);
    await requestBrowserProbeScript();
    await goForwardWithServedAssetDrain(page);
    const independentResponse = await independentRequest.get(probeUrl + '?independent=1');
    const independentHash = crypto.createHash('sha256').update(await independentResponse.body()).digest('hex');
    expect(independentHash).not.toBe(browserHash);
    await context.close();
    context = undefined;
    const records = await servedAssets.reportForOrigin(origin);
    expect(records).toContainEqual({ path: probePath, sha256: browserHash });
  } finally {
    await independentRequest?.dispose();
    await context?.close();
    await new Promise<void>((resolve, reject) => {
      server.close((error) => error ? reject(error) : resolve());
    });
  }
});

test('RQ-18 provenance accepts only canceled assets from a committed superseded main-frame loader', () => {
  const oldMainFrameLoader = {
    frameId: 'main-frame',
    loaderId: 'old-loader',
    hadMatchingHash: true,
  };
  const committedNavigation = {
    mainFrameId: 'main-frame',
    mainFrameLoaderId: 'new-loader',
    supersededMainLoaderIds: new Set(['old-loader']),
  };

  expect(isCdpNavigationAbortCandidate(
    { errorText: 'net::ERR_ABORTED', canceled: true },
    oldMainFrameLoader,
    'main-frame',
  )).toBe(true);
  expect(isVerifiedSupersededMainFrameAbort(oldMainFrameLoader, committedNavigation)).toBe(true);
  expect(isVerifiedSupersededMainFrameAbort(oldMainFrameLoader, {
    ...committedNavigation,
    mainFrameLoaderId: 'old-loader',
  })).toBe(false);
  expect(isVerifiedSupersededMainFrameAbort(oldMainFrameLoader, {
    ...committedNavigation,
    supersededMainLoaderIds: new Set<string>(),
  })).toBe(false);
  expect(isVerifiedSupersededMainFrameAbort({ ...oldMainFrameLoader, hadMatchingHash: false }, committedNavigation)).toBe(false);
  expect(isVerifiedSupersededMainFrameAbort({ ...oldMainFrameLoader, frameId: 'child-frame' }, committedNavigation)).toBe(false);
  expect(isCdpNavigationAbortCandidate(
    { errorText: 'net::ERR_ABORTED', canceled: false },
    oldMainFrameLoader,
    'main-frame',
  )).toBe(false);
  expect(isCdpNavigationAbortCandidate(
    { errorText: 'net::ERR_FAILED', canceled: true },
    oldMainFrameLoader,
    'main-frame',
  )).toBe(false);
});

test('RQ-18 provenance reports a failed duplicate asset even when another page captured its hash', async ({ browser, browserName }) => {
  test.skip(browserName !== 'chromium', 'RQ-18 duplicate asset failure regression uses Chromium CDP request events.');
  test.setTimeout(30_000);
  const cssPath = `/assets/rq18-duplicate-failure-${suffixKey}.css`;
  const cssBody = ':root { --rq18-asset-probe: 1; }';
  const server = createServer((incoming, outgoing) => {
    if (incoming.url === '/with-css') {
      outgoing.statusCode = 200;
      outgoing.setHeader('content-type', 'text/html; charset=utf-8');
      outgoing.end(`<!doctype html><html><head><link rel="stylesheet" href="${cssPath}"></head><body></body></html>`);
      return;
    }
    if (incoming.url === cssPath) {
      outgoing.statusCode = 200;
      outgoing.setHeader('content-type', 'text/css; charset=utf-8');
      outgoing.setHeader('cache-control', 'no-store');
      outgoing.end(cssBody);
      return;
    }
    outgoing.statusCode = 404;
    outgoing.end();
  });
  await new Promise<void>((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolve);
  });
  const address = server.address();
  if (!address || typeof address === 'string') {
    await new Promise<void>((resolve) => server.close(() => resolve()));
    throw new Error('Could not start local duplicate-asset regression server.');
  }

  const origin = `http://127.0.0.1:${address.port}`;
  const cssUrl = new URL(cssPath, origin).toString();
  const contexts: BrowserContext[] = [];
  const newTrackedPage = async (servedAssets: ReturnType<typeof createServedAssetRecorder>) => {
    const context = await browser.newContext({ serviceWorkers: 'block' });
    contexts.push(context);
    const page = await context.newPage();
    await servedAssets.recordPage(page);
    return page;
  };
  const captureCss = async (servedAssets: ReturnType<typeof createServedAssetRecorder>) => {
    const page = await newTrackedPage(servedAssets);
    await page.goto(new URL('/with-css', origin).toString(), { waitUntil: 'load' });
    await servedAssets.waitForPage(page);
    const records = await servedAssets.reportForOrigin(origin);
    expect(records).toContainEqual({
      path: cssPath,
      sha256: crypto.createHash('sha256').update(cssBody).digest('hex'),
    });
    return page;
  };

  try {
    const activeAbortRecorder = createServedAssetRecorder();
    await captureCss(activeAbortRecorder);
    const activeAbortPage = await newTrackedPage(activeAbortRecorder);
    await activeAbortPage.route(cssUrl, (route) => route.abort('aborted'));
    const activeAbortPromise = activeAbortPage.waitForEvent(
      'requestfailed',
      (browserRequest) => browserRequest.url() === cssUrl,
    );
    await activeAbortPage.goto(new URL('/with-css', origin).toString(), { waitUntil: 'domcontentloaded' });
    const activeAbort = await activeAbortPromise;
    expect(activeAbort.failure()?.errorText).toBe('net::ERR_ABORTED');
    await activeAbortRecorder.waitForPage(activeAbortPage);
    await expect(activeAbortRecorder.reportForOrigin(origin)).rejects.toThrow(`${cssPath}:request-failed`);

    const genuineFailureRecorder = createServedAssetRecorder();
    await captureCss(genuineFailureRecorder);
    const failedPage = await newTrackedPage(genuineFailureRecorder);
    await failedPage.route(cssUrl, (route) => route.abort('failed'));
    const failedRequestPromise = failedPage.waitForEvent(
      'requestfailed',
      (browserRequest) => browserRequest.url() === cssUrl,
    );
    await failedPage.goto(new URL('/with-css', origin).toString(), { waitUntil: 'domcontentloaded' });
    const failedRequest = await failedRequestPromise;
    expect(failedRequest.failure()?.errorText).toBeTruthy();
    expect(failedRequest.failure()?.errorText).not.toBe('net::ERR_ABORTED');
    await genuineFailureRecorder.waitForPage(failedPage);
    await expect(genuineFailureRecorder.reportForOrigin(origin)).rejects.toThrow(`${cssPath}:request-failed`);
  } finally {
    await Promise.all(contexts.map((context) => context.close().catch(() => undefined)));
    await new Promise<void>((resolve, reject) => {
      server.close((error) => error ? reject(error) : resolve());
    });
  }
});

test('RQ-18 provenance accepts a duplicate script canceled by a committed browser navigation', async ({ browser, browserName }) => {
  test.skip(browserName !== 'chromium', 'RQ-18 navigation-cancellation regression requires Chromium CDP loader evidence.');
  test.setTimeout(30_000);
  const scriptPath = `/assets/rq18-navigation-abort-${suffixKey}.js`;
  const scriptBody = 'window.__rq18NavigationAbortProbe = true;';
  let scriptRequestCount = 0;
  let signalSecondScriptRequest = () => {};
  const secondScriptRequestStarted = new Promise<void>((resolve) => { signalSecondScriptRequest = resolve; });
  let signalSecondScriptConnectionClosed = () => {};
  const secondScriptConnectionClosed = new Promise<void>((resolve) => { signalSecondScriptConnectionClosed = resolve; });
  let secondScriptClosedWithoutResponse = false;
  const server = createServer((incoming, outgoing) => {
    if (incoming.url === '/with-script' || incoming.url === '/with-script-then-navigate') {
      outgoing.statusCode = 200;
      outgoing.setHeader('content-type', 'text/html; charset=utf-8');
      const scheduledNavigation = incoming.url === '/with-script-then-navigate'
        ? '<script>setTimeout(() => window.location.assign("/next"), 250);</script>'
        : '';
      outgoing.end(`<!doctype html><html><head>${scheduledNavigation}<script src="${scriptPath}"></script></head><body>old page</body></html>`);
      return;
    }
    if (incoming.url === '/next') {
      outgoing.statusCode = 200;
      outgoing.setHeader('content-type', 'text/html; charset=utf-8');
      outgoing.end('<!doctype html><html><head></head><body>committed destination</body></html>');
      return;
    }
    if (incoming.url === scriptPath) {
      scriptRequestCount += 1;
      outgoing.statusCode = 200;
      outgoing.setHeader('content-type', 'text/javascript; charset=utf-8');
      outgoing.setHeader('cache-control', 'no-store');
      if (scriptRequestCount === 1) {
        outgoing.end(scriptBody);
      } else if (scriptRequestCount === 2) {
        // Keep the duplicate response genuinely in flight. The browser, not
        // a Playwright route abort, must cancel it when /next commits.
        signalSecondScriptRequest();
        outgoing.once('close', () => {
          secondScriptClosedWithoutResponse = !outgoing.writableEnded;
          signalSecondScriptConnectionClosed();
        });
      } else {
        outgoing.end(scriptBody);
      }
      return;
    }
    outgoing.statusCode = 404;
    outgoing.end();
  });
  await new Promise<void>((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolve);
  });
  const address = server.address();
  if (!address || typeof address === 'string') {
    await new Promise<void>((resolve) => server.close(() => resolve()));
    throw new Error('Could not start local navigation-abort regression server.');
  }

  const origin = `http://127.0.0.1:${address.port}`;
  const oldPageUrl = new URL('/with-script', origin).toString();
  const navigatingPageUrl = new URL('/with-script-then-navigate', origin).toString();
  const nextPageUrl = new URL('/next', origin).toString();
  const contexts: BrowserContext[] = [];
  const recorder = createServedAssetRecorder();
  const newTrackedPage = async () => {
    const context = await browser.newContext({ serviceWorkers: 'block' });
    contexts.push(context);
    const page = await context.newPage();
    await recorder.recordPage(page);
    return page;
  };

  try {
    const completedPage = await newTrackedPage();
    await completedPage.goto(oldPageUrl, { waitUntil: 'load' });
    await recorder.waitForPage(completedPage);
    const priorRecords = await recorder.reportForOrigin(origin);
    expect(priorRecords).toContainEqual({
      path: scriptPath,
      sha256: crypto.createHash('sha256').update(scriptBody).digest('hex'),
    });

    const navigatingPage = await newTrackedPage();
    const browserAssetFailure = navigatingPage.waitForEvent('requestfailed', (request) => {
      return request.url() === new URL(scriptPath, origin).toString();
    });
    const destinationNavigation = navigatingPage.waitForEvent(
      'framenavigated',
      (frame) => frame === navigatingPage.mainFrame() && frame.url() === nextPageUrl,
    );
    await navigatingPage.goto(navigatingPageUrl, { waitUntil: 'commit' });
    await secondScriptRequestStarted;
    await destinationNavigation;
    expect(navigatingPage.url()).toBe(nextPageUrl);
    await expect(navigatingPage.locator('body')).toHaveText('committed destination');
    const failedAssetRequest = await browserAssetFailure;
    expect(failedAssetRequest.failure()?.errorText).toBe('net::ERR_ABORTED');
    await secondScriptConnectionClosed;
    expect(scriptRequestCount).toBe(2);
    expect(secondScriptClosedWithoutResponse).toBe(true);
    await recorder.waitForPage(navigatingPage);
    const records = await recorder.reportForOrigin(origin);
    expect(records).toContainEqual({
      path: scriptPath,
      sha256: crypto.createHash('sha256').update(scriptBody).digest('hex'),
    });
  } finally {
    await Promise.all(contexts.map((context) => context.close().catch(() => undefined)));
    await new Promise<void>((resolve, reject) => {
      server.close((error) => error ? reject(error) : resolve());
    });
  }
});

test('RQ-18 provenance timeout reports safe capture counters', async ({ browser, browserName }) => {
  test.skip(browserName !== 'chromium', 'RQ-18 timeout diagnostics regression uses Chromium request routing.');
  test.setTimeout(30_000);
  const cssPath = `/assets/rq18-timeout-diagnostics-${suffixKey}.css`;
  const server = createServer((_incoming, outgoing) => {
    outgoing.statusCode = 200;
    outgoing.setHeader('content-type', 'text/html; charset=utf-8');
    outgoing.end('<!doctype html><html><head></head><body></body></html>');
  });
  await new Promise<void>((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolve);
  });
  const address = server.address();
  if (!address || typeof address === 'string') {
    await new Promise<void>((resolve) => server.close(() => resolve()));
    throw new Error('Could not start local timeout-diagnostics regression server.');
  }

  const origin = `http://127.0.0.1:${address.port}`;
  const cssUrl = new URL(cssPath, origin).toString();
  let releaseHeldRoute = () => {};
  const heldRoute = new Promise<void>((resolve) => { releaseHeldRoute = resolve; });
  let routeIntercepted = () => {};
  const intercepted = new Promise<void>((resolve) => { routeIntercepted = resolve; });
  let context: BrowserContext | undefined;

  try {
    context = await browser.newContext({ serviceWorkers: 'block' });
    const page = await context.newPage();
    const servedAssets = createServedAssetRecorder({ drainTimeoutMs: 100 });
    await servedAssets.recordPage(page);
    await page.route(cssUrl, async (route) => {
      routeIntercepted();
      await heldRoute;
      await route.abort('aborted').catch(() => undefined);
    });
    await page.goto(origin, { waitUntil: 'domcontentloaded' });
    const requestStarted = page.waitForEvent('request', (browserRequest) => browserRequest.url() === cssUrl);
    await page.evaluate((url) => {
      const stylesheet = document.createElement('link');
      stylesheet.rel = 'stylesheet';
      stylesheet.href = url;
      document.head.append(stylesheet);
    }, cssUrl);
    await requestStarted;
    await intercepted;
    const expectedPathHash = crypto.createHash('sha256').update(cssPath).digest('hex').slice(0, 16);
    await expect(servedAssets.waitForPage(page)).rejects.toThrow(
      new RegExp('Timed out waiting for browser-served asset bodies to settle '
        + '\\(active=1 cdp=\\d+ pendingCaptures=\\d+ bodyReadStarted=\\d+'
        + ' bodyReadCompleted=\\d+ bodyReadFailed=\\d+'
        + ' pendingPathHashes=' + expectedPathHash + '\\)\\.'),
    );
  } finally {
    releaseHeldRoute();
    await context?.close().catch(() => undefined);
    await new Promise<void>((resolve, reject) => {
      server.close((error) => error ? reject(error) : resolve());
    });
  }
});

test('RQ-18: current permanent QR booking and archive/reactivation lifecycle', async ({ browser, page }) => {
  test.setTimeout(600_000);
  page.setDefaultTimeout(30_000);
  page.setDefaultNavigationTimeout(30_000);
  const servedAssets = createServedAssetRecorder();
  await servedAssets.recordPage(page);
  let pageErrors = 0;
  page.on('pageerror', () => { pageErrors += 1; });
  markRq18Phase('admin-login');
  await loginAdminWithRequiredTwoFactor(page);
  await verifyT18SpecialistsNavigation(page);
  markRq18Phase('admin-setup-page');
  await gotoWithServedAssetDrain(page, '/admin/setup-directions');
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

  await reloadWithServedAssetDrain(page);
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
  const booking = await openPublicAddress(browser, appOrigin, publicCode, servedAssets);
  try {
    if (booking.status !== 200 || booking.startCount.value !== 1) {
      throw new Error(
        'Available permanent QR did not open exactly one anonymous short session '
        + '(HTTP status ' + booking.status + '; start-session POST count ' + booking.startCount.value + ').',
      );
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
    try {
      await servedAssets.waitForPage(booking.page);
    } finally {
      await booking.context.close().catch(() => undefined);
    }
  }

  markRq18Phase('reopen-permanent-address');
  const reopen = await openPublicAddress(browser, appOrigin, publicCode, servedAssets);
  try {
    if (reopen.status !== 200 || reopen.startCount.value !== 1) {
      throw new Error('Reopening the permanent QR did not create one fresh short session.');
    }
    await waitForPublicForm(reopen.page);
  } finally {
    try {
      await servedAssets.waitForPage(reopen.page);
    } finally {
      await reopen.context.close().catch(() => undefined);
    }
  }

  markRq18Phase('deactivate-resource-preserving-current-queue');
  await gotoWithServedAssetDrain(page, '/admin/setup-directions?section=resources');
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

  const archived = await openPublicAddress(browser, appOrigin, publicCode, servedAssets);
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
    try {
      await servedAssets.waitForPage(archived.page);
    } finally {
      await archived.context.close().catch(() => undefined);
    }
  }

  markRq18Phase('reactivate-resource');
  await gotoWithServedAssetDrain(page, '/admin/setup-directions?section=resources');
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

  const reactivated = await openPublicAddress(browser, appOrigin, publicCode, servedAssets);
  try {
    if (reactivated.status !== 200 || reactivated.startCount.value !== 1) {
      throw new Error('Reactivated permanent QR did not open a fresh anonymous short session.');
    }
    await waitForPublicForm(reactivated.page);
  } finally {
    try {
      await servedAssets.waitForPage(reactivated.page);
    } finally {
      await reactivated.context.close().catch(() => undefined);
    }
  }

  markRq18Phase('completed');
  if (pageErrors !== 0) throw new Error('Unexpected uncaught Admin browser errors were observed.');
  await servedAssets.reportForOrigin(appOrigin);
});
