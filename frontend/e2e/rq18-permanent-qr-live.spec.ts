/**
 * RQ-18 — S-15 e2e: постоянный QR направления из setup-flow (REAL_API).
 *
 * ACCEPTANCE.md S-15: «Сохраненное направление D-01 и QR-тип D-03, затем
 * отключенный/архивный вариант → Получить QR из настройки, открыть ссылку
 * в отдельном браузере, выбрать услугу, записаться → Ссылка ведет к
 * правильному владельцу/составу; тип/срок правдивы; после archive нельзя
 * незаметно записаться; постоянный адрес не отменяет короткие сессии».
 *
 * Поток (directive §15):
 *  1. Admin /admin/setup-directions → собирает SYNTHETIC resource-owned
 *     направление (профиль + doctorless-услуга + ACTIVE QueueResource —
 *     путь RQ-17 e2e).
 *  2. Admin создаёт permanent QR в чек-листе (idempotent re-provision
 *     восстанавливает ТОТ ЖЕ код), скачивает PNG, копирует ссылку.
 *  3. ОТДЕЛЬНЫЙ anonymous browser context открывает /q/<code>:
 *     РОВНО ОДИН public start-session → существующий QueueJoin flow →
 *     form → complete → запись в canonical очереди.
 *  4. Archive (деактивация ресурса): та же ссылка больше НЕ записывает —
 *     единый анонимный отказ без внутренних причин.
 *  5. Reactivate: ТОТ ЖЕ адрес снова работает (E-055 §7).
 *
 * Запуск: реальный стек (vite dev + backend + БД с админом);
 * креды — QA_ADMIN_USERNAME / QA_ADMIN_PASSWORD (прецедент rq17 spec).
 */
import { test, expect, type Page } from '@playwright/test';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

function totpCode(secret: string, atMs = Date.now()): string {
  // RFC 6238 TOTP (SHA-1, 6 digits, 30s) with an explicit base32 decode —
  // Node has no native base32 and Buffer.from(s, 'base32') is invalid.
  const decodeBase32 = (s: string): Buffer => {
    const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
    let bits = '';
    for (const ch of s.replace(/=+$/, '').toUpperCase()) {
      const idx = alphabet.indexOf(ch);
      if (idx < 0) continue;
      bits += idx.toString(2).padStart(5, '0');
    }
    const bytes: number[] = [];
    for (let i = 0; i + 8 <= bits.length; i += 8) {
      bytes.push(parseInt(bits.slice(i, i + 8), 2));
    }
    return Buffer.from(bytes);
  };
  const counter = Math.floor(atMs / 1000 / 30);
  const buf = Buffer.alloc(8);
  buf.writeBigUInt64BE(BigInt(counter));
  const hmac = crypto.createHmac('sha1', decodeBase32(secret)).update(buf).digest();
  const offset = hmac[hmac.length - 1] & 0x0f;
  const code = ((hmac[offset] & 0x7f) << 24) | (hmac[offset + 1] << 16) | (hmac[offset + 2] << 8) | hmac[offset + 3];
  return String(code % 1_000_000).padStart(6, '0');
}

const ADMIN_USERNAME = process.env.QA_ADMIN_USERNAME || 'admin';
const artifactsDir = path.join(process.cwd(), '..', 'output', 'playwright');

function requiredAdminPassword() {
  const password = process.env.QA_ADMIN_PASSWORD;
  if (!password) {
    throw new Error('Set QA_ADMIN_PASSWORD to run RQ-18 S-15 e2e tests.');
  }
  return password;
}

const suffix = process.env.QA_SUFFIX || String(Date.now()).slice(-6);
// The QueueProfile key field pattern is [a-z_]+ — map digits to letters.
const suffixKey = suffix.split('').map((d) => 'abcdefghij'[Number(d)] || 'k').join('');
// NOTE: the key pattern is [a-z_]+ — the prefix must be letters-only too.
const resourceTag = `rqqrdir${suffixKey}`;
const profileKey = `rqqrdir${suffixKey}`;
const profileTitle = `RQ-18 направление ${suffix}`;
const serviceName = `RQ-18 услуга ${suffix}`;
const patientName = 'Тест Пациент RQ-18';
const patientPhone = '+998 (90) 000-11-22';

