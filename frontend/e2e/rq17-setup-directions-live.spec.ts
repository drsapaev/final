/**
 * RQ-17 — S-14 e2e: собранный путь настройки направления (REAL_API).
 *
 * Brief `RQ17_SETUP_PATH_BRIEF.md` §5: «Admin browser + REAL_API. "Новый
 * врач/ресурс" читается буквально — e2e покрывает ОБЕ оси D-01».
 *
 * Ось doctor-owned: мастер S-14 ведёт врача в /admin/users (canonical
 * onboarding, атомарное User+Doctor) — «нет второго onboarding» фиксируется
 * тем, что внутри мастера НЕТ формы создания врача, только переход.
 * Ось resource-owned: полный путь НАЧИНАЕТСЯ С ЧИСТОГО SETUP SCREEN (S-14
 * «from empty form», round-3 owner-ревью P1): мастер ведёт в профиль с
 * новым тегом и doctorless-услугу через ссылки существующих экранов, тег
 * выбирается в селекторе оси после создания/возврата, затем draft
 * QueueResource и активация через gate §3.1; checklist пересчитывает
 * статусы из API.
 *
 * Негативные комбинации инварианта §3.1 (12 пинов) покрываются
 * интеграционными пинами контракта
 * (backend/tests/integration/test_rq17_owner_invariant.py), не e2e.
 *
 * Запуск: реальный стек (vite dev + backend + БД с админом);
 * креды — QA_ADMIN_USERNAME / QA_ADMIN_PASSWORD (прецедент
 * admin-navigation.spec.ts).
 */
import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const ADMIN_USERNAME = process.env.QA_ADMIN_USERNAME || 'admin';
const artifactsDir = path.join(process.cwd(), '..', 'output', 'playwright');

function requiredAdminPassword() {
  const password = process.env.QA_ADMIN_PASSWORD;
  if (!password) {
    throw new Error('Set QA_ADMIN_PASSWORD to run RQ-17 S-14 e2e tests.');
  }
  return password;
}

const suffix = process.env.QA_SUFFIX || String(Date.now()).slice(-6);
const resourceTag = `rq17res${suffix}`;
const profileKey = `rq17_res_${suffix}`;
const profileTitle = `RQ-17 ресурс ${suffix}`;
const serviceName = `RQ-17 услуга ${suffix}`;

if (!fs.existsSync(artifactsDir)) {
  fs.mkdirSync(artifactsDir, { recursive: true });
}

test.describe.configure({ mode: 'serial' });

test.beforeEach(async ({ page }) => {
  await page.goto('/login');
  await page.fill('input[name="username"]', ADMIN_USERNAME);
  await page.fill('input[name="password"]', requiredAdminPassword());
  await page.click('button:has-text("Войти")');
  await page.waitForLoadState('networkidle');
});

