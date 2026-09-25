import { expect, test, type Page, type Route } from '@playwright/test';
import { installAuthenticatedQaHarness } from './support/authenticatedQa';

const mediaItem = (id: number, title: string) => ({
  id,
  title,
  description: null,
  category: 'photo',
  tooth: '16',
  capture_date: '2026-09-20',
  mime_type: 'image/png',
  file_size: 16,
  patient_id: 701,
  visit_id: 901,
  created_at: '2026-09-20T10:00:00Z',
  updated_at: '2026-09-20T10:00:00Z',
});

async function installDentistApiMocks(page: Page) {
  await installAuthenticatedQaHarness(page, { role: 'Doctor' });
  const files = new Map<number, ReturnType<typeof mediaItem>>([[41, mediaItem(41, 'Синтетический снимок')]]);
  let nextId = 42;

  await page.route('**/api/v1/v2/emr/901', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'No synthetic EMR yet' }) });
      return;
    }
    return route.fallback();
  });

  await page.route('**/api/v1/patients/**', async (route) => {
    if (route.request().method() !== 'GET') return route.fallback();
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([{
        id: 701,
        first_name: 'Synthetic',
        last_name: 'Patient',
        full_name: 'Synthetic Patient',
        phone: '0000000000',
        created_at: '2026-09-20T10:00:00Z',
      }]),
    });
  });

  await page.route('**/api/v1/dental/media**', async (route: Route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const idMatch = path.match(/\/dental\/media\/(\d+)(?:\/content)?$/);
    const id = idMatch ? Number(idMatch[1]) : null;

    if (path === '/api/v1/dental/media' && request.method() === 'GET') {
      const items = [...files.values()];
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items, total: items.length, page: 1, size: 100 }),
      });
      return;
    }

    if (path === '/api/v1/dental/media' && request.method() === 'POST') {
      const created = mediaItem(nextId++, 'Новый синтетический снимок');
      files.set(created.id, created);
      await route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify(created) });
      return;
    }

    if (id !== null && path.endsWith('/content') && request.method() === 'GET') {
      await route.fulfill({ status: 200, contentType: 'image/png', body: Buffer.from('synthetic image bytes') });
      return;
    }

    if (id !== null && request.method() === 'PATCH') {
      const current = files.get(id);
      if (!current) {
        await route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'not found' }) });
        return;
      }
      const patch = request.postDataJSON() as Partial<ReturnType<typeof mediaItem>>;
      const updated = { ...current, ...patch };
      files.set(id, updated);
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(updated) });
      return;
    }

    if (id !== null && request.method() === 'DELETE') {
      files.delete(id);
      await route.fulfill({ status: 204, body: '' });
      return;
    }

    return route.fallback();
  });
}

async function installDentistQueueFlowMocks(page: Page) {
  const requests: string[] = [];

  await page.route('**/api/v1/queue/available-specialists', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ specialists: [{ id: 7, specialty: 'dentistry', doctor_name: 'Synthetic Dentist' }] }),
    });
  });

  await page.route('**/api/v1/registrar/queues/today**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ queues: [{ id: 7, specialist_id: 7, specialty: 'dentistry', entries: [], is_open: true }] }),
    });
  });

  await page.route('**/api/v1/queue/7/call-next**', async (route) => {
    requests.push('call-next');
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        patient: { id: 91, patient_id: 701, name: 'Synthetic Patient', number: 8 },
      }),
    });
  });

  await page.route('**/api/v1/doctor/queue/91/start-visit', async (route) => {
    requests.push('start-visit');
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, patient_id: 701, visit_id: 901, status: 'in_progress' }),
    });
  });

  await page.route('**/api/v1/v2/emr/901', async (route) => {
    if (route.request().method() !== 'POST') return route.fallback();
    requests.push('save-emr');
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ row_version: 2 }),
    });
  });

  await page.route('**/api/v1/doctor/queue/91/complete', async (route) => {
    requests.push('complete-queue');
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true }) });
  });

  await page.route('**/api/v1/doctor/dentistry/queue/today', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ entries: [] }) });
  });

  return requests;
}

