import fs from 'node:fs';
import path from 'node:path';
import { expect, test } from '@playwright/test';

const repoRoot = path.resolve(process.cwd(), '..');
const artifactsDir = path.join(repoRoot, 'output', 'playwright', 'telegram-miniapp-release-gate');

const MINI_APP_VIEWPORTS = [
  { width: 375, height: 812 },
  { width: 768, height: 1024 },
  { width: 1280, height: 960 },
  { width: 1920, height: 1080 },
];

const MINI_APP_SCENARIOS = [
  {
    name: 'onboarding-new',
    query: '?section=appointments',
    auth: 'telegram',
    manifest: buildOnboardingManifest('not_found'),
    expectedTexts: ['Заявка на запись', 'Отправить заявку'],
  },
  {
    name: 'onboarding-pending',
    query: '?section=appointments',
    auth: 'telegram',
    manifest: buildOnboardingManifest('pending_review'),
    expectedTexts: ['Статус заявки', 'Проверить снова'],
  },
  {
    name: 'needs-more-info',
    query: '?section=appointments',
    auth: 'telegram',
    manifest: buildOnboardingManifest('needs_more_info'),
    expectedTexts: ['Статус заявки', 'Обновить заявку'],
  },
  {
    name: 'rejected',
    query: '?section=appointments',
    auth: 'telegram',
    manifest: buildOnboardingManifest('rejected'),
    expectedTexts: ['Статус заявки', 'Обновить заявку'],
  },
  {
    name: 'linked-existing',
    query: '?section=appointments',
    auth: 'telegram',
    manifest: buildOnboardingManifest('linked_existing'),
    expectedTexts: ['Статус заявки', 'Вернуться в Telegram'],
  },
  {
    name: 'created-patient',
    query: '?section=appointments',
    auth: 'telegram',
    manifest: buildOnboardingManifest('created_patient'),
    expectedTexts: ['Статус заявки', 'Вернуться в Telegram'],
  },
  {
    name: 'linked-cabinet',
    query: '?section=cabinet',
    auth: 'telegram',
    manifest: buildLinkedPatientManifest(),
    cabinetSummary: buildLinkedCabinetSummary(),
    expectedTexts: ['Алишер С.', 'Доступ подтверждён'],
  },
  {
    name: 'missing-token',
    query: '?section=appointments',
    auth: 'none',
    expectedTexts: ['Telegram', 'Связаться с клиникой'],
  },
  {
    name: 'wrong-section-token',
    query: '?section=queue&entryToken=qa_appointments_wrong_section',
    auth: 'entry-token',
    manifestErrorReason: 'entry_token_invalid',
    expectedTexts: ['Mini App', 'Проверить снова'],
  },
  {
    name: 'expired-token',
    query: '?section=appointments&entryToken=qa_appointments_expired',
    auth: 'entry-token',
    manifestErrorReason: 'entry_token_expired',
    expectedTexts: ['Mini App', 'Проверить снова'],
  },
];

const ADMIN_PROFILE = {
  id: 7,
  username: 'admin',
  full_name: 'Telegram Admin',
  role: 'Admin',
  roles: ['Admin'],
  email: 'admin@example.com',
  is_active: true,
  is_superuser: true,
};

const REGISTRAR_DASHBOARD = {
  funnel: {
    started: 8,
    opened: 8,
    submitted: 6,
    pendingReview: 3,
    needsMoreInfo: 1,
    linkedExisting: 1,
    createdPatient: 1,
    rejected: 0,
    expired: 0,
    averageReviewTimeMinutes: 18,
    averagePendingTimeMinutes: 32,
    submittedToLinkedOrCreatedRate: 33,
    rejectionRate: 0,
    needsMoreInfoRate: 17,
  },
  dashboard: {
    pendingRequests: 3,
    overdueRequests: 1,
    todaySubmitted: 6,
    linkedOrCreatedToday: 2,
    averageReviewTimeMinutes: 18,
    conversionRate: 33,
  },
};