test('S-14 doctor-owned: мастер ведёт в существующие экраны, без второго onboarding', async ({ page }) => {
  await page.goto('/admin/setup-directions');
  await page.waitForLoadState('networkidle');

  // экран-вход открылся, чек-лист отрисован (статусы из API)
  await expect(page.getByTestId('setup-directions-heading')).toBeVisible();
  await expect(page.getByTestId('setup-checklist')).toBeVisible();

  // мастер S-14 с пустой формы
  await page.getByTestId('setup-wizard-open').click();
  await expect(page.getByTestId('setup-wizard')).toBeVisible();

  // «нет второго onboarding»: внутри мастера НЕТ формы создания врача —
  // только переход в /admin/users (canonical onboarding)
  await expect(page.getByTestId('setup-wizard-step-executor')).toHaveText(/.+/);
  const doctorInputs = page
    .getByTestId('setup-wizard-step-executor')
    .locator('input');
  await expect(doctorInputs).toHaveCount(0);

  // doctor-шаг ведёт в /admin/users
  await page.getByTestId('setup-wizard-axis-doctor').click();
  await page.getByRole('link', { name: /Пользователи|Users/i }).first().click();
  await expect(page).toHaveURL(/\/admin\/users$/);

  // возврат в путь: шаг «услуги» ведёт в каталог услуг
  await page.goto('/admin/setup-directions');
  await page.getByTestId('setup-wizard-open').click();
  await page.getByTestId('setup-wizard-axis-doctor').click();
  await page.getByRole('link', { name: /Услуги|Services/i }).first().click();
  await expect(page).toHaveURL(/\/admin\/services/);

  // шаг «отображение» ведёт в профили очередей
  await page.goto('/admin/setup-directions');
  await page.getByTestId('setup-wizard-open').click();
  await page.getByTestId('setup-wizard-axis-doctor').click();
  await page.getByTestId('setup-wizard-services-next').click();
  await page.getByRole('link', { name: /профил|profiles/i }).first().click();
  await expect(page).toHaveURL(/\/admin\/services/);

  // шаг «проверка»: возврат на чек-лист, статусы пересчитаны
  await page.goto('/admin/setup-directions');
  await page.getByTestId('setup-wizard-open').click();
  await page.getByTestId('setup-wizard-axis-doctor').click();
  await page.getByTestId('setup-wizard-services-next').click();
  await page.getByTestId('setup-wizard-display-next').click();
  await page.getByTestId('setup-wizard-verify-open').click();
  await expect(page.getByTestId('setup-checklist')).toBeVisible();

  // шаг «QR»: точка расширения зашита, выдача QR — после RQ-18
  await page.getByTestId('setup-wizard-open').click();
  await page.getByTestId('setup-wizard-axis-doctor').click();
  await page.getByTestId('setup-wizard-services-next').click();
  await page.getByTestId('setup-wizard-display-next').click();
  await page.getByTestId('setup-wizard-verify-open').click();
  await expect(page.getByTestId('setup-wizard-step-qr')).toBeVisible();

  await page.screenshot({
    path: path.join(artifactsDir, 'rq17-s14-doctor-owned.png'),
    fullPage: true,
  });
});

