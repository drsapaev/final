// @ts-check
import { test, expect } from '@playwright/test';
import type { Page, Route } from '@playwright/test';

/**
 * Final gate remainder (codex-lab-workflow-hardening-plan, §Final gate
 * execution record): непрерывный сквозной mocked-путь ОДНОЙ спекой —
 * очередь -> создать -> заполнить -> сохранить -> preview -> утвердить ->
 * PDF-печать -> revise -> история.
 *
 * До этой спеки revise-контракт был покрыт только на API-уровне
 * (backend test_lab_reporting_api_flow), а на browser-уровне встречался
 * лишь mock-фикстурой available_actions:['revise','print']
 * (lab-preview-pdf.spec.ts). Здесь полный жизненный цикл одного бланка
 * проходит непрерывно в одном браузерном контексте: один пациент, один
 * созданный бланк #90, одна ревизия #91 — с серверным стейт-моком,
 * воспроизводящим контракты backend (статусы DRAFT -> IN_PROGRESS ->
 * FINALIZED -> PRINTED; revise -> новый DRAFT c supersedes_instance_id
 * и скопированными значениями; Idempotency-Key replay на CREATE).
 *
 * Self-contained: no backend, no credentials — every /api/v1/** call is
 * intercepted with page.route; the session is fabricated via sessionStorage
 * (auth_token + auth_profile, the RoleGuard sources).
 *
 * Контртракт finding 2 из Final gate execution record: спека НЕ читает
 * кастомные response-заголовки в page-JS (кросс-оригин VITE_API_BASE_URL
 * не экспонирует их без Access-Control-Expose-Headers) — все счётчики и
 * порядок вызовов фиксируются на Node-стороне (route-хендлеры +
 * page.on('request')).
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

const TEMPLATE_SUMMARY = {
  id: 5,
  code: 'rule_demo',
  name: 'Rule Demo',
  family: 'chemistry',
  is_active: true,
  published_version_id: 51,
  draft_version_id: null,
  latest_version_id: 51,
};

const TEMPLATE_VERSION = {
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
        {
          id: 1,
          field_key: 'wbc',
          label: 'Лейкоциты',
          value_type: 'text',
          unit: '',
          reference_mode: 'static_text',
          reference_text: '',
          required: false,
          sort_order: 10,
          reference_rule: null,
          visibility_rule: null,
          highlight_rule: null,
        },
      ],
    },
  ],
};

const TEMPLATE_DETAIL = {
  ...TEMPLATE_SUMMARY,
  versions: [TEMPLATE_VERSION],
};

// Очередь: пациент без бланка (report_instance_id=null) — стартовая точка
// пути «создать». appointment a-3 (тот же идентификатор, что в
// lab-dirty-guard.spec.ts для этого пациента).
const QUEUE_ENTRY = {
  id: 3,
  appointment_id: 'a-3',
  patient_id: 103,
  patient_fio: 'Пациент Без Бланка',
  patient_phone: '',
  status: 'waiting',
  report_instance_id: null,
  services: [],
  service_codes: [],
  service_details: [],
};

const PATIENT_ID = 103;
const VISIT_ID = 703;
const CREATED_INSTANCE_ID = 90;
const REVISED_INSTANCE_ID = 91;

type InstanceStatus = 'DRAFT' | 'IN_PROGRESS' | 'FINALIZED' | 'PRINTED';

// Server-owned действия по статусу — контракт из backend
// test_lab_reporting_api_flow (available_actions — SSOT для UI).
function actionsForStatus(status: InstanceStatus): string[] {
  if (status === 'FINALIZED' || status === 'PRINTED') {
    return ['revise', 'print'];
  }
  return ['edit', 'save_draft', 'finalize', 'preview'];
}

// Полная запись бланка — форма ответа GET /lab/report-instances/{id}
// (INSTANCE_A из lab-dirty-guard.spec.ts + supersedes_instance_id).
function makeInstanceRecord(
  id: number,
  status: InstanceStatus,
  options: { wbcValue?: string; supersedesInstanceId?: number | null; createdAt: string } = {
    wbcValue: '',
    supersedesInstanceId: null,
    createdAt: '2026-09-26T08:00:00.000000+00:00',
  },
) {
  return {
    id,
    status,
    template_id: 5,
    patient_id: PATIENT_ID,
    visit_id: VISIT_ID,
    updated_at: options.createdAt,
    signer_snapshot: {},
    supersedes_instance_id: options.supersedesInstanceId ?? null,
    available_actions: actionsForStatus(status),
    critical_findings: [],
    patient_snapshot: { patient_id: PATIENT_ID, full_name: QUEUE_ENTRY.patient_fio },
    template: TEMPLATE_DETAIL,
    template_version: TEMPLATE_VERSION,
    sections: TEMPLATE_VERSION.sections.map((section) => ({
      ...section,
      fields: section.fields.map((field) => ({ ...field, value_text: options.wbcValue ?? '' })),
    })),
  };
}

// Summary-форма — ответ GET /lab/report-instances?patient_id=... (карточки
// истории) и ?limit=... (недавние бланки). Поля can_* — по контракту
// API-flow (DRAFT/IN_PROGRESS: edit+finalize; FINALIZED/PRINTED: revise+print).
function makeHistorySummary(record: ReturnType<typeof makeInstanceRecord>) {
  const editable = record.status === 'DRAFT' || record.status === 'IN_PROGRESS';
  return {
    id: record.id,
    patient_id: record.patient_id,
    visit_id: record.visit_id,
    template_id: record.template_id,
    template_version_id: TEMPLATE_VERSION.id,
    status: record.status,
    created_at: record.updated_at,
    finalized_at: record.status === 'FINALIZED' || record.status === 'PRINTED' ? record.updated_at : null,
    printed_at: record.status === 'PRINTED' ? record.updated_at : null,
    // LabReportInstanceSummaryOut: patient_snapshot присутствует в summary —
    // карточка истории показывает ФИО, а не «Пациент #NN».
    patient_snapshot: { patient_id: PATIENT_ID, full_name: QUEUE_ENTRY.patient_fio },
    template: { name: TEMPLATE_SUMMARY.name },
    flagged_findings_count: 0,
    critical_findings_count: 0,
    max_flag_severity: null,
    available_actions: actionsForStatus(record.status),
    can_edit: editable,
    can_save_draft: editable,
    can_mark_ready: false,
    can_finalize: editable,
    can_revise: !editable,
    can_print: !editable,
    can_preview: editable,
  };
}

function json(route: Route, payload: unknown, headers: Record<string, string> = {}) {
  return route.fulfill({
    status: 200,
    contentType: 'application/json',
    headers,
    body: JSON.stringify(payload),
  });
}

function syntheticPdf(route: Route, body: string, filename: string) {
  return route.fulfill({
    status: 200,
    contentType: 'application/pdf',
    headers: {
      'content-disposition': `inline; filename="${filename}"`,
      'cache-control': 'private, no-store',
    },
    body,
  });
}

interface LabApiCall {
  url: string;
  method: string;
}

// ────────────────────────────────────────────────────────────────────────────
// Server state mock: бланк живёт в state.instances; каждая операция
// (bulk-values/finalize/mark-printed/revise) мутирует его по контракту
// backend-сервиса, поэтому UI-ре-гидрат ответами честен.
// ────────────────────────────────────────────────────────────────────────────
const state: {
  instances: Array<ReturnType<typeof makeInstanceRecord>>;
  nextInstanceId: number;
} = {
  instances: [],
  nextInstanceId: CREATED_INSTANCE_ID,
};

let labApiCalls: Array<LabApiCall> = [];

// Node-side счётчики (НЕ page-JS): кросс-оригин-безопасны.
let createPostCount = 0;
let createPayloads: Array<Record<string, unknown>> = [];
let createIdempotencyKeys: string[] = [];
let createReplayBodies = new Map<string, Record<string, unknown>>();
let bulkSavePostCount = 0;
let lastBulkSavePayload: Array<Record<string, unknown>> | null = null;
let lastBulkSaveQuery = '';
let previewGetCount = 0;
let finalizePostCount = 0;
let printLabResultsPostCount = 0;
let pdfGetCount = 0;
let markPrintedPostCount = 0;
let revisePostCount = 0;
let historyPatientRequests: string[] = [];

function instanceById(id: number) {
  return state.instances.find((record) => record.id === id);
}

async function installSession(page: Page) {
  await page.addInitScript(({ token, profile }) => {
    window.sessionStorage.setItem('auth_token', token);
    window.sessionStorage.setItem('refresh_token', token);
    window.sessionStorage.setItem('auth_profile', JSON.stringify(profile));
    window.sessionStorage.setItem('user', JSON.stringify(profile));
    // Захват window.open: preview/PDF открывают blob-вкладки; нельзя дать
    // настоящему popup-менеджеру Playwright мешать тесту (паттерн
    // lab-preview-pdf.spec.ts).
    const opened: string[] = [];
    (window as unknown as { __openedWindows: string[] }).__openedWindows = opened;
    window.open = ((url?: string | URL) => {
      opened.push(String(url));
      return {} as Window;
    }) as typeof window.open;
  }, { token: FAKE_TOKEN, profile: LAB_PROFILE });
}

async function installApiMocks(page: Page) {
  // Полный лог вызовов /api/v1 (lab + print) — для ассертов ПОРЯДКА
  // операций (print -> pdf -> mark-printed). Route-хендлеры перехватывают
  // запрос до сети, поэтому счётчик считывает событие request (фиксирует
  // все вызовы, включая замокированные) — паттерн lab-preview-pdf.
  page.on('request', (request) => {
    const url = request.url();
    if (url.includes('/api/v1/lab/') || url.includes('/api/v1/print/')) {
      labApiCalls.push({ url, method: request.method() });
    }
  });

  // Generic fallback: any other API call succeeds empty instead of erroring.
  await page.route('**/api/v1/**', (route) => {
    if (route.request().method() === 'OPTIONS') return route.fulfill({ status: 204 });
    return json(route, {});
  });

  await page.route('**/api/v1/setup/status**', (route) => json(route, { initialized: true }));

  // Очередь: после создания бланка точка входа пациента ссылается на него
  // (queue refresh после finalize/print получает консистентный read-model).
  await page.route('**/api/v1/lab/queue/today**', (route) => json(route, {
    entries: [
      {
        ...QUEUE_ENTRY,
        report_instance_id: state.instances.length > 0 ? state.instances[0].id : null,
      },
    ],
    total: 1,
    date: '2026-09-26',
    timezone: 'Asia/Tashkent',
  }));

  await page.route('**/api/v1/lab/templates**', (route) => json(route, [TEMPLATE_SUMMARY]));
  await page.route('**/api/v1/lab/templates/5', (route) => json(route, TEMPLATE_DETAIL));

  await page.route('**/api/v1/lab/template-resolutions/resolve', (route) => json(route, {
    patient_id: PATIENT_ID,
    visit_id: VISIT_ID,
    resolution_mode: 'mapped',
    service_codes: [],
    service_names: [],
    matched_service_codes: [],
    unmapped_service_codes: [],
    default_template: TEMPLATE_SUMMARY,
    allowed_templates: [TEMPLATE_SUMMARY],
  }));

  // История пациента (patient_id=...) / недавние бланки (limit=...):
  // один endpoint, параметр различает сценарии (loadReportHistory /
  // loadRecentReports оба зовут listInstances).
  await page.route('**/api/v1/lab/report-instances?**', (route) => {
    const patientId = new URL(route.request().url()).searchParams.get('patient_id');
    if (patientId) historyPatientRequests.push(patientId);
    const summaries = state.instances
      .filter((record) => !patientId || record.patient_id === Number(patientId))
      .map(makeHistorySummary);
    return json(route, summaries);
  });

  // CREATE: Idempotency-Key replay-контракт (PR 3351 review round 9) —
  // повторный POST с тем же ключом получает сохранённый ответ.
  await page.route('**/api/v1/lab/report-instances', async (route) => {
    if (route.request().method() !== 'POST') {
      return json(route, []);
    }
    createPostCount += 1;
    const payload = route.request().postDataJSON() as Record<string, unknown>;
    createPayloads.push(payload);
    const idempotencyKey = route.request().headers()['idempotency-key'] || null;
    if (idempotencyKey) {
      createIdempotencyKeys.push(idempotencyKey);
      if (createReplayBodies.has(idempotencyKey)) {
        return json(route, createReplayBodies.get(idempotencyKey));
      }
    }
    const record = makeInstanceRecord(state.nextInstanceId, 'DRAFT', {
      wbcValue: '',
      supersedesInstanceId: null,
      createdAt: '2026-09-26T08:00:00.000000+00:00',
    });
    state.instances.push(record);
    state.nextInstanceId += 1;
    if (idempotencyKey) {
      createReplayBodies.set(idempotencyKey, record as unknown as Record<string, unknown>);
    }
    return json(route, record);
  });

  const instanceRoute = (id: number, handle: (route: Route, record: ReturnType<typeof makeInstanceRecord>) => Promise<unknown> | unknown) =>
    page.route(`**/api/v1/lab/report-instances/${id}`, async (route) => {
      const record = instanceById(id);
      if (!record) {
        return route.fulfill({ status: 404, contentType: 'application/json', body: '{"detail":"not found"}' });
      }
      return (await handle(route, record)) as unknown as void;
    });

  await instanceRoute(CREATED_INSTANCE_ID, (route, record) => json(route, record));
  await instanceRoute(REVISED_INSTANCE_ID, (route, record) => json(route, record));

  // SAVE: bulk-values возвращает instance с СОХРАНЁННЫМИ значениями (реальный
  // backend-контракт — иначе честный ре-гидрат затирал бы draft) и меняет
  // статус DRAFT -> IN_PROGRESS.
  await page.route(`**/api/v1/lab/report-instances/${CREATED_INSTANCE_ID}/bulk-values**`, (route) => {
    bulkSavePostCount += 1;
    const items = (route.request().postDataJSON() as Array<{ field_key?: string; value_text?: string | null }>) || [];
    lastBulkSavePayload = items as Array<Record<string, unknown>>;
    lastBulkSaveQuery = new URL(route.request().url()).search;
    const record = instanceById(CREATED_INSTANCE_ID);
    if (!record) {
      return route.fulfill({ status: 404, contentType: 'application/json', body: '{"detail":"not found"}' });
    }
    const updatedKeys: string[] = [];
    record.sections = record.sections.map((section) => ({
      ...section,
      fields: section.fields.map((field) => {
        const item = items.find((entry) => entry.field_key === field.field_key);
        if (!item) return field;
        updatedKeys.push(String(field.field_key));
        return { ...field, value_text: item.value_text ?? '' };
      }),
    }));
    if (record.status === 'DRAFT') record.status = 'IN_PROGRESS';
    record.available_actions = actionsForStatus(record.status);
    record.updated_at = '2026-09-26T08:05:00.000000+00:00';
    return json(route, { instance: record, updated_field_keys: updatedKeys });
  });

  // PR8: серверный preview-маршрут отдаёт синтетический PDF-блоб.
  await page.route(`**/api/v1/lab/report-instances/${CREATED_INSTANCE_ID}/preview`, (route) => {
    previewGetCount += 1;
    return syntheticPdf(route, '%PDF-synthetic-preview', `lab-report-${CREATED_INSTANCE_ID}-preview.pdf`);
  });

  await page.route(`**/api/v1/lab/report-instances/${CREATED_INSTANCE_ID}/finalize`, (route) => {
    finalizePostCount += 1;
    const record = instanceById(CREATED_INSTANCE_ID);
    if (!record) {
      return route.fulfill({ status: 404, contentType: 'application/json', body: '{"detail":"not found"}' });
    }
    record.status = 'FINALIZED';
    record.available_actions = actionsForStatus(record.status);
    record.updated_at = '2026-09-26T08:10:00.000000+00:00';
    return json(route, record);
  });

  // Печать: прямой канал печати недоступен (нет принтера) — workbench
  // переходит на PDF-fallback (downloadPdf -> window.open -> mark-printed).
  // Этот канал проходит через НАСТОЯЩИЙ PDF-маршрут (тот же движок, что
  // чинил PR8 hotfix) и помечает бланк PRINTED.
  await page.route('**/api/v1/print/lab-results', (route) => {
    printLabResultsPostCount += 1;
    return json(route, { success: false, error: 'no printer attached (mocked)' });
  });

  await page.route(`**/api/v1/lab/report-instances/${CREATED_INSTANCE_ID}/pdf`, (route) => {
    pdfGetCount += 1;
    return syntheticPdf(route, '%PDF-synthetic-final', `lab-report-${CREATED_INSTANCE_ID}.pdf`);
  });

  await page.route(`**/api/v1/lab/report-instances/${CREATED_INSTANCE_ID}/mark-printed`, (route) => {
    markPrintedPostCount += 1;
    const record = instanceById(CREATED_INSTANCE_ID);
    if (!record) {
      return route.fulfill({ status: 404, contentType: 'application/json', body: '{"detail":"not found"}' });
    }
    record.status = 'PRINTED';
    record.available_actions = actionsForStatus(record.status);
    record.updated_at = '2026-09-26T08:15:00.000000+00:00';
    return json(route, record);
  });

  // REVISE: создаёт НОВЫЙ бланк (старый остаётся в истории неизменным) со
  // скопированными значениями и supersedes_instance_id (контракт
  // service.revise: status DRAFT, supersedes_instance_id, values copied).
  await page.route(`**/api/v1/lab/report-instances/${CREATED_INSTANCE_ID}/revise`, (route) => {
    revisePostCount += 1;
    const original = instanceById(CREATED_INSTANCE_ID);
    if (!original) {
      return route.fulfill({ status: 404, contentType: 'application/json', body: '{"detail":"not found"}' });
    }
    const wbcValue = original.sections[0]?.fields[0]?.value_text ?? '';
    const revised = makeInstanceRecord(state.nextInstanceId, 'DRAFT', {
      wbcValue,
      supersedesInstanceId: CREATED_INSTANCE_ID,
      createdAt: '2026-09-26T08:20:00.000000+00:00',
    });
    state.instances.push(revised);
    state.nextInstanceId += 1;
    return json(route, revised);
  });

  await page.route('**/api/v1/lab/catalog/**', (route) => json(route, []));
}

