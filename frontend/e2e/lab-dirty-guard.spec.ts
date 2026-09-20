// @ts-check
import { test, expect } from '@playwright/test';
import type { Page, Route } from '@playwright/test';

/**
 * PR5 (lab workflow hardening plan): mocked workflow spec.
 * Self-contained: no backend, no credentials — every /api/v1/** call is
 * intercepted with page.route; the session is fabricated via sessionStorage
 * (auth_token + auth_profile, the RoleGuard sources).
 *
 * Covers:
 *   1. dirty value -> select another queue patient -> Cancel preserves input;
 *   2. dirty template -> Create -> Cancel preserves both drafts and sends no POST;
 *   3. create template -> returned template is selected in the editor;
 *   4. instance state/URL synchronization is latest-wins for open, clear, and create.
 */

const LAB_PROFILE = {
  id: 7,
  username: 'lab_staff',
  full_name: 'Lab Staff',
  role: 'Lab',
  roles: ['Lab'],
};

// Minimal unsigned token shape: the UI only decodes claims client-side and
// every API call is mocked, so the signature is irrelevant here.
const FAKE_TOKEN = [
  'eyJhbGciOiJIUzI1NiJ9',
  'eyJzdWIiOiI3Iiwicm9sZSI6IkxhYiIsImV4cCI6OTk5OTk5OTk5OX0',
  'sig',
].join('.');

const TEMPLATES_SUMMARY = [
  { id: 5, code: 'rule_demo', name: 'Rule Demo', family: 'chemistry', is_active: true, published_version_id: 51, draft_version_id: null, latest_version_id: 51 },
];

const TEMPLATE_DETAIL = {
  ...TEMPLATES_SUMMARY[0],
  versions: [
    {
      id: 51,
      template_id: 5,
      version_no: 1,
      status: 'PUBLISHED',
      layout_preset: 'lab_table_classic_v1',
      page_settings: {},
      branding_overrides: {},
      signer_defaults: {},
      footer_notes: '',
      sections: [
        {
          id: 1,
          key: 's1',
          title: 'Раздел 1',
          sort_order: 10,
          section_style: {},
          fields: [
            { id: 1, field_key: 'wbc', label: 'Лейкоциты', value_type: 'text', unit: '', reference_mode: 'static_text', reference_text: '', required: false, sort_order: 10, reference_rule: null, visibility_rule: null, highlight_rule: null },
          ],
        },
      ],
    },
  ],
};

const INSTANCE_A = {
  id: 88,
  status: 'DRAFT',
  template_id: 5,
  patient_id: 101,
  visit_id: 701,
  updated_at: '2026-09-13T08:00:00.000000+00:00',
  signer_snapshot: {},
  available_actions: ['edit', 'save_draft', 'finalize'],
  critical_findings: [],
  patient_snapshot: { patient_id: 101, full_name: 'Пациент Один' },
  template: TEMPLATE_DETAIL,
  template_version: TEMPLATE_DETAIL.versions[0],
  sections: TEMPLATE_DETAIL.versions[0].sections.map((section) => ({
    ...section,
    fields: section.fields.map((field) => ({ ...field, value_text: '' })),
  })),
};

const INSTANCE_B = {
  ...INSTANCE_A,
  id: 89,
  patient_id: 102,
  patient_snapshot: { patient_id: 102, full_name: 'Пациент Два' },
};

const INSTANCE_CREATED = {
  ...INSTANCE_A,
  id: 90,
  updated_at: '2026-09-13T08:05:00.000000+00:00',
};

const QUEUE_ENTRIES = [
  { id: 1, appointment_id: 'a-1', patient_id: 101, patient_fio: 'Пациент Один', patient_phone: '', status: 'waiting', report_instance_id: 88, services: [], service_codes: [], service_details: [] },
  { id: 2, appointment_id: 'a-2', patient_id: 102, patient_fio: 'Пациент Два', patient_phone: '', status: 'waiting', report_instance_id: 89, services: [], service_codes: [], service_details: [] },
  { id: 3, appointment_id: 'a-3', patient_id: 103, patient_fio: 'Пациент Без Бланка', patient_phone: '', status: 'waiting', report_instance_id: null, services: [], service_codes: [], service_details: [] },
];

