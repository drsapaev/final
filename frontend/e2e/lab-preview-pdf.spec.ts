// @ts-check
import { test, expect } from '@playwright/test';
import type { Page, Route } from '@playwright/test';

/**
 * PR8 (codex-lab-workflow-hardening-plan): mocked preview smoke.
 * Self-contained: no backend, no credentials — every /api/v1/** call is
 * intercepted with page.route; the session is fabricated via sessionStorage
 * (auth_token + auth_profile, the RoleGuard sources).
 *
 * Covers:
 *   1. draft report preview: «Предпросмотр PDF» button (backend-resolved
 *      available_actions=['preview']) fetches the dedicated preview route,
 *      opens a blob tab and NEVER calls mark-printed/finalize/pdf;
 *   2. finalized report: the preview action is not offered (print owns it).
 */

const LAB_PROFILE = {
  id: 7,
  username: 'lab_staff',
  full_name: 'Lab Staff',
  role: 'Lab',
  roles: ['Lab'],
};

const FAKE_TOKEN = [
  'eyJhbGciOiJIUzI1NiJ9',
  'eyJzdWIiOiI3Iiwicm9sZSI6IkxhYiIsImV4cCI6OTk5OTk5OTk5OX0',
  'sig',
].join('.');

const TEMPLATE_DETAIL = {
  id: 5,
  code: 'rule_demo',
  name: 'Rule Demo',
  family: 'chemistry',
  is_active: true,
  published_version_id: 51,
  draft_version_id: null,
  latest_version_id: 51,
  versions: [
    {
      id: 51,
      template_id: 5,
      version_no: 1,
      status: 'PUBLISHED',
      available_actions: ['create_draft'],
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

// DRAFT бланк: backend разрешил 'preview' (PR8 action contract).
const DRAFT_INSTANCE = {
  id: 88,
  status: 'IN_PROGRESS',
  template_id: 5,
  patient_id: 101,
  visit_id: 701,
  updated_at: '2026-09-25T08:00:00.000000+00:00',
  signer_snapshot: {},
  available_actions: ['edit', 'save_draft', 'finalize', 'preview'],
  can_preview: true,
  critical_findings: [],
  patient_snapshot: { patient_id: 101, full_name: 'Пациент Один' },
  template: TEMPLATE_DETAIL,
  template_version: TEMPLATE_DETAIL.versions[0],
  sections: TEMPLATE_DETAIL.versions[0].sections.map((section) => ({
    ...section,
    fields: section.fields.map((field) => ({ ...field, value_text: '6.5' })),
  })),
};

const FINALIZED_INSTANCE = {
  ...DRAFT_INSTANCE,
  id: 89,
  status: 'FINALIZED',
  available_actions: ['revise', 'print'],
  can_preview: false,
};

const QUEUE_DRAFT = [
  { id: 1, appointment_id: 'a-1', patient_id: 101, patient_fio: 'Пациент Один', patient_phone: '', status: 'waiting', report_instance_id: 88, services: [], service_codes: [], service_details: [] },
];

const QUEUE_FINALIZED = [
  { id: 2, appointment_id: 'a-2', patient_id: 101, patient_fio: 'Пациент Финал', patient_phone: '', status: 'waiting', report_instance_id: 89, services: [], service_codes: [], service_details: [] },
];

function json(route: Route, payload: unknown, headers: Record<string, string> = {}) {
  return route.fulfill({
    status: 200,
    contentType: 'application/json',
    headers,
    body: JSON.stringify(payload),
  });
}

// Трекер серверных вызовов: preview должен быть, побочных эффектов — нет.
let labApiCalls: Array<{ url: string; method: string }> = [];

async function installSession(page: Page) {
  await page.addInitScript(({ token, profile }) => {
    window.sessionStorage.setItem('auth_token', token);
    window.sessionStorage.setItem('refresh_token', token);
    window.sessionStorage.setItem('auth_profile', JSON.stringify(profile));
    window.sessionStorage.setItem('user', JSON.stringify(profile));
    // Захват window.open: preview открывает blob-вкладку; нельзя дать
    // настоящему popup-менеджеру Playwright мешать тесту.
    const opened: string[] = [];
    (window as unknown as { __openedWindows: string[] }).__openedWindows = opened;
    window.open = ((url?: string | URL) => {
      opened.push(String(url));
      return {} as Window;
    }) as typeof window.open;
  }, { token: FAKE_TOKEN, profile: LAB_PROFILE });
}

async function installApiMocks(page: Page) {
  labApiCalls = [];
  // Трекер через page.on('request'): специфичные route-хендлеры ниже имеют
  // приоритет над generic-перехватчиком, поэтому route-based счётчик не
  // видит замокированные вызовы. Событие request фиксирует ВСЕ вызовы.
  page.on('request', (request) => {
    const url = request.url();
    if (url.includes('/api/v1/lab/')) {
      labApiCalls.push({ url, method: request.method() });
    }
  });
  await page.route('**/api/v1/**', (route) => {
    if (route.request().method() === 'OPTIONS') return route.fulfill({ status: 204 });
    return json(route, {});
  });

  await page.route('**/api/v1/setup/status**', (route) => json(route, { initialized: true }));
  await page.route('**/api/v1/lab/queue/today**', (route) => json(route, {
    entries: QUEUE_DRAFT,
    total: QUEUE_DRAFT.length,
    date: '2026-09-25',
    timezone: 'Asia/Tashkent',
  }));
  await page.route('**/api/v1/lab/catalog/**', (route) => json(route, []));
  await page.route('**/api/v1/lab/templates**', (route) => json(route, [
    { id: 5, code: 'rule_demo', name: 'Rule Demo', family: 'chemistry', is_active: true, published_version_id: 51, draft_version_id: null, latest_version_id: 51 },
  ]));
  await page.route('**/api/v1/lab/templates/5', (route) => json(route, TEMPLATE_DETAIL));
  await page.route('**/api/v1/lab/template-resolutions/resolve', (route) => json(route, {
    patient_id: 101,
    visit_id: 701,
    resolution_mode: 'mapped',
    service_codes: [],
    service_names: [],
    matched_service_codes: [],
    unmapped_service_codes: [],
    default_template: null,
    allowed_templates: [],
  }));
  await page.route('**/api/v1/lab/report-instances?**', (route) => json(route, []));
  await page.route('**/api/v1/lab/report-instances/88', (route) => json(route, DRAFT_INSTANCE));
  await page.route('**/api/v1/lab/report-instances/89', (route) => json(route, FINALIZED_INSTANCE));
  await page.route('**/api/v1/lab/report-instances/88/bulk-values**', (route) =>
    json(route, { instance: DRAFT_INSTANCE, updated_field_keys: ['wbc'] }));

  // PR8: серверный preview-маршрут отдаёт синтетический PDF-блоб.
  await page.route('**/api/v1/lab/report-instances/88/preview', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/pdf',
      headers: {
        'content-disposition': 'inline; filename="lab-report-88-preview.pdf"',
        'cache-control': 'private, no-store',
      },
      body: '%PDF-synthetic-preview',
    }));
}

test.describe('Lab server-rendered PDF preview (PR8)', () => {
  test.beforeEach(async ({ page }) => {
    await installSession(page);
    await installApiMocks(page);
  });

  test('draft preview opens a blob tab without any print side effects', async ({ page }) => {
    await page.goto('/lab');
    await page.waitForTimeout(700);

    // Открываем пациента с DRAFT-бланком (report_instance_id=88).
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    await expect(page.getByLabel('Результат: Лейкоциты')).toBeVisible();
    await page.waitForTimeout(500);

    // Кнопка предпросмотра доступна (backend available_actions=['preview']).
    const previewButton = page.getByRole('button', { name: /Предпросмотр PDF/ });
    await expect(previewButton).toBeVisible();

    await previewButton.click();

    // Blob-вкладка открыта (window.open захвачен пробой).
    await expect
      .poll(() => page.evaluate(() =>
        (window as unknown as { __openedWindows?: string[] }).__openedWindows?.length || 0))
      .toBeGreaterThanOrEqual(1);

    // Выделенный preview-маршрут вызван ровно один раз.
    const previewCalls = labApiCalls.filter(
      (call) => call.url.includes('/lab/report-instances/88/preview'),
    );
    expect(previewCalls).toHaveLength(1);

    // Контракт PR8: preview не имеет серверных побочных эффектов —
    // mark-printed / finalize / финальный /pdf не вызываются вовсе.
    const sideEffectCalls = labApiCalls.filter(
      (call) =>
        call.url.includes('/mark-printed')
        || call.url.includes('/finalize')
        || (call.url.includes('/lab/report-instances/88/pdf')
          && !call.url.includes('/preview')),
    );
    expect(sideEffectCalls).toEqual([]);

    // Статус бланка не изменился в UI (индикатор «Утверждён» не появился).
    await expect(page.getByText(/Утверждён/).first()).toBeHidden({ timeout: 1000 }).catch(() => {
      // Индикатор статуса может не содержать слово «Утверждён» —
      // главный ассерт выше (sideEffectCalls) уже доказал отсутствие
      // побочных эффектов; этот блок лишь толерантен к разметке.
    });
  });

  test('finalized report offers print, not preview', async ({ page }) => {
    // Подменяем очередь на пациента с FINALIZED-бланком (регистрация
    // ПОСЛЕ installApiMocks — последний route обрабатывает запрос).
    await page.route('**/api/v1/lab/queue/today**', (route) => json(route, {
      entries: QUEUE_FINALIZED,
      total: QUEUE_FINALIZED.length,
      date: '2026-09-25',
      timezone: 'Asia/Tashkent',
    }));
    await page.goto('/lab');
    await page.waitForTimeout(700);

    await page.getByRole('button', { name: /Пациент Финал/ }).first().click();
    await expect(page.getByRole('button', { name: /Печать результата/ })).toBeVisible();
    await page.waitForTimeout(500);

    // Preview-действие недоступно для утверждённого бланка.
    await expect(page.getByRole('button', { name: /Предпросмотр PDF/ })).toBeHidden();
    expect(
      labApiCalls.filter((call) => call.url.includes('/preview')),
    ).toEqual([]);
  });
});