const REGISTRAR_DUPLICATE_CANDIDATES = [
  {
    candidateId: 'cand-safe-existing-1',
    maskedName: 'Рђ*** РЎ***',
    maskedPhone: '+998 ** *** ** 42',
    dobYear: 1990,
    dobMonth: 5,
    recentVisitSummary: 'РџРѕСЃР»РµРґРЅРёР№ РІРёР·РёС‚: 2026-05-11, С„РёР»РёР°Р» Р§РёР»Р°РЅР·Р°СЂ',
    branch: 'Р§РёР»Р°РЅР·Р°СЂ',
    matchScore: 0.93,
    matchReasons: ['phone_match', 'name_similarity', 'recent_visit_match'],
    riskLevel: 'high',
  },
  {
    candidateId: 'cand-safe-existing-2',
    maskedName: 'Рђ*** РЎ***',
    maskedPhone: '+998 ** *** ** 18',
    dobYear: 1990,
    dobMonth: 5,
    recentVisitSummary: 'РљРѕРЅС‚Р°РєС‚ Р±РµР· Р°РєС‚РёРІРЅС‹С… РІРёР·РёС‚РѕРІ',
    branch: 'Р®РЅСѓСЃР°Р±Р°Рґ',
    matchScore: 0.58,
    matchReasons: ['name_similarity'],
    riskLevel: 'medium',
  },
];

const REGISTRAR_REQUESTS = {
  total: 1,
  items: [
    {
      id: 101,
      status: 'pending_review',
      createdAt: '2026-05-27T09:15:00Z',
      contactName: 'Alisher Safarov',
      contactPhone: '+998 ** *** ** 42',
      desiredService: 'Кардиолог',
      desiredBranch: 'Чиланзар',
      desiredDate: '2026-05-28',
      desiredTime: '15:30',
      note: 'Нужен удобный слот после обеда.',
      auditTrail: [
        {
          action: 'pending_review',
          reviewer: 'System review',
          timestamp: '2026-05-27T09:15:00Z',
        },
      ],
      notificationPreview: {
        title: 'Заявка принята',
        body: 'Регистратура проверит детали записи и свяжет Telegram с картой пациента.',
        ctaLabel: 'Открыть Mini App',
      },
    },
  ],
};

const REGISTRAR_DUPLICATES = {
  reviewed: true,
  topRiskLevel: 'high',
  highConfidenceCandidateExists: true,
  candidates: [
    {
      candidateId: 'cand-safe-existing-1',
      maskedName: 'А*** С***',
      maskedPhone: '+998 ** *** ** 42',
      dobYear: 1990,
      dobMonth: 5,
      recentVisitSummary: 'Последний визит: 2026-05-11, филиал Чиланзар',
      branch: 'Чиланзар',
      matchScore: 0.93,
      matchReasons: ['phone_match', 'name_similarity', 'recent_visit_match'],
      riskLevel: 'high',
    },
    {
      candidateId: 'cand-safe-existing-2',
      maskedName: 'А*** С***',
      maskedPhone: '+998 ** *** ** 18',
      dobYear: 1990,
      dobMonth: 5,
      recentVisitSummary: 'Контакт без активных визитов',
      branch: 'Юнусабад',
      matchScore: 0.58,
      matchReasons: ['name_similarity'],
      riskLevel: 'medium',
    },
  ],
};

test.describe.configure({ mode: 'serial' });

test.beforeAll(() => {
  fs.mkdirSync(artifactsDir, { recursive: true });
});