let templateCreatePostCount = 0;
let reportInstanceCreatePostCount = 0;
let instance88GetCount = 0;
let instance89GetCount = 0;
let instance88DelayMs = 0;
let reportInstanceCreateDelayMs = 0;
let lastReportInstanceCreatePayload: Record<string, unknown> | null = null;
let templateResolutionDelayByPatient = new Map<string, number>();

async function installSession(page: Page) {
  await page.addInitScript(({ token, profile }) => {
    window.sessionStorage.setItem('auth_token', token);
    window.sessionStorage.setItem('refresh_token', token);
    window.sessionStorage.setItem('auth_profile', JSON.stringify(profile));
    window.sessionStorage.setItem('user', JSON.stringify(profile));
  }, { token: FAKE_TOKEN, profile: LAB_PROFILE });
}

async function installApiMocks(page: Page) {
  // Generic fallback: any other API call succeeds empty instead of erroring.
  await page.route('**/api/v1/**', (route) => {
    if (route.request().method() === 'OPTIONS') return route.fulfill({ status: 204 });
    return json(route, {});
  });

  await page.route('**/api/v1/setup/status**', (route) => json(route, { initialized: true }));

  const json = (route: Route, payload: unknown) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });

  await page.route('**/api/v1/lab/queue/today**', (route) => json(route, {
    entries: QUEUE_ENTRIES,
    total: QUEUE_ENTRIES.length,
    date: '2026-09-13',
    timezone: 'Asia/Tashkent',
  }));
  await page.route('**/api/v1/lab/templates/5', (route) => json(route, TEMPLATE_DETAIL));
  await page.route('**/api/v1/lab/templates/9', (route) => json(route, {
    ...TEMPLATES_SUMMARY[0],
    id: 9,
    code: 'new_rule_t',
    name: 'Новый шаблон правил',
    published_version_id: null,
    latest_version_id: null,
    versions: [],
  }));
  await page.route('**/api/v1/lab/templates', (route) => {
    if (route.request().method() === 'POST') {
      templateCreatePostCount += 1;
      return json(route, { id: 9, code: 'new_rule_t', name: 'Новый шаблон правил', family: 'chemistry', is_active: true, published_version_id: null, draft_version_id: null, latest_version_id: null });
    }
    return json(route, TEMPLATES_SUMMARY);
  });
  await page.route('**/api/v1/lab/template-resolutions/resolve', async (route) => {
    const payload = route.request().postDataJSON() as Record<string, unknown>;
    const patientId = String(payload.patient_id ?? '');
    const delayMs = templateResolutionDelayByPatient.get(patientId) ?? 0;
    if (delayMs > 0) {
      await new Promise((resolve) => setTimeout(resolve, delayMs));
    }
    return json(route, {
      visit_id: 600 + Number(patientId),
      service_codes: [`svc-${patientId}`],
      allowed_templates: TEMPLATES_SUMMARY,
      default_template: TEMPLATES_SUMMARY[0],
      unmapped_service_codes: [],
      resolution_mode: 'mapped',
    });
  });
  await page.route('**/api/v1/lab/report-instances?**', (route) => json(route, []));
  await page.route('**/api/v1/lab/report-instances', async (route) => {
    if (route.request().method() === 'POST') {
      reportInstanceCreatePostCount += 1;
      const payload = route.request().postDataJSON() as Record<string, unknown>;
      lastReportInstanceCreatePayload = payload;
      if (reportInstanceCreateDelayMs > 0) {
        await new Promise((resolve) => setTimeout(resolve, reportInstanceCreateDelayMs));
      }
      const patientId = Number(payload.patient_id);
      return json(route, {
        ...INSTANCE_CREATED,
        patient_id: patientId,
        visit_id: payload.visit_id,
        patient_snapshot: {
          patient_id: patientId,
          full_name: patientId === 102 ? 'Пациент Два' : 'Пациент Один',
        },
      });
    }
    return json(route, []);
  });
  await page.route('**/api/v1/lab/report-instances/88', async (route) => {
    instance88GetCount += 1;
    if (instance88DelayMs > 0) {
      await new Promise((resolve) => setTimeout(resolve, instance88DelayMs));
    }
    return json(route, INSTANCE_A);
  });
  await page.route('**/api/v1/lab/report-instances/89', (route) => {
    instance89GetCount += 1;
    return json(route, INSTANCE_B);
  });
  await page.route('**/api/v1/lab/report-instances/90', (route) => json(route, INSTANCE_CREATED));
  await page.route('**/api/v1/lab/catalog/**', (route) => json(route, []));
  await page.route('**/api/v1/lab/recent-reports**', (route) => json(route, []));
}