if (!fs.existsSync(artifactsDir)) {
  fs.mkdirSync(artifactsDir, { recursive: true });
}

test.describe.configure({ mode: 'serial' });

let publicCode = '';

/** Counts public start-session requests through ANY page in the test. */
function trackStartSessions(context: { on: Page['on'] }, counter: { n: number }) {
  context.on('request', (request) => {
    if (request.url().includes('/start-session')) {
      counter.n += 1;
    }
  });
}

/** Builds the resource-owned direction via the RQ-17 setup surfaces
 * (mirrors the proven rq17-setup-directions-live.spec.ts flow). */
async function buildDirection(page: Page) {
  // 0) wizard opens; resource axis starts WITHOUT a tag (deferred start)
  await page.goto('/admin/setup-directions');
  await page.waitForLoadState('networkidle');
  await page.getByTestId('setup-wizard-open').click();
  await expect(page.getByTestId('setup-wizard')).toBeVisible();
  await page.getByTestId('setup-wizard-axis-resource').click();

  // 1) profile with a NEW tag (QR-visible by default)
  await page.getByTestId('setup-wizard-services-next').click();
  await page.getByRole('link', { name: /профил|profiles/i }).first().click();
  await expect(page).toHaveURL(/\/admin\/services/);
  await page.getByRole('button', { name: /Добавить|Создать/i }).first().click();
  const modal = page.locator('.admin-qp-modal');
  await expect(modal).toBeVisible();
  await modal.locator('input').first().fill(profileKey);
  await modal.locator('input').nth(1).fill(profileTitle);
  await modal.locator('input').nth(2).fill(profileTitle);
  await modal.locator('input').nth(3).fill(resourceTag);
  await modal.getByRole('button', { name: /Сохранить|Создать/i }).first().click();
  await expect(page.getByText(profileTitle).first()).toBeVisible({ timeout: 15000 });

  // 2) back: the created tag is selectable in the axis selector
  await page.goto('/admin/setup-directions');
  await page.waitForLoadState('networkidle');
  await page.getByTestId('setup-wizard-open').click();
  await page.getByTestId('setup-wizard-tag-select').click();
  // the wizard listbox re-anchors on parent re-renders and the option may
  // fall off-viewport — click via DOM (React onClick still fires)
  await page
    .getByRole('option', { name: resourceTag })
    .first()
    .evaluate((el) => (el as HTMLElement).click());
  await page.getByTestId('setup-wizard-axis-resource').click();
  await page.getByRole('link', { name: /Услуги|Services/i }).first().click();
  await expect(page).toHaveURL(/\/admin\/services/);

  // 3) doctorless service of the new tag (the form is tabbed: Основное/Очередь)
  await page.getByRole('heading', { name: 'Справочник услуг' }).waitFor();
  await page.getByRole('button', { name: 'Добавить услугу' }).first().click();
  const form = page.locator('form').last();
  await form.locator('input[type="text"]').first().fill(serviceName);
  // category = custom Select (RQ-06.b contract): trigger is a
  // button[aria-haspopup="listbox"], NOT a native <select>/combobox role
  await form.locator('button[aria-haspopup="listbox"]').first().click();
  await page.getByRole('option').nth(1).click();
  await page.waitForTimeout(700);
  // the category determines the code-prefix group; the code input has
  // maxLength=3 — provisional fill triggers the mismatch hint that names
  // the ALLOWED prefix («Допустимо: D»), then refill + verify
  await form.getByPlaceholder('K01').fill('ZZ9');
  await page.waitForTimeout(500);
  const formText0 = (await form.textContent()) || '';
  const allowed = formText0.match(/Допустимо:\s*([A-ZА-ЯЁa-zа-яё])/)?.[1];
  const serviceCode = `${allowed || 'T'}${suffix.slice(-2)}`;
  await form.getByPlaceholder('K01').fill(serviceCode);
  await page.waitForTimeout(300);
  const codeNow = await form.getByPlaceholder('K01').inputValue();
  console.log('SERVICE CODE set to:', codeNow, '(expected', serviceCode + ')');
  if (codeNow !== serviceCode) {
    throw new Error(`service code input mismatch: ${codeNow} != ${serviceCode}`);
  }
  await form.locator('input[type="number"]').first().fill('15000');
  await form.locator('input[type="number"]').nth(1).fill('20');
  await page.getByRole('button', { name: 'Очередь' }).first().click();
  await form.locator('button[aria-haspopup="listbox"]').last().click();
  // the queue-tag Select renders PROFILE TITLES as option labels
  await page.getByRole('option', { name: profileTitle }).first().click();
  await form.getByRole('button', { name: 'Сохранить' }).click();
  try {
    await expect(page.getByText(/Услуга создана|услуга успешно/i).first()).toBeVisible({ timeout: 15000 });
  } catch (e) {
    // dump the Основное tab state: category/code values + inline errors
    await page.getByRole('button', { name: 'Основное' }).first().click().catch(() => {});
    await page.waitForTimeout(800);
    const formText = (await form.textContent()) || '';
    console.log('SAVE-FAIL form text:', formText.replace(/\s+/g, ' ').slice(0, 700));
    const codeVal = await form.getByPlaceholder('K01').inputValue().catch(() => 'n/a');
    console.log('SAVE-FAIL code value:', codeVal);
    await page.screenshot({ path: path.join(artifactsDir, 'rq18-save-fail.png'), fullPage: true });
    throw e;
  }

  // 4) draft QueueResource + activation through the §3.1 gate
  await page.goto('/admin/setup-directions');
  await page.waitForLoadState('networkidle');
  await page.getByTestId('setup-view-resources').click();
  await page.getByText('Загрузка реестра').waitFor({ state: 'hidden', timeout: 25000 }).catch(() => {});
  await page.getByTestId('qr-resource-create-toggle').click();
  const tagSelect = page.getByTestId('qr-resource-tag-select');
  await tagSelect.click();
  await page
    .getByRole('option', { name: resourceTag })
    .first()
    .evaluate((el) => (el as HTMLElement).click());
  await page.getByTestId('qr-resource-display-name-input').fill(`Ресурс ${resourceTag}`);
  await page.getByTestId('qr-resource-submit').click();
  const draftRow = page
    .locator('[data-testid^="qr-resource-row-"]')
    .filter({ hasText: resourceTag });
  await expect(draftRow).toBeVisible({ timeout: 15000 });
  await draftRow.locator('[data-testid^="qr-resource-toggle-"]').click();
  await expect(draftRow.getByTestId('qr-resource-badge-active')).toBeVisible({ timeout: 15000 });
}

