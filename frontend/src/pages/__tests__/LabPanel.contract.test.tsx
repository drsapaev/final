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
    expect(source).toContain('instanceParamId');
    expect(source).toContain('}, [activeInstanceId, dismissPendingTransition, instanceParamId, loadInstance]);');
  });

  it('makes report transitions latest-wins and marks every state-driven URL change', () => {
    const source = readLabPanelSource();
    const transitionBlock = extractBlock(
      source,
      'const applyInstanceTransition = useCallback(async (',
      'const loadInstance = useCallback((',
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
    expect(source).toContain('change.operation.epoch');
    expect(source).toContain('getOperationContext={getReportOperationContext}');
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

  it('guards template retries and rolls back a failed detail selection', () => {
    const source = readLabPanelSource();
    const loadTemplatesBlock = extractBlock(
      source,
      'const loadTemplates = useCallback(async (preferredTemplateId: string | number | null = null) => {',
      'const loadReportHistory = useCallback(async (patientId: string | number) => {',
    );
    const templateWorkbenchBlock = extractBlock(
      source,
      '<LabTemplateWorkbench',
      '</section>',
    );

    expect(loadTemplatesBlock).toContain('retryAction: () => guardTransition(async () => {');
    expect(loadTemplatesBlock).toContain('await loadTemplates(preferredTemplateId)');
    expect(templateWorkbenchBlock).toContain('const previousTemplate = selectedTemplateRef.current');
    expect(templateWorkbenchBlock).toContain('setSelectedTemplate(previousTemplate)');
    expect(templateWorkbenchBlock).toContain('templateTransitionPending={templateTransitionPending}');
  });
});

// PR #3351: pending-контракт и URL single-writer контракты.
describe('LabPanel pending/latest-wins and URL writer contracts (PR #3351)', () => {
  it('scopes the pending-block to the sources the transition affects', () => {
    const source = readLabPanelSource();
    const guardBlock = extractBlock(
      source,
      'const guardTransition = useCallback((',
      '}, [guardDirtyTransition, notify]);',
    );

    // Блокировка учитывает только затрагиваемые источники: pending report
    // не должен запрещать смену шаблона и наоборот.
    expect(guardBlock).toContain('options?.sourceIds');
    expect(guardBlock).toContain('options.sourceIds?.includes(source)');
    // Полная область (переходы без sourceIds) блокируется при любом pending.
    expect(guardBlock).toContain(': [...pendingOperationSourcesRef.current]');
  });

  it('marks each transition with its affected source scope', () => {
    const source = readLabPanelSource();
    // Смена пациента / Escape / внутренние открытия отчёта — report-область.
    expect(source).toContain("{ sourceIds: ['report'] }");
    // Смена шаблона / retry списка шаблонов — template-область.
    expect(source).toContain("{ sourceIds: ['template'] }");
    // PR 3351 (review round 2, P1): смена report instance — даже из внешнего
    // URL (urlIntent) — тоже report-область: смена отчёта не уничтожает
    // template-черновик (секции смонтированы одновременно через hidden).
    // Все источники спрашивает только route-level уход с /lab.
    expect(source).not.toContain('sourceIds: options.urlIntent ? undefined');
  });

  it('scopes template archive/clone to the template source only (review round 2 P1)', () => {
    const templateSource = fs.readFileSync(
      path.resolve(__dirname, '../../components/laboratory/LabTemplateWorkbench.tsx'),
      'utf8',
    );
    // PR 3351: archive/clone меняют только шаблон — dirty report-draft не
    // должен спрашиваться и сбрасываться (сценарий A из ревью).
    expect(templateSource).toContain("guardTransition(archiveAndRefresh, { sourceIds: ['template'] })");
    expect(templateSource).toContain("guardTransition(cloneAndRefresh, { sourceIds: ['template'] })");
    expect(templateSource).not.toContain('guardTransition(archiveAndRefresh)');
    expect(templateSource).not.toContain('guardTransition(cloneAndRefresh)');
  });

  it('wires the route-level leave guard through the app shell (review round 2 P1)', () => {
    const source = readLabPanelSource();
    const appSource = fs.readFileSync(
      path.resolve(__dirname, '../../App.tsx'),
      'utf8',
    );
    const headerSource = fs.readFileSync(
      path.resolve(__dirname, '../../components/layout/HeaderNew.tsx'),
      'utf8',
    );
    const searchSource = fs.readFileSync(
      path.resolve(__dirname, '../../components/search/GlobalSearchBar.tsx'),
      'utf8',
    );

    // Guard-реестр поднят на уровень App: LabPanel берёт его из контекста,
    // провайдер монтируется в App (внутри BrowserRouter).
    expect(source).toContain('useLabDirtyGuard()');
    expect(appSource).toContain('<LabDirtyGuardProvider>');
    // Header / sidebar / Command Palette / глобальный поиск — через guarded
    // navigate: уход с /lab при dirty-черновиках не может пройти молча.
    expect(headerSource).toContain('useGuardedLabNavigate()');
    expect(appSource).toContain('useGuardedLabNavigate()');
    expect(searchSource).toContain('useGuardedLabNavigate()');
    // Logout: clearToken только после подтверждённого перехода (onLeave).
    expect(headerSource).toContain("navigate(loginRoute, { onLeave: () => { auth.clearToken(); setProfile(null); } })");
    expect(headerSource).not.toContain('auth.clearToken(); setProfile(null); navigate(loginRoute)');
  });

  it('wires every navigation writer through the guarded navigator (review round 3 P1)', () => {
    // PR 3351 (review round 3, P1): центр уведомлений — последний обходной
    // путь: прямой window.history.pushState + синтетический popstate миновал
    // route-level leave guard. Все navigation writers обязаны использовать
    // единый guarded navigator.
    const inboxSource = fs.readFileSync(
      path.resolve(__dirname, '../../components/notifications/NotificationInbox.tsx'),
      'utf8',
    );
    expect(inboxSource).toContain('useGuardedLabNavigate()');
    expect(inboxSource).not.toContain('window.history.pushState');
    expect(inboxSource).not.toContain('new PopStateEvent');

    // Route identity вместо префикса: только зарегистрированный маршрут
    // LabPanel сохраняет панель ('/lab/results' — уход через wildcard).
    const guardSource = fs.readFileSync(
      path.resolve(__dirname, '../../components/laboratory/LabDirtyGuardContext.tsx'),
      'utf8',
    );
    expect(guardSource).toContain('findRouteByPath(pathname)?.component === \'LabPanel\'');
    expect(guardSource).not.toContain('pathname.startsWith(\'/lab/\')');

    // Pending-only операция блокирует ЛЮБОЙ уход с /lab: guardRouteLeave
    // вызывается безусловно (не только при dirty), sentinel вооружён при
    // dirty ИЛИ pending, провайдер публикует реактивный hasPendingOperations.
    expect(guardSource).toContain('const leavesLabRoute = !isLabRoutePath(targetPathname)');
    expect(guardSource).not.toContain('!leavesLab || !hasDirtyRef.current()');
    expect(guardSource).toContain('hasPendingOperations');
    expect(guardSource).toContain('if (!hasDirtyRef.current() && !hasPendingRef.current)');
    expect(guardSource).toContain('hasDirtySources={guard.hasDirtySources}');
    expect(guardSource).toContain('hasPendingOperations={hasPendingOperations}');

    // Sentinel не оставляет фантомную запись: collapse + замена записи при
    // подтверждённом SPA-уходе (navigate replace).
    expect(guardSource).toContain('collapse()');
    expect(guardSource).toContain('replaceSentinelEntry');
  });

  it('resolves lab route identity with the router matcher and keeps sidebar query navigation replace-only (review round 4)', () => {
    // PR 3351 (review round 4, P1): findRouteByPath обязан использовать
    // matcher React Router (matchPath { end: true }), а не точное строковое
    // равенство: '/lab/' рендерит LabPanel через trailing-slash
    // нормализацию роутера, и guard не должен считать такой URL уходом.
    const registrySource = fs.readFileSync(
      path.resolve(__dirname, '../../routing/routeRegistry.ts'),
      'utf8',
    );
    expect(registrySource).toContain("matchPath({ path: route.path, end: true }, pathname)");
    expect(registrySource).not.toContain('route.path === pathname');

    // PR 3351 (review round 4, P2): query-навигация sidebar — replace, не
    // push: внутренние /lab-переходы не создают history-записей, иначе
    // дельта -2 подтверждённого ухода ломается, а под sentinel остаётся
    // помеченная копия («мёртвый» Back после Save).
    const appSource = fs.readFileSync(
      path.resolve(__dirname, '../../App.tsx'),
      'utf8',
    );
    expect(appSource).toContain('search: `?${params.toString()}` }, { replace: true })');

    const guardSource = fs.readFileSync(
      path.resolve(__dirname, '../../components/laboratory/LabDirtyGuardContext.tsx'),
      'utf8',
    );
    // Вытеснение sentinel'а опознаётся по двойнику (тот же router-idx без
    // маркера), а не по href: после in-lab replace (смена ?instance / ?tab)
    // URL двойника расходится с sentinel-URL, и href-эвристика молча
    // глотала browser Back как «in-lab дрейф». Push поверх вооружённого
    // sentinel'а (рост history.length) перевзвешивает sentinel, а не
    // помечает чужую запись.
    expect(guardSource).toContain('isDisplacedTwin()');
    expect(guardSource).toContain('sentinelIdx');
    expect(guardSource).toContain('armedLength');
    expect(guardSource).not.toContain('window.location.href === labLeaveSentinel.getHref()');

    // Маркер переживает router-replace СИНХРОННО: render-based remark
    // полагался на коммит рендера, который React 18 может прервать
    // (supersede-навигация) — маркер затирался, collapse не находил запись.
    // Декоратор merge-ит маркер прямо в history.replaceState.
    expect(guardSource).toContain('installSentinelHistoryPatch()');
    expect(guardSource).toContain('[SENTINEL_STATE_KEY]: true },');
  });

  it('keeps report CREATE latest-wins: create does not block transitions', () => {
    const workbenchSource = fs.readFileSync(
      path.resolve(__dirname, '../../components/laboratory/LabReportWorkbench.tsx'),
      'utf8',
    );
    // PR #3351: create — latest-wins (поздний ответ отбрасывается по
    // operation-context), все остальные операции блокируют переходы.
    expect(workbenchSource).toContain("const reportOperationBlocksTransition = (saving && busyAction !== 'create') || autoSaving;");
  });

  it('writes the URL from the live browser search, not a stale render closure', () => {
    const source = readLabPanelSource();
    // Все URL-писатели строят query от window.location.search: замыкание
    // location.search прошлого рендера отставало от последнего navigate и
    // затирало свежий tab=reports обратно на tab=queue.
    expect(source).toContain('new URLSearchParams(window.location.search)');
    // URL-sync не пишет поверх ещё не обработанного внешнего popstate.
    expect(source).toContain('window.location.search !== lastAppWrittenSearchRef.current');
    // pendingSync-контракты описывают фактический адрес, а не последний рендер.
    expect(source).toContain('function getCurrentUrlInstanceId(');
    expect(source).toContain('const currentUrlInstanceId = getCurrentUrlInstanceId(instanceParamRef.current);');
  });

  it('does not roll a failed intent back over a newer external URL intent', () => {
    const source = readLabPanelSource();
    const catchBlock = extractBlock(
      source,
      'const urlBelongsToThisTransition = instanceIdsMatch(currentUrlInstanceId, instanceId)',
      'if (!urlBelongsToThisTransition) return;',
    );
    expect(catchBlock).toContain('instanceIdsMatch(currentUrlInstanceId, transitionSourceUrlId)');
  });
});
