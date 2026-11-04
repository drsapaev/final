/**
 * RQ-17 — T18 current Admin setup paths for Doctor and QueueResource owners.
 *
 * This spec follows the backend-facts screen and existing Admin editors. It
 * creates a canonical Doctor through User Management and a QueueResource
 * through the setup screen, then proves both directions remain hidden until
 * explicit publication and become ready/bookable in the public QR catalog.
 * All rows live only in the owned synthetic staging database and are removed
 * with that project.
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

type QueueProfileRow = {
  key?: string;
  name?: string;
  title?: string;
  title_ru?: string;
  queue_tags?: string[];
  is_active?: boolean;
  show_on_qr_page?: boolean;
};

type DoctorRow = {
  id: number;
  specialty: string;
};

type SpecialtyRow = {
  code: string;
  title_ru?: string;
  title_en?: string;
  title_uz?: string;
};

type DirectionTarget = {
  owner_type: 'doctor' | 'resource';
  owner_id: number;
  queue_tag: string;
  label: string;
  is_active: boolean;
  eligible_for_new_booking: boolean;
};

type DirectionRow = {
  profile: { key: string; show_on_qr_page: boolean };
  resolved_mode: 'booking' | 'overview' | 'unresolved';
  configuration_state: 'ready' | 'incomplete' | 'conflict' | 'unavailable';
  effective_availability: 'available' | 'unavailable' | 'conflict';
  public_availability: boolean;
  booking_targets: DirectionTarget[];
  allowed_next_actions: Array<{ kind: string; entity_key?: string | null }>;
};

type DirectionFacts = {
  directions: DirectionRow[];
};

function isGetResponseForPath(
  response: import('@playwright/test').Response,
  suffixPath: string,
) {
  return response.request().method() === 'GET'
    && new URL(response.url()).pathname.endsWith(suffixPath);
}

async function waitForAdminDirections(page: Page): Promise<DirectionFacts> {
  const responsePromise = page.waitForResponse((response) =>
    isGetResponseForPath(response, '/queue/admin/directions')
  );
  await page.goto('/admin/setup-directions');
  const response = await responsePromise;
  expect(response.ok(), 'Admin directions facts should load from the backend').toBeTruthy();
  return await response.json() as DirectionFacts;
}

function directionForKey(facts: DirectionFacts, key: string): DirectionRow {
  const direction = facts.directions.find((item) => item.profile.key === key);
  expect(direction, 'Admin read model should include the requested synthetic profile').toBeDefined();
  return direction!;
}

function queueProfileTitle(profile: QueueProfileRow): string {
  return profile.title_ru?.trim() || profile.title?.trim() || profile.name?.trim() || profile.key || '';
}

function expectDirectionState(
  direction: DirectionRow,
  expected: {
    key: string;
    ownerType: DirectionTarget['owner_type'];
    ownerId: number;
    queueTag: string;
    published: boolean;
  },
) {
  expect(direction.profile).toMatchObject({
    key: expected.key,
    show_on_qr_page: expected.published,
  });
  expect(direction.resolved_mode).toBe('booking');
  expect(direction.configuration_state).toBe(expected.published ? 'ready' : 'incomplete');
  expect(direction.effective_availability).toBe('available');
  expect(direction.public_availability).toBe(expected.published);
  expect(direction.booking_targets).toHaveLength(1);
  expect(direction.booking_targets[0]).toMatchObject({
    owner_type: expected.ownerType,
    owner_id: expected.ownerId,
    queue_tag: expected.queueTag,
    is_active: true,
    eligible_for_new_booking: true,
  });
  const publishAction = direction.allowed_next_actions.some(
    (action) => action.kind === 'publish_profile' && action.entity_key === expected.key,
  );
  expect(publishAction).toBe(!expected.published);
}

function expectDoctorDirectionState(
  direction: DirectionRow,
  expected: { key: string; ownerId: number; queueTag: string },
  published: boolean,
) {
  expect(direction.profile).toMatchObject({ key: expected.key, show_on_qr_page: published });
  expect(direction.resolved_mode).toBe('booking');
  expect(direction.effective_availability).toBe('available');
  expect(direction.booking_targets).toContainEqual(expect.objectContaining({
    owner_type: 'doctor',
    owner_id: expected.ownerId,
    queue_tag: expected.queueTag,
    is_active: true,
    eligible_for_new_booking: true,
  }));
  expect(direction.public_availability).toBe(published);
  expect(direction.configuration_state).toBe(published ? 'ready' : 'incomplete');
  const publishAction = direction.allowed_next_actions.some(
    (action) => action.kind === 'publish_profile' && action.entity_key === expected.key,
  );
  expect(publishAction).toBe(!published);
}

async function createHiddenQueueProfile(
  page: Page,
  input: { key: string; title: string; queueTag: string },
) {
  await page.goto('/admin/setup-directions');
  const links = page.getByTestId('setup-editor-links');
  await expect(links).toBeVisible();
  await links.locator('a[href*="servicesTab=queue-profiles"]').click();
  await expect(page).toHaveURL(/servicesTab=queue-profiles/);
  await page.getByRole('button', { name: /Добавить|Add/i }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  const profileKeyInput = dialog.locator('#queue-profile-key');
  await expect(profileKeyInput).toHaveAttribute('pattern', '[a-z_]+');
  expect(input.key).toMatch(/^[a-z_]+$/);
  await profileKeyInput.fill(input.key);
  await dialog.locator('#queue-profile-title-en').fill(input.title);
  await dialog.locator('#queue-profile-title-ru').fill(input.title);
  await dialog.locator('#queue-profile-tags').fill(input.queueTag);

  const createResponsePromise = page.waitForResponse((response) => {
    const pathname = new URL(response.url()).pathname;
    return response.request().method() === 'POST' && pathname.endsWith('/queues/profiles');
  });
  await dialog.getByRole('button', { name: /Создать вкладку очереди|Create queue tab/i }).click();
  const createResponse = await createResponsePromise;
  expect(createResponse.ok(), 'new QueueProfile should be created through the Admin editor').toBeTruthy();
  expect(createResponse.request().postDataJSON()).toMatchObject({ show_on_qr_page: false });
  await expect(dialog).toHaveCount(0);
  await expect(page.getByRole('row').filter({ hasText: input.title })).toHaveCount(1);
}

async function createCatalogService(
  page: Page,
  input: {
    name: string;
    profileKey: string;
    queueProfiles: QueueProfileRow[];
    queueTag: string;
    doctorSpecialty?: string;
    doctorId?: number;
  },
) {
  await page.getByRole('button', { name: /Добавить услугу|Add service/i }).first().click();
  const serviceEditor = page.getByRole('heading', { name: /Добавление услуги|Add service/i }).locator('..');
  const serviceForm = serviceEditor.locator('form').last();
  await expect(serviceForm).toBeVisible();
  await serviceForm.locator('input[type="text"]').first().fill(input.name);

  const categorySelect = serviceForm.locator('.mac-select').first().getByRole('button');
  await categorySelect.click();
  const categoryOptions = page.getByRole('listbox').getByRole('option');
  if (await categoryOptions.count() > 1) {
    await categoryOptions.nth(1).click();
  } else {
    await expect(categoryOptions).toHaveCount(1);
    await categoryOptions.first().click();
  }

  if (input.doctorId !== undefined && input.doctorSpecialty) {
    const doctorSelects = serviceForm.locator('.mac-select');
    await expect(doctorSelects).toHaveCount(3);
    await doctorSelects.nth(2).getByRole('button').click();
    const doctorOptions = page.getByRole('listbox').getByRole('option')
      .filter({ hasText: new RegExp('\\(' + input.doctorSpecialty + '\\)', 'i') });
    await expect(doctorOptions).toHaveCount(1);
    await doctorOptions.click();
  }

  await serviceEditor.getByRole('button', { name: /Очередь|Queue/i }).click();
  const queueTagSelect = serviceForm.locator('.mac-select').first().getByRole('button');
  await queueTagSelect.click();
  const activeProfiles = input.queueProfiles.filter((profile) => profile.is_active !== false);
  const selectedProfileIndex = activeProfiles.findIndex((profile) => profile.key === input.profileKey
    && (profile.queue_tags?.[0] || profile.key) === input.queueTag);
  expect(selectedProfileIndex, 'the chosen QueueProfile must map to the requested service queue tag').toBeGreaterThanOrEqual(0);
  const queueTagOptions = page.getByRole('listbox').getByRole('option');
  await expect(queueTagOptions).toHaveCount(activeProfiles.length + 1);
  await queueTagOptions.nth(selectedProfileIndex + 1).click();

  await serviceEditor.getByRole('button', { name: /Опции|Options/i }).click();
  const requiresDoctor = serviceForm.getByRole('checkbox', { name: /Требует врача|Doctor required/i });
  if (input.doctorId === undefined) {
    await expect(requiresDoctor).not.toBeChecked();
  } else {
    await requiresDoctor.click();
    await expect(requiresDoctor).toBeChecked();
  }

  const createResponsePromise = page.waitForResponse((response) => {
    const pathname = new URL(response.url()).pathname;
    return response.request().method() === 'POST' && /\/services\/?$/.test(pathname);
  });
  await serviceForm.getByRole('button', { name: /Сохранить услугу|Сохранить|Save service|Save/i }).click();
  const createResponse = await createResponsePromise;
  expect(createResponse.ok(), 'synthetic queue service should be created through the Service Catalog').toBeTruthy();
  expect(createResponse.request().postDataJSON()).toMatchObject({
    queue_tag: input.queueTag,
    doctor_id: input.doctorId ?? null,
    requires_doctor: input.doctorId !== undefined,
  });
  await expect(page.getByText(input.name).first()).toBeVisible();
}

async function publishQueueProfile(page: Page, key: string, title: string) {
  await page.goto('/admin/services?servicesTab=queue-profiles');
  const row = page.getByRole('row').filter({ hasText: title });
  await expect(row).toHaveCount(1);
  await row.getByRole('button', { name: /для настройки QR-публикации|to manage QR publication/i }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  const qrVisibility = dialog.getByRole('checkbox', {
    name: /Показывать профиль на QR-странице|Show profile on QR page/i,
  });
  await expect(qrVisibility).not.toBeChecked();
  await qrVisibility.click();
  await expect(qrVisibility).toBeChecked();

  const updateResponsePromise = page.waitForResponse((response) => {
    const pathname = new URL(response.url()).pathname;
    return response.request().method() === 'PUT' && pathname.endsWith('/queues/profiles/' + key);
  });
  await dialog.getByRole('button', { name: /Сохранить вкладку очереди|Сохранить|Save/i }).click();
  const updateResponse = await updateResponsePromise;
  expect(updateResponse.ok(), 'explicit QR publication should be saved through the QueueProfile editor').toBeTruthy();
  expect(updateResponse.request().postDataJSON()).toMatchObject({ show_on_qr_page: true });
  await expect(dialog).toHaveCount(0);
}

test('current setup screen resolves Doctor and QueueResource directions through explicit QR publication', async ({ page }) => {
  test.setTimeout(420_000);
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

  const initialFacts = await waitForAdminDirections(page);
  await expect(page.getByTestId('setup-directions-heading')).toBeVisible();
  const editorLinks = page.getByTestId('setup-editor-links');
  await expect(editorLinks).toBeVisible();
  await expect(page.locator('[data-testid^="setup-wizard-"]')).toHaveCount(0);
  await expect(editorLinks.locator('a[href*="servicesTab=queue-profiles"]')).toHaveCount(1);
  await expect(editorLinks.locator('a[href*="servicesTab=catalog"]')).toHaveCount(1);
  await expect(editorLinks.locator('a[href*="/admin/users"]')).toHaveCount(1);

  const resourceRouteTags = initialFacts.directions.flatMap((direction) =>
    direction.booking_targets
      .filter((target) => target.owner_type === 'resource')
      .map((target) => target.queue_tag.trim().toLowerCase()),
  );

  const profilesResponsePromise = page.waitForResponse((response) =>
    isGetResponseForPath(response, '/queues/profiles')
  );
  await editorLinks.locator('a[href*="servicesTab=queue-profiles"]').click();
  const profilesResponse = await profilesResponsePromise;
  expect(profilesResponse.ok(), 'existing QueueProfiles should be readable').toBeTruthy();
  const profilesPayload = await profilesResponse.json() as { profiles?: QueueProfileRow[] };
  const existingProfiles = profilesPayload.profiles || [];

  // The resource axis is configured through a QueueProfile with no Doctor.
  await createHiddenQueueProfile(page, { key: profileKey, title: profileTitle, queueTag: resourceTag });

  const doctorsResponsePromise = page.waitForResponse((response) =>
    isGetResponseForPath(response, '/services/admin/doctors')
  );
  await page.goto('/admin/services?servicesTab=catalog');
  const doctorsResponse = await doctorsResponsePromise;
  expect(doctorsResponse.ok(), 'existing Doctor owners should be readable').toBeTruthy();
  const existingDoctors = await doctorsResponse.json() as DoctorRow[];
  expect(Array.isArray(existingDoctors), 'Admin doctor picker should return a typed list').toBeTruthy();

  // Start canonical Doctor onboarding from the existing setup screen link.
  await page.goto('/admin/setup-directions');
  const userLink = page.getByTestId('setup-editor-links').locator('a[href*="/admin/users"]');
  await userLink.click();
  await expect(page.getByTestId('queue-setup-return-link')).toBeVisible();
  const addUserButton = page.getByRole('button', { name: /Добавить пользователя|Add user/i });
  const specialtiesResponsePromise = page.waitForResponse((response) =>
    isGetResponseForPath(response, '/admin/doctors/specialty-vocabulary')
  );
  await addUserButton.click();
  const specialtiesResponse = await specialtiesResponsePromise;
  expect(specialtiesResponse.ok(), 'canonical Doctor specialty vocabulary should load').toBeTruthy();
  const specialtyPayload = await specialtiesResponse.json() as SpecialtyRow[] | { items?: SpecialtyRow[] };
  const specialtyItems = (Array.isArray(specialtyPayload)
    ? specialtyPayload
    : specialtyPayload.items || []).filter((item) => Boolean(item?.code));
  const usedDoctorSpecialties = new Set(
    existingDoctors.map((doctor) => doctor.specialty.trim().toLowerCase()).filter(Boolean),
  );
  const doctorRouteCandidate = specialtyItems.flatMap((specialty) => {
    const specialtyCode = specialty.code.trim().toLowerCase();
    if (!specialtyCode || usedDoctorSpecialties.has(specialtyCode) || resourceRouteTags.includes(specialtyCode)) {
      return [];
    }
    const matchingProfiles = existingProfiles.filter((profile) =>
      profile.is_active !== false
      && typeof profile.show_on_qr_page === 'boolean'
      && (profile.queue_tags?.[0] || profile.key)?.trim().toLowerCase() === specialtyCode,
    );
    if (matchingProfiles.length !== 1) return [];
    const profile = matchingProfiles[0];
    const direction = initialFacts.directions.find((item) => item.profile.key === profile.key);
    if (!direction
      || direction.effective_availability !== 'available'
      || direction.configuration_state === 'conflict'
      || direction.booking_targets.length > 0) {
      return [];
    }
    return [{ specialty, profile }];
  })[0];
  const routeReadiness = doctorRouteCandidate ? [] : specialtyItems.map((specialty) => {
      const code = specialty.code.trim().toLowerCase();
      const profiles = existingProfiles
        .filter((profile) => (profile.queue_tags?.[0] || profile.key)?.trim().toLowerCase() === code)
        .map((profile) => {
          const direction = initialFacts.directions.find((item) => item.profile.key === profile.key);
          return {
            key: profile.key,
            active: profile.is_active !== false,
            published: profile.show_on_qr_page,
            state: direction?.configuration_state,
            availability: direction?.effective_availability,
            existingTargets: direction?.booking_targets.map((target) => `${target.owner_type}:${target.queue_tag}`) || [],
          };
        });
      return {
        code,
        doctorAlreadyExists: usedDoctorSpecialties.has(code),
        resourceAlreadyUsesTag: resourceRouteTags.includes(code),
        profiles,
      };
    }).filter((item) => !item.doctorAlreadyExists && !item.resourceAlreadyUsesTag).slice(0, 20);
  expect(
    doctorRouteCandidate,
    `synthetic staging needs one available QueueProfile route for a canonical Doctor specialty; route candidates: ${JSON.stringify(routeReadiness)}`,
  ).toBeDefined();
  const { specialty: doctorSpecialty, profile: doctorProfile } = doctorRouteCandidate!;
  const doctorProfileTitle = queueProfileTitle(doctorProfile);
  expect(doctorProfileTitle, 'selected QueueProfile should have a visible Admin label').not.toBe('');
  const doctorName = 'SYNTHETIC-RQ17 Doctor ' + suffix;
  const doctorUsername = 'synthetic_rq17_doc_' + suffix;
  const doctorEmail = 'synthetic.rq17.' + suffix + '@example.invalid';

  const userDialog = page.getByRole('dialog');
  await expect(userDialog).toBeVisible();
  await userDialog.locator('.mac-select-trigger').first().click();
  const doctorRole = page.getByRole('listbox').getByRole('option').filter({ hasText: /Врач|Doctor/i });
  await expect(doctorRole).toHaveCount(1);
  await doctorRole.click();
  const specialtyTrigger = userDialog.locator('#user-modal-doctor-specialty');
  await expect(specialtyTrigger).toBeVisible();
  await specialtyTrigger.click();
  const specialtyOptions = page.getByRole('listbox').getByRole('option');
  await expect(specialtyOptions).toHaveCount(specialtyItems.length + 1);
  const selectedSpecialtyIndex = specialtyItems.findIndex((item) => item.code === doctorSpecialty.code);
  expect(selectedSpecialtyIndex).toBeGreaterThanOrEqual(0);
  await specialtyOptions.nth(selectedSpecialtyIndex + 1).click();

  const textInputs = userDialog.locator('input[type="text"]');
  await textInputs.nth(0).fill(doctorUsername);
  await textInputs.nth(1).fill(doctorName);
  await userDialog.locator('input[type="email"]').fill(doctorEmail);
  const doctorPassword = 'Synthetic-' + crypto.randomBytes(24).toString('hex') + '!A1';
  await userDialog.locator('input[type="password"]').nth(0).fill(doctorPassword);
  await expect(userDialog.locator('input[type="password"]')).toHaveCount(2);
  await userDialog.locator('input[type="password"]').nth(1).fill(doctorPassword);
  const userCreateResponsePromise = page.waitForResponse((response) => {
    const pathname = new URL(response.url()).pathname;
    return response.request().method() === 'POST' && pathname.endsWith('/users/users');
  });
  await userDialog.getByRole('button', { name: 'Create user', exact: true }).click();
  const userCreateResponse = await userCreateResponsePromise;
  expect(userCreateResponse.ok(), 'Doctor should be created through normal User Management').toBeTruthy();
  expect(userCreateResponse.request().postDataJSON()).toMatchObject({
    username: doctorUsername,
    email: doctorEmail,
    full_name: doctorName,
    role: 'Doctor',
    doctor_profile: { specialty: doctorSpecialty.code },
  });
  await expect(userDialog).toHaveCount(0);
  await page.getByTestId('queue-setup-return-link').click();
  await expect(page.getByTestId('setup-directions-heading')).toBeVisible();

  const createdDoctorsResponsePromise = page.waitForResponse((response) =>
    isGetResponseForPath(response, '/services/admin/doctors')
  );
  const catalogProfilesResponsePromise = page.waitForResponse((response) =>
    isGetResponseForPath(response, '/queues/profiles')
  );
  await page.goto('/admin/services?servicesTab=catalog');
  const [createdDoctorsResponse, catalogProfilesResponse] = await Promise.all([
    createdDoctorsResponsePromise,
    catalogProfilesResponsePromise,
  ]);
  expect(createdDoctorsResponse.ok()).toBeTruthy();
  expect(catalogProfilesResponse.ok(), 'Service Catalog should load the current QueueProfile list').toBeTruthy();
  const doctors = await createdDoctorsResponse.json() as DoctorRow[];
  const catalogProfilePayload = await catalogProfilesResponse.json() as { profiles?: QueueProfileRow[] };
  const catalogQueueProfiles = catalogProfilePayload.profiles || [];
  const createdDoctorMatches = doctors.filter((doctor) => doctor.specialty === doctorSpecialty.code);
  expect(
    createdDoctorMatches,
    'the selected unused specialty should resolve to exactly the newly created Doctor',
  ).toHaveLength(1);
  const doctorId = createdDoctorMatches[0].id;

  await createCatalogService(page, {
    name: 'Synthetic RQ-17 Doctor service ' + suffix,
    profileKey: doctorProfile.key!,
    queueProfiles: catalogQueueProfiles,
    queueTag: doctorSpecialty.code,
    doctorSpecialty: doctorSpecialty.code,
    doctorId,
  });
  await createCatalogService(page, {
    name: serviceName,
    profileKey,
    queueProfiles: catalogQueueProfiles,
    queueTag: resourceTag,
  });

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

  const resourceId = Number(
    (await resourceRow.getAttribute('data-testid'))?.replace('qr-resource-row-', ''),
  );
  expect(Number.isInteger(resourceId) && resourceId > 0, 'QueueResource should have a persisted ID').toBeTruthy();

  // Before any test-controlled publication, the Doctor direction must resolve
  // to its Doctor target and the new resource profile must remain hidden.
  let facts = await waitForAdminDirections(page);
  const doctorPublishedBeforeSetup = doctorProfile.show_on_qr_page === true;
  expectDoctorDirectionState(directionForKey(facts, doctorProfile.key!), {
    key: doctorProfile.key!,
    ownerId: doctorId,
    queueTag: doctorSpecialty.code,
  }, doctorPublishedBeforeSetup);
  expectDirectionState(directionForKey(facts, profileKey), {
    key: profileKey,
    ownerType: 'resource',
    ownerId: resourceId,
    queueTag: resourceTag,
    published: false,
  });

  if (!doctorPublishedBeforeSetup) {
    await publishQueueProfile(page, doctorProfile.key!, doctorProfileTitle);
    facts = await waitForAdminDirections(page);
  }
  expectDoctorDirectionState(directionForKey(facts, doctorProfile.key!), {
    key: doctorProfile.key!,
    ownerId: doctorId,
    queueTag: doctorSpecialty.code,
  }, true);
  expectDirectionState(directionForKey(facts, profileKey), {
    key: profileKey,
    ownerType: 'resource',
    ownerId: resourceId,
    queueTag: resourceTag,
    published: false,
  });

  await publishQueueProfile(page, profileKey, profileTitle);
  facts = await waitForAdminDirections(page);
  expectDoctorDirectionState(directionForKey(facts, doctorProfile.key!), {
    key: doctorProfile.key!,
    ownerId: doctorId,
    queueTag: doctorSpecialty.code,
  }, true);
  expectDirectionState(directionForKey(facts, profileKey), {
    key: profileKey,
    ownerType: 'resource',
    ownerId: resourceId,
    queueTag: resourceTag,
    published: true,
  });

  const publicCatalogResponse = await page.context().request.get(
    new URL('/api/v1/queues/profiles/public', page.url()).toString(),
  );
  expect(publicCatalogResponse.ok(), 'public QR catalog should expose published profiles').toBeTruthy();
  const publicCatalog = await publicCatalogResponse.json() as {
    specialists?: Array<{ specialty?: string }>;
  };
  const publicProfileKeys = (publicCatalog.specialists || []).map((specialist) => specialist.specialty);
  expect(publicProfileKeys).toEqual(expect.arrayContaining([doctorProfile.key!, profileKey]));

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