async function login(page: Page) {
  await page.goto('/login');
  await page
    .locator('input[name="username"], input[aria-label*="мя пользователя"]')
    .first()
    .fill(ADMIN_USERNAME);
  await page.locator('input[type="password"]').first().fill(requiredAdminPassword());
  await page.getByRole('button', { name: /войти/i }).first().click();
  // Admin = critical role: the stack enforces TOTP 2FA (verify step). The
  // e2e seeds a known secret and computes live codes.
  const secret = process.env.QA_TOTP_SECRET;
  // NOTE: isVisible() does NOT wait — waitFor is required here (the 2FA
  // screen renders after the login POST completes).
  const twoFaInput = page.locator('input[autocomplete="one-time-code"], input[inputmode="numeric"], input[name="twoFactorCode"]').first();
  await twoFaInput.waitFor({ state: 'visible', timeout: 12000 }).catch(() => {});
  const twoFaVisible = await twoFaInput.isVisible().catch(() => false);
  if (twoFaVisible) {
    if (!secret) throw new Error('QA_TOTP_SECRET required for the admin 2FA step');
    // TOTP windows: a code generated right at a 30s boundary can be
    // rejected — retry with FRESH codes (same practice as QA runners).
    for (let attempt = 0; attempt < 4; attempt++) {
      await twoFaInput.fill(totpCode(secret));
      await page.getByRole('button', { name: /подтверд/i }).first().click();
      await page.waitForTimeout(2500);
      const stillOn2fa = await twoFaInput.isVisible().catch(() => false);
      if (!stillOn2fa) break;
    }
  }
  await page.waitForLoadState('networkidle');
  for (let i = 0; i < 10; i++) {
    if (!page.url().includes('/login')) return;
    await page.waitForTimeout(1000);
  }
  throw new Error(
    `Login did not complete; still on ${page.url()}; ` +
    `inputs=${await page.locator('input').count()}; ` +
    `body=${(await page.locator('body').textContent())?.slice(0, 200)}`,
  );
}