test('S-14 resource-owned: с чистого setup screen — wizard ведёт профиль/услугу, тег выбирается после создания, draft → активация через gate', async ({ page }) => {
  test.setTimeout(180_000);

  // 0) старт СТРОГО с экрана-входа: новое направление начинается «с пустой
  //    формы» — resource-ось доступна БЕЗ существующего тега (round-3 P1:
  //    прежняя версия скрывала это, создавая профиль/услугу вне мастера)
  await page.goto('/admin/setup-directions');
  await page.waitForLoadState('networkidle');
  await expect(page.getByTestId('setup-directions-heading')).toBeVisible();
  await page.getByTestId('setup-wizard-open').click();
  await expect(page.getByTestId('setup-wizard')).toBeVisible();
  // deferred start: кнопка resource-оси активна и без выбранного тега
  await expect(page.getByTestId('setup-wizard-axis-resource')).not.toBeDisabled();
  await page.getByTestId('setup-wizard-axis-resource').click();
  await expect(page.getByTestId('setup-wizard-step-services')).toBeVisible();

  // 1) шаг «отображение» (через мастер) → QueueProfilesManager: профиль
  //    с НОВЫМ тегом (queue_tags вводится списком; это существующий экран,
  //    не поверхность пути RQ-17)
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

  // 2) возврат в путь: тег создан — выбирается в селекторе resource-оси
  //    («выбор созданного тега после возврата»), шаг «услуги» → ServiceCatalog
  await page.goto('/admin/setup-directions');
  await page.waitForLoadState('networkidle');
  await page.getByTestId('setup-wizard-open').click();
  await page.getByTestId('setup-wizard-tag-select').click();
  await page.getByRole('option', { name: resourceTag }).first().click();
  await page.getByTestId('setup-wizard-axis-resource').click();
  await page.getByRole('link', { name: /Услуги|Services/i }).first().click();
  await expect(page).toHaveURL(/\/admin\/services/);

  // 3) doctorless-услуга нового тега (ServiceCatalog; ADM-06-прецедент)
  await page.getByRole('heading', { name: 'Справочник услуг' }).waitFor();
  await page.getByRole('button', { name: 'Добавить услугу' }).click();
  const form = page.locator('form').last();
  await form.locator('input[type="text"]').first().fill(serviceName);
  await form.getByPlaceholder('K01').fill(`T${suffix.slice(-2)}`);
  await form.locator('select').first().selectOption('7');
  await form.locator('input[type="number"]').first().fill('15000');
  await form.locator('input[type="number"]').nth(1).fill('20');
  // requires_doctor остаётся дефолтным (doctorless — нижняя нога gate §3.1)
  await page.getByRole('button', { name: 'Очередь' }).click();
  await form.locator('select').last().selectOption(resourceTag);
  await form.getByRole('button', { name: 'Сохранить' }).click();
  await expect(page.getByText('Услуга создана')).toBeVisible({ timeout: 15000 });

  // 4) экран-вход: мастер ведёт на проверку — тег в чек-листе, статусы
  //    пересчитаны из API ((б) готово, оси ещё нет — ресурс не создан)
  await page.goto('/admin/setup-directions');
  await page.waitForLoadState('networkidle');
  await page.getByTestId('setup-wizard-open').click();
  await page.getByTestId('setup-wizard-tag-select').click();
  await page.getByRole('option', { name: resourceTag }).first().click();
  await page.getByTestId('setup-wizard-axis-resource').click();
  await page.getByTestId('setup-wizard-services-next').click();
  await page.getByTestId('setup-wizard-display-next').click();
  await page.getByTestId('setup-wizard-verify-open').click();
  const row = page.getByTestId(`setup-checklist-row-${resourceTag}`);
  await expect(row).toBeVisible({ timeout: 15000 });

  // 5) QueueResource-менеджер: draft-ресурс (draft-by-default)
  await page.getByTestId('setup-view-resources').click();
  await page.getByTestId('qr-resource-create-toggle').click();
  // «ноль технических ключей»: тег — выбор из существующих значений
  const createForm = page.getByTestId('qr-resource-create-form');
  await expect(createForm).toBeVisible();
  const tagSelect = page.getByTestId('qr-resource-tag-select');
  await tagSelect.click();
  await page.getByRole('option', { name: resourceTag }).first().click();
  await page.getByTestId('qr-resource-display-name-input').fill(`Ресурс ${resourceTag}`);
  // active НЕ включаем — draft (S-14: услуги/профиль → draft → активация)
  await page.getByTestId('qr-resource-submit').click();
  await expect(page.getByTestId('qr-resource-error')).toHaveCount(0);
  await expect(page.locator('[data-testid^="qr-resource-row-"]').first()).toBeVisible({ timeout: 15000 });
  await expect(page.getByTestId('qr-resource-badge-draft').first()).toBeVisible();

  // 6) активация через gate §3.1 (doctorless-услуга тега существует)
  const draftRow = page.locator('[data-testid^="qr-resource-row-"]').first();
  await draftRow.locator('[data-testid^="qr-resource-toggle-"]').click();
  await expect(page.getByTestId('qr-resource-badge-active').first()).toBeVisible({ timeout: 15000 });

  // 7) чек-лист: ось resource, (а) готово
  await page.getByTestId('setup-view-checklist').click();
  await expect(row.getByTestId('setup-row-axis-resource')).toBeVisible({ timeout: 15000 });

  await page.screenshot({
    path: path.join(artifactsDir, 'rq17-s14-resource-owned.png'),
    fullPage: true,
  });

  fs.writeFileSync(
    path.join(artifactsDir, 'rq17-s14-ids.json'),
    JSON.stringify({ suffix, resourceTag, profileKey, serviceName }, null, 2),
    'utf8',
  );
});

test('S-14 text pin: ноль технических ключей в формах пути', async ({ page }) => {
  await page.goto('/admin/setup-directions');
  await page.waitForLoadState('networkidle');

  // мастер: ноль свободного ввода — всё выбор/ссылки/кнопки
  await page.getByTestId('setup-wizard-open').click();
  await expect(page.getByTestId('setup-wizard').locator('input')).toHaveCount(0);

  // менеджер QueueResource: тег — селектор из существующих значений,
  // среди текстовых полей формы нет поля queue_tag
  await page.getByTestId('setup-wizard-close').click();
  await page.getByTestId('setup-view-resources').click();
  await page.getByTestId('qr-resource-create-toggle').click();
  await expect(page.getByTestId('qr-resource-tag-select')).toBeVisible();
  const tagInputs = page
    .getByTestId('qr-resource-create-form')
    .locator('input')
    .filter({ hasNot: page.locator('[data-testid="qr-resource-display-name-input"], [data-testid="qr-resource-code-input"]') });
  const tagInputCount = await tagInputs.evaluateAll((nodes) =>
    nodes.filter((node) => /тег|queue_tag/i.test(node.getAttribute('name') || '')).length,
  );
  expect(tagInputCount).toBe(0);
});
