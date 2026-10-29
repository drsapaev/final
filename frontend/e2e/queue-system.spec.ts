import { test, expect, type Page } from '@playwright/test';

const REGISTRAR_USERNAME = process.env.QA_REGISTRAR_USERNAME || 'registrar@clinic.com';
const REGISTRAR_QUEUE_PATH = '/registrar/queue';
const QUEUE_SNAPSHOT_PATH = '/registrar/queues/today';
const QUEUE_ROW_SELECTOR = '.qt-table-container tbody tr.mac-table-row';

interface QueueEntrySnapshot {
  queue_number?: string | number | null;
  number?: string | number | null;
  patient_name?: string | null;
  name?: string | null;
  source?: string | null;
  source_kind?: string | null;
  status?: string | null;
}

interface DoctorQueueSnapshot {
  specialist_id?: string | number | null;
  queue_resource_id?: string | number | null;
  is_open?: boolean;
  entries?: QueueEntrySnapshot[];
}

interface QueueSnapshotPayload {
  queues?: DoctorQueueSnapshot[];
}

interface QueueDoctorSelection {
  doctorId: string;
  payload: QueueSnapshotPayload;
}

interface VisibleQueueSignature {
  number: string;
  patient: string;
  source: string;
}

function requiredRegistrarPassword() {
  const password = process.env.QA_REGISTRAR_PASSWORD;
  if (!password) {
    throw new Error('Set QA_REGISTRAR_PASSWORD to run queue system e2e tests.');
  }
  return password;
}

function isQueueSnapshotResponse(response: { url(): string; request(): { method(): string } }) {
  return response.request().method() === 'GET' && response.url().includes(QUEUE_SNAPSHOT_PATH);
}

async function waitForQueueSnapshot(page: Page): Promise<QueueSnapshotPayload> {
  const response = await page.waitForResponse(isQueueSnapshotResponse, { timeout: 15_000 });
  expect(response.ok(), 'Registrar queue snapshot request must succeed.').toBe(true);
  return await response.json() as QueueSnapshotPayload;
}

async function selectableDoctorOptionCount(page: Page): Promise<number> {
  const doctorFilter = page.locator('#modern-queue-doctor');
  await expect(doctorFilter).toBeVisible();
  await doctorFilter.click();

  const options = page.getByRole('listbox').getByRole('option');
  await expect(
    options.nth(1),
    'Queue system E2E requires at least one available synthetic doctor.'
  ).toBeVisible({ timeout: 15_000 });

  const count = await options.count();
  await doctorFilter.click();
  return count;
}

async function selectDoctorOption(page: Page, optionIndex: number): Promise<QueueDoctorSelection> {
  const doctorFilter = page.locator('#modern-queue-doctor');
  await expect(doctorFilter).toBeVisible();
  await doctorFilter.click();

  const doctorOption = page.getByRole('listbox').getByRole('option').nth(optionIndex);
  await expect(
    doctorOption,
    'Queue system E2E requires the expected synthetic doctor option to exist.'
  ).toBeVisible({ timeout: 15_000 });

  const snapshotPromise = waitForQueueSnapshot(page);
  await doctorOption.click();

  await expect.poll(
    () => new URL(page.url()).searchParams.get('doctor'),
    { message: 'Selecting a doctor must persist its ID in the canonical route.' }
  ).not.toBeNull();

  const doctorId = new URL(page.url()).searchParams.get('doctor');
  expect(doctorId, 'The selected doctor ID must be present in the route.').toMatch(/^\d+$/);

  const payload = await snapshotPromise;
  await expect(page.locator('.mqm-stats-grid')).toBeVisible();
  return { doctorId: doctorId!, payload };
}

async function selectFirstAvailableDoctor(page: Page): Promise<QueueDoctorSelection> {
  const count = await selectableDoctorOptionCount(page);
  expect(count, 'Queue system E2E requires at least one available synthetic doctor.').toBeGreaterThan(1);
  return selectDoctorOption(page, 1);
}

function queueOwnedByDoctor(
  payload: QueueSnapshotPayload,
  doctorId: string
): DoctorQueueSnapshot | undefined {
  return payload.queues?.find((queue) =>
    String(queue.specialist_id) === doctorId
    && (queue.queue_resource_id === null || queue.queue_resource_id === undefined)
  );
}

function normalizedText(value: string): string {
  return value.replace(/\s+/g, ' ').trim();
}