test.beforeEach(async ({ page }) => {
  await login(page);
});

test('S-15 admin: setup → permanent QR provision → same code on re-provision → PNG download + copy', async ({ page }) => {
  test.setTimeout(240_000);
  await buildDirection(page);

  // чек-лист: карточка направления несёт блок постоянного QR
  await page.getByTestId('setup-view-checklist').click();
  const row = page.getByTestId(`setup-checklist-row-${resourceTag}`);
  await expect(row).toBeVisible({ timeout: 15000 });
  const qrBlock = page.getByTestId(`setup-qr-block-${resourceTag}`);
  await expect(qrBlock).toBeVisible();

  // первый provision: created=true, URL /q/<12 кодов>
  await page.getByTestId(`setup-qr-provision-${resourceTag}`).click();
  const urlEl = page.getByTestId(`setup-qr-url-${resourceTag}`);
  await expect(urlEl).toBeVisible({ timeout: 15000 });
  const urlText = (await urlEl.textContent()) || '';
  expect(urlText).toMatch(/\/q\/[a-z0-9]{12}$/);
  publicCode = (urlText.match(/\/q\/([a-z0-9]{12})/) as RegExpMatchArray)[1];
  expect(page.getByTestId(`setup-qr-image-${resourceTag}`)).toBeVisible();

  // честность: без TTL-формулировок, с постоянной пометкой
  const blockText = (await qrBlock.textContent()) || '';
  expect(blockText).not.toMatch(/истек|действует до|expires|TTL/i);

  // повторный provision (reload-восстановление): ТОТ ЖЕ код
  await page.reload();
  await page.waitForLoadState('networkidle');
  const showBtn = page.getByTestId(`setup-qr-show-${resourceTag}`);
  await expect(showBtn).toBeVisible({ timeout: 15000 });
  await showBtn.click();
  const urlEl2 = page.getByTestId(`setup-qr-url-${resourceTag}`);
  await expect(urlEl2).toBeVisible({ timeout: 15000 });
  expect((await urlEl2.textContent()) || '').toContain(publicCode);

  // скачивание PNG (адрес без PII, имя файла из opaque-кода)
  const [download] = await Promise.all([
    page.waitForEvent('download', { timeout: 15000 }),
    page.getByTestId(`setup-qr-download-${resourceTag}`).click(),
  ]);
  expect(download.suggestedFilename()).toBe(`qr-direction-${publicCode}.png`);

  // копирование ссылки
  await page.getByTestId(`setup-qr-copy-${resourceTag}`).click();

  await page.screenshot({
    path: path.join(artifactsDir, 'rq18-s15-admin-qr.png'),
    fullPage: true,
  });
  fs.writeFileSync(
    path.join(artifactsDir, 'rq18-s15-ids.json'),
    JSON.stringify({ suffix, resourceTag, profileKey, publicCode }, null, 2),
    'utf8',
  );
});

