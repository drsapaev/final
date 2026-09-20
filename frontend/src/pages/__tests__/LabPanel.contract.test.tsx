import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const labPanelPath = path.resolve(__dirname, '../LabPanel.tsx');

const readLabPanelSource = () => fs.readFileSync(labPanelPath, 'utf8');

const extractBlock = (source: string, startMarker: string, endMarker: string) => {
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

    // Refs for AbortControllers — strict:true added `<AbortController | null>` type.
    expect(source).toContain('queueAbortControllerRef = useRef<AbortController | null>(null)');
    expect(source).toContain('loadMoreAbortControllerRef = useRef<AbortController | null>(null)');

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
      'const loadTemplates = useCallback(async (preferredTemplateId: string | number | null = null) => {',
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
      'const loadTemplates = useCallback(async (preferredTemplateId: string | number | null = null) => {',
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

  it('keeps the current template selected across refreshes without a stale closure fallback', () => {
    const source = readLabPanelSource();
    const loadTemplatesBlock = extractBlock(
      source,
      'const loadTemplates = useCallback(async (preferredTemplateId: string | number | null = null) => {',
      'const loadReportHistory = useCallback(async (patientId: string | number) => {',
    );

    expect(source).toContain('selectedTemplateIdRef');
    expect(loadTemplatesBlock).toMatch(/preferredTemplateId\s*\?\?\s*selectedTemplateIdRef\.current/);
    expect(source).toContain('selectedTemplateIdRef.current = (selectedTemplate?.id');
    expect(loadTemplatesBlock).toContain('selectedTemplateIdRef.current = (detail?.id');
  });

  it('separates initial data loading from URL instance restoration', () => {
    const source = readLabPanelSource();
    expect(source).toContain('pendingInstanceUrlSyncRef');
    expect(source).toContain('instanceRequestSequenceRef');
    expect(source).toContain('instanceParamRef.current = instanceParam');
    expect(source).toContain('const instanceParam = searchParams.get(\'instance\')');
    expect(source).toContain('}, [loadLabAppointments, loadRecentReports, loadTemplates]);');
    expect(source).toContain('}, [activeInstanceId, instanceParam, loadInstance]);');
  });

  it('makes report transitions latest-wins and marks every state-driven URL change', () => {
    const source = readLabPanelSource();
    const transitionBlock = extractBlock(
      source,
      'const applyInstanceTransition = useCallback(async (',
      'const loadInstance = useCallback(async (instanceId: string | number) => {',
    );

    expect(transitionBlock).toContain('const requestId = beginInstanceTransition(instanceId, {');
    expect(transitionBlock).toContain('forcePending: options.clearCurrent');
    expect(transitionBlock).toContain('requestId !== instanceRequestSequenceRef.current');
    expect(transitionBlock).toContain('if (options.clearCurrent)');
    expect(source).toContain('beginInstanceTransition(null)');
    expect(source).toContain('onInstanceChange={handleInstanceChange}');
    expect(source).toContain('void applyInstanceTransition(instanceId, { clearCurrent: true })');
    expect(source).toContain('instanceIdsMatch(instanceId, pendingSync.targetId)');
    expect(source).toContain('instanceIdsMatch(activeInstanceId, pendingSync.targetId)');
    expect(source).toContain("change.kind === 'update'");
    expect(source).toContain('change.expectedInstanceId');
  });

  it('keeps template resolution latest-wins across rapid patient changes', () => {
    const source = readLabPanelSource();
    const resolutionBlock = extractBlock(
      source,
      'const loadTemplateResolution = useCallback(async (appointment: Record<string, unknown> | null) => {',
      'const beginInstanceTransition = useCallback((',
    );

    expect(source).toContain('templateResolutionRequestRef = useRef(0)');
    expect(resolutionBlock).toContain('const requestId = ++templateResolutionRequestRef.current');
    expect(resolutionBlock).toContain('requestId !== templateResolutionRequestRef.current');
    expect(resolutionBlock).toContain('requestId === templateResolutionRequestRef.current');
  });

  it('routes template creation through the same dirty transition guard', () => {
    const source = readLabPanelSource();
    const templateWorkbenchBlock = extractBlock(
      source,
      '<LabTemplateWorkbench',
      '</section>',
    );

    expect(templateWorkbenchBlock).toContain('guardTransition={guardTransition}');
  });
});