function openedWindowsCount(page: Page) {
  return page.evaluate(() =>
    (window as unknown as { __openedWindows?: string[] }).__openedWindows?.length || 0);
}

test.describe('Lab full-path (final gate, mocked)', () => {
  test.use({ viewport: { width: 1440, height: 1100 } });

  test.beforeEach(async ({ page }) => {
    state.instances = [];
    state.nextInstanceId = CREATED_INSTANCE_ID;
    labApiCalls = [];
    createPostCount = 0;
    createPayloads = [];
    createIdempotencyKeys = [];
    createReplayBodies = new Map<string, Record<string, unknown>>();
    bulkSavePostCount = 0;
    lastBulkSavePayload = null;
    lastBulkSaveQuery = '';
    previewGetCount = 0;
    finalizePostCount = 0;
    printLabResultsPostCount = 0;
    pdfGetCount = 0;
    markPrintedPostCount = 0;
    revisePostCount = 0;
    historyPatientRequests = [];
    await installSession(page);
    await installApiMocks(page);
  });

  test('queue -> create -> fill -> save -> preview -> finalize -> print(PDF) -> revise -> history, one instance lineage', async ({ page }) => {
    // Все 3 tabpanel смонтированы постоянно (hidden-секции PR5), а панель
    // очереди рендерит свою копию истории (lqw-history-*) — скрытую при
    // активной вкладке отчётов. Статусные/исторические ассерты скоупятся
    // на reports-tabpanel: getByRole исключает скрытые узлы из a11y-дерева,
    // но getByText — нет (урок «stable hidden locator» из PR #3351).
    const reportsPanel = page.locator('#lab-panel-tabpanel-reports');

    // ── Фаза 1: очередь ───────────────────────────────────────────────────

    // Пациент без бланка — вход в путь через создание.
    await page.goto('/lab');
    const queueCard = page.getByRole('button', { name: /Пациент Без Бланка/ }).first();
    await expect(queueCard).toBeVisible();
    // Стабилизируем двойную загрузку (URL-sync перезапускает эффекты).
    await page.waitForTimeout(700);

    await queueCard.click();
    // Разрешение шаблонов визита завершено -> вкладка отчётов, режим создания.
    await expect(page.getByRole('button', { name: 'Создать отчёт' })).toBeVisible();

    // ── Фаза 2: создать ────────────────────────────────────────────────
    await page.getByRole('button', { name: 'Создать отчёт' }).click();
    await expect.poll(() => createPostCount).toBe(1);
    await expect(reportsPanel.getByText(`Отчёт #${CREATED_INSTANCE_ID}`).first()).toBeVisible();
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBe(String(CREATED_INSTANCE_ID));

    // Payload контракта CREATE: пациент/приём/визит/шаблон + Idempotency-Key
    // (PR 3351 review round 9 — exactly-once для неидемпотентного POST).
    expect(createPayloads[0]).toMatchObject({
      patient_id: PATIENT_ID,
      appointment_id: 'a-3',
      visit_id: VISIT_ID,
      template_id: 5,
    });
    expect(createIdempotencyKeys).toHaveLength(1);
    expect(createIdempotencyKeys[0]).toBeTruthy();

    // Свежий бланк: черновик, редактор пуст и доступен.
    const fieldInput = page.getByLabel('Результат: Лейкоциты');
    await expect(fieldInput).toBeVisible();
    await expect(fieldInput).toHaveValue('');
    await expect(reportsPanel.getByText('Черновик').first()).toBeVisible();

    // ── Фаза 3: заполнить ──────────────────────────────────────────────
    await fieldInput.fill('6.5');
    await expect(fieldInput).toHaveValue('6.5');
    await expect(page.getByText(/несохранённые изменения/).first()).toBeVisible();

    // ── Фаза 4: сохранить ──────────────────────────────────────────────
    await page.getByRole('button', { name: 'Сохранить черновик' }).click();
    await expect.poll(() => bulkSavePostCount).toBe(1);
    // Optimistic locking: bulk-save несёт expected_updated_at (WF-06).
    expect(lastBulkSaveQuery).toContain('expected_updated_at=');
    // Полная форма payload (persistDraft): field_key + value_text +
    // обнуленные value_numeric/comment — пиним точную форму контракта.
    expect(lastBulkSavePayload).toEqual([{ field_key: 'wbc', value_text: '6.5', value_numeric: null, comment: null }]);
    // Статус DRAFT -> IN_PROGRESS; ре-гидрат ответом сохраняет значение.
    await expect(reportsPanel.getByText('Заполняется').first()).toBeVisible();
    await expect(fieldInput).toHaveValue('6.5');
    await expect(page.getByText(/несохранённые изменения/)).toHaveCount(0);
    // История пациента запрослена после создания и сохранения.
    expect(historyPatientRequests.length).toBeGreaterThanOrEqual(1);

    // ── Фаза 5: preview (PR8, до утверждения) ──────────────────────────
    await page.getByRole('button', { name: 'Предпросмотр PDF' }).click();
    await expect.poll(() => previewGetCount).toBe(1);
    await expect
      .poll(() => openedWindowsCount(page))
      .toBeGreaterThanOrEqual(1);
    // Preview не имеет серверных побочных эффектов (контракт PR8):
    // finalize / финальный /pdf / mark-printed не вызываются.
    expect(finalizePostCount).toBe(0);
    expect(pdfGetCount).toBe(0);
    expect(markPrintedPostCount).toBe(0);
    // Статус не изменился.
    await expect(reportsPanel.getByText('Заполняется').first()).toBeVisible();

    // ── Фаза 6: утвердить ──────────────────────────────────────────────
    await page.getByRole('button', { name: 'Утвердить' }).click();
    const finalizeDialog = page.getByRole('dialog');
    await expect(finalizeDialog).toBeVisible();
    await expect(finalizeDialog.getByRole('heading', { name: 'Утверждение отчёта' })).toBeVisible();
    // Подтверждение в диалоге (не путать с кнопкой actions bar).
    await finalizeDialog.getByRole('button', { name: 'Утвердить' }).click();
    await expect(finalizeDialog).toHaveCount(0);

    await expect.poll(() => finalizePostCount).toBe(1);
    // Бланк утверждён: статус, смена доступных действий.
    await expect(reportsPanel.getByText('Утверждён').first()).toBeVisible();
    await expect(page.getByRole('button', { name: 'Сохранить черновик' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Предпросмотр PDF' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: /Исправленная версия/ })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Печать результата' })).toBeVisible();
    // Утверждение — тоже save-операция: persistDraft мог отправить
    // финальные значения, но финализация ровно одна.
    expect(revisePostCount).toBe(0);
    // История пациента обновилась после утверждения.
    await expect
      .poll(() => historyPatientRequests.filter((patientId) => patientId === String(PATIENT_ID)).length)
      .toBeGreaterThanOrEqual(2);

    // ── Фаза 7: печать (PDF-fallback) ──────────────────────────────────
    await page.getByRole('button', { name: 'Печать результата' }).click();
    // Прямой канал печати отвергнут -> PDF-маршрут -> blob-вкладка ->
    // mark-printed. Порядок строго такой (handlePrint fallback).
    await expect.poll(() => printLabResultsPostCount).toBe(1);
    await expect.poll(() => pdfGetCount).toBe(1);
    await expect.poll(() => markPrintedPostCount).toBe(1);
    const printIndex = labApiCalls.findIndex((call) => call.url.includes('/print/lab-results'));
    const pdfIndex = labApiCalls.findIndex((call) => call.url.includes(`/lab/report-instances/${CREATED_INSTANCE_ID}/pdf`));
    const markPrintedIndex = labApiCalls.findIndex((call) => call.url.includes(`/lab/report-instances/${CREATED_INSTANCE_ID}/mark-printed`));
    expect(printIndex).toBeGreaterThanOrEqual(0);
    expect(pdfIndex).toBeGreaterThan(printIndex);
    expect(markPrintedIndex).toBeGreaterThan(pdfIndex);
    // Blob-вкладка финального PDF открыта (вторая window.open).
    await expect
      .poll(() => openedWindowsCount(page))
      .toBeGreaterThanOrEqual(2);
    await expect(reportsPanel.getByText('Напечатан').first()).toBeVisible();

    // ── Фаза 8: revise ─────────────────────────────────────────────────
    await page.getByRole('button', { name: /Исправленная версия/ }).click();
    const reviseDialog = page.getByRole('dialog');
    await expect(reviseDialog).toBeVisible();
    await expect(reviseDialog.getByRole('heading', { name: 'Создание исправленной версии' })).toBeVisible();
    await reviseDialog.getByRole('button', { name: 'Создать версию' }).click();
    await expect(reviseDialog).toHaveCount(0);

    await expect.poll(() => revisePostCount).toBe(1);
    // Ревизия открывается как АКТИВНЫЙ бланк: новый id, статус черновика,
    // значения скопированы, видна связь с оригиналом (supersedes).
    await expect(reportsPanel.getByText(`Отчёт #${REVISED_INSTANCE_ID}`).first()).toBeVisible();
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBe(String(REVISED_INSTANCE_ID));
    await expect(page.getByText(`← исправленная версия отчёта #${CREATED_INSTANCE_ID}`)).toBeVisible();
    // Статус-бейдж ревизии — черновик (в reports-панели, не скрытая копия).
    await expect(reportsPanel.getByText('Черновик').first()).toBeVisible();
    await expect(fieldInput).toHaveValue('6.5');
    await expect(fieldInput).toBeEnabled();
    // Полный цикл доступен снова: draft-действия вернулись.
    await expect(page.getByRole('button', { name: 'Сохранить черновик' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Утвердить' })).toBeVisible();

    // ── Фаза 9: история ────────────────────────────────────────────────
    // Панель истории пациента показывает ОБЕ записи: ревизия (черновик) и
    // оригинал (напечатан) — «предыдущая версия остаётся в истории».
    await expect(reportsPanel.getByText('Доступные отчёты пациента')).toBeVisible();
    const originalCard = reportsPanel.getByRole('button', {
      name: `Отчёт Rule Demo, ${QUEUE_ENTRY.patient_fio}, Напечатан`,
    });
    const revisedCard = reportsPanel.getByRole('button', {
      name: `Отчёт Rule Demo, ${QUEUE_ENTRY.patient_fio}, Черновик`,
    });
    await expect(originalCard).toBeVisible();
    await expect(revisedCard).toBeVisible();

    // Открытие оригинала из истории: read-only бланк с revise/print.
    await originalCard.click();
    await expect(reportsPanel.getByText(`Отчёт #${CREATED_INSTANCE_ID}`).first()).toBeVisible();
    await expect.poll(() => new URL(page.url()).searchParams.get('instance')).toBe(String(CREATED_INSTANCE_ID));
    await expect(reportsPanel.getByText('Напечатан').first()).toBeVisible();
    await expect(fieldInput).toBeDisabled();
    await expect(page.getByRole('button', { name: /Исправленная версия/ })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Печать результата' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Сохранить черновик' })).toHaveCount(0);

    // Контроль ровно-один-раз по всем мутациям жизненного цикла:
    // бланк создан один раз, финализирован один, напечатан один,
    // отревижен один — дублей от ре-гидратов и refresh-ов нет.
    expect(createPostCount).toBe(1);
    expect(finalizePostCount).toBe(1);
    expect(markPrintedPostCount).toBe(1);
    expect(revisePostCount).toBe(1);
  });
});