test('S-15 patient: /q/<code> in a SEPARATE browser context — ONE start-session, existing QueueJoin completes', async ({ browser }) => {
  test.setTimeout(180_000);
  expect(publicCode, 'admin test must provision the code first').toBeTruthy();

  const context = await browser.newContext(); // отдельный анонимный клиент
  const page = await context.newPage();
  const counter = { n: 0 };
  page.on('request', (request) => {
    if (request.url().includes('/start-session')) counter.n += 1;
  });

  await page.goto(`/q/${publicCode}`);
  // существующий QueueJoin state machine: info шаг (без выбора врачей —
  // завершение direction-сессии только typed profile choice)
  await expect(page.getByText(/в очереди/i)).toBeVisible({ timeout: 20000 });
  expect(counter.n).toBe(1); // РОВНО ОДИН start-session

  await page.getByRole('button', { name: /продолжить/i }).click();
  await page.getByLabel(/фио пациента/i).fill(patientName);
  await page.getByLabel(/номер телефона/i).fill(patientPhone);
  await page.getByRole('button', { name: /присоединиться/i }).click();
  // success screen: «Вы в очереди! №N» (existing QueueJoin result UI)
  await expect(page.getByText('Вы в очереди!')).toBeVisible({ timeout: 20000 });
  await expect(page.getByText(/Ваш номер в очереди/i)).toBeVisible();

  // повторное открытие той же ссылки — новая короткая сессия, снова можно
  await page.goto(`/q/${publicCode}`);
  await expect(page.getByText(/в очереди/i)).toBeVisible({ timeout: 20000 });
  expect(counter.n).toBe(2);

  await page.screenshot({
    path: path.join(artifactsDir, 'rq18-s15-patient-join.png'),
    fullPage: true,
  });
  await context.close();
});

test('S-15 archive: same /q/<code> refuses anonymously; reactivate — the SAME address works again', async ({ browser, page: adminPage }) => {
  test.setTimeout(180_000);
  expect(publicCode).toBeTruthy();

  // archive-нога: деактивация ACTIVE QueueResource (resource-ось снята)
  await adminPage.goto('/admin/setup-directions');
  await adminPage.waitForLoadState('networkidle');
  await adminPage.getByTestId('setup-view-resources').click();
  const ownRow = adminPage
    .locator('[data-testid^="qr-resource-row-"]')
    .filter({ hasText: resourceTag });
  await expect(ownRow.getByTestId('qr-resource-badge-active')).toBeVisible({ timeout: 15000 });
  await ownRow.locator('[data-testid^="qr-resource-toggle-"]').click();
  await expect(ownRow.getByTestId('qr-resource-badge-draft')).toBeVisible({ timeout: 15000 });

  // анонимный отказ: единый unavailable, без внутренних причин
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto(`/q/${publicCode}`);
  await expect(page.getByTestId('qj-direction-unavailable')).toBeVisible({ timeout: 20000 });
  const text = (await page.getByTestId('qj-direction-unavailable').textContent()) || '';
  expect(text).not.toMatch(new RegExp(resourceTag, 'i'));
  expect(text).not.toContain(publicCode);

  // reactivate: ТОТ ЖЕ адрес снова работает (E-055 §7)
  await adminPage.getByTestId('setup-view-resources').click();
  const ownRow2 = adminPage
    .locator('[data-testid^="qr-resource-row-"]')
    .filter({ hasText: resourceTag });
  await expect(ownRow2.getByTestId('qr-resource-badge-draft')).toBeVisible({ timeout: 15000 });
  await ownRow2.locator('[data-testid^="qr-resource-toggle-"]').click();
  await expect(ownRow2.getByTestId('qr-resource-badge-active')).toBeVisible({ timeout: 15000 });

  await page.goto(`/q/${publicCode}`);
  await expect(page.getByText(/в очереди/i)).toBeVisible({ timeout: 20000 });
  await context.close();
});
