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
  { id: 6, code: 'rule_demo_b', name: 'Rule Demo B', family: 'chemistry', is_active: true, published_version_id: 61, draft_version_id: null, latest_version_id: 61 },
];

const TEMPLATE_DETAIL = {
  ...TEMPLATES_SUMMARY[0],
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

const TEMPLATE_DETAIL_B = {
  ...TEMPLATE_DETAIL,
  ...TEMPLATES_SUMMARY[1],
  versions: TEMPLATE_DETAIL.versions.map((version) => ({
    ...version,
    id: 61,
    template_id: 6,
  })),
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
  { id: 4, appointment_id: 'a-4', patient_id: 103, patient_fio: 'Пациент Без Бланка Повтор', patient_phone: '', status: 'waiting', report_instance_id: null, services: [], service_codes: [], service_details: [] },
];

let templateCreatePostCount = 0;
let reportInstanceCreatePostCount = 0;
let bulkSavePostCount = 0;
let instance88GetCount = 0;
let instance89GetCount = 0;
let instance88DelayMs = 0;
let instance88ResponseGate: Promise<void> | null = null;
let releaseInstance88Response: (() => void) | null = null;
let instance89ResponseGate: Promise<void> | null = null;
let releaseInstance89Response: (() => void) | null = null;
let instance89ShouldFail = false;
let template5GetCount = 0;
let template5FirstResponseGate: Promise<void> | null = null;
let releaseTemplate5FirstResponse: (() => void) | null = null;
let template5ResponseGate: Promise<void> | null = null;
let releaseTemplate5Response: (() => void) | null = null;
let template5ShouldFail = false;
let template6ShouldFail = false;
let template5FooterNotes = '';
let templateDraftUpdateCount = 0;
let reportInstanceCreateResponseGate: Promise<void> | null = null;
let releaseReportInstanceCreateResponse: (() => void) | null = null;
let lastReportInstanceCreatePayload: Record<string, unknown> | null = null;
let templateResolutionDelayByPatient = new Map<string, number>();
let bulkSaveResponseGate: Promise<void> | null = null;
let releaseBulkSaveResponse: (() => void) | null = null;
let templateDraftSaveResponseGate: Promise<void> | null = null;
let releaseTemplateDraftSaveResponse: (() => void) | null = null;
let templateResolution101ResponseGate: Promise<void> | null = null;
let releaseTemplateResolution101Response: (() => void) | null = null;
let templateResolutionPatientRequests: string[] = [];
let reportHistoryPatientRequests: string[] = [];
let history101ResponseGate: Promise<void> | null = null;
let releaseHistory101Response: (() => void) | null = null;
let history102ResponseGate: Promise<void> | null = null;
let releaseHistory102Response: (() => void) | null = null;

// Скрытый locator карточки пациента очереди: tabpanel очереди смонтирован
// всегда (hidden-секции), а getByRole исключает скрытые элементы из a11y
// дерева — как только отчёт открывается и вкладка очереди скрывается,
// getByRole(...).dispatchEvent перестаёт находить кнопку и тест флапает
// (PR #3351: «использовать стабильный скрытый locator»). dispatchEvent
// не требует видимости. Карточка пациента — div[role="button"], не <button>.
function queuePatientButton(page: Page, name: string) {
  return page.locator('#lab-panel-tabpanel-queue [role="button"]', { hasText: name }).first();
}

async function installSession(page: Page) {
  await page.addInitScript(({ token, profile }) => {
    window.sessionStorage.setItem('auth_token', token);
    window.sessionStorage.setItem('refresh_token', token);
    window.sessionStorage.setItem('auth_profile', JSON.stringify(profile));
    window.sessionStorage.setItem('user', JSON.stringify(profile));
  }, { token: FAKE_TOKEN, profile: LAB_PROFILE });
}

async function waitForReactToSettle(page: Page) {
  await page.evaluate(() => new Promise<void>((resolve) => {
    window.requestAnimationFrame(() => window.requestAnimationFrame(() => resolve()));
  }));
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
  await page.route('**/api/v1/lab/templates/5', async (route) => {
    template5GetCount += 1;
    if (template5GetCount === 1 && template5FirstResponseGate) {
      await template5FirstResponseGate;
    }
    if (template5ResponseGate) await template5ResponseGate;
    if (template5ShouldFail) {
      return route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"failed"}' });
    }
    return json(route, {
      ...TEMPLATE_DETAIL,
      versions: TEMPLATE_DETAIL.versions.map((version) => ({
        ...version,
        footer_notes: template5FooterNotes,
      })),
    });
  });
  await page.route('**/api/v1/lab/templates/6', (route) => {
    if (template6ShouldFail) {
      return route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"failed"}' });
    }
    return json(route, TEMPLATE_DETAIL_B);
  });
  await page.route('**/api/v1/lab/templates/5/versions', (route) => json(route, { id: 52 }));
  await page.route('**/api/v1/lab/template-versions/52', async (route) => {
    if (route.request().method() === 'PUT') {
      templateDraftUpdateCount += 1;
      if (templateDraftSaveResponseGate) await templateDraftSaveResponseGate;
      const payload = route.request().postDataJSON() as Record<string, unknown>;
      template5FooterNotes = String(payload.footer_notes ?? '');
      return json(route, { id: 52, ...payload });
    }
    return json(route, { id: 52 });
  });
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
    templateResolutionPatientRequests.push(patientId);
    if (patientId === '101' && templateResolution101ResponseGate) {
      await templateResolution101ResponseGate;
    }
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
  await page.route('**/api/v1/lab/report-instances?**', async (route) => {
    const patientId = new URL(route.request().url()).searchParams.get('patient_id');
    if (patientId) reportHistoryPatientRequests.push(patientId);
    if (patientId === '101' && history101ResponseGate) await history101ResponseGate;
    if (patientId === '102' && history102ResponseGate) await history102ResponseGate;
    return json(route, patientId ? [{ id: `history-${patientId}`, patient_id: Number(patientId) }] : []);
  });
  await page.route('**/api/v1/lab/report-instances', async (route) => {
    if (route.request().method() === 'POST') {
      reportInstanceCreatePostCount += 1;
      const payload = route.request().postDataJSON() as Record<string, unknown>;
      lastReportInstanceCreatePayload = payload;
      if (reportInstanceCreateResponseGate) {
        await reportInstanceCreateResponseGate;
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
    if (instance88ResponseGate) await instance88ResponseGate;
    if (instance88DelayMs > 0) {
      await new Promise((resolve) => setTimeout(resolve, instance88DelayMs));
    }
    return json(route, INSTANCE_A);
  });
  await page.route('**/api/v1/lab/report-instances/89', async (route) => {
    instance89GetCount += 1;
    if (instance89ResponseGate) await instance89ResponseGate;
    if (instance89ShouldFail) {
      return route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"failed"}' });
    }
    return json(route, INSTANCE_B);
  });
  await page.route('**/api/v1/lab/report-instances/90', (route) => json(route, INSTANCE_CREATED));
  await page.route('**/api/v1/lab/report-instances/88/bulk-values**', async (route) => {
    bulkSavePostCount += 1;
    if (bulkSaveResponseGate) await bulkSaveResponseGate;
    // Реальный backend возвращает instance с СОХРАНЁННЫМИ значениями —
    // иначе честный ре-гидрат ответом затирал бы только что записанный draft.
    const items = (route.request().postDataJSON() as Array<{ field_key?: string; value_text?: string | null }>) || [];
    const savedSections = INSTANCE_A.sections.map((section) => ({
      ...section,
      fields: section.fields.map((field) => {
        const item = items.find((entry) => entry.field_key === field.field_key);
        return item ? { ...field, value_text: item.value_text ?? '' } : field;
      }),
    }));
    return json(route, {
      instance: {
        ...INSTANCE_A,
        sections: savedSections,
        updated_at: '2026-09-13T08:00:01.000000+00:00',
      },
    });
  });
  await page.route('**/api/v1/lab/catalog/**', (route) => json(route, []));
  await page.route('**/api/v1/lab/recent-reports**', (route) => json(route, []));
}

