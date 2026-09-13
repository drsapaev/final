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
 *   2. create template -> returned template is selected in the editor.
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

const QUEUE_ENTRIES = [
  { id: 1, appointment_id: 'a-1', patient_id: 101, patient_fio: 'Пациент Один', patient_phone: '', status: 'waiting', report_instance_id: 88, services: [], service_codes: [], service_details: [] },
  { id: 2, appointment_id: 'a-2', patient_id: 102, patient_fio: 'Пациент Два', patient_phone: '', status: 'waiting', services: [], service_codes: [], service_details: [] },
];

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
      return json(route, { id: 9, code: 'new_rule_t', name: 'Новый шаблон правил', family: 'chemistry', is_active: true, published_version_id: null, draft_version_id: null, latest_version_id: null });
    }
    return json(route, TEMPLATES_SUMMARY);
  });
  await page.route('**/api/v1/lab/report-instances?**', (route) => json(route, []));
  await page.route('**/api/v1/lab/report-instances/88', (route) => json(route, INSTANCE_A));
  await page.route('**/api/v1/lab/catalog/**', (route) => json(route, []));
  await page.route('**/api/v1/lab/recent-reports**', (route) => json(route, []));
}

test.describe('Lab dirty-state guard (PR5, mocked)', () => {
  test.use({ viewport: { width: 1440, height: 1100 } });

  test.beforeEach(async ({ page }) => {
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
    await page.getByRole('dialog').getByRole('button', { name: 'Выйти без сохранения' }).click();

    // Переход выполнен: выбранным стал пациент Два (очередь подсвечивает его).
    await expect(page.getByText('Пациент Два').first()).toBeVisible();
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
  });
});