for (const viewport of MINI_APP_VIEWPORTS) {
  for (const scenario of MINI_APP_SCENARIOS) {
    test(`Mini App release gate ${scenario.name} ${viewport.width}`, async ({ page }) => {
      const errors = monitorRuntimeErrors(page);
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await installMiniAppMocks(page, scenario);
      await page.goto(`/telegram/mini-app/patient${scenario.query}`, { waitUntil: 'domcontentloaded' });
      await waitForMiniAppScenario(page, scenario);
      await expectNoHorizontalOverflow(page);
      await expectNoSensitiveText(page);
      expect(errors).toEqual([]);

      const screenshotPath = path.join(artifactsDir, `miniapp-${scenario.name}-${viewport.width}.png`);
      await page.screenshot({ path: screenshotPath, fullPage: true });
    });
  }
}

test('TelegramManager dashboard and inbox 1280', async ({ page }) => {
  const errors = monitorRuntimeErrors(page);
  await page.setViewportSize({ width: 1280, height: 960 });
  await installAdminMocks(page);
  await page.goto('/admin/integrations/telegram', { waitUntil: 'domcontentloaded' });

  await expect(page.getByText('REQUEST_REVIEW patient requests')).toBeVisible();
  await expect(page.getByText('Conversion rate')).toBeVisible();
  // PR-41: use .first() — memoization changed render timing, causing 3 matches
  await expect(page.getByText('Link this patient').first()).toBeVisible();

  await expectNoHorizontalOverflow(page);
  await expectNoSensitiveText(page);
  expect(errors).toEqual([]);

  await page.screenshot({
    path: path.join(artifactsDir, 'telegram-manager-dashboard-1280.png'),
    fullPage: true,
  });
});

test('TelegramManager duplicate review modal 1280', async ({ page }) => {
  const errors = monitorRuntimeErrors(page);
  await page.setViewportSize({ width: 1280, height: 960 });
  await installAdminMocks(page);
  await page.goto('/admin/integrations/telegram', { waitUntil: 'domcontentloaded' });

  await expect(page.getByText('REQUEST_REVIEW patient requests')).toBeVisible();
  await page.getByRole('button', { name: 'Refresh duplicate candidates for request 101' }).click();
  await expect(page.getByRole('button', { name: 'Link this patient' }).first()).toBeEnabled();
  await page.getByRole('button', { name: 'Link this patient' }).first().click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.getByText('This action will be audit logged.')).toBeVisible();

  await expectNoSensitiveText(page);
  expect(errors).toEqual([]);

  await page.screenshot({
    path: path.join(artifactsDir, 'telegram-manager-link-modal-1280.png'),
    fullPage: true,
  });
});

function buildOnboardingManifest(status) {
  const request = status === 'not_found'
    ? null
    : {
      status,
      contactName: 'Алишер Сафаров',
      contactPhone: '+998 ** *** ** 42',
      desiredService: 'Кардиолог',
      desiredBranch: 'Чиланзар',
      desiredDate: '2026-05-28',
      desiredTime: '15:30',
      note: 'Нужен слот после обеда.',
      reviewMessage: status === 'needs_more_info'
        ? 'Пожалуйста, уточните филиал или удобный интервал.'
        : status === 'rejected'
          ? 'Свяжитесь с клиникой для безопасной проверки контакта.'
          : status === 'pending_review'
            ? 'Заявка принята. Мы проверяем контактные данные.'
            : 'Регистратура завершила проверку заявки.',
    };

  return {
    language: { code: 'ru' },
    scope: { type: 'onboarding' },
    onboarding: { request },
    capabilities: {
      appointments: {
        status: 'request_review_enabled',
        onboarding_request_enabled: true,
      },
      visits: { status: 'staff_approval_required' },
      queue: { status: 'staff_approval_required' },
      forms: { status: 'staff_approval_required' },
      cabinet: { status: 'staff_approval_required' },
      payments: { status: 'staff_approval_required' },
      results: { status: 'staff_approval_required' },
    },
  };
}

