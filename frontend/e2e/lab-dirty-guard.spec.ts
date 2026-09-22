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
// PR 3351 (review round 9, P1): Idempotency-Key-контракт создания бланка.
// Мок воспроизводит IdempotencyMiddleware: повторный POST с тем же ключом
// получает СОХРАНЁННЫЙ ответ (replay вместо повторного INSERT); первый
// ответ по ключу может «теряться» (502 ПОСЛЕ серверного commit — reverse
// proxy / crash вкладки); каждый НОВЫЙ ключ — новая операция и новый
// легитимный бланк (id из отдельной последовательности).
let reportInstanceCreateIdempotencyKeys: string[] = [];
let reportInstanceCreateReplayBodies = new Map<string, Record<string, unknown>>();
let reportInstanceCreateLostResponseKeys = new Set<string>();
let reportInstanceCreateLoseFirstResponseForKey = false;
let reportInstanceCreateNextInstanceId = 90;
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
      const idempotencyKey = route.request().headers()['idempotency-key'] || null;
      if (idempotencyKey) {
        reportInstanceCreateIdempotencyKeys.push(idempotencyKey);
      }
      if (reportInstanceCreateResponseGate) {
        await reportInstanceCreateResponseGate;
      }
      const patientId = Number(payload.patient_id);
      // PR 3351 (review round 9, P1): replay-контракт IdempotencyMiddleware —
      // ключ УЖЕ закоммитил бланк: повтор с тем же ключом возвращает
      // сохранённый ответ, хендлер не исполняется (нет второго INSERT).
      if (idempotencyKey && reportInstanceCreateReplayBodies.has(idempotencyKey)) {
        return json(route, reportInstanceCreateReplayBodies.get(idempotencyKey));
      }
      const body = {
        ...INSTANCE_CREATED,
        id: reportInstanceCreateNextInstanceId,
        patient_id: patientId,
        visit_id: payload.visit_id,
        patient_snapshot: {
          patient_id: patientId,
          full_name: patientId === 102 ? 'Пациент Два' : 'Пациент Один',
        },
      };
      if (idempotencyKey) {
        // Хендлер отработал и middleware закэшировал 2xx-ответ по ключу...
        reportInstanceCreateReplayBodies.set(idempotencyKey, body);
        reportInstanceCreateNextInstanceId += 1;
        // ...но транспорт может потерять ПЕРВЫЙ ответ этого ключа (502
        // после commit): клиент не знает ID созданного бланка.
        if (
          reportInstanceCreateLoseFirstResponseForKey
          && !reportInstanceCreateLostResponseKeys.has(idempotencyKey)
        ) {
          reportInstanceCreateLostResponseKeys.add(idempotencyKey);
          return route.fulfill({
            status: 502,
            contentType: 'application/json',
            body: '{"detail":"upstream response lost after commit"}',
          });
        }
      }
      return json(route, body);
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
    reportInstanceCreateIdempotencyKeys = [];
    reportInstanceCreateReplayBodies = new Map();
    reportInstanceCreateLostResponseKeys = new Set();
    reportInstanceCreateLoseFirstResponseForKey = false;
    reportInstanceCreateNextInstanceId = 90;
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

  // PR 3351 (review round 9, P2): внешний urlIntent с targetId=null и без
  // ?tab= — canonical home (тот же контракт, что Header brand). Подтверждён-
  // ный Discard очищает и отчёт, и контекст пациента (reload-parity: /lab
  // после перезагрузки — Queue без выбранного пациента), адрес остаётся
  // СТРОГО /lab. Прежний тест закреплял уход на reports с create-режимом —
  // round 9 явно переопределяет: вкладкой владеет URL.
  test('removing the report from the URL is guarded and Discard lands on canonical /lab with the Queue tab (review round 9)', async ({ page }) => {
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

    // Отчёт и контекст пациента очищены, редактор закрыт.
    await expect(page.getByText('Отчёт #88')).toHaveCount(0);
    await expect(fieldInput).toHaveCount(0);
    // Canonical home: Queue, адрес строго /lab.
    const panelTabs = page.getByRole('tablist', { name: 'Панель лаборатории' });
    await expect(panelTabs.getByRole('tab').nth(0)).toHaveAttribute('aria-selected', 'true');
    await expect.poll(() => new URL(page.url()).pathname + new URL(page.url()).search).toBe('/lab');
    // Пациент не выбран — история не перезагружается (канонический home =
    // то, что открылось бы после reload).
    expect(reportHistoryPatientRequests.length).toBe(historyRequestsBeforeClear);
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

  test('a patient switch during a pending report CREATE is blocked; the committed blank opens for the original patient exactly once (review round 8)', async ({ page }) => {
    // PR 3351 (review round 8, P1): round 7 держал CREATE latest-wins для
    // контекстных переходов — смена пациента в полёте отбрасывала ПОЗДНИЙ
    // ответ по operation-context: серверный бланк уже создан, а оператор
    // не видел ни его, ни обновления read-model и повторял CREATE (дубль).
    // Round 8: CREATE блокирует и контекстные переходы — переключение на
    // пациента B в полёте запрещено, server outcome не теряется.
    reportInstanceCreateResponseGate = new Promise<void>((resolve) => {
      releaseReportInstanceCreateResponse = resolve;
    });
    await page.goto('/lab');
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    await expect(page.getByText('Отчёт #88').first()).toBeVisible();

    const addButton = page.getByRole('button', { name: 'Добавить бланк' });
    await addButton.click();
    await expect.poll(() => reportInstanceCreatePostCount).toBe(1);
    await expect(addButton).toBeDisabled();

    // Смена пациента в полёте неидемпотентного POST: pending-блок без
    // destructive-диалога — контекст пациента A жив, отчёт #88 открыт.
    await page.getByRole('tab').first().click();
    await page.getByRole('button', { name: /Пациент Два/ }).first().click();
    await expect(page.getByText('сохраняется…').first()).toBeVisible();
    await expect(page.getByText('Отчёт #89').first()).toHaveCount(0);
    // Отчёт #88 жив (hidden-секция reports при активной вкладке очереди) —
    // контекст не сменился: URL по-прежнему владеет пациентом 101 / #88.
    await expect(page.getByText('Отчёт #88').first()).toHaveCount(1);
    await expect.poll(() => new URL(page.url()).searchParams.get('patient')).toBe('101');
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBe('88');

    // CREATE завершён в исходном контексте: ответ ПРИНЯТ — бланк #90
    // открывается пациенту Один, отложенная (round 8) запись канонизирует
    // URL, POST выполнен ровно один раз (дублей нет).
    releaseReportInstanceCreateResponse?.();
    await waitForReactToSettle(page);
    await expect(page.getByText('Отчёт #90').first()).toBeVisible();
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBe('90');
    await expect.poll(() => reportHistoryPatientRequests.at(-1)).toBe('101');
    expect(reportInstanceCreatePostCount).toBe(1);

    // Canonical read-model целостен: переход к пациенту B теперь разрешён
    // (pending снят, черновики чисты) и открывает его отчёт #89.
    await page.getByRole('tab').first().click();
    await page.getByRole('button', { name: /Пациент Два/ }).first().click();
    await expect(page.getByText('Отчёт #89').first()).toBeVisible();
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBe('89');
    expect(reportInstanceCreatePostCount).toBe(1);
  });

  test('an external URL instance intent during a pending report CREATE is blocked and rolled back; after completion the intent opens (review round 8)', async ({ page }) => {
    // PR 3351 (review round 8, P1): внешний ?instance=89 — контекстный
    // переход report-области; в полёте неидемпотентного CREATE он
    // блокируется pending-блоком (toast) и откатывается к текущему
    // контексту. Round 7 позволял переход и отбрасывал поздний create по
    // operation-context — теряя server outcome. Dirty-template аспект
    // перехода (report-скоуп, без диалога) покрыт отдельным тестом ниже.
    reportInstanceCreateResponseGate = new Promise<void>((resolve) => {
      releaseReportInstanceCreateResponse = resolve;
    });
    await page.goto('/lab');
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    await expect(page.getByText('Отчёт #88').first()).toBeVisible();

    await page.getByRole('button', { name: 'Добавить бланк' }).click();
    await expect.poll(() => reportInstanceCreatePostCount).toBe(1);

    await page.evaluate(() => {
      window.history.pushState({}, '', '/lab?instance=89');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });
    await expect(page.getByText('сохраняется…').first()).toBeVisible();
    await expect(page.getByText('Отчёт #89').first()).toHaveCount(0);
    // Намерение ОТЛОЖЕНО (round 8): адресная строка остаётся за intent-ом
    // (тот же контракт, что у dirty-диалога), отчёт не переключается до
    // завершения операции.
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBe('89');
    expect(reportInstanceCreatePostCount).toBe(1);

    // CREATE завершён: бланк #90 создан (POST ровно один, история
    // пациента обновлена), отложенное намерение выполняется retry-ом —
    // отчёт #89 открывается без диалога (черновики чисты).
    releaseReportInstanceCreateResponse?.();
    await waitForReactToSettle(page);
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(page.getByText('Отчёт #89').first()).toBeVisible();
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBe('89');
    // Read-model пациента A (создателя бланка) обновлён до открытия #89
    // (последним запросом будет история пациента B — сам #89).
    expect(reportHistoryPatientRequests).toContain('101');
    expect(reportInstanceCreatePostCount).toBe(1);
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

  test('a same-patient appointment switch during a pending report CREATE is blocked; the blank commits to the original appointment (review round 8)', async ({ page }) => {
    // PR 3351 (review round 8, P1): повторный визит того же пациента —
    // тоже контекстный переход (appointment_id меняет payload): round 7
    // пропускал смену и затем отбрасывал ответ (rejected), теряя
    // созданный бланк. Round 8 блокирует переход — контекст a-3 жив,
    // ответ принимается, бланк #90 открывается.
    reportInstanceCreateResponseGate = new Promise<void>((resolve) => {
      releaseReportInstanceCreateResponse = resolve;
    });
    await page.goto('/lab');

    await page.getByRole('button', { name: /Пациент Без Бланка/ }).first().click();
    await expect(page.getByRole('button', { name: 'Создать отчёт' })).toBeVisible();
    await page.getByRole('button', { name: 'Создать отчёт' }).click();
    await expect.poll(() => reportInstanceCreatePostCount).toBe(1);

    // Смена приёма в полёте заблокирована: pending-блок, контекст a-3.
    await page.getByRole('tab').first().click();
    await page.getByRole('button', { name: /Пациент Без Бланка Повтор/ }).first().click();
    await expect(page.getByText('сохраняется…').first()).toBeVisible();
    // Кнопка CREATE жива и заблокирована в hidden-секции reports (getByRole
    // исключает скрытые узлы из a11y-дерева — DOM-локатор).
    const creatingButton = page.locator('#lab-panel-tabpanel-reports button', { hasText: 'Создаю...' });
    await expect(creatingButton).toHaveCount(1);
    await expect(creatingButton).toBeDisabled();

    // Ответ принят в неизменном контексте: бланк #90 открывается,
    // payload принадлежит исходному приёму a-3, POST ровно один.
    releaseReportInstanceCreateResponse?.();
    await waitForReactToSettle(page);
    await expect(page.getByText('Отчёт #90').first()).toBeVisible();
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBe('90');
    expect(lastReportInstanceCreatePayload).toMatchObject({ appointment_id: 'a-3' });
    expect(reportInstanceCreatePostCount).toBe(1);
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

  // PR 3351 (review round 5, P1): штатные same-Lab push writers — Header
  // brand и Command Palette — не могут запушить запись поверх вооружённого
  // sentinel'а. guarded navigator делает любой переход lab→lab replace'ом
  // (идентичный URL — no-op): дельта -2 подтверждённого ухода остаётся
  // корректной, устаревшая помеченная копия не остаётся в history.
  test('Header brand does not push above the sentinel: cancel keeps the draft, confirmed Back leaves the lab (review round 5)', async ({ page }) => {
    await page.goto('/health');
    await page.goto('/lab');
    await page.waitForTimeout(700);
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    const fieldInput = page.getByLabel('Результат: Лейкоциты');
    await expect(fieldInput).toBeVisible();
    await page.waitForTimeout(700);
    await fieldInput.fill('6.5');
    await expect(page.getByText(/несохранённые изменения/).first()).toBeVisible();
    const historyLengthBeforeBrand = await page.evaluate(() => window.history.length);

    // Header brand → canonical /lab для lab-пользователя. Это internal
    // переход (тот же маршрут LabPanel): с фиксом — replace, диалогом
    // владеет urlIntent-флоу панели (удаление instance из URL).
    await page.getByTitle('На главную').click();
    const dialog = page.getByRole('dialog').filter({ hasText: 'Несохранённые изменения' });
    await expect(dialog).toBeVisible();
    await dialog.getByRole('button', { name: 'Отмена' }).click();
    await expect(dialog).toBeHidden();

    // Отмена внутреннего перехода: черновик жив, URL отчёта восстановлен,
    // history НЕ выросла (replace поверх sentinel, не push).
    await expect(fieldInput).toHaveValue('6.5');
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBe('88');
    expect(await page.evaluate(() => window.history.length)).toBe(historyLengthBeforeBrand);

    // Browser Back вытесняет sentinel → guard-диалог → подтверждение
    // РЕАЛЬНО покидает /lab (push поверх sentinel оставил бы под ним
    // устаревшую копию: -2 приземлялся на неё, leaveIntent зависал).
    await page.evaluate(() => window.history.back());
    await expect(dialog).toBeVisible();
    await dialog.getByRole('button', { name: 'Выйти без сохранения' }).click();
    await expect.poll(() => new URL(page.url()).pathname, { timeout: 4000 }).toBe('/health');
  });

  test('Command Palette navigation to Lab Panel does not push above the sentinel (review round 5)', async ({ page }) => {
    await page.goto('/health');
    await page.goto('/lab');
    await page.waitForTimeout(700);
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    const fieldInput = page.getByLabel('Результат: Лейкоциты');
    await expect(fieldInput).toBeVisible();
    await page.waitForTimeout(700);
    await fieldInput.fill('6.5');
    await expect(page.getByText(/несохранённые изменения/).first()).toBeVisible();
    const historyLengthBeforePalette = await page.evaluate(() => window.history.length);

    // Command Palette (Ctrl+K) → маршрут «Лаборатория» (canonical /lab).
    await page.keyboard.press('Control+k');
    const palette = page.getByRole('dialog', { name: 'Command palette' });
    await expect(palette).toBeVisible();
    await palette.getByLabel('Search commands').fill('Лаборатория');
    await palette.getByRole('option', { name: /Лаборатория/ }).first().click();
    // Палитра закрылась; диалогом владеет urlIntent-флоу панели.
    await expect(palette).toHaveCount(0);
    const dialog = page.getByRole('dialog').filter({ hasText: 'Несохранённые изменения' });
    await expect(dialog).toBeVisible();
    await dialog.getByRole('button', { name: 'Отмена' }).click();
    await expect(dialog).toBeHidden();

    // Отмена: черновик жив, URL отчёта восстановлен, history НЕ выросла.
    await expect(fieldInput).toHaveValue('6.5');
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBe('88');
    expect(await page.evaluate(() => window.history.length)).toBe(historyLengthBeforePalette);

    // Back → подтверждённый уход реально покидает /lab.
    await page.evaluate(() => window.history.back());
    await expect(dialog).toBeVisible();
    await dialog.getByRole('button', { name: 'Выйти без сохранения' }).click();
    await expect.poll(() => new URL(page.url()).pathname, { timeout: 4000 }).toBe('/health');
  });

  // PR 3351 (review round 5, P2): прямой вход в /lab без реальной
  // предыдущей записи. Под twin нет страницы: navigate(-2) за границей
  // history — no-op, а destructive Discard уже необратимо сбросил бы
  // черновик. Вытеснение sentinel'а абсорбируется БЕЗ диалога; SPA-уход
  // (Profile) по-прежнему работает и завершается.
  test('direct /lab entry without a previous page absorbs browser Back instead of a dead-end Discard dialog (review round 5)', async ({ page }) => {
    // Первая и единственная навигация страницы — реального предшественника
    // нет. page.goto оставляет под /lab начальную about:blank-запись
    // (length 2), а реальный браузер при вводе адреса в новой вкладке
    // ЗАМЕНЯЕТ её (length 1). location.replace воспроизводит реальный
    // сценарий прямого входа: под /lab нет ни одной записи.
    await page.goto('about:blank');
    await page.evaluate(() => window.location.replace('http://localhost:5173/lab'));
    await page.waitForLoadState('load');
    await page.waitForTimeout(700);
    expect(await page.evaluate(() => window.history.length)).toBe(1);
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    const fieldInput = page.getByLabel('Результат: Лейкоциты');
    await expect(fieldInput).toBeVisible();
    await page.waitForTimeout(700);
    await fieldInput.fill('6.5');
    await expect(page.getByText(/несохранённые изменения/).first()).toBeVisible();

    // Back: НЕ destructive-диалог — вытеснение абсорбируется (уходить
    // некуда), панель смонтирована, черновик жив.
    await page.evaluate(() => window.history.back());
    await page.waitForTimeout(500);
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(fieldInput).toHaveValue('6.5');
    expect(new URL(page.url()).pathname).toBe('/lab');

    // Повторный Back — тот же абсорб: guard не «умер», но и не предлагает
    // несуществующее назначение.
    await page.evaluate(() => window.history.back());
    await page.waitForTimeout(500);
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(fieldInput).toHaveValue('6.5');
    expect(new URL(page.url()).pathname).toBe('/lab');

    // SPA-уход по-прежнему доступен и ЗАВЕРШАЕТСЯ: подтверждённый Profile-
    // переход уходит с /lab (leaveIntent не зависает).
    await page.getByRole('button', { name: 'Профиль пользователя' }).click();
    await page.getByRole('menuitem', { name: 'Профиль' }).click();
    const dialog = page.getByRole('dialog').filter({ hasText: 'Несохранённые изменения' });
    await expect(dialog).toBeVisible();
    await dialog.getByRole('button', { name: 'Выйти без сохранения' }).click();
    await expect.poll(() => new URL(page.url()).pathname, { timeout: 4000 }).toBe('/clinical/profile');
  });

  // PR 3351 (review round 6, P1): полная защита документа (refresh / закрытие
  // вкладки) обязана учитывать pending-операции, а не только dirty-state.
  // Прежние per-workbench beforeunload-хуки ставили слушатель только по
  // dirty-флагу: clone ЧИСТОГО шаблона (неидемпотентный POST без
  // Idempotency-Key) обрывался без предупреждения — ответ терялся, список
  // не обновлялся, и оператор повторял clone, создавая вторую копию.
  // Провайдер-level beforeunload (dirty ИЛИ pending) закрывает сценарий:
  // попытка покинуть документ блокируется, POST висит и завершается ровно
  // один раз, после завершения reload свободен.
  test('a pending clone blocks the unload attempt via beforeunload and the POST executes exactly once (review round 6)', async ({ page }) => {
    let releaseClone: () => void = () => {};
    const cloneGate = new Promise<void>((resolve) => { releaseClone = resolve; });
    let clonePostCount = 0;
    await page.route('**/api/v1/lab/templates/5/clone', async (route) => {
      clonePostCount += 1;
      await cloneGate;
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ id: 7, code: 'rule_demo_copy', name: 'Rule Demo (копия)' }),
      });
    });

    // Явный обработчик beforeunload-диалогов: dismiss = «остаться на
    // странице» (навигация отменяется). Без обработчика Playwright тоже
    // dismiss-ит — но тогда «диалог был» неотличимо от «диалога не было».
    const dialogs: string[] = [];
    page.on('dialog', (dialog) => {
      dialogs.push(dialog.type());
      void dialog.dismiss().catch(() => {});
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
    const cloneSent = page.waitForRequest((request) => (
      request.method() === 'POST'
      && request.url().endsWith('/api/v1/lab/templates/5/clone')
    ));
    await cloneButton.click();
    await cloneSent;
    await expect(cloneButton).toBeDisabled();
    expect(clonePostCount).toBe(1);

    // Попытка покинуть документ при чистых черновиках и висящем POST:
    // beforeunload-диалог, dismiss отменяет навигацию — SPA жива, POST не
    // оборван (остаётся disabled = pending).
    await page.evaluate(() => { window.location.href = '/health'; }).catch(() => {});
    await page.waitForTimeout(400);
    expect(dialogs).toContain('beforeunload');
    expect(new URL(page.url()).pathname).toBe('/lab');
    await expect(cloneButton).toBeDisabled();

    // Операция завершена: pending снят → попытка уйти проходит БЕЗ
    // beforeunload-диалога, и за весь сценарий clone выполнился ровно
    // один раз (дублей нет — оператору не нужно повторять запрос).
    releaseClone();
    await expect(cloneButton).toBeEnabled();
    dialogs.length = 0;
    await page.evaluate(() => { window.location.href = '/health'; }).catch(() => {});
    await expect.poll(() => new URL(page.url()).pathname, { timeout: 4000 }).toBe('/health');
    expect(dialogs).toHaveLength(0);
    expect(clonePostCount).toBe(1);
  });

  // PR 3351 (review round 6, P2): canonical /lab (defaultItem: 'queue' в
  // routeRegistry) обязан означать ровно то, что откроется после reload:
  // URL /lab без ?tab= — вкладка очереди. Прежний tab-sync молча пропускал
  // «нет таба»: после Header brand адрес показывал /lab, а экран оставался
  // на Templates — адрес нельзя было ни сохранить, ни скопировать, ни
  // восстановить. Черновик шаблона при этом не теряется: все три workbench
  // смонтированы одновременно (hidden-секции), смена вкладки их не
  // размонтирует.
  test('Header brand to canonical /lab shows the Queue tab and keeps the templates draft mounted (review round 6)', async ({ page }) => {
    await page.goto('/lab?tab=templates');
    await expect(new URL(page.url()).searchParams.get('tab')).toBe('templates');
    await page.waitForTimeout(700);

    // Dirty-черновик шаблона без пациента: под-вкладка «Оформление» → подвал.
    await page.getByRole('tab', { name: 'Оформление' }).click();
    const footerInput = page.getByLabel('Подвал шаблона');
    await expect(footerInput).toBeEnabled();
    await footerInput.fill('Несохранённый подвал');
    await waitForReactToSettle(page);

    const panelTabs = page.getByRole('tablist', { name: 'Панель лаборатории' });
    await expect(panelTabs.getByRole('tab').nth(1)).toHaveAttribute('aria-selected', 'true');
    const historyLengthBeforeBrand = await page.evaluate(() => window.history.length);

    // Header brand → canonical /lab. Это in-lab replace (round 5): history
    // не растёт, второй /lab-записи нет; guard-диалога нет — внутренняя
    // смена вкладки не уничтожает draft.
    await page.getByTitle('На главную').click();
    await expect.poll(() => new URL(page.url()).pathname + new URL(page.url()).search).toBe('/lab');
    expect(await page.evaluate(() => window.history.length)).toBe(historyLengthBeforeBrand);

    // URL /lab = вкладка очереди: адрес и экран согласованы, после reload
    // открылась бы та же вкладка (раньше экран оставался на Templates).
    await expect(panelTabs.getByRole('tab').nth(0)).toHaveAttribute('aria-selected', 'true');
    await expect(panelTabs.getByRole('tab').nth(1)).toHaveAttribute('aria-selected', 'false');

    // Черновик шаблона жив (hidden-секция): возврат на вкладку шаблонов
    // возвращает редактор с тем же несохранённым подвалом.
    await expect(footerInput).toHaveValue('Несохранённый подвал');
    await panelTabs.getByRole('tab').nth(1).click();
    await expect(footerInput).toBeVisible();
    await expect(footerInput).toHaveValue('Несохранённый подвал');
    await expect.poll(() => new URL(page.url()).searchParams.get('tab')).toBe('templates');

    // Dirty-черновик: защита документа теперь у провайдера (бывший
    // per-workbench хук) — попытка покинуть документ блокируется и в этой
    // конфигурации (dirty ИЛИ pending, единый владелец).
    const dialogs: string[] = [];
    page.on('dialog', (dialog) => {
      dialogs.push(dialog.type());
      void dialog.dismiss().catch(() => {});
    });
    await page.evaluate(() => { window.location.href = '/health'; }).catch(() => {});
    await page.waitForTimeout(400);
    expect(dialogs).toContain('beforeunload');
    expect(new URL(page.url()).pathname).toBe('/lab');
    await expect(footerInput).toHaveValue('Несохранённый подвал');
  });

  // PR 3351 (review round 9, P2): canonical /lab при ОТКРЫТОМ ЧИСТОМ отчёте.
  // URL-restore видит instanceId=null при activeInstanceId=88 — подтверждённый
  // callback безусловно делал switchTab('reports') и дописывал ?tab=reports
  // поверх canonical /lab: brand-«дом» не был домом (экран Reports, отчёт
  // очищен). Round 9: вкладкой владеет сам URL — tab-less /lab = Queue,
  // адрес остаётся СТРОГО /lab (reload-parity: без пациента и бланка).
  test('Header brand from a clean open report lands on canonical /lab with the Queue tab (review round 9)', async ({ page }) => {
    await page.goto('/lab');
    await page.waitForTimeout(700);
    // Чистый (не dirty) отчёт #88 пациента 101 на вкладке reports.
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    const fieldInput = page.getByLabel('Результат: Лейкоциты');
    await expect(fieldInput).toBeVisible();
    await page.waitForTimeout(700);
    const panelTabs = page.getByRole('tablist', { name: 'Панель лаборатории' });
    await expect(panelTabs.getByRole('tab').nth(2)).toHaveAttribute('aria-selected', 'true');
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBe('88');

    // Header brand → canonical /lab: replace, guard чистый — диалога нет.
    await page.getByTitle('На главную').click();

    // URL строго /lab: ни ?tab=reports (round-9 регрессия), ни ?patient=101
    // (canonical = reload-parity), ни ?instance.
    await expect.poll(() => new URL(page.url()).pathname + new URL(page.url()).search).toBe('/lab');

    // Экран: Queue выбрана, редактор отчёта закрыт (activeInstance=null),
    // контекст пациента очищен.
    await expect(panelTabs.getByRole('tab').nth(0)).toHaveAttribute('aria-selected', 'true');
    await expect(panelTabs.getByRole('tab').nth(2)).toHaveAttribute('aria-selected', 'false');
    await expect(page.getByText('Отчёт #88').first()).toHaveCount(0);
    await expect(fieldInput).toHaveCount(0);

    // History не выросла (in-lab replace), а после reload открылась бы та
    // же вкладка Queue (адрес = экран).
    const historyLengthAfterBrand = await page.evaluate(() => window.history.length);
    await page.reload();
    await page.waitForTimeout(700);
    await expect(panelTabs.getByRole('tab').nth(0)).toHaveAttribute('aria-selected', 'true');
    expect(await page.evaluate(() => window.history.length)).toBe(historyLengthAfterBrand);
  });

  // PR 3351 (review round 9, P2): тот же pin для Command Palette → Lab
  // Panel (второй shell-писатель canonical /lab).
  test('Command Palette to Lab Panel from a clean open report lands on canonical /lab with the Queue tab (review round 9)', async ({ page }) => {
    await page.goto('/lab');
    await page.waitForTimeout(700);
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    const fieldInput = page.getByLabel('Результат: Лейкоциты');
    await expect(fieldInput).toBeVisible();
    await page.waitForTimeout(700);

    // Command Palette (Ctrl+K) → маршрут «Лаборатория» (canonical /lab).
    await page.keyboard.press('Control+k');
    const palette = page.getByRole('dialog', { name: 'Command palette' });
    await expect(palette).toBeVisible();
    await palette.getByLabel('Search commands').fill('Лаборатория');
    await palette.getByRole('option', { name: /Лаборатория/ }).first().click();
    await expect(palette).toHaveCount(0);

    // Чистый отчёт: guard без диалога — сразу canonical-приземление.
    const panelTabs = page.getByRole('tablist', { name: 'Панель лаборатории' });
    await expect.poll(() => new URL(page.url()).pathname + new URL(page.url()).search).toBe('/lab');
    await expect(panelTabs.getByRole('tab').nth(0)).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByText('Отчёт #88').first()).toHaveCount(0);
    await expect(fieldInput).toHaveCount(0);
  });

  // PR 3351 (review round 9, P2): внешний urlIntent с targetId=null и ЯВНОЙ
  // вкладкой адреса — вкладкой владеет URL: /lab?tab=reports очищает бланк,
  // но ОСТАВЛЯЕТ вкладку Reports (не уводит на Queue).
  test('an external tab-holding null intent keeps the URL-owned tab when clearing the report (review round 9)', async ({ page }) => {
    await page.goto('/lab');
    await page.waitForTimeout(700);
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    await expect(page.getByLabel('Результат: Лейкоциты')).toBeVisible();
    await page.waitForTimeout(700);

    // Внешний intent: /lab?tab=reports без instance (brand-подобный переход
    // с явной вкладкой).
    await page.evaluate(() => {
      window.history.pushState({}, '', '/lab?tab=reports');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });
    await page.waitForTimeout(400);

    // Бланк очищен, но вкладка — Reports (её выбрал URL), контекст пациента
    // сохранён, адрес явно владеет tab.
    const panelTabs = page.getByRole('tablist', { name: 'Панель лаборатории' });
    await expect(panelTabs.getByRole('tab').nth(2)).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByText('Отчёт #88').first()).toHaveCount(0);
    await expect.poll(() => new URL(page.url()).searchParams.get('tab')).toBe('reports');
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBeNull();
  });

  // PR 3351 (review round 9, P2): «Продлить сессию» — реальный refresh.
  // Прежняя кнопка только прятала предупреждение и показывала тост «про-
  // длеваем»: JWT оставался прежним, повторное предупреждение того же
  // поколения молчало (warningFired), сессия истекала. Теперь клик вызыва-
  // ет канонический single-flight /authentication/refresh; предупреждение
  // закрывается ТОЛЬКО после нового значения access token с будущим exp;
  // неудача оставляет его открытым с явной ошибкой.
  test('the extend-session button performs a real refresh: failure keeps the warning open, success lands a new token (review round 9)', async ({ page }) => {
    // Токен внутри 5-минутного порога: предупреждение срабатывает на
    // mount-проверке опроса. Собирается в рантайме (как installToken в
    // компонентных тестах) — единый JWT-литерал в исходнике триггерит
    // secret-сканер CI.
    const nearExpiryToken = [
      'eyJhbGciOiJIUzI1NiJ9',
      Buffer.from(JSON.stringify({
        sub: '7',
        role: 'Lab',
        exp: Math.floor((Date.now() + 4 * 60_000) / 1000),
      })).toString('base64'),
      'sig',
    ].join('.');
    const freshToken = [
      'eyJhbGciOiJIUzI1NiJ9',
      Buffer.from(JSON.stringify({
        sub: '7',
        role: 'Lab',
        exp: Math.floor((Date.now() + 60 * 60_000) / 1000),
      })).toString('base64'),
      'sig',
    ].join('.');
    await page.addInitScript((token) => {
      window.sessionStorage.setItem('auth_token', token);
      window.sessionStorage.setItem('refresh_token', token);
    }, nearExpiryToken);

    let refreshPostCount = 0;
    let refreshShouldFail = true;
    await page.route('**/api/v1/authentication/refresh', async (route) => {
      refreshPostCount += 1;
      if (refreshShouldFail) {
        return route.fulfill({
          status: 401,
          contentType: 'application/json',
          body: '{"detail":"refresh token expired"}',
        });
      }
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ access_token: freshToken, refresh_token: freshToken }),
      });
    });

    await page.goto('/lab');
    await page.waitForTimeout(700);
    const warning = page.getByRole('alertdialog', { name: 'Предупреждение об истечении сессии' });
    await expect(warning).toBeVisible();
    const refreshTokenBefore = await page.evaluate(() => window.sessionStorage.getItem('auth_token'));
    expect(refreshTokenBefore).toBe(nearExpiryToken);

    // Попытка 1: refresh отклонён (refresh token истёк) — предупреждение
    // НЕ закрыто, явная ошибка, кнопка доступна для повтора.
    await warning.getByRole('button', { name: 'Продлить сессию' }).click();
    await expect.poll(() => refreshPostCount).toBeGreaterThanOrEqual(1);
    await expect(page.getByText(/Не удалось продлить сессию/).first()).toBeVisible();
    await expect(warning).toBeVisible();
    expect(await page.evaluate(() => window.sessionStorage.getItem('auth_token'))).toBe(nearExpiryToken);

    // Попытка 2: refresh успешен — в хранилище НОВОЕ значение с будущим
    // exp, предупреждение закрывается только теперь.
    refreshShouldFail = false;
    await warning.getByRole('button', { name: 'Продлить сессию' }).click();
    await expect.poll(() => refreshPostCount).toBeGreaterThanOrEqual(2);
    await expect(warning).toHaveCount(0);
    await expect.poll(() => page.evaluate(() => window.sessionStorage.getItem('auth_token'))).toBe(freshToken);
  });

  // PR 3351 (review round 7, P1): report CREATE больше не обходит защиту
  // документа. POST /lab/report-instances неидемпотентен и без
  // Idempotency-Key: refresh/закрытие вкладки/Profile-уход поверх летящего
  // create теряли ответ — оператор после повторного входа создавал второй
  // бланк для того же пациента. CREATE остаётся latest-wins ТОЛЬКО для
  // контекстных переходов внутри панели (см. отдельный unit/contract
  // coverage); полный уход блокируется наравне с save/finalize/print.
  test('a pending report CREATE blocks unload and Profile leave until the POST completes, and executes exactly once (review round 7)', async ({ page }) => {
    // Гейт create-ответа: POST «висит», пока тест не отпустит.
    reportInstanceCreateResponseGate = new Promise<void>((resolve) => {
      releaseReportInstanceCreateResponse = resolve;
    });
    const dialogs: string[] = [];
    page.on('dialog', (dialog) => {
      dialogs.push(dialog.type());
      void dialog.dismiss().catch(() => {});
    });

    await page.goto('/lab');
    await page.waitForTimeout(700);
    // Чистый контекст: отчёт #88 открыт, правок НЕТ — dirty=false у обоих
    // workbench-ей. Блокирует только pending CREATE (split-уровень round 7:
    // blocksDocumentLeave=true при blocksContextTransition=false).
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    await expect(page.getByLabel('Результат: Лейкоциты')).toBeVisible();
    await page.waitForTimeout(700);

    const addButton = page.getByRole('button', { name: 'Добавить бланк' });
    const createSent = page.waitForRequest((request) => (
      request.method() === 'POST'
      && request.url().endsWith('/api/v1/lab/report-instances')
    ));
    await addButton.click();
    await createSent;
    expect(reportInstanceCreatePostCount).toBe(1);
    await expect(addButton).toBeDisabled();

    // Refresh/close при чистых черновиках и висящем CREATE: beforeunload
    // диалог, dismiss отменяет навигацию — SPA жива, POST не оборван.
    await page.evaluate(() => { window.location.href = '/health'; }).catch(() => {});
    await page.waitForTimeout(400);
    expect(dialogs).toContain('beforeunload');
    expect(new URL(page.url()).pathname).toBe('/lab');
    await expect(addButton).toBeDisabled();
    dialogs.length = 0;

    // SPA route-leave (Profile) при висящем CREATE: pending-блок без
    // destructive диалога, пользователь остаётся на /lab.
    await page.getByRole('button', { name: 'Профиль пользователя' }).click();
    await page.getByRole('menuitem', { name: 'Профиль' }).click();
    await expect(page.getByRole('button', { name: 'Выйти без сохранения' })).toHaveCount(0);
    await expect(page.getByText('сохраняется…').first()).toBeVisible();
    await page.waitForTimeout(400);
    expect(new URL(page.url()).pathname).toBe('/lab');

    // CREATE завершён: pending снят → уход проходит без диалога, и за весь
    // сценарий POST выполнился ровно один раз (дублей бланка нет).
    releaseReportInstanceCreateResponse?.();
    await expect(addButton).toBeEnabled();
    await waitForReactToSettle(page);
    await page.getByRole('button', { name: 'Профиль пользователя' }).click();
    await page.getByRole('menuitem', { name: 'Профиль' }).click();
    await expect.poll(() => new URL(page.url()).pathname, { timeout: 4000 }).not.toBe('/lab');
    expect(dialogs).toHaveLength(0);
    expect(reportInstanceCreatePostCount).toBe(1);
  });

  // PR 3351 (review round 8, P1): browser Back в полёте неидемпотентного
  // report CREATE. Round 7 исключал CREATE из sentinel-а (latest-wins):
  // Back посреди POST уходил с /lab, ответ терялся, оператор повторял
  // создание — второй бланк. Round 8: sentinel вооружен и в полёте CREATE
  // (контракт blocksDocumentLeave), Back абсорбируется pending-блоком,
  // операция завершается на месте, POST ровно один, а СЛЕДУЮЩИЙ Back
  // уходит на /health — без фантомной записи и без stale twin restore
  // (отложенная запись ?instance по historyGuardEngaged).
  test('browser Back during a pending report CREATE is absorbed; the POST executes exactly once and the next Back leaves to /health (review round 8)', async ({ page }) => {
    reportInstanceCreateResponseGate = new Promise<void>((resolve) => {
      releaseReportInstanceCreateResponse = resolve;
    });
    // Реальная история: /health -> /lab (под twin-записью — предшественник).
    await page.goto('/health');
    await page.goto('/lab');
    await page.waitForTimeout(700);
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    await expect(page.getByText('Отчёт #88').first()).toBeVisible();
    await page.waitForTimeout(700);

    const addButton = page.getByRole('button', { name: 'Добавить бланк' });
    await addButton.click();
    await expect.poll(() => reportInstanceCreatePostCount).toBe(1);
    await expect(addButton).toBeDisabled();

    // Back в полёте: вытеснение twin-записи абсорбируется pending-блоком —
    // без destructive-диалога, панель жива, операция не оборвана.
    await page.evaluate(() => window.history.back());
    await expect(page.getByRole('button', { name: 'Выйти без сохранения' })).toHaveCount(0);
    await expect(page.getByText('сохраняется…').first()).toBeVisible();
    await page.waitForTimeout(400);
    expect(new URL(page.url()).pathname).toBe('/lab');
    await expect(addButton).toBeDisabled();
    expect(reportInstanceCreatePostCount).toBe(1);

    // Операция завершена: бланк #90 открыт, sentinel свёрнут, отложенная
    // запись ?instance=90 легла на реальную запись истории.
    releaseReportInstanceCreateResponse?.();
    await expect(addButton).toBeEnabled();
    await waitForReactToSettle(page);
    await expect(page.getByText('Отчёт #90').first()).toBeVisible();
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBe('90');
    expect(reportInstanceCreatePostCount).toBe(1);

    // ОДИН Back уходит на реальную предыдущую страницу — без фантома и
    // без отката URL/отчёта на до-create twin (stale restore).
    await page.evaluate(() => window.history.back());
    await expect.poll(() => new URL(page.url()).pathname, { timeout: 4000 }).toBe('/health');
    expect(reportInstanceCreatePostCount).toBe(1);
  });

  // PR 3351 (review round 9, P1): exactly-once для report CREATE по
  // операции. Навигационные блокировки round 7/8 не покрывают транспортный
  // разрыв ПОСЛЕ серверного commit: 502 reverse proxy / crash вкладки
  // оставляли frontend без ID созданного бланка — оператор повторял клик и
  // получал ВТОРОЙ бланк. Round 9: каждый клик создания несёт устойчивый
  // Idempotency-Key (sessionStorage, reload-safe); повтор потерянного
  // ответа отправляет ТОТ ЖЕ ключ — backend возвращает закоммиченный бланк
  // вместо второго INSERT; подтверждённый исход освобождает ключ —
  // следующее создание это новая операция (новый легитимный бланк).
  test('a lost HTTP response after commit is retried with the same Idempotency-Key and creates exactly one blank (review round 9)', async ({ page }) => {
    // Мок-режим: первый ответ КАЖДОГО нового ключа «теряется» после commit.
    reportInstanceCreateLoseFirstResponseForKey = true;

    await page.goto('/lab');
    await page.waitForTimeout(700);
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    await expect(page.getByText('Отчёт #88').first()).toBeVisible();
    await page.waitForTimeout(700);

    const addButton = page.getByRole('button', { name: 'Добавить бланк' });

    // Попытка 1: backend закоммитил бланк #90, но ответ потерян (502) —
    // клиент не знает ID и видит ошибку сети.
    await addButton.click();
    await expect.poll(() => reportInstanceCreatePostCount).toBe(1);
    // Потерян только ПЕРВЫЙ ответ (первый ключ): дальнейшие попытки
    // доходят до клиента штатно.
    reportInstanceCreateLoseFirstResponseForKey = false;
    await expect(addButton).toBeEnabled();
    expect(reportInstanceCreateIdempotencyKeys).toHaveLength(1);
    const operationKey = reportInstanceCreateIdempotencyKeys[0];
    expect(operationKey).toBeTruthy();
    // Ни один бланк ещё не открыт: исход неизвестен.
    await expect(page.getByText('Отчёт #90').first()).toHaveCount(0);

    // Round 10 (CodeQL #1315): в окне неопределённого исхода слот
    // sessionStorage хранит ТОЛЬКО { key, payloadDigest } — ни raw payload
    // (ФЛИ: patient_id/appointment_id/клинические поля), ни его подстрок:
    // digest-hex/префиксы/UUID не содержат подчёркиваний и кириллицы.
    const slotEntries = await page.evaluate(() => {
      const out: Record<string, string> = {};
      for (let i = 0; i < window.sessionStorage.length; i += 1) {
        const k = window.sessionStorage.key(i);
        if (k && k.startsWith('lab:report-create:idempotency:')) {
          out[k] = window.sessionStorage.getItem(k) as string;
        }
      }
      return out;
    });
    expect(Object.keys(slotEntries)).toHaveLength(1);
    const slotRaw = Object.values(slotEntries)[0];
    const slotRecord = JSON.parse(slotRaw) as Record<string, unknown>;
    expect(Object.keys(slotRecord).sort()).toEqual(['key', 'payloadDigest']);
    expect(slotRecord.key).toBe(operationKey);
    expect(String(slotRecord.payloadDigest)).toMatch(/^(sha256|fnv1a):/);
    expect(slotRaw).not.toContain('patient_id');
    expect(slotRaw).not.toContain('appointment_id');
    expect(slotRaw).not.toContain('visit_id');
    expect(slotRaw).not.toContain('service_codes');

    // Попытка 2: оператор повторяет тот же логический клик — ТОТ ЖЕ
    // Idempotency-Key (слот пережил неопределённый исход), backend
    // возвращает закоммиченный #90 (replay), второй INSERT нет.
    await addButton.click();
    await expect.poll(() => reportInstanceCreatePostCount).toBe(2);
    expect(reportInstanceCreateIdempotencyKeys[1]).toBe(operationKey);
    await waitForReactToSettle(page);
    await expect(page.getByText('Отчёт #90').first()).toBeVisible();
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBe('90');
    // Бланка #91 не существует — ровно один закоммиченный бланк.
    await expect(page.getByText('Отчёт #91').first()).toHaveCount(0);
    expect(reportInstanceCreateNextInstanceId).toBe(91);

    // Исход подтверждён — ключ отработал: следующее создание это НОВАЯ
    // операция (новый ключ → новый легитимный отдельный бланк #91).
    await expect(addButton).toBeEnabled();
    await addButton.click();
    await expect.poll(() => reportInstanceCreatePostCount).toBe(3);
    expect(reportInstanceCreateIdempotencyKeys[2]).not.toBe(operationKey);
    await waitForReactToSettle(page);
    await expect(page.getByText('Отчёт #91').first()).toBeVisible();
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBe('91');
    // Итог: 3 POST (1 потерян + 1 replay + 1 новый) = 2 закоммиченных
    // бланка (#90, #91) — дубля от потерянного ответа нет.
    expect(reportInstanceCreateNextInstanceId).toBe(92);
  });

  // PR 3351 (review round 7, P2): вкладка-база отката фиксируется один раз
  // на всю цепочку urlIntent-ов. Второй tab-less intent, пришедший пока
  // первый ждёт решения в dirty-dialog, раньше затирал исходную вкладку
  // (reports) нормализованным queue — Cancel возвращал на очередь и прятал
  // редактируемый отчёт за другой вкладкой.
  test('a superseding tab-less URL intent keeps the original rollback tab: Cancel returns to Reports (review round 7)', async ({ page }) => {
    await page.goto('/lab');
    await page.waitForTimeout(700);
    // Dirty-редактирование отчёта #88 на вкладке reports.
    await page.getByRole('button', { name: /Пациент Один/ }).first().click();
    const fieldInput = page.getByLabel('Результат: Лейкоциты');
    await expect(fieldInput).toBeVisible();
    await page.waitForTimeout(700);
    await fieldInput.fill('7.2');
    await expect(page.getByText(/несохранённые изменения/).first()).toBeVisible();
    const panelTabs = page.getByRole('tablist', { name: 'Панель лаборатории' });
    await expect(panelTabs.getByRole('tab').nth(2)).toHaveAttribute('aria-selected', 'true');
    await expect.poll(() => new URL(page.url()).searchParams.get('tab')).toBe('reports');
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBe('88');

    // Внешний tab-less intent A (instance=89): guard-диалог открыт,
    // pre-intent вкладка = reports.
    await page.evaluate(() => {
      window.history.pushState({}, '', '/lab?instance=89');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();

    // Superseding tab-less intent B (instance=90) пока диалог intent A
    // ждёт решения: цель обновляется, база отката — нет.
    await page.evaluate(() => {
      window.history.pushState({}, '', '/lab?instance=90');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });
    await page.waitForTimeout(300);
    await expect(dialog).toBeVisible();
    expect(await dialog.count()).toBe(1);

    // Cancel: откат к отчёту #88 на ИСХОДНОЙ вкладке reports (не queue),
    // URL явно владеет tab, draft сохранён.
    await dialog.getByRole('button', { name: 'Отмена' }).click();
    await expect(dialog).toBeHidden();
    await expect(panelTabs.getByRole('tab').nth(2)).toHaveAttribute('aria-selected', 'true');
    await expect.poll(() => new URL(page.url()).searchParams.get('tab')).toBe('reports');
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBe('88');
    await expect(page.getByText('Отчёт #88').first()).toBeVisible();
    await expect(fieldInput).toHaveValue('7.2');
  });
});