function visibleQueueSignatures(queue: DoctorQueueSnapshot | undefined): VisibleQueueSignature[] | null {
  const entries = queue?.entries ?? [];
  if (entries.length === 0) return null;

  const signatures: VisibleQueueSignature[] = [];
  for (const entry of entries) {
    const number = entry.queue_number ?? entry.number;
    const patient = normalizedText(entry.patient_name ?? entry.name ?? '');
    if (
      number === null
      || number === undefined
      || !/^\d+$/.test(String(number))
      || !patient
      || patient === '—'
      || patient === 'Неизвестный пациент'
    ) {
      return null;
    }

    const isOnline = entry.source === 'online'
      || entry.source === 'qr'
      || entry.source_kind === 'online_queue';
    signatures.push({
      number: String(number),
      patient,
      source: isOnline ? 'QR' : 'Desk',
    });
  }

  return signatures;
}

function signatureKey(signature: VisibleQueueSignature): string {
  return [signature.number, signature.patient, signature.source].join('|');
}

async function expectVisibleQueueToMatch(
  page: Page,
  expected: VisibleQueueSignature[],
  message: string
): Promise<void> {
  await expect.poll(async () => {
    const actual = await page.locator(QUEUE_ROW_SELECTOR).evaluateAll((rows) =>
      rows.map((row) => {
        const number = row.querySelector('.qt-table-cell-number')?.textContent?.trim() ?? '';
        const patientCell = row.querySelector('.qt-table-cell-primary');
        const patient = Array.from(patientCell?.childNodes ?? [])
          .filter((node) => node.nodeType === Node.TEXT_NODE)
          .map((node) => node.textContent ?? '')
          .join('')
          .replace(/\s+/g, ' ')
          .trim();
        const source = patientCell?.querySelector('.qt-source-badge')?.textContent?.trim() ?? '';
        return { number, patient, source };
      })
    );

    return actual.length === expected.length && actual.every((row, index) =>
      row.number === expected[index].number
      && row.patient === expected[index].patient
      && row.source === expected[index].source
    );
  }, { message, timeout: 15_000 }).toBe(true);
}

async function selectDoctorWithQueue(
  page: Page,
  requiresWaitingEntry = false
): Promise<{ selection: QueueDoctorSelection; queue: DoctorQueueSnapshot; signatures: VisibleQueueSignature[] }> {
  const optionCount = await selectableDoctorOptionCount(page);

  for (let optionIndex = 1; optionIndex < optionCount; optionIndex += 1) {
    const selection = await selectDoctorOption(page, optionIndex);
    const queue = queueOwnedByDoctor(selection.payload, selection.doctorId);
    const signatures = visibleQueueSignatures(queue);
    const hasWaitingEntry = (queue?.entries ?? []).some((entry) => entry.status === 'waiting');

    if (queue && signatures && (!requiresWaitingEntry || hasWaitingEntry)) {
      return { selection, queue, signatures };
    }
  }

  const requiredData = requiresWaitingEntry
    ? 'a doctor-owned queue with a waiting synthetic entry'
    : 'a doctor-owned queue with numbered synthetic entries';
  throw new Error('Queue system E2E requires ' + requiredData + '; seed the disposable test database before running this spec.');
}

