import { test, expect, type Page, type Response } from '@playwright/test';

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
  routing_specialists?: Array<string | number>;
  is_open?: boolean;
  entries?: QueueEntrySnapshot[];
}

interface QueueSnapshotPayload {
  queues?: DoctorQueueSnapshot[];
}

interface AvailableSpecialistOption {
  id?: string | number | null;
  doctor_name?: string | null;
  full_name?: string | null;
  name?: string | null;
  user?: { full_name?: string | null };
  specialty_display?: string | null;
  specialty?: string | null;
  cabinet?: string | number | null;
}

interface AvailableSpecialistsPayload {
  specialists?: AvailableSpecialistOption[];
}

interface AvailableSpecialistsObservation {
  ok: boolean;
  payload: AvailableSpecialistsPayload;
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

const availableSpecialistsByPage = new WeakMap<Page, Promise<AvailableSpecialistsObservation>>();

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

function isAvailableSpecialistsResponse(response: Response): boolean {
  if (response.request().method() !== 'GET') return false;

  try {
    return new URL(response.url()).pathname.endsWith('/queue/available-specialists');
  } catch {
    return false;
  }
}

function observeAvailableSpecialists(page: Page): void {
  let resolveObservation: (observation: AvailableSpecialistsObservation) => void = () => undefined;
  const observation = new Promise<AvailableSpecialistsObservation>((resolve) => {
    resolveObservation = resolve;
  });

  const onResponse = (response: Response) => {
    if (!isAvailableSpecialistsResponse(response)) return;
    page.off('response', onResponse);

    void response.json().then(
      (payload: AvailableSpecialistsPayload) => {
        resolveObservation({ ok: response.ok(), payload });
      },
      () => resolveObservation({ ok: response.ok(), payload: {} })
    );
  };

  page.on('response', onResponse);
  availableSpecialistsByPage.set(page, observation);
}

async function availableSpecialistsFor(page: Page): Promise<AvailableSpecialistOption[]> {
  const observation = availableSpecialistsByPage.get(page);
  expect(observation, 'Available-specialists response must be observed before queue navigation.').toBeDefined();

  const result = await observation!;
  expect(result.ok, 'The available-specialists request must succeed.').toBe(true);
  expect(
    Array.isArray(result.payload.specialists),
    'The available-specialists response must include its specialists list.'
  ).toBe(true);
  return result.payload.specialists!;
}

function doctorIdForOptionLabel(
  optionLabel: string,
  specialists: AvailableSpecialistOption[]
): string {
  const matches = specialists.filter((specialist) => {
    if (specialist.id === null || specialist.id === undefined) return false;

    const doctorName = specialist.doctor_name
      || specialist.full_name
      || specialist.user?.full_name
      || specialist.name;
    if (!doctorName) return false;

    const specialtyLabel = specialist.specialty_display || specialist.specialty || '';
    const labelPrefix = normalizedText(
      `${doctorName}${specialtyLabel ? ` • ${specialtyLabel}` : ''}`
    );
    if (!optionLabel.startsWith(labelPrefix)) return false;

    const suffix = optionLabel.slice(labelPrefix.length);
    return !specialist.cabinet || suffix.includes(String(specialist.cabinet));
  });

  expect(
    matches,
    'The selected doctor option must resolve to exactly one available-specialists ID.'
  ).toHaveLength(1);

  const doctorId = String(matches[0].id);
  expect(doctorId, 'The selected doctor ID must be numeric.').toMatch(/^\d+$/);
  return doctorId;
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

  const optionLabel = normalizedText(await doctorOption.innerText());
  const specialists = await availableSpecialistsFor(page);
  const expectedDoctorId = doctorIdForOptionLabel(optionLabel, specialists);
  const previousDoctorId = new URL(page.url()).searchParams.get('doctor');
  expect(
    expectedDoctorId,
    'The next selection must be a different doctor so the route and queue refresh can be distinguished.'
  ).not.toBe(previousDoctorId);

  const snapshotPromise = waitForQueueSnapshot(page);
  await doctorOption.click();

  await expect.poll(
    () => new URL(page.url()).searchParams.get('doctor'),
    { message: 'Selecting the displayed doctor must persist that exact ID in the canonical route.' }
  ).toBe(expectedDoctorId);
  await expect(doctorFilter).toContainText(optionLabel);

  const payload = await snapshotPromise;
  await expect(page.locator('.mqm-stats-grid')).toBeVisible();
  return { doctorId: expectedDoctorId, payload };
}

async function selectFirstAvailableDoctor(page: Page): Promise<QueueDoctorSelection> {
  const count = await selectableDoctorOptionCount(page);
  expect(count, 'Queue system E2E requires at least one available synthetic doctor.').toBeGreaterThan(1);
  return selectDoctorOption(page, 1);
}

function queueForSelectedDoctor(
  payload: QueueSnapshotPayload,
  doctorId: string
): DoctorQueueSnapshot | undefined {
  const selectedDoctorId = Number(doctorId);
  return payload.queues?.find((queue) => {
    if (
      queue.specialist_id !== null
      && queue.specialist_id !== undefined
      && Number(queue.specialist_id) === selectedDoctorId
    ) {
      return true;
    }

    return queue.routing_specialists?.some(
      (routedSpecialistId) => Number(routedSpecialistId) === selectedDoctorId
    ) ?? false;
  });
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
    const queue = queueForSelectedDoctor(selection.payload, selection.doctorId);
    const signatures = visibleQueueSignatures(queue);
    const hasWaitingEntry = (queue?.entries ?? []).some((entry) => entry.status === 'waiting');

    if (queue && signatures && (!requiresWaitingEntry || hasWaitingEntry)) {
      return { selection, queue, signatures };
    }
  }

  const requiredData = requiresWaitingEntry
    ? 'a doctor-owned or resource-routed queue with a waiting synthetic entry'
    : 'a doctor-owned or resource-routed queue with numbered synthetic entries';
  throw new Error('Queue system E2E requires ' + requiredData + '; seed the disposable test database before running this spec.');
}

test.describe('Queue System Tests', () => {
  // Some queue scenarios change synthetic queue state. Keep this file serial so
  // those actions cannot race with the read-only queue assertions below.
  test.describe.configure({ mode: 'serial' });

  test.beforeEach(async ({ page }) => {
    observeAvailableSpecialists(page);
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

      const queue = queueForSelectedDoctor(selection.payload, selection.doctorId);
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
    const updatedQueue = queueForSelectedDoctor(updatedPayload, selection.doctorId);
    expect(updatedQueue, 'The selected doctor or routed resource queue must remain available after call-next.').toBeDefined();

    const waitingAfter = (updatedQueue?.entries ?? []).filter((entry) => entry.status === 'waiting').length;
    const calledAfter = (updatedQueue?.entries ?? []).filter((entry) => entry.status === 'called').length;
    expect(waitingAfter < waitingBefore, 'A successful call must remove one entry from the waiting state.').toBe(true);
    expect(calledAfter > calledBefore, 'A successful call must place an entry in the called state.').toBe(true);
  });
});