function buildLinkedPatientManifest() {
  return {
    language: { code: 'ru' },
    scope: { type: 'linked_patient' },
    capabilities: {
      appointments: { status: 'preview_enabled', preview_enabled: true, create_enabled: true },
      visits: { status: 'summary_enabled', read_enabled: true },
      queue: { status: 'summary_enabled', read_enabled: true },
      forms: { status: 'preview_enabled', read_enabled: true },
      cabinet: { status: 'summary_enabled', read_enabled: true },
      payments: { status: 'summary_enabled', read_enabled: true },
      results: { status: 'ready_pdf_list_enabled', read_enabled: true },
    },
  };
}

function buildLinkedCabinetSummary() {
  return {
    patient: { name: 'Алишер С.' },
    appointments: [
      { id: 3201, status: 'Подтверждён', department: 'Кардиология', date: '2026-05-28' },
    ],
    visits: [
      { id: 8804, status: 'Завершён', department: 'Кардиология', date: '2026-05-11' },
    ],
    queue: [
      { number: 'A-037', status: 'Ожидает', cabinet: '204' },
    ],
    payments: { debt: '150 000' },
    reports: [
      { id: 'rpt-1', name: 'Результат визита', ready_at: '2026-05-11', status: 'ready' },
    ],
  };
}

function monitorRuntimeErrors(page) {
  const errors = [];
  page.on('pageerror', (error) => {
    errors.push(`pageerror:${error.message}`);
  });
  page.on('console', (msg) => {
    const text = msg.text();
    if (
      msg.type() === 'error' &&
      (
        text === 'Failed to load resource: the server responded with a status of 403 (Forbidden)' ||
        text === 'Failed to load resource: the server responded with a status of 500 (Internal Server Error)' ||
        /WebSocket connection to 'ws:\/\/localhost:5173\/ws\/chat(\?token=.*)?' failed: Connection closed before receiving a handshake response/.test(text)
      )
    ) {
      return;
    }
    if (msg.type() === 'error' || /AxiosError|Traceback|pma_|pmo_|entryToken=|paymentId|invoiceId/i.test(text)) {
      errors.push(`console:${text}`);
    }
  });
  return errors;
}

async function installMiniAppMocks(page, scenario) {
  if (scenario.auth === 'telegram') {
    await page.addInitScript(() => {
      window.Telegram = {
        WebApp: {
          initData: 'qa.init.data',
          initDataUnsafe: { user: { language_code: 'ru' } },
          ready() {},
          expand() {},
          close() {},
        },
      };
    });
  }

  await page.route('**/api/v1/setup/status', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ initialized: true }),
    });
  });

  // PR-39 / Medium-11: CSRF bootstrap now enabled by default — mock the endpoint
  await page.route('**/api/v1/auth/csrf-token', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ csrf_token: 'test-csrf-token' }),
    });
  });

  await page.route('**/api/v1/telemetry', async (route) => {
    await route.fulfill({ status: 204, body: '' });
  });

  await page.route('**/api/v1/telegram/mini-app/patient/manifest', async (route) => {
    if (scenario.manifestErrorReason) {
      await route.fulfill({
        status: 403,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: { reason: scenario.manifestErrorReason },
        }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(scenario.manifest),
    });
  });

  await page.route('**/api/v1/telegram/mini-app/cabinet/summary', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(scenario.cabinetSummary || buildLinkedCabinetSummary()),
    });
  });

  await page.route('**/api/v1/telegram/mini-app/onboarding/requests', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        request: {
          ...(scenario.manifest?.onboarding?.request || {}),
          status: 'pending_review',
        },
      }),
    });
  });
}