test.describe('Queue System Tests', () => {
  // Some queue scenarios change synthetic queue state. Keep this file serial so
  // those actions cannot race with the read-only queue assertions below.
  test.describe.configure({ mode: 'serial' });

  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[type="text"]', REGISTRAR_USERNAME);
    await page.fill('input[type="password"]', requiredRegistrarPassword());
    await page.click('button[type="submit"]');
    await page.waitForLoadState('networkidle');
  });

  test('should display queue management interface', async ({ page }) => {
    await page.goto(REGISTRAR_QUEUE_PATH);
    await expect(page).toHaveURL(/\/registrar\/queue(?:\?.*)?$/);
    await expect(page.locator('text=Очередь')).toBeVisible();
    await expect(page.locator('text=Онлайн-очередь')).toBeVisible();
  });

  test('should keep doctor-scoped actions disabled until a doctor is selected', async ({ page }) => {
    await page.goto(REGISTRAR_QUEUE_PATH);

    const openReceptionButton = page.getByRole('button', { name: /Открыть при[её]м/ });
    const callNextButton = page.locator('button[title="Backend call-next command"]');

    await expect(page.locator('.qt-empty-state')).toBeVisible();
    await expect(openReceptionButton).toBeDisabled();
    await expect(callNextButton).toBeDisabled();

    await selectFirstAvailableDoctor(page);
    await expect(callNextButton).toBeEnabled();

    // The page does not currently expose is_open in its queue snapshot. In this
    // registrar view, selecting a doctor must enable its open-reception action.
    await expect(openReceptionButton).toBeEnabled();
  });

  test('should display backend-assigned queue numbering for the selected doctor', async ({ page }) => {
    await page.goto(REGISTRAR_QUEUE_PATH);

    const { signatures } = await selectDoctorWithQueue(page);
    expect(
      signatures.every((signature) => /^\d+$/.test(signature.number)),
      'Synthetic queue entries must include backend-assigned numeric queue numbers.'
    ).toBe(true);

    await expectVisibleQueueToMatch(
      page,
      signatures,
      'Visible queue numbers and patient labels must match the selected synthetic doctor queue.'
    );
  });

  test('should display queue statistics after selecting a doctor', async ({ page }) => {
    await page.goto(REGISTRAR_QUEUE_PATH);
    await selectFirstAvailableDoctor(page);

    const statsGrid = page.locator('.mqm-stats-grid');
    await expect(statsGrid).toBeVisible();
    await expect(statsGrid.locator('.mqm-stat-card')).toHaveCount(3);
  });

  test('should show the correct queue after switching between doctors', async ({ page }) => {
    await page.goto(REGISTRAR_QUEUE_PATH);
    const optionCount = await selectableDoctorOptionCount(page);

    let firstDoctor: { id: string; signatures: VisibleQueueSignature[] } | null = null;
    let secondDoctor: { id: string; signatures: VisibleQueueSignature[] } | null = null;
    const visitedDoctorIds = new Set<string>();

    for (let optionIndex = 1; optionIndex < optionCount; optionIndex += 1) {
      const selection = await selectDoctorOption(page, optionIndex);
      if (visitedDoctorIds.has(selection.doctorId)) continue;
      visitedDoctorIds.add(selection.doctorId);

      const queue = queueOwnedByDoctor(selection.payload, selection.doctorId);
      const signatures = visibleQueueSignatures(queue);
      if (!signatures) continue;

      if (!firstDoctor) {
        firstDoctor = { id: selection.doctorId, signatures };
        await expectVisibleQueueToMatch(
          page,
          signatures,
          'Visible queue rows must match the first selected synthetic doctor queue.'
        );
        continue;
      }

      const displaysDifferentQueue = JSON.stringify(
        signatures.map(signatureKey)
      ) !== JSON.stringify(firstDoctor.signatures.map(signatureKey));
      if (!displaysDifferentQueue) continue;

      secondDoctor = { id: selection.doctorId, signatures };
      await expectVisibleQueueToMatch(
        page,
        signatures,
        'Switching doctors must replace the visible rows with the newly selected synthetic doctor queue.'
      );
      break;
    }

    expect(
      Boolean(firstDoctor && secondDoctor && firstDoctor.id !== secondDoctor.id),
      'Seed two doctors with non-empty, visibly distinct synthetic queues to verify doctor-specific filtering.'
    ).toBe(true);
  });

  test('should call the next waiting patient for the selected doctor', async ({ page }) => {
    await page.goto(REGISTRAR_QUEUE_PATH);
    const { selection, queue } = await selectDoctorWithQueue(page, true);
    const waitingBefore = (queue.entries ?? []).filter((entry) => entry.status === 'waiting').length;
    const calledBefore = (queue.entries ?? []).filter((entry) => entry.status === 'called').length;
    expect(waitingBefore, 'The selected synthetic queue must contain a waiting entry.').toBeGreaterThan(0);

    const callNextButton = page.locator('button[title="Backend call-next command"]');
    await expect(callNextButton).toBeVisible();
    await expect(callNextButton).toBeEnabled();

    const callResponsePromise = page.waitForResponse((response) =>
      response.request().method() === 'POST'
      && response.url().includes('/queue/' + selection.doctorId + '/call-next')
    );
    const updatedSnapshotPromise = waitForQueueSnapshot(page);
    await callNextButton.click();

    const callResponse = await callResponsePromise;
    expect(callResponse.ok(), 'The call-next command must succeed for the seeded synthetic queue.').toBe(true);
    const updatedPayload = await updatedSnapshotPromise;
    const updatedQueue = queueOwnedByDoctor(updatedPayload, selection.doctorId);
    expect(updatedQueue, 'The selected doctor queue must remain available after call-next.').toBeDefined();

    const waitingAfter = (updatedQueue?.entries ?? []).filter((entry) => entry.status === 'waiting').length;
    const calledAfter = (updatedQueue?.entries ?? []).filter((entry) => entry.status === 'called').length;
    expect(waitingAfter < waitingBefore, 'A successful call must remove one entry from the waiting state.').toBe(true);
    expect(calledAfter > calledBefore, 'A successful call must place an entry in the called state.').toBe(true);
  });
});
