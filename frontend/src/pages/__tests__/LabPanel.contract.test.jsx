import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const labPanelPath = path.resolve(__dirname, '../LabPanel.jsx');

const readLabPanelSource = () => fs.readFileSync(labPanelPath, 'utf8');

const extractBlock = (source, startMarker, endMarker) => {
  const start = source.indexOf(startMarker);
  expect(start).toBeGreaterThanOrEqual(0);
  const end = source.indexOf(endMarker, start);
  expect(end).toBeGreaterThan(start);
  return source.slice(start, end);
};

// P-03 fix: контракт-тесты обновлены под lab/queue/today façade.
// Раньше тесты проверяли, что LabPanel делает прямой fetch к
// /registrar/queues/today и нормализует ответ через formatAppointmentEntry.
// Теперь эти обязанности перенесены на backend (GET /lab/queue/today),
// а LabPanel использует labReportingApi.listQueueToday().
describe('LabPanel queue/report status contract', () => {
  it('does not duplicate formatAppointmentEntry — normalization moved to backend façade', () => {
    // P-03 fix: formatAppointmentEntry удалена, нормализация на backend.
    // Если кто-то вернёт эту функцию — контракт нарушен.
    const source = readLabPanelSource();
    expect(source).not.toContain('function formatAppointmentEntry(');
    expect(source).not.toContain('formatAppointmentEntry(queue, entry)');
  });

  it('uses labReportingApi.listQueueToday façade instead of direct registrar fetch', () => {
    const source = readLabPanelSource();
    const loadBlock = extractBlock(
      source,
      'const loadLabAppointments = useCallback(async () => {',
      'const loadMoreAppointments = useCallback(async () => {',
    );

    // P-03 fix: должен использовать façade метод.
    // STRAT#7: listQueueToday теперь вызывается с pagination params.
    expect(loadBlock).toContain('labReportingApi.listQueueToday(');
    expect(loadBlock).toContain('limit: LAB_QUEUE_PAGE_SIZE');
    expect(loadBlock).toContain('offset: 0');
    // Не должен делать прямой fetch к registrar endpoint.
    expect(loadBlock).not.toContain('/registrar/queues/today');
    expect(loadBlock).not.toContain('new URLSearchParams({ department: \'lab\' })');
    // Не должен вручную нормализовать nested queues[] → плоский массив
    // (теперь backend возвращает плоский entries[] напрямую).
    expect(loadBlock).not.toContain('payload?.queues || []');
    expect(loadBlock).not.toContain('.flatMap((queue) =>');
  });

  it('STRAT#7: loadMoreAppointments fetches next page with server-side offset', () => {
    const source = readLabPanelSource();
    const loadMoreBlock = extractBlock(
      source,
      'const loadMoreAppointments = useCallback(async () => {',
      '// H-2 fix: keyboard shortcuts',
    );

    expect(loadMoreBlock).toContain('labReportingApi.listQueueToday(null, {');
    expect(loadMoreBlock).toContain('limit: LAB_QUEUE_PAGE_SIZE');
    expect(loadMoreBlock).toContain('offset: queueOffset');
    // Аппендит к существующему списку, не заменяет
    expect(loadMoreBlock).toContain('setAppointments((current) => [...current, ...newEntries])');
    // Обновляет offset и hasMore
    expect(loadMoreBlock).toContain('setQueueOffset((current) => current + newEntries.length)');
    expect(loadMoreBlock).toContain('setHasMoreQueue(');
  });

  it('STRAT#7: passes server-side pagination props to LabQueueWorkbench', () => {
    const source = readLabPanelSource();
    expect(source).toContain('onLoadMore={loadMoreAppointments}');
    expect(source).toContain('hasMore={hasMoreQueue}');
    expect(source).toContain('loadingMore={loadingMore}');
    expect(source).toContain('queueTotal={queueTotal}');
  });

  it('STRAT#16: AbortController in loadLabAppointments and loadMoreAppointments', () => {
    const source = readLabPanelSource();

    // Refs for AbortControllers
    expect(source).toContain('queueAbortControllerRef = useRef(null)');
    expect(source).toContain('loadMoreAbortControllerRef = useRef(null)');

    // loadLabAppointments: abort previous + create new + pass signal
    const loadBlock = extractBlock(
      source,
      'const loadLabAppointments = useCallback(async () => {',
      'const loadMoreAppointments = useCallback(async () => {',
    );
    expect(loadBlock).toContain('queueAbortControllerRef.current.abort()');
    expect(loadBlock).toContain('new AbortController()');
    expect(loadBlock).toContain('signal: controller.signal');
    // Abort error tolerance
    expect(loadBlock).toContain('isAbortLikeError(error)');

    // loadMoreAppointments: same pattern
    const loadMoreBlock = extractBlock(
      source,
      'const loadMoreAppointments = useCallback(async () => {',
      '// H-2 fix: keyboard shortcuts',
    );
    expect(loadMoreBlock).toContain('loadMoreAbortControllerRef.current.abort()');
    expect(loadMoreBlock).toContain('signal: controller.signal');
    expect(loadMoreBlock).toContain('isAbortLikeError(error)');

    // Cleanup effect on unmount
    expect(source).toContain('STRAT#16: cleanup');
    expect(source).toContain('queueAbortControllerRef.current.abort()');
    expect(source).toContain('loadMoreAbortControllerRef.current.abort()');
  });

  it('relies on backend-provided lab report summary fields without re-inventing status', () => {
    // P-03 fix: backend /lab/queue/today уже возвращает latest_lab_report
    // и связанные поля (lab_report_status, report_instance_id, etc.).
    // Frontend не должен переопределять эти поля вручную.
    const source = readLabPanelSource();

    // Façade возвращает entries[] — frontend использует их как есть.
    const loadBlock = extractBlock(
      source,
      'const loadLabAppointments = useCallback(async () => {',
      'const loadTemplates = useCallback(async (preferredTemplateId = null) => {',
    );
    expect(loadBlock).toContain('normalizeListPayload(payload?.entries ?? [])');
    // Frontend не долженfabricировать статусы — они приходят готовые с backend.
    expect(source).not.toContain('status: latestLabReport?.status || entry.status,');
    expect(source).not.toContain('payment_status: entry.payment_status || \'pending\'');
    expect(source).not.toContain('queue_status: entry.status || \'waiting\'');
  });

  it('does not add BFF-lite endpoints for the lab queue contract repair', () => {
    const source = readLabPanelSource();

    expect(source).not.toContain('/api/v1/ui/');
    expect(source).not.toContain('/ui/lab');
  });

  it('does not fetch report instances by visit_ids to enrich normal queue rows', () => {
    const source = readLabPanelSource();
    const loadBlock = extractBlock(
      source,
      'const loadLabAppointments = useCallback(async () => {',
      'const loadTemplates = useCallback(async (preferredTemplateId = null) => {',
    );

    expect(loadBlock).not.toContain('visit_ids');
    expect(loadBlock).not.toContain('mergeQueueEntriesWithLabInstances');
    expect(source).not.toContain('function mergeQueueEntriesWithLabInstances');
  });

  it('does not import unused tokenManager or getApiBaseUrl after façade migration', () => {
    // P-03 fix: после миграции на façade эти импорты больше не нужны.
    // Если кто-то их вернёт — это сигнал, что LabPanel снова делает
    // прямые fetch-запросы в обход labReportingApi.
    const source = readLabPanelSource();
    expect(source).not.toContain('from \'../utils/tokenManager\'');
    expect(source).not.toContain('from \'../api/runtime\'');
    expect(source).not.toContain('const API_V1_BASE');
  });
});