async function installAdminMocks(page) {
  const token = createJwt(ADMIN_PROFILE);
  await page.addInitScript(({ authToken, profile }) => {
    window.sessionStorage.setItem('auth_token', authToken);
    window.sessionStorage.setItem('auth_profile', JSON.stringify(profile));
    window.sessionStorage.setItem('user', JSON.stringify(profile));
  }, {
    authToken: token,
    profile: ADMIN_PROFILE,
  });

  await page.route('**/api/v1/setup/status', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ initialized: true }),
    });
  });

  await page.route('**/api/v1/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(ADMIN_PROFILE),
    });
  });

  // PR-39 / Medium-11: CSRF bootstrap now enabled by default — mock the endpoint
  await page.route('**/api/v1/auth/csrf-token', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ csrf_token: 'test-csrf-token' }),
    });
  });

  await page.route('**/api/v1/messages/conversations', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    });
  });

  await page.route('**/api/v1/messages/unread', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ unread_count: 0 }),
    });
  });

  await page.route('**/api/v1/users/me/preferences', async (route) => {
    if (route.request().method() === 'PUT') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ theme: 'light' }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ theme: 'light', language: 'ru' }),
    });
  });

  await page.route('**/api/v1/telegram/bot-status', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        active: true,
        configured: true,
        webhook_configured: true,
        stats: { total_users: 42, active_users: 18 },
      }),
    });
  });

  await page.route('**/api/v1/admin/telegram/integration-status', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        active: true,
        webhook_set: true,
        linked_users: 18,
        total_users: 42,
        mode: 'webhook',
        qr_linking_enabled: true,
        contact_linking_enabled: true,
        configured: true,
        patient_bot: { supported_languages: ['ru', 'uz', 'en'] },
        staff_bot: { supported_roles: ['Admin', 'Registrar'] },
        supported_functions: ['queue', 'payments', 'documents'],
        planned_functions: ['results'],
      }),
    });
  });

  await page.route('**/api/v1/admin/telegram/templates', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    });
  });

  await page.route('**/api/v1/telegram/onboarding/analytics/summary', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(REGISTRAR_DASHBOARD),
    });
  });

  await page.route('**/api/v1/telegram/onboarding/requests/export*', async (route) => {
    await route.fulfill({
      status: 200,
      headers: { 'content-type': 'text/csv;charset=utf-8' },
      body: 'created_at,status,contact_name_masked,contact_phone_masked\n2026-05-27,pending_review,A***,+998 ** *** ** 42\n',
    });
  });

  await page.route('**/api/v1/telegram/onboarding/requests/101/search-patients', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(REGISTRAR_DUPLICATES),
    });
  });

  await page.route('**/api/v1/telegram/onboarding/requests*', async (route) => {
    const url = route.request().url();
    if (url.includes('/search-patients') || url.includes('/export')) {
      await route.fallback();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(REGISTRAR_REQUESTS),
    });
  });

  await page.route('**/api/v1/telemetry', async (route) => {
    await route.fulfill({ status: 204, body: '' });
  });
}

function createJwt(profile) {
  const encode = (value) => Buffer.from(JSON.stringify(value)).toString('base64url');
  const now = Math.floor(Date.now() / 1000);
  return [
    encode({ alg: 'HS256', typ: 'JWT' }),
    encode({
      sub: String(profile.id),
      exp: now + 60 * 60,
      role: profile.role,
      username: profile.username,
    }),
    'qa-signature',
  ].join('.');
}

async function waitForMiniAppScenario(page, scenario) {
  await expect(page.locator('main')).toBeVisible();
  await expect(page.locator('h1')).toBeVisible();
  await expect.poll(async () => {
    const text = await page.locator('body').innerText();
    return text.trim().length;
  }).toBeGreaterThan(0);
  await expect.poll(async () => {
    const bodyText = await page.locator('body').innerText();
    return scenario.expectedTexts.every((text) => bodyText.includes(text));
  }, {
    message: `waiting for scenario content: ${scenario.name}`,
  }).toBe(true);
}

async function expectNoHorizontalOverflow(page) {
  const overflow = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));

  expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.clientWidth + 1);
}

async function expectNoSensitiveText(page) {
  const text = await page.locator('body').innerText();
  expect(text).not.toMatch(/pma_[a-z0-9_]+|pmo_[a-z0-9_]+|entryToken=|AxiosError|Traceback|diagnosis|lab details|paymentId|invoiceId/i);
}