test.describe('Lab dirty-state guard (PR5, mocked)', () => {
  test.use({ viewport: { width: 1440, height: 1100 } });

  test.beforeEach(async ({ page }) => {
    templateCreatePostCount = 0;
    reportInstanceCreatePostCount = 0;
    bulkSavePostCount = 0;
    instance88GetCount = 0;
    instance89GetCount = 0;
    instance88DelayMs = 0;
    instance88ResponseGate = null;
    releaseInstance88Response = null;
    instance89ResponseGate = null;
    releaseInstance89Response = null;
    instance89ShouldFail = false;
    template5GetCount = 0;
    template5FirstResponseGate = null;
    releaseTemplate5FirstResponse = null;
    template5ResponseGate = null;
    releaseTemplate5Response = null;
    template5ShouldFail = false;
    template6ShouldFail = false;
    template5FooterNotes = '';
    templateDraftUpdateCount = 0;
    reportInstanceCreateResponseGate = null;
    releaseReportInstanceCreateResponse = null;
    lastReportInstanceCreatePayload = null;
    templateResolutionDelayByPatient = new Map();
    bulkSaveResponseGate = null;
    releaseBulkSaveResponse = null;
    templateDraftSaveResponseGate = null;
    releaseTemplateDraftSaveResponse = null;
    templateResolution101ResponseGate = null;
    releaseTemplateResolution101Response = null;
    templateResolutionPatientRequests = [];
    reportHistoryPatientRequests = [];
    history101ResponseGate = null;
    releaseHistory101Response = null;
    history102ResponseGate = null;
    releaseHistory102Response = null;
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
    // PR #3351: детерминированный gate вместо задержки: доказываем, что GET
    // первого отчёта уже начался, и только тогда кликаем второго пациента.
    instance88ResponseGate = new Promise<void>((resolve) => {
      releaseInstance88Response = resolve;
    });
    await page.goto('/lab');

    await queuePatientButton(page, 'Пациент Один').dispatchEvent('click');
    await expect.poll(() => instance88GetCount).toBe(1);
    await queuePatientButton(page, 'Пациент Два').dispatchEvent('click');

    await expect(page.getByText('Отчёт #89').first()).toBeVisible();
    const staleResponse = page.waitForResponse((response) => response.url().includes('/report-instances/88'));
    releaseInstance88Response?.();
    await staleResponse;
    await waitForReactToSettle(page);
    await expect(page.getByText('Отчёт #88')).toHaveCount(0);
    expect(instance88GetCount).toBe(1);
    expect(instance89GetCount).toBe(1);
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBe('89');
  });

  test('a late history response cannot replace the newly selected patient history', async ({ page }) => {
    history101ResponseGate = new Promise<void>((resolve) => {
      releaseHistory101Response = resolve;
    });
    await page.goto('/lab');

    await queuePatientButton(page, 'Пациент Один').dispatchEvent('click');
    await expect.poll(() => reportHistoryPatientRequests.includes('101')).toBe(true);
    await queuePatientButton(page, 'Пациент Два').dispatchEvent('click');

    await expect(page.getByText('Отчёт #89').first()).toBeVisible();
    const reportsPanel = page.locator('#lab-panel-tabpanel-reports');
    await expect(reportsPanel.getByText('Отчёт #history-102').first()).toBeVisible();
    const staleHistoryResponse = page.waitForResponse((response) => (
      response.url().includes('/report-instances?')
      && new URL(response.url()).searchParams.get('patient_id') === '101'
    ));
    releaseHistory101Response?.();
    await staleHistoryResponse;
    await waitForReactToSettle(page);

    await expect(reportsPanel.getByText('Отчёт #history-101')).toHaveCount(0);
    await expect(reportsPanel.getByText('Отчёт #history-102').first()).toBeVisible();
  });

  test('finishing target history cannot restore the previous report URL', async ({ page }) => {
    await page.goto('/lab');
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    await expect(page.getByText('Отчёт #88').first()).toBeVisible();
    const initialInstance88Requests = instance88GetCount;

    history102ResponseGate = new Promise<void>((resolve) => {
      releaseHistory102Response = resolve;
    });
    await page.getByRole('tab').first().click();
    await page.getByRole('button', { name: /Пациент Два/ }).first().click();
    await expect.poll(() => instance89GetCount).toBe(1);
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBe('89');
    await waitForReactToSettle(page);

    const targetHistoryResponse = page.waitForResponse((response) => (
      response.url().includes('/report-instances?')
      && new URL(response.url()).searchParams.get('patient_id') === '102'
    ));
    releaseHistory102Response?.();
    await targetHistoryResponse;
    await waitForReactToSettle(page);

    await expect(page.getByText('Отчёт #89').first()).toBeVisible();
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBe('89');
    expect(instance88GetCount).toBe(initialInstance88Requests);
  });

  test('a newer external URL intent supersedes an in-flight report load', async ({ page }) => {
    instance89ResponseGate = new Promise<void>((resolve) => {
      releaseInstance89Response = resolve;
    });
    await page.goto('/lab');
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    await expect(page.getByText('Отчёт #88').first()).toBeVisible();
    const fieldInput = page.getByLabel('Результат: Лейкоциты');

    await page.evaluate(() => {
      window.history.pushState({}, '', '/lab?instance=89');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });
    await expect.poll(() => instance89GetCount).toBe(1);
    await expect(fieldInput).toBeDisabled();
    await page.evaluate(() => {
      window.history.pushState({}, '', '/lab?instance=90');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });

    await expect(page.getByText('Отчёт #90').first()).toBeVisible();
    const staleResponse = page.waitForResponse((response) => response.url().includes('/report-instances/89'));
    releaseInstance89Response?.();
    await staleResponse;
    await waitForReactToSettle(page);
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBe('90');
    await expect(page.getByText('Отчёт #89')).toHaveCount(0);
  });

  test('a stale failed load cannot dismiss a newer guarded URL intent', async ({ page }) => {
    instance89ResponseGate = new Promise<void>((resolve) => {
      releaseInstance89Response = resolve;
    });
    instance89ShouldFail = true;
    await page.goto('/lab');
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    const fieldInput = page.getByLabel('Результат: Лейкоциты');
    await fieldInput.fill('7.2');
    await expect(page.getByText(/несохранённые изменения/).first()).toBeVisible();

    await page.evaluate(() => {
      window.history.pushState({}, '', '/lab?instance=89');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });
    let dialog = page.getByRole('dialog').filter({ hasText: 'Несохранённые изменения' });
    await expect(dialog).toBeVisible();
    await dialog.getByRole('button', { name: 'Выйти без сохранения' }).click();
    await expect.poll(() => instance89GetCount).toBe(1);

    await page.evaluate(() => {
      window.history.pushState({}, '', '/lab?instance=90');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });
    // PR #3351 discard contract: the report draft was reset by the first
    // Discard, so the newer 90 intent runs immediately — there is no second
    // confirmation dialog for the already-discarded draft, and no autosave
    // can resurrect it.
    const staleResponse = page.waitForResponse((response) => response.url().includes('/report-instances/89'));
    releaseInstance89Response?.();
    await staleResponse;
    await waitForReactToSettle(page);

    await expect(page.getByRole('dialog').filter({ hasText: 'Несохранённые изменения' })).toHaveCount(0);
    await expect(page.getByText(/несохранённые изменения/).first()).toHaveCount(0);
    await expect(page.getByText('Отчёт #90').first()).toBeVisible();
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBe('90');
  });

  test('a failed external report load restores the current report URL', async ({ page }) => {
    instance89ShouldFail = true;
    await page.goto('/lab');
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    await expect(page.getByText('Отчёт #88').first()).toBeVisible();
    const reportsPanel = page.locator('#lab-panel-tabpanel-reports');
    await expect(reportsPanel.getByText('Отчёт #history-101').first()).toBeVisible();
    const historyRequestsBeforeFailure = reportHistoryPatientRequests.filter((id) => id === '101').length;

    await page.evaluate(() => {
      window.history.pushState({}, '', '/lab?instance=89');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });

    await expect.poll(() => instance89GetCount).toBe(1);
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBe('88');
    await expect(page.getByText('Отчёт #88').first()).toBeVisible();
    await expect.poll(
      () => reportHistoryPatientRequests.filter((id) => id === '101').length,
    ).toBeGreaterThan(historyRequestsBeforeFailure);
    await expect(reportsPanel.getByText('Отчёт #history-101').first()).toBeVisible();
    const fieldInput = page.getByLabel('Результат: Лейкоциты');
    await fieldInput.fill('7.1');
    await page.getByRole('button', { name: 'Сохранить черновик' }).click();
    await expect.poll(() => bulkSavePostCount).toBe(1);
  });

  test('a failed queue report load keeps the selected patient and clears the stale report URL', async ({ page }) => {
    await page.goto('/lab');
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    await expect(page.getByText('Отчёт #88').first()).toBeVisible();
    instance89ShouldFail = true;

    await page.getByRole('tab').first().click();
    const failedResponse = page.waitForResponse((response) => (
      response.url().includes('/report-instances/89') && response.status() === 500
    ));
    await page.getByRole('button', { name: /Пациент Два/ }).first().click();
    await expect.poll(() => instance89GetCount).toBe(1);
    await failedResponse;
    await waitForReactToSettle(page);
    await expect.poll(() => new URL(page.url()).searchParams.get('patient')).toBe('102');
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBeNull();
    await expect(page.getByText('Отчёт #88')).toHaveCount(0);
    await expect.poll(() => reportHistoryPatientRequests.at(-1)).toBe('102');
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
    const breadcrumb = page.getByRole('navigation', { name: 'Навигация' });
    await expect(breadcrumb).toContainText('Пациент Два');
    await expect(breadcrumb).not.toContainText('Пациент Один');
    await page.waitForTimeout(300);
    await expect(page.getByText('Отчёт #88')).toHaveCount(0);
    expect(instance88GetCount).toBe(1);
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBe('89');
  });

  test('Cancel on an external URL transition restores the active report URL', async ({ page }) => {
    await page.goto('/lab');
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    const fieldInput = page.getByLabel('Результат: Лейкоциты');
    await fieldInput.fill('6.8');
    await expect(page.getByText(/несохранённые изменения/).first()).toBeVisible();

    await page.evaluate(() => {
      window.history.pushState({}, '', '/lab?instance=89');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });
    const dialog = page.getByRole('dialog').filter({ hasText: 'Несохранённые изменения' });
    await expect(dialog).toBeVisible();
    await dialog.getByRole('button', { name: 'Отмена' }).click();

    await expect(fieldInput).toHaveValue('6.8');
    await expect(page.getByText('Отчёт #88').first()).toBeVisible();
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBe('88');
    await expect.poll(() => new URL(page.url()).searchParams.get('patient')).toBe('101');
    expect(instance89GetCount).toBe(0);
  });

  test('Escape cancellation keeps the dirty report and current tab intact', async ({ page }) => {
    await page.goto('/lab');
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    const fieldInput = page.getByLabel('Результат: Лейкоциты');
    await fieldInput.fill('6.9');
    await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());

    await page.keyboard.press('Escape');
    const dialog = page.getByRole('dialog').filter({ hasText: 'Несохранённые изменения' });
    await expect(dialog).toBeVisible();
    await expect(page.getByRole('tablist', { name: 'Панель лаборатории' }).getByRole('tab').nth(2)).toHaveAttribute('aria-selected', 'true');
    await dialog.getByRole('button', { name: 'Отмена' }).click();

    await expect(fieldInput).toHaveValue('6.9');
    await expect(page.getByText('Отчёт #88').first()).toBeVisible();
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBe('88');
  });

  test('Escape closes an external URL guard once and rolls the URL back', async ({ page }) => {
    await page.goto('/lab');
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    const fieldInput = page.getByLabel('Результат: Лейкоциты');
    await fieldInput.fill('7.1');
    await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
    await page.evaluate(() => {
      window.history.pushState({}, '', '/lab?instance=89');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });
    const dialog = page.getByRole('dialog').filter({ hasText: 'Несохранённые изменения' });
    await expect(dialog).toBeVisible();

    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBe('88');
    await expect(fieldInput).toHaveValue('7.1');
    await waitForReactToSettle(page);
    await expect(page.getByRole('dialog').filter({ hasText: 'Несохранённые изменения' })).toHaveCount(0);
  });

  test('removing the report from the URL is guarded and Discard clears the active report', async ({ page }) => {
    await page.goto('/lab');
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    const fieldInput = page.getByLabel('Результат: Лейкоциты');
    await fieldInput.fill('6.9');
    await expect(page.getByText(/несохранённые изменения/).first()).toBeVisible();
    const historyRequestsBeforeClear = reportHistoryPatientRequests.length;

    await page.evaluate(() => {
      window.history.pushState({}, '', '/lab');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });
    const dialog = page.getByRole('dialog').filter({ hasText: 'Несохранённые изменения' });
    await expect(dialog).toBeVisible();
    await dialog.getByRole('button', { name: 'Выйти без сохранения' }).click();

    await expect(page.getByText('Отчёт #88')).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Создать отчёт' })).toBeVisible();
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBeNull();
    await expect.poll(() => reportHistoryPatientRequests.length).toBeGreaterThan(historyRequestsBeforeClear);
    expect(reportHistoryPatientRequests.at(-1)).toBe('101');
  });

  test('returning the URL to the active report dismisses the stale pending transition', async ({ page }) => {
    await page.goto('/lab');
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    const fieldInput = page.getByLabel('Результат: Лейкоциты');
    await fieldInput.fill('7.0');
    await expect(page.getByText(/несохранённые изменения/).first()).toBeVisible();

    await page.evaluate(() => {
      window.history.pushState({}, '', '/lab?instance=89');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });
    const dialog = page.getByRole('dialog').filter({ hasText: 'Несохранённые изменения' });
    await expect(dialog).toBeVisible();
    // Транзиент pre-existing: даём urlIntent-флоу панели зафиксироваться
    // (pendingUrlIntent + URL-sync) до второго внешнего перехода — иначе
    // под нагрузкой полный прогон гонит два popstate в один кадр.
    await waitForReactToSettle(page);
    await page.evaluate(() => {
      window.history.pushState({}, '', '/lab?patient=101&instance=88');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });

    await expect(dialog).toHaveCount(0);
    await expect(fieldInput).toHaveValue('7.0');
    await expect(page.getByText('Отчёт #88').first()).toBeVisible();
    expect(instance89GetCount).toBe(0);
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
    reportInstanceCreateResponseGate = new Promise<void>((resolve) => {
      releaseReportInstanceCreateResponse = resolve;
    });
    await page.goto('/lab');
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    await expect(page.getByText('Отчёт #88').first()).toBeVisible();

    await page.getByRole('button', { name: 'Добавить бланк' }).click();
    await expect.poll(() => reportInstanceCreatePostCount).toBe(1);
    await page.getByRole('tab').first().click();
    await page.getByRole('button', { name: /Пациент Два/ }).first().click();
    await expect(page.getByText('Отчёт #89').first()).toBeVisible();

    const createResponse = page.waitForResponse((response) => (
      response.request().method() === 'POST'
      && response.url().endsWith('/api/v1/lab/report-instances')
    ));
    releaseReportInstanceCreateResponse?.();
    await createResponse;
    await waitForReactToSettle(page);
    await expect.poll(() => reportHistoryPatientRequests.at(-1)).toBe('102');
    await expect(page.getByText('Отчёт #90')).toHaveCount(0);
    await expect(page.getByText('Отчёт #89').first()).toBeVisible();
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBe('89');
    expect(reportHistoryPatientRequests.at(-1)).toBe('102');
  });

  test('a URL instance change under a dirty template loads the report without a dialog and keeps the template draft', async ({ page }) => {
    reportInstanceCreateResponseGate = new Promise<void>((resolve) => {
      releaseReportInstanceCreateResponse = resolve;
    });
    await page.goto('/lab');
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    await expect(page.getByText('Отчёт #88').first()).toBeVisible();

    await page.getByRole('button', { name: 'Добавить бланк' }).click();
    await expect.poll(() => reportInstanceCreatePostCount).toBe(1);

    const panelTabs = page.getByRole('tablist', { name: 'Панель лаборатории' });
    await panelTabs.getByRole('tab').nth(1).click();
    await page.getByRole('tab', { name: 'Оформление' }).click();
    const footerInput = page.getByLabel('Подвал шаблона');
    await footerInput.fill('Несохранённый подвал');
    // У шаблонного workbench нет видимого dirty-бейджа (в отличие от отчёта) —
    // даём notify-эффекту зафиксировать dirty в реестре guard-а.
    await waitForReactToSettle(page);

    // PR 3351 (review round 2, P1): смена report instance из внешнего URL —
    // report-скоуп: dirty template-draft не спрашивается и не сбрасывается.
    await page.evaluate(() => {
      window.history.pushState({}, '', '/lab?instance=89');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });

    // Диалога нет: report-draft чист, template-draft вне области перехода.
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(page.getByText('Отчёт #89').first()).toBeVisible();
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBe('89');

    const createResponse = page.waitForResponse((response) => (
      response.request().method() === 'POST'
      && response.url().endsWith('/api/v1/lab/report-instances')
    ));
    releaseReportInstanceCreateResponse?.();
    await createResponse;
    await waitForReactToSettle(page);

    // Поздний create не может затереть URL intent (latest-wins по
    // operation-context), а template-draft пережил смену отчёта.
    await expect(page.getByText('Отчёт #89').first()).toBeVisible();
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBe('89');
    await expect(footerInput).toHaveValue('Несохранённый подвал');
  });

  test('a dirty template survives a URL instance change without a guard dialog', async ({ page }) => {
    await page.goto('/lab');
    await page.waitForTimeout(700);
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    await expect(page.getByText('Отчёт #88').first()).toBeVisible();

    const panelTabs = page.getByRole('tablist', { name: 'Панель лаборатории' });
    await panelTabs.getByRole('tab').nth(1).click();
    await page.getByRole('tab', { name: 'Оформление' }).click();
    const footerInput = page.getByLabel('Подвал шаблона');
    await footerInput.fill('Несохранённый подвал');
    await waitForReactToSettle(page);

    await page.evaluate(() => {
      window.history.pushState({}, '', '/lab?instance=89');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });

    // PR 3351 (review round 2, P1, сценарий B): смена report instance
    // (browser Back/Forward между ?instance=) не сбрасывает template-draft.
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(page.getByText('Отчёт #89').first()).toBeVisible();
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBe('89');

    await panelTabs.getByRole('tab').nth(1).click();
    await expect(footerInput).toHaveValue('Несохранённый подвал');
  });

  test('dirty report -> template Clone runs without a guard dialog and preserves the report draft', async ({ page }) => {
    await page.route('**/api/v1/lab/templates/5/clone', (route) => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ id: 7, code: 'rule_demo_copy', name: 'Rule Demo (копия)' }),
    }));
    await page.goto('/lab');
    await page.waitForTimeout(700);
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    const fieldInput = page.getByLabel('Результат: Лейкоциты');
    await expect(fieldInput).toBeVisible();
    await page.waitForTimeout(700);
    await fieldInput.fill('6.5');
    await expect(page.getByText(/несохранённые изменения/).first()).toBeVisible();

    const panelTabs = page.getByRole('tablist', { name: 'Панель лаборатории' });
    await panelTabs.getByRole('tab').nth(1).click();

    // PR 3351 (review round 2, P1, сценарий A): clone меняет только шаблон
    // (template-скоуп) — dirty report-draft не спрашивается и не сбрасывается.
    const cloneResponse = page.waitForResponse((response) => (
      response.request().method() === 'POST'
      && response.url().endsWith('/api/v1/lab/templates/5/clone')
    ));
    await page.getByRole('button', { name: 'Клонировать' }).click();
    await cloneResponse;
    await waitForReactToSettle(page);

    await expect(page.getByRole('dialog')).toHaveCount(0);
    await panelTabs.getByRole('tab').nth(2).click();
    await expect(fieldInput).toHaveValue('6.5');
    await expect(page.getByText(/несохранённые изменения/).first()).toBeVisible();
  });

  test('route leave via header Profile is guarded while a lab draft is dirty', async ({ page }) => {
    await page.goto('/lab');
    await page.waitForTimeout(700);
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    const fieldInput = page.getByLabel('Результат: Лейкоциты');
    await expect(fieldInput).toBeVisible();
    await page.waitForTimeout(700);
    await fieldInput.fill('6.5');
    await expect(page.getByText(/несохранённые изменения/).first()).toBeVisible();

    // PR 3351 (review round 2, P1): SPA-уход с /lab (Header → Profile) больше
    // не обходит dirty-guard.
    await page.getByRole('button', { name: 'Профиль пользователя' }).click();
    await page.getByRole('menuitem', { name: 'Профиль' }).click();

    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await dialog.getByRole('button', { name: 'Отмена' }).click();
    await expect(dialog).toBeHidden();

    // Отмена: остались на /lab, черновик и контекст нетронуты.
    await expect(page.getByText('Отчёт #88').first()).toBeVisible();
    await expect(fieldInput).toHaveValue('6.5');
    expect(new URL(page.url()).pathname).toBe('/lab');

    // Подтверждённый уход: discard → профиль открывается.
    await page.getByRole('button', { name: 'Профиль пользователя' }).click();
    await page.getByRole('menuitem', { name: 'Профиль' }).click();
    await expect(dialog).toBeVisible();
    await dialog.getByRole('button', { name: 'Выйти без сохранения' }).click();
    await expect.poll(() => new URL(page.url()).pathname).not.toBe('/lab');
  });

  test('browser Back to the previous route is guarded while a lab draft is dirty', async ({ page }) => {
    // Реальная история: /health -> /lab (in-lab переходы используют replace
    // и не создают записей, поэтому запись под /lab — предыдущая страница).
    await page.goto('/health');
    await page.goto('/lab');
    await page.waitForTimeout(700);
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    const fieldInput = page.getByLabel('Результат: Лейкоциты');
    await expect(fieldInput).toBeVisible();
    await page.waitForTimeout(700);
    await fieldInput.fill('6.5');
    await expect(page.getByText(/несохранённые изменения/).first()).toBeVisible();

    // PR 3351 (review round 2, P1): browser Back вытесняет sentinel — pop
    // абсорбируется на том же /lab URL, guard-диалог спрашивает решение.
    await page.evaluate(() => window.history.back());
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await dialog.getByRole('button', { name: 'Отмена' }).click();
    await expect(dialog).toBeHidden();

    await expect(page.getByText('Отчёт #88').first()).toBeVisible();
    await expect(fieldInput).toHaveValue('6.5');
    expect(new URL(page.url()).pathname).toBe('/lab');

    // Подтверждённый уход: discard → реальная предыдущая страница.
    await page.evaluate(() => window.history.back());
    await expect(dialog).toBeVisible();
    await dialog.getByRole('button', { name: 'Выйти без сохранения' }).click();
    await expect.poll(() => new URL(page.url()).pathname).toBe('/health');
  });

  test('logout waits for the guard confirmation and keeps the session on cancel', async ({ page }) => {
    await page.goto('/lab');
    await page.waitForTimeout(700);
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    const fieldInput = page.getByLabel('Результат: Лейкоциты');
    await expect(fieldInput).toBeVisible();
    await page.waitForTimeout(700);
    await fieldInput.fill('6.5');
    await expect(page.getByText(/несохранённые изменения/).first()).toBeVisible();

    // PR 3351 (review round 2, P1): logout очищает токен ТОЛЬКО после
    // подтверждённого перехода (onLeave), не до него.
    await page.getByRole('button', { name: 'Профиль пользователя' }).click();
    await page.locator('#logout-header-btn').click();

    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await dialog.getByRole('button', { name: 'Отмена' }).click();
    await expect(dialog).toBeHidden();

    const tokenAfterCancel = await page.evaluate(() => window.sessionStorage.getItem('auth_token'));
    expect(tokenAfterCancel).toBeTruthy();
    expect(new URL(page.url()).pathname).toBe('/lab');
    await expect(fieldInput).toHaveValue('6.5');

    await page.getByRole('button', { name: 'Профиль пользователя' }).click();
    await page.locator('#logout-header-btn').click();
    await expect(dialog).toBeVisible();
    await dialog.getByRole('button', { name: 'Выйти без сохранения' }).click();

    await expect.poll(() => page.evaluate(() => window.sessionStorage.getItem('auth_token'))).toBeNull();
    await expect.poll(() => new URL(page.url()).pathname).not.toBe('/lab');
  });

  // ─── PR 3351, review round 3 ────────────────────────────────────────────────
  // P1: центр уведомлений обходит guard; route identity вместо /lab/*-префикса;
  // pending-only операция не блокирует уход; P2: фантомная sentinel-запись.

  test('notification center navigation is guarded while a lab draft is dirty (review round 3)', async ({ page }) => {
    await page.route('**/api/v1/notifications/inbox**', (route) => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [{
          id: 501,
          type: 'message_received',
          title: 'Новое сообщение',
          message: 'Сообщение от регистратора',
          created_at: '2026-09-13T09:00:00+00:00',
          role: 'lab',
          payload_snapshot: { metadata: { conversation_id: 77 } },
        }],
      }),
    }));
    await page.goto('/lab');
    await page.waitForTimeout(700);
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    const fieldInput = page.getByLabel('Результат: Лейкоциты');
    await expect(fieldInput).toBeVisible();
    await page.waitForTimeout(700);
    await fieldInput.fill('6.5');
    await expect(page.getByText(/несохранённые изменения/).first()).toBeVisible();

    // Колокольчик → центр уведомлений → клик по уведомлению message_received.
    // Прежний прямой обход History API выполнял переход молча: LabPanel
    // размонтировалась без решения пользователя.
    await page.getByRole('button', { name: 'Уведомления', exact: true }).click();
    const inbox = page.getByRole('dialog', { name: 'Центр уведомлений' });
    await expect(inbox).toBeVisible();
    await page.getByRole('button', { name: 'Открыть уведомление: Новое сообщение' }).click();

    // Guard-диалог открыт (кнопка «Выйти без сохранения» уникальна для него),
    // URL остался /lab.
    const guardDiscard = page.getByRole('button', { name: 'Выйти без сохранения' });
    await expect(guardDiscard).toBeVisible();
    expect(new URL(page.url()).pathname).toBe('/lab');

    // Отмена: черновик и контекст нетронуты.
    await page.getByRole('button', { name: 'Отмена' }).click();
    await expect(guardDiscard).toHaveCount(0);
    await expect(fieldInput).toHaveValue('6.5');
    expect(new URL(page.url()).pathname).toBe('/lab');

    // Подтверждённый уход: discard → переход по цели уведомления.
    await page.getByRole('button', { name: 'Открыть уведомление: Новое сообщение' }).click();
    await expect(guardDiscard).toBeVisible();
    await guardDiscard.click();
    await expect.poll(() => new URL(page.url()).pathname, { timeout: 4000 }).not.toBe('/lab');
  });

  test('notification lab_results deep-link asks the guard instead of unmounting the panel (review round 3)', async ({ page }) => {
    await page.route('**/api/v1/notifications/inbox**', (route) => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [{
          id: 502,
          type: 'lab_results',
          title: 'Готовы результаты',
          message: 'Результаты анализов готовы',
          created_at: '2026-09-13T09:05:00+00:00',
          role: 'lab',
          payload_snapshot: { metadata: {} },
        }],
      }),
    }));
    await page.goto('/lab');
    await page.waitForTimeout(700);
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    const fieldInput = page.getByLabel('Результат: Лейкоциты');
    await expect(fieldInput).toBeVisible();
    await page.waitForTimeout(700);
    await fieldInput.fill('6.5');
    await expect(page.getByText(/несохранённые изменения/).first()).toBeVisible();

    // '/lab/results' НЕ является зарегистрированным маршрутом: wildcard уводит
    // на /not-found и размонтирует панель. Route identity обязан считать это
    // уходом — guard-диалог, а не молчаливая потеря черновика.
    await page.getByRole('button', { name: 'Уведомления', exact: true }).click();
    const inbox = page.getByRole('dialog', { name: 'Центр уведомлений' });
    await expect(inbox).toBeVisible();
    await page.getByRole('button', { name: 'Открыть уведомление: Готовы результаты' }).click();

    const guardDiscard = page.getByRole('button', { name: 'Выйти без сохранения' });
    await expect(guardDiscard).toBeVisible();
    expect(new URL(page.url()).pathname).toBe('/lab');
    await expect(page.getByText('Отчёт #88').first()).toBeVisible();

    // Отмена: отчёт и введённое значение на месте.
    await page.getByRole('button', { name: 'Отмена' }).click();
    await expect(guardDiscard).toHaveCount(0);
    await expect(page.getByText('Отчёт #88').first()).toBeVisible();
    await expect(fieldInput).toHaveValue('6.5');
    expect(new URL(page.url()).pathname).toBe('/lab');
  });

  test('pending-only clone blocks Profile/logout leave until the operation completes (review round 3)', async ({ page }) => {
    let releaseClone: () => void = () => {};
    const cloneGate = new Promise<void>((resolve) => { releaseClone = resolve; });
    await page.route('**/api/v1/lab/templates/5/clone', async (route) => {
      await cloneGate;
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ id: 7, code: 'rule_demo_copy', name: 'Rule Demo (копия)' }),
      });
    });
    await page.goto('/lab');
    await page.waitForTimeout(700);
    // Открываем отчёт (шаблон 5 становится выбранным), но НЕ редактируем:
    // оба черновика чистые — блокирует только pending-операция.
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    await expect(page.getByLabel('Результат: Лейкоциты')).toBeVisible();
    await page.waitForTimeout(700);

    const panelTabs = page.getByRole('tablist', { name: 'Панель лаборатории' });
    await panelTabs.getByRole('tab').nth(1).click();
    const cloneButton = page.getByRole('button', { name: 'Клонировать' });

    // waitForRequest (не waitForResponse): gated-роут не отвечает, пока
    // тест не отпустит гейт — сам факт отправки POST-а и есть pending.
    const cloneSent = page.waitForRequest((request) => (
      request.method() === 'POST'
      && request.url().endsWith('/api/v1/lab/templates/5/clone')
    ));
    await cloneButton.click();
    await cloneSent;
    // POST отправлен и «висит» — операция pending, черновики чистые.
    await expect(cloneButton).toBeDisabled();

    // Profile во время pending: уход заблокирован (pending-контракт, без
    // guard-диалога), пользователь остаётся на /lab.
    await page.getByRole('button', { name: 'Профиль пользователя' }).click();
    await page.getByRole('menuitem', { name: 'Профиль' }).click();
    await expect(page.getByRole('button', { name: 'Выйти без сохранения' })).toHaveCount(0);
    await expect(page.getByText('сохраняется…').first()).toBeVisible();
    await page.waitForTimeout(400);
    expect(new URL(page.url()).pathname).toBe('/lab');

    // Logout во время pending: токен НЕ очищается (onLeave не выполнялся).
    await page.getByRole('button', { name: 'Профиль пользователя' }).click();
    await page.locator('#logout-header-btn').click();
    await expect(page.getByRole('button', { name: 'Выйти без сохранения' })).toHaveCount(0);
    await page.waitForTimeout(400);
    const tokenDuringPending = await page.evaluate(() => window.sessionStorage.getItem('auth_token'));
    expect(tokenDuringPending).toBeTruthy();
    expect(new URL(page.url()).pathname).toBe('/lab');

    // Операция завершена: pending снят, уход проходит без диалога.
    releaseClone();
    await expect(cloneButton).toBeEnabled();
    await waitForReactToSettle(page);
    await page.getByRole('button', { name: 'Профиль пользователя' }).click();
    await page.getByRole('menuitem', { name: 'Профиль' }).click();
    await expect.poll(() => new URL(page.url()).pathname, { timeout: 4000 }).not.toBe('/lab');
  });

  test('browser Back is absorbed while a clean template clone is pending (review round 3)', async ({ page }) => {
    let releaseClone: () => void = () => {};
    const cloneGate = new Promise<void>((resolve) => { releaseClone = resolve; });
    await page.route('**/api/v1/lab/templates/5/clone', async (route) => {
      await cloneGate;
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ id: 7, code: 'rule_demo_copy', name: 'Rule Demo (копия)' }),
      });
    });
    // Реальная история: /health -> /lab.
    await page.goto('/health');
    await page.goto('/lab');
    await page.waitForTimeout(700);
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    await expect(page.getByLabel('Результат: Лейкоциты')).toBeVisible();
    await page.waitForTimeout(700);

    const panelTabs = page.getByRole('tablist', { name: 'Панель лаборатории' });
    await panelTabs.getByRole('tab').nth(1).click();
    const cloneButton = page.getByRole('button', { name: 'Клонировать' });
    const cloneSent = page.waitForRequest((request) => (
      request.method() === 'POST'
      && request.url().endsWith('/api/v1/lab/templates/5/clone')
    ));
    await cloneButton.click();
    await cloneSent;
    await expect(cloneButton).toBeDisabled();

    // Browser Back во время pending: sentinel (dirty||pending) вытесняется,
    // pop абсорбируется, pending-блок оставляет пользователя на /lab.
    await page.evaluate(() => window.history.back());
    await expect(page.getByRole('button', { name: 'Выйти без сохранения' })).toHaveCount(0);
    await expect(page.getByText('сохраняется…').first()).toBeVisible();
    await page.waitForTimeout(400);
    expect(new URL(page.url()).pathname).toBe('/lab');

    // Операция завершена → sentinel свёрнут (фантомной записи нет) →
    // ОДИН Back уходит на реальную предыдущую страницу.
    releaseClone();
    await expect(cloneButton).toBeEnabled();
    await waitForReactToSettle(page);
    await page.waitForTimeout(300);
    await page.evaluate(() => window.history.back());
    await expect.poll(() => new URL(page.url()).pathname, { timeout: 4000 }).toBe('/health');
  });

  test('browser Back after a manual save leaves the lab in one press (review round 3)', async ({ page }) => {
    // PR 3351 (review round 3, P2): sentinel не оставляет фантомную запись —
    // после Save (draft стал clean) ОДНО нажатие Back уходит на предыдущую
    // страницу, а не на молчаливый дубликат /lab.
    await page.goto('/health');
    await page.goto('/lab');
    await page.waitForTimeout(700);
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    const fieldInput = page.getByLabel('Результат: Лейкоциты');
    await expect(fieldInput).toBeVisible();
    await page.waitForTimeout(700);
    await fieldInput.fill('6.5');
    await expect(page.getByText(/несохранённые изменения/).first()).toBeVisible();

    await page.getByRole('button', { name: 'Сохранить черновик' }).click();
    await expect.poll(() => bulkSavePostCount).toBe(1);
    // Сохранение завершено: dirty снят, sentinel свёрнут.
    await expect(page.getByText(/несохранённые изменения/).first()).toBeHidden();
    await waitForReactToSettle(page);
    await page.waitForTimeout(300);

    await page.evaluate(() => window.history.back());
    await expect.poll(() => new URL(page.url()).pathname, { timeout: 4000 }).toBe('/health');
  });

  test('Back after a confirmed Profile leave returns to the lab without a phantom duplicate (review round 3)', async ({ page }) => {
    // PR 3351 (review round 3, P2): подтверждённый SPA-уход ЗАМЕНЯЕТ
    // sentinel-запись (navigate replace): Back возвращается на реальный /lab,
    // второй Back — на предыдущую страницу; дубликата /lab в истории нет.
    await page.goto('/health');
    await page.goto('/lab');
    await page.waitForTimeout(700);
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    const fieldInput = page.getByLabel('Результат: Лейкоциты');
    await expect(fieldInput).toBeVisible();
    await page.waitForTimeout(700);
    await fieldInput.fill('6.5');
    await expect(page.getByText(/несохранённые изменения/).first()).toBeVisible();

    await page.getByRole('button', { name: 'Профиль пользователя' }).click();
    await page.getByRole('menuitem', { name: 'Профиль' }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await dialog.getByRole('button', { name: 'Выйти без сохранения' }).click();
    await expect.poll(() => new URL(page.url()).pathname, { timeout: 4000 }).not.toBe('/lab');

    // Первый Back: возврат на /lab (панель перемонтируется — черновик был
    // сброшен осознанно).
    await page.evaluate(() => window.history.back());
    await expect.poll(() => new URL(page.url()).pathname, { timeout: 4000 }).toBe('/lab');
    // Второй Back: предыдущая страница — БЕЗ промежуточного дубля /lab
    // (фантомная sentinel-запись заменена, а не запушена поверх).
    await page.evaluate(() => window.history.back());
    await expect.poll(() => new URL(page.url()).pathname, { timeout: 4000 }).toBe('/health');
  });

  // ─── PR 3351, review round 4 ────────────────────────────────────────────────
  // P1: route identity строго по matcher'у React Router (trailing-slash /lab/);
  // P2: query-sidebar навигация не создаёт history-записей (replace) —
  // инвариант sentinel «один Back после Save» и «Back без устаревшей копии».

  test('browser Back guard works on the trailing-slash /lab/ URL (review round 4)', async ({ page }) => {
    // PR 3351 (review round 4, P1): '/lab/' не канонизируется (Vercel отдаёт
    // index.html как есть), но React Router матчит его маршруту '/lab' и
    // продолжает рендерить LabPanel. Guard обязан считать такой URL «в /lab»:
    // прежде findRouteByPath сравнивал строки, sentinel не вооружался, и
    // browser Back молча размонтировал панель с dirty-черновиком.
    //
    // Deep-link с уже готовыми параметрами (?tab=templates): sync-эффект
    // панели пишет URL только при изменении params — адрес остаётся '/lab/'
    // на всё время редактирования шаблона, и sentinel вооружается именно на
    // trailing-slash URL.
    await page.goto('/health');
    await page.goto('/lab/?tab=templates');
    expect(new URL(page.url()).pathname).toBe('/lab/');
    await page.waitForTimeout(700);

    await page.getByRole('tab', { name: 'Оформление' }).click();
    const footerInput = page.getByLabel('Подвал шаблона');
    await expect(footerInput).toBeEnabled();
    await footerInput.fill('Несохранённый подвал');
    // У шаблонного workbench нет видимого dirty-бейджа — даём notify-эффекту
    // зафиксировать dirty в реестре guard-а.
    await waitForReactToSettle(page);
    expect(new URL(page.url()).pathname).toBe('/lab/');

    // Sentinel вооружён и на '/lab/': Back вытесняет его, pop абсорбируется
    // на том же URL, guard-диалог спрашивает решение.
    await page.evaluate(() => window.history.back());
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await dialog.getByRole('button', { name: 'Отмена' }).click();
    await expect(dialog).toBeHidden();

    // Отмена: панель смонтирована на trailing-slash URL, черновик жив.
    await expect(footerInput).toHaveValue('Несохранённый подвал');
    expect(new URL(page.url()).pathname).toBe('/lab/');

    // Подтверждённый уход: sentinel + дубль → реальная предыдущая страница.
    await page.evaluate(() => window.history.back());
    await expect(dialog).toBeVisible();
    await dialog.getByRole('button', { name: 'Выйти без сохранения' }).click();
    await expect.poll(() => new URL(page.url()).pathname, { timeout: 4000 }).toBe('/health');
  });

  test('a sidebar tab switch keeps history clean: one Back after Save leaves the lab (review round 4)', async ({ page }) => {
    // PR 3351 (review round 4, P2): query-навигация sidebar (смена ?tab) —
    // replace, не push. Push создавал запись поверх sentinel'а и ломал
    // контракт «после Save один Back уходит на предыдущую страницу»: первый
    // Back молча приземлялся на помеченную копию под sentinel.
    await page.goto('/health');
    await page.goto('/lab');
    await page.waitForTimeout(700);
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    const fieldInput = page.getByLabel('Результат: Лейкоциты');
    await expect(fieldInput).toBeVisible();
    await page.waitForTimeout(700);
    await fieldInput.fill('6.5');
    await expect(page.getByText(/несохранённые изменения/).first()).toBeVisible();

    // Смена вкладки через SIDEBAR (query-навигация) при dirty-черновике:
    // in-lab переход без диалога и — с фиксом — без новой history-записи.
    // Открытие отчёта само переключает панель на вкладку reports (Бланки) —
    // возвращаемся к редактору отчёта через sidebar.
    const sidebarNav = page.locator('.mac-sidebar-nav');
    await sidebarNav.getByRole('button', { name: 'Шаблоны' }).click();
    await expect.poll(() => new URL(page.url()).searchParams.get('tab')).toBe('templates');
    // Dirty-черновик отчёта пережил смену вкладки (workbench смонтирован в
    // скрытой секции): возвращаемся на вкладку отчёта и сохраняем.
    await sidebarNav.getByRole('button', { name: 'Бланки' }).click();
    await expect.poll(() => new URL(page.url()).searchParams.get('tab')).toBe('reports');
    await expect(fieldInput).toBeVisible();
    await expect(fieldInput).toHaveValue('6.5');
    await expect(page.getByText(/несохранённые изменения/).first()).toBeVisible();

    await page.getByRole('button', { name: 'Сохранить черновик' }).click();
    await expect.poll(() => bulkSavePostCount).toBe(1);
    await expect(page.getByText(/несохранённые изменения/).first()).toBeHidden();
    await waitForReactToSettle(page);
    await page.waitForTimeout(300);

    // ОДИН Back уходит на реальную предыдущую страницу: две смены вкладки не
    // добавили записей — под sentinel осталась ровно одна /lab-запись.
    await page.evaluate(() => window.history.back());
    await expect.poll(() => new URL(page.url()).pathname, { timeout: 4000 }).toBe('/health');
  });

  test('after a sidebar tab switch a confirmed Profile leave keeps exactly one lab history entry (review round 4)', async ({ page }) => {
    // PR 3351 (review round 4, P2): подтверждённый SPA-уход заменяет
    // sentinel-запись. При push-навигации sidebar под заменённой записью
    // оставалась помеченная копия: Back возвращал пользователя на устаревший
    // /lab-дубль, и только следующий Back — на реальную запись.
    await page.goto('/health');
    await page.goto('/lab');
    await page.waitForTimeout(700);
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    const fieldInput = page.getByLabel('Результат: Лейкоциты');
    await expect(fieldInput).toBeVisible();
    await page.waitForTimeout(700);
    await fieldInput.fill('6.5');
    await expect(page.getByText(/несохранённые изменения/).first()).toBeVisible();

    // Смена вкладки через sidebar при dirty-черновике (replace — записей нет).
    await page.locator('.mac-sidebar-nav').getByRole('button', { name: 'Шаблоны' }).click();
    await expect.poll(() => new URL(page.url()).searchParams.get('tab')).toBe('templates');

    // Подтверждённый уход: discard → профиль.
    await page.getByRole('button', { name: 'Профиль пользователя' }).click();
    await page.getByRole('menuitem', { name: 'Профиль' }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await dialog.getByRole('button', { name: 'Выйти без сохранения' }).click();
    await expect.poll(() => new URL(page.url()).pathname, { timeout: 4000 }).not.toBe('/lab');

    // Первый Back: РОВНО одна /lab-запись — реальная запись с вкладкой
    // отчёта (не устаревшая копия с ?tab=templates под заменённым sentinel;
    // открытие отчёта само переключает панель на tab=reports).
    await page.evaluate(() => window.history.back());
    await expect.poll(() => new URL(page.url()).pathname, { timeout: 4000 }).toBe('/lab');
    expect(new URL(page.url()).searchParams.get('tab')).toBe('reports');
    // Второй Back: предыдущая страница — без промежуточного /lab-дубля.
    await page.evaluate(() => window.history.back());
    await expect.poll(() => new URL(page.url()).pathname, { timeout: 4000 }).toBe('/health');
  });

  test('late create from another appointment of the same patient is rejected', async ({ page }) => {
    reportInstanceCreateResponseGate = new Promise<void>((resolve) => {
      releaseReportInstanceCreateResponse = resolve;
    });
    await page.goto('/lab');

    await page.getByRole('button', { name: /Пациент Без Бланка/ }).first().click();
    await expect(page.getByRole('button', { name: 'Создать отчёт' })).toBeVisible();
    await page.getByRole('button', { name: 'Создать отчёт' }).click();
    await expect.poll(() => reportInstanceCreatePostCount).toBe(1);

    await page.getByRole('tab').first().click();
    await page.getByRole('button', { name: /Пациент Без Бланка Повтор/ }).click();
    // The workbench keeps the in-flight create disabled until its response
    // settles, even after the appointment context changes.
    await expect(page.getByRole('button', { name: 'Создаю...' })).toBeDisabled();
    const createResponse = page.waitForResponse((response) => (
      response.request().method() === 'POST'
      && response.url().endsWith('/api/v1/lab/report-instances')
    ));
    releaseReportInstanceCreateResponse?.();
    await createResponse;
    await waitForReactToSettle(page);
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBeNull();

    await expect(page.getByText('Отчёт #90')).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Создать отчёт' })).toBeVisible();
    expect(lastReportInstanceCreatePayload).toMatchObject({ appointment_id: 'a-3' });
  });

  test('late template resolution cannot contaminate the next patient create payload', async ({ page }) => {
    templateResolution101ResponseGate = new Promise<void>((resolve) => {
      releaseTemplateResolution101Response = resolve;
    });
    await page.goto('/lab');

    await queuePatientButton(page, 'Пациент Один').dispatchEvent('click');
    await expect.poll(() => templateResolutionPatientRequests.includes('101')).toBe(true);
    await queuePatientButton(page, 'Пациент Два').dispatchEvent('click');
    await expect(page.getByText('Отчёт #89').first()).toBeVisible();
    await expect.poll(() => templateResolutionPatientRequests.includes('102')).toBe(true);
    const staleResolutionResponse = page.waitForResponse((response) => {
      if (!response.url().endsWith('/api/v1/lab/template-resolutions/resolve')) return false;
      return String(response.request().postDataJSON()?.patient_id ?? '') === '101';
    });
    releaseTemplateResolution101Response?.();
    await staleResolutionResponse;
    await waitForReactToSettle(page);

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

  test('late template detail cannot replace the newly created template', async ({ page }) => {
    template5FirstResponseGate = new Promise<void>((resolve) => {
      releaseTemplate5FirstResponse = resolve;
    });
    await page.goto('/lab?tab=templates');
    await expect.poll(() => template5GetCount).toBe(1);

    await page.getByRole('button', { name: 'Новый' }).click();
    await page.getByLabel('Код шаблона').fill('new_rule_t');
    await page.getByLabel('Название шаблона').fill('Новый шаблон правил');
    await page.getByRole('button', { name: 'Создать' }).click();

    await expect(page.getByText('new_rule_t').first()).toBeVisible();
    const staleTemplateResponse = page.waitForResponse((response) => response.url().endsWith('/api/v1/lab/templates/5'));
    releaseTemplate5FirstResponse?.();
    await staleTemplateResponse;
    await waitForReactToSettle(page);
    await expect(page.getByText('new_rule_t').first()).toBeVisible();
    expect(templateCreatePostCount).toBe(1);
  });

  test('template editor stays locked until a selected template detail finishes loading', async ({ page }) => {
    await page.goto('/lab?tab=templates');
    await page.getByRole('tab', { name: 'Оформление' }).click();
    const footerInput = page.getByLabel('Подвал шаблона');
    await expect(footerInput).toBeEnabled();

    template5ResponseGate = new Promise<void>((resolve) => {
      releaseTemplate5Response = resolve;
    });
    const detailResponse = page.waitForResponse((response) => (
      response.url().endsWith('/api/v1/lab/templates/5') && response.status() === 200
    ));
    await page.getByRole('button', { name: /Rule Demo/ }).first().click();
    await expect.poll(() => template5GetCount).toBe(2);
    await expect(footerInput).toBeDisabled();

    releaseTemplate5Response?.();
    await detailResponse;
    await waitForReactToSettle(page);
    await expect(footerInput).toBeEnabled();
  });

  test('failed template detail restores the previous editable template', async ({ page }) => {
    await page.goto('/lab?tab=templates');
    const fieldButton = page.getByRole('button', { name: /Поле: Лейкоциты/ });
    await expect(fieldButton).toBeVisible();
    template5ShouldFail = true;
    const failedDetail = page.waitForResponse((response) => (
      response.url().endsWith('/api/v1/lab/templates/5') && response.status() === 500
    ));

    await page.getByRole('button', { name: /Rule Demo/ }).first().click();
    await failedDetail;
    await waitForReactToSettle(page);

    await expect(fieldButton).toBeVisible();
    await expect(page.getByRole('button', { name: 'Новый' })).toBeEnabled();
  });

  test('failed target template keeps the freshly saved source draft', async ({ page }) => {
    await page.goto('/lab?tab=templates');
    await page.getByRole('tab', { name: 'Оформление' }).click();
    const footerInput = page.getByLabel('Подвал шаблона');
    await footerInput.fill('Сохранённый подвал A');
    template6ShouldFail = true;

    await page.getByRole('button', { name: /Rule Demo B/ }).first().click();
    const dialog = page.getByRole('dialog').filter({ hasText: 'Несохранённые изменения' });
    await expect(dialog).toBeVisible();
    const failedTarget = page.waitForResponse((response) => (
      response.url().endsWith('/api/v1/lab/templates/6') && response.status() === 500
    ));
    await dialog.getByRole('button', { name: 'Сохранить и перейти' }).click();
    await failedTarget;
    await waitForReactToSettle(page);

    expect(templateDraftUpdateCount).toBe(1);
    expect(template5FooterNotes).toBe('Сохранённый подвал A');
    await expect(footerInput).toHaveValue('Сохранённый подвал A');
    await expect(page.getByRole('button', { name: 'Новый' })).toBeEnabled();
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
    // Транзиент tab-sync (pre-existing): после двух быстрых переключений
    // вкладок панель может отставать на шаг — ждём фактической видимости
    // вкладки шаблонов перед поиском кнопки «Новый».
    await expect(page.locator('#lab-panel-tabpanel-templates')).toBeVisible();
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

  // PR #3351 (P1 — pending-контракт): report SAVE блокирует контекстный
  // переход затрагиваемого источника — нет ни разрушительного перехода,
  // ни повторной записи; после завершения сохранения пользователь
  // остаётся на прежнем отчёте. Template SAVE аналогично блокирует смену
  // шаблона на уровне панели (UI списка шаблонов к тому же полностью
  // блокируется на время записи — контракт проверяется в unit-тестах
  // LabPanel.contract.test.tsx).
  test('a patient transition is blocked while a report save is in flight', async ({ page }) => {
    bulkSaveResponseGate = new Promise<void>((resolve) => {
      releaseBulkSaveResponse = resolve;
    });
    await page.goto('/lab');
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    const fieldInput = page.getByLabel('Результат: Лейкоциты');
    await expect(fieldInput).toBeVisible();
    await page.waitForTimeout(700);
    await fieldInput.fill('6.6');
    await expect(page.getByText(/несохранённые изменения/).first()).toBeVisible();

    await page.getByRole('button', { name: 'Сохранить черновик' }).click();
    await expect.poll(() => bulkSavePostCount).toBe(1);

    // Переход к другому пациенту во время записи — заблокирован.
    await page.getByRole('tab').first().click();
    await queuePatientButton(page, 'Пациент Два').dispatchEvent('click');
    await page.waitForTimeout(300);
    expect(instance89GetCount).toBe(0);
    expect(bulkSavePostCount).toBe(1);
    await expect(page.getByText(/сохраняется…/).first()).toBeVisible();

    // Сохранение завершается — переход НЕ выполняется автоматически:
    // пользователь остаётся на отчёте #88 с сохранённым значением.
    releaseBulkSaveResponse?.();
    await page.waitForTimeout(300);
    expect(instance89GetCount).toBe(0);
    await page.getByRole('tab').nth(2).click();
    await expect(page.getByText('Отчёт #88').first()).toBeVisible();
    await expect(fieldInput).toHaveValue('6.6');
    await expect(page.getByText(/несохранённые изменения/)).toHaveCount(0);
  });
});