async function openPhotoArchive(page: Page) {
  await page.goto('/doctor/dentistry?patientId=701&visitId=901&tab=visit', { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('button', { name: /Фотоархив/ })).toBeVisible({ timeout: 20_000 });
  await page.getByRole('button', { name: /Фотоархив/ }).click();
  await expect(page.getByRole('heading', { name: /Фото и рентген архив/ })).toBeVisible();
  await expect(page.getByText('Синтетический снимок')).toBeVisible();
}

test.describe('Dentist panel — synthetic product flow', () => {
  test('queue call starts the returned visit, saves EMR, then completes the queue entry', async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('language', 'ru'));
    await installDentistApiMocks(page);
    const requests = await installDentistQueueFlowMocks(page);
    await page.setViewportSize({ width: 1280, height: 800 });

    await page.goto('/doctor/dentistry?tab=queue', { waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: 'Вызвать', exact: true }).click();
    const startVisit = page.getByRole('button', { name: /Начать приём.*Synthetic Patient/i });
    await expect(startVisit).toBeVisible();
    await startVisit.click();

    const complaint = page.getByRole('textbox', { name: 'Жалобы и анамнез пациента' });
    await expect(complaint).toBeVisible();
    await complaint.fill('Synthetic complaint for lifecycle check');
    await page.getByRole('button', { name: 'Завершить приём и вызвать следующего пациента' }).click();

    const confirmDialog = page.getByRole('dialog');
    await expect(confirmDialog.getByRole('heading', { name: 'Завершить приём?' })).toBeVisible();
    await confirmDialog.getByRole('button', { name: 'Завершить приём', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Вызвать', exact: true })).toBeVisible();
    expect(requests).toEqual(['call-next', 'start-visit', 'save-emr', 'complete-queue']);
  });

  test('legacy tabs resolve to supported screens and server search is usable', async ({ page }) => {
    await installDentistApiMocks(page);
    await page.setViewportSize({ width: 1280, height: 800 });

    await page.goto('/doctor/dentistry?tab=appointments', { waitUntil: 'domcontentloaded' });
    const search = page.getByRole('searchbox', { name: 'Поиск пациента' });
    await expect(search).toBeVisible({ timeout: 20_000 });
    await search.fill('Synthetic');
    await expect(page.getByText('Synthetic Patient')).toBeVisible();
    await page.getByRole('button', { name: /Выбрать пациента Synthetic Patient/ }).click();
    await expect(page.getByRole('region', { name: 'Notifications Alt+T' })).toContainText(/нет активного визита/);

    await page.goto('/doctor/dentistry?tab=ai-assistant', { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { name: 'Протоколы визитов' })).toBeVisible({ timeout: 20_000 });
    await page.goto('/doctor/dentistry?tab=unknown-tab', { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { name: 'Управление онлайн-очередью' })).toBeVisible({ timeout: 20_000 });
  });

  test('photo archive loads, previews, uploads, and rehydrates persisted files', async ({ page }, testInfo) => {
    await installDentistApiMocks(page);
    await page.setViewportSize({ width: 1280, height: 800 });
    await openPhotoArchive(page);

    const firstContent = page.getByRole('button', { name: 'Просмотр' }).first();
    await firstContent.click();
    await expect(page.getByRole('dialog').getByRole('heading', { name: 'Синтетический снимок' })).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.getByText('Синтетический снимок')).toBeVisible();

    await page.locator('input[type="file"]').setInputFiles({
      name: 'synthetic.png',
      mimeType: 'image/png',
      buffer: Buffer.from('synthetic attachment'),
    });
    await page.getByRole('textbox', { name: 'Название снимка' }).fill('Новый снимок QA');
    await page.getByRole('button', { name: 'Загрузить файлы', exact: true }).click();
    await expect(page.getByRole('status').getByText('Снимок сохранён.')).toBeVisible();
    await expect(page.getByText('Новый синтетический снимок')).toBeVisible();

    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('button', { name: /Фотоархив/ })).toBeVisible({ timeout: 20_000 });
    await page.getByRole('button', { name: /Фотоархив/ }).click();
    await expect(page.getByText('Новый синтетический снимок')).toBeVisible({ timeout: 20_000 });
    const screenshotPath = testInfo.outputPath('dentist-photo-archive.png');
    await page.screenshot({ path: screenshotPath, fullPage: true });
    await testInfo.attach('dentist-photo-archive', { path: screenshotPath, contentType: 'image/png' });
  });

  test('patient search screen fits supported viewport and theme combinations', async ({ page }, testInfo) => {
    await page.addInitScript(() => {
      localStorage.setItem('language', 'ru');
    });
    await installDentistApiMocks(page);

    const measurements: Array<{ width: number; theme: string; firstContentMs: number; repeatContentMs: number }> = [];
    for (const width of [375, 768, 1280]) {
      for (const theme of ['light', 'dark']) {
        await page.addInitScript((mode) => {
          localStorage.setItem('colorScheme', mode);
          localStorage.setItem('theme', mode);
          localStorage.setItem('ui_theme', mode);
        }, theme);
        await page.setViewportSize({ width, height: 860 });

        const start = Date.now();
        await page.goto('/doctor/dentistry?tab=patients', { waitUntil: 'domcontentloaded' });
        const firstSearch = page.getByRole('searchbox', { name: 'Поиск пациента' });
        await expect(firstSearch).toBeVisible({ timeout: 20_000 });
        await firstSearch.fill('Synthetic');
        await expect(page.getByRole('button', { name: /Выбрать пациента Synthetic Patient/ })).toBeVisible();
        const firstContentMs = Date.now() - start;

        const repeatStart = Date.now();
        await page.goto('/doctor/dentistry?tab=patients', { waitUntil: 'domcontentloaded' });
        const repeatSearch = page.getByRole('searchbox', { name: 'Поиск пациента' });
        await expect(repeatSearch).toBeVisible({ timeout: 20_000 });
        await repeatSearch.fill('Synthetic');
        await expect(page.getByRole('button', { name: /Выбрать пациента Synthetic Patient/ })).toBeVisible();
        const repeatContentMs = Date.now() - repeatStart;

        await expect.poll(() => page.evaluate(() => document.body.getAttribute('data-theme'))).toBe(theme);
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
        expect(overflow, `horizontal overflow at ${width}px in ${theme} theme`).toBe(false);
        measurements.push({ width, theme, firstContentMs, repeatContentMs });
        const screenshotPath = testInfo.outputPath(`dentist-patients-${width}-${theme}.png`);
        await page.screenshot({ path: screenshotPath, fullPage: true });
        await testInfo.attach(`dentist-patients-${width}-${theme}`, { path: screenshotPath, contentType: 'image/png' });
      }
    }
    testInfo.annotations.push({ type: 'content-timing-ms', description: JSON.stringify(measurements) });

    console.log(`Synthetic dentist content timings (ms): ${JSON.stringify(measurements)}`);
  });

  test('photo archive fits supported viewport and theme combinations', async ({ page }, testInfo) => {
    await page.addInitScript(() => {
      localStorage.setItem('language', 'ru');
    });
    await installDentistApiMocks(page);

    for (const width of [375, 768, 1280]) {
      for (const theme of ['light', 'dark']) {
        await page.addInitScript((mode) => {
          localStorage.setItem('colorScheme', mode);
          localStorage.setItem('theme', mode);
          localStorage.setItem('ui_theme', mode);
        }, theme);
        await page.setViewportSize({ width, height: 860 });
        await openPhotoArchive(page);
        await expect.poll(() => page.evaluate(() => document.body.getAttribute('data-theme'))).toBe(theme);
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
        expect(overflow, `photo archive horizontal overflow at ${width}px in ${theme} theme`).toBe(false);
        if (width === 375 && theme === 'light') {
          const screenshotPath = testInfo.outputPath('dentist-photo-archive-375-light.png');
          await page.screenshot({ path: screenshotPath, fullPage: true });
          await testInfo.attach('dentist-photo-archive-375-light', { path: screenshotPath, contentType: 'image/png' });
        }
      }
    }
  });
});