test.describe('Lab dirty-state guard (PR5, mocked)', () => {
  test.use({ viewport: { width: 1440, height: 1100 } });

  test.beforeEach(async ({ page }) => {
    templateCreatePostCount = 0;
    reportInstanceCreatePostCount = 0;
    instance88GetCount = 0;
    instance89GetCount = 0;
    instance88DelayMs = 0;
    reportInstanceCreateDelayMs = 0;
    lastReportInstanceCreatePayload = null;
    templateResolutionDelayByPatient = new Map();
    await installSession(page);
    await installApiMocks(page);
  });

  test('dirty value -> select another queue patient -> Cancel preserves input', async ({ page }) => {
    await page.goto('/lab');
    // Стабилизируем двойную загрузку (URL-sync перезапускает открытие отчёта).
    await page.waitForTimeout(700);

    // Открываем пациента А (report_instance_id=88 -> редактор отчёта).
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    const fieldInput = page.getByLabel('Результат: Лейкоциты');
    await expect(fieldInput).toBeVisible();
    await page.waitForTimeout(700);

    // Вводим значение -> dirty.
    await fieldInput.fill('6.5');
    await expect(fieldInput).toHaveValue('6.5');
    // Ждём подтверждения dirty-state (isDirtyRef обновляется в effect).
    await expect(page.getByText(/несохранённые изменения/).first()).toBeVisible();

    // Возвращаемся в очередь (вкладка скрылась при открытии отчёта).
    await page.getByRole('tab').first().click();

    // Клик по другому пациенту очереди -> guard-диалог.
    await page.getByRole('button', { name: /Пациент Два/ }).first().dispatchEvent('click');
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();

    // Отмена: пользователь и введённое значение остаются на месте.
    await dialog.getByRole('button', { name: 'Отмена' }).click();
    await expect(dialog).toBeHidden();
    await expect(fieldInput).toHaveValue('6.5');
  });

  test('dirty value -> select another queue patient -> discard opens the other patient', async ({ page }) => {
    await page.goto('/lab');
    await page.waitForTimeout(700);

    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    const fieldInput = page.getByLabel('Результат: Лейкоциты');
    await expect(fieldInput).toBeVisible();
    await page.waitForTimeout(700);
    await fieldInput.fill('6.5');
    await expect(page.getByText(/несохранённые изменения/).first()).toBeVisible();

    await page.getByRole('tab').first().click();
    await page.getByRole('button', { name: /Пациент Два/ }).first().dispatchEvent('click');
    // Вложенного guard быть не должно: РОВНО один диалог на переход.
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    expect(await dialog.count()).toBe(1);
    await dialog.getByRole('button', { name: 'Выйти без сохранения' }).click();

    // Согласованный контекст: пациент Два И его отчёт #89 (не отчёт A).
    await expect.poll(() => instance89GetCount).toBeGreaterThan(0);
    expect(instance88GetCount).toBe(1);
    await expect(page.getByText('Пациент Два').first()).toBeVisible();
    await expect(page.getByText('Отчёт #89').first()).toBeVisible();
    // Диалог закрыт, повторного подтверждения нет.
    await expect(dialog).toHaveCount(0);
  });

  test('rapid report selection is latest-wins when the first response arrives last', async ({ page }) => {
    instance88DelayMs = 600;
    await page.goto('/lab');

    await page.getByRole('button', { name: /Пациент Один/ }).first().dispatchEvent('click');
    await page.getByRole('button', { name: /Пациент Два/ }).first().dispatchEvent('click');

    await expect(page.getByText('Отчёт #89').first()).toBeVisible();
    await page.waitForTimeout(instance88DelayMs + 200);
    await expect(page.getByText('Отчёт #88')).toHaveCount(0);
    expect(instance88GetCount).toBe(1);
    expect(instance89GetCount).toBe(1);
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBe('89');
  });

  test('dirty URL transition keeps the requested report after Discard', async ({ page }) => {
    await page.goto('/lab');
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    const fieldInput = page.getByLabel('Результат: Лейкоциты');
    await fieldInput.fill('6.5');
    await expect(page.getByText(/несохранённые изменения/).first()).toBeVisible();

    await page.evaluate(() => {
      window.history.pushState({}, '', '/lab?instance=89');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });

    const dialog = page.getByRole('dialog').filter({ hasText: 'Несохранённые изменения' });
    await expect(dialog).toBeVisible();
    await dialog.getByRole('button', { name: 'Выйти без сохранения' }).click();

    await expect(page.getByText('Отчёт #89').first()).toBeVisible();
    await page.waitForTimeout(300);
    await expect(page.getByText('Отчёт #88')).toHaveCount(0);
    expect(instance88GetCount).toBe(1);
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBe('89');
  });

  test('selecting a patient without a report clears the old instance without restoring it', async ({ page }) => {
    await page.goto('/lab');
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    await expect(page.getByText('Отчёт #88').first()).toBeVisible();

    await page.getByRole('tab').first().click();
    await page.getByRole('button', { name: /Пациент Без Бланка/ }).first().click();

    await expect(page.getByText('Пациент Без Бланка').first()).toBeVisible();
    await expect(page.getByRole('button', { name: 'Создать отчёт' })).toBeVisible();
    await expect(page.getByText('Отчёт #88')).toHaveCount(0);
    await page.waitForTimeout(300);
    expect(instance88GetCount).toBe(1);
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBeNull();
  });

  test('creating another blank keeps the new instance instead of restoring the old URL id', async ({ page }) => {
    await page.goto('/lab');
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    await expect(page.getByText('Отчёт #88').first()).toBeVisible();
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBe('88');

    await page.getByRole('button', { name: 'Добавить бланк' }).click();

    await expect(page.getByText('Отчёт #90').first()).toBeVisible();
    await page.waitForTimeout(300);
    await expect(page.getByText('Отчёт #88')).toHaveCount(0);
    expect(reportInstanceCreatePostCount).toBe(1);
    expect(instance88GetCount).toBe(1);
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBe('90');
  });

  test('late create response cannot replace a newer patient report', async ({ page }) => {
    reportInstanceCreateDelayMs = 700;
    await page.goto('/lab');
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    await expect(page.getByText('Отчёт #88').first()).toBeVisible();

    await page.getByRole('button', { name: 'Добавить бланк' }).click();
    await expect.poll(() => reportInstanceCreatePostCount).toBe(1);
    await page.getByRole('tab').first().click();
    await page.getByRole('button', { name: /Пациент Два/ }).first().click();
    await expect(page.getByText('Отчёт #89').first()).toBeVisible();

    await page.waitForTimeout(reportInstanceCreateDelayMs + 250);
    await expect(page.getByText('Отчёт #90')).toHaveCount(0);
    await expect(page.getByText('Отчёт #89').first()).toBeVisible();
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBe('89');
  });

  test('late template resolution cannot contaminate the next patient create payload', async ({ page }) => {
    templateResolutionDelayByPatient.set('101', 700);
    instance88DelayMs = 500;
    await page.goto('/lab');

    await page.getByRole('button', { name: /Пациент Один/ }).first().dispatchEvent('click');
    await page.getByRole('button', { name: /Пациент Два/ }).first().dispatchEvent('click');
    await expect(page.getByText('Отчёт #89').first()).toBeVisible();
    await page.waitForTimeout(800);

    await page.getByRole('button', { name: 'Добавить бланк' }).click();
    await expect.poll(() => reportInstanceCreatePostCount).toBe(1);
    expect(lastReportInstanceCreatePayload).toMatchObject({
      patient_id: 102,
      appointment_id: 'a-2',
      visit_id: 702,
      service_codes: ['svc-102'],
    });
    await expect(page.getByText('Отчёт #90').first()).toBeVisible();
  });

  test('reopening the same report performs one refresh request without URL restore duplication', async ({ page }) => {
    await page.goto('/lab');
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    await expect(page.getByText('Отчёт #88').first()).toBeVisible();
    expect(instance88GetCount).toBe(1);

    await page.getByRole('tab').first().click();
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    await expect(page.getByText('Отчёт #88').first()).toBeVisible();
    await page.waitForTimeout(300);
    expect(instance88GetCount).toBe(2);
  });

  test('create template -> returned template is selected in the editor', async ({ page }) => {
    await page.goto('/lab?tab=templates');
    await page.waitForTimeout(700);

    await page.getByRole('button', { name: 'Новый' }).click();
    await page.getByLabel('Код шаблона').fill('new_rule_t');
    await page.getByLabel('Название шаблона').fill('Новый шаблон правил');
    await page.getByRole('button', { name: 'Создать' }).click();

    // Возвращённый шаблон (id=9) выбран: в редакторе виден его код.
    await expect(page.getByText('new_rule_t').first()).toBeVisible();
    expect(templateCreatePostCount).toBe(1);
  });

  test('dirty template -> Create -> Cancel preserves both drafts and sends no POST', async ({ page }) => {
    await page.goto('/lab?tab=templates');
    await page.waitForTimeout(700);

    // Делаем текущий шаблон dirty.
    await page.getByRole('tab', { name: 'Оформление' }).click();
    const footerInput = page.getByLabel('Подвал шаблона');
    await footerInput.fill('Несохранённый подвал');
    await expect(footerInput).toHaveValue('Несохранённый подвал');

    // A tab/query URL change must not re-fetch templates and hydrate over the
    // dirty editor state.
    const panelTabs = page.getByRole('tablist', { name: 'Панель лаборатории' });
    await panelTabs.getByRole('tab').nth(0).click();
    await panelTabs.getByRole('tab').nth(1).click();
    await expect(footerInput).toHaveValue('Несохранённый подвал');

    // Заполняем форму нового шаблона и нажимаем Create. POST должен ждать
    // решения dirty-guard, а не выполняться заранее.
    await page.getByRole('button', { name: 'Новый' }).click();
    const codeInput = page.getByLabel('Код шаблона');
    const nameInput = page.getByLabel('Название шаблона');
    await codeInput.fill('new_rule_t');
    await nameInput.fill('Новый шаблон правил');
    await page.getByRole('button', { name: 'Создать' }).click();

    const guardDialog = page.getByRole('dialog').filter({ hasText: 'Несохранённые изменения' });
    await expect(guardDialog).toBeVisible();
    expect(templateCreatePostCount).toBe(0);

    await guardDialog.getByRole('button', { name: 'Отмена' }).click();
    await expect(guardDialog).toBeHidden();

    // Оба введённых значения остаются; создание не отправлено.
    await expect(footerInput).toHaveValue('Несохранённый подвал');
    await expect(codeInput).toHaveValue('new_rule_t');
    await expect(nameInput).toHaveValue('Новый шаблон правил');
    expect(templateCreatePostCount).toBe(0);
  });
});
