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
    expect(source).toContain('}, [activeInstanceId, dismissPendingTransition, instanceParamId, loadInstance, syncUrlToCurrentContext]);');
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

    // PR 3351 (review round 4, P2): query-навигация sidebar для /lab —
    // replace, не push: внутренние /lab-переходы не создают history-записей,
    // иначе дельта -2 подтверждённого ухода ломается, а под sentinel остаётся
    // помеченная копия («мёртвый» Back после Save). Round 5 уточнил скоуп:
    // replace только для маршрута LabPanel (см. следующий тест), поэтому
    // здесь проверяется router-матчинг + форма query-ветки.
    const appSource = fs.readFileSync(
      path.resolve(__dirname, '../../App.tsx'),
      'utf8',
    );
    expect(appSource).toContain('search: `?${params.toString()}` }, { replace: replaceQueryEntry })');

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

  it('scopes sidebar replace to the LabPanel route, keeps shell same-lab writers push-free and handles the no-predecessor direct entry (review round 5)', () => {
    // PR 3351 (review round 5, P1): replace в query-ветке sidebar — ТОЛЬКО
    // для маршрута LabPanel. Doctor-панели (doctor/cardiology/dermatology/
    // dentistry) делят этот код, но их контракт — PUSH (P-029): browser Back
    // ходит между вкладками панели; replace размонтировал бы панель вместе с
    // несохранёнными клиническими черновиками.
    const appSource = fs.readFileSync(
      path.resolve(__dirname, '../../App.tsx'),
      'utf8',
    );
    expect(appSource).toContain('const replaceQueryEntry = chrome.route?.component === \'LabPanel\'');
    expect(appSource).toContain('{ replace: replaceQueryEntry }');
    // Безусловный replace из round 4 убран — doctor-панели вернулись на push.
    expect(appSource).not.toContain('search: `?${params.toString()}` }, { replace: true })');

    // P-029 push-контракт doctor-панелей не тронут.
    const doctorStateSource = fs.readFileSync(
      path.resolve(__dirname, '../../hooks/useDoctorPanelState.ts'),
      'utf8',
    );
    expect(doctorStateSource).toContain('navigate({ pathname: location.pathname, search: params.toString() }, { replace: false })');

    // PR 3351 (review round 5, P1): push поверх sentinel'а закрыт системно —
    // на уровне guarded navigator-а. Любой in-lab переход (Header brand →
    // canonical /lab, Command Palette → Lab Panel) — replace, идентичный
    // URL — no-op: вторая /lab-запись не создаётся ни при вооружённом
    // sentinel, ни до его вооружения.
    const guardSource = fs.readFileSync(
      path.resolve(__dirname, '../../components/laboratory/LabDirtyGuardContext.tsx'),
      'utf8',
    );
    expect(guardSource).toContain('function resolveToHref(to: To): string');
    expect(guardSource).toContain('resolveToHref(to) !== window.location.href');
    expect(guardSource).toContain('navigate(to as To, { ...navigateOptions, replace: true });');

    // PR 3351 (review round 5, P2): arm() фиксирует наличие реальной записи
    // под twin; вытеснение без предшественника не открывает destructive
    // диалог, а подтверждённый уход проверяет фактическое приземление и
    // гарантированно завершает переход (leaveIntent не зависает).
    expect(guardSource).toContain('armedWithPredecessor');
    expect(guardSource).toContain('hadRealPredecessor()');
    expect(guardSource).toContain('scheduleConfirmedLeaveCompletion');
    expect(guardSource).toContain('lastNonLabLocationRef');
    // Предшественник вычисляется один раз на lab-заезд (reset при уходе с
    // /lab) — пересчёт на каждом arm ломался о forward-слот sentinel'а.
    expect(guardSource).toContain('stayHasPredecessor');
    expect(guardSource).toContain('resetStayPredecessor');
    // React 19 коммитит POP-рендер синхронно внутри dispatch popstate ДО
    // popstate-обработчика: drift-ветка обязана пропускать twin-landing
    // (иначе remark помечал двойника и глотал вытеснение).
    expect(guardSource).toContain('poppedOntoTwin');
  });

  it('owns document protection at the provider level and defers session-expiry redirects past pending operations (review round 6)', () => {
    // PR 3351 (review round 6, P1): beforeunload (refresh / закрытие
    // вкладки) раньше ставили сами workbench'и — и только по dirty-state.
    // Pending-only мутация (clone чистого шаблона, finalize/print чистого
    // отчёта — неидемпотентные POST без Idempotency-Key) обрывалась без
    // предупреждения. Единственный владелец защиты документа — провайдер:
    // он видит ОБЩЕЕ состояние (dirty-источники ИЛИ pending-операции).
    const readComponent = (relative: string) => fs.readFileSync(
      path.resolve(__dirname, relative),
      'utf8',
    );
    const templateWorkbenchSource = readComponent('../../components/laboratory/LabTemplateWorkbench.tsx');
    const reportWorkbenchSource = readComponent('../../components/laboratory/LabReportWorkbench.tsx');
    expect(templateWorkbenchSource).not.toContain('addEventListener(\'beforeunload\'');
    expect(reportWorkbenchSource).not.toContain('addEventListener(\'beforeunload\'');

    const guardSource = readComponent('../../components/laboratory/LabDirtyGuardContext.tsx');
    expect(guardSource).toContain('window.addEventListener(\'beforeunload\', handleBeforeUnload)');
    // Условие внутри обработчика — dirty ИЛИ pending по render-time рефам
    // (слушатель не перевешивается на флипах состояния).
    expect(guardSource).toContain('if (!hasDirtyRef.current() && !hasPendingRef.current) return;');

    // PR 3351 (review round 6, P1): истечение сессии больше не делает hard
    // navigation поверх pending-операции. LabPanel переводится на
    // usePendingAwareSessionExpiry; прямой window.location.href = '/login'
    // остаётся ровно один — внутри onExpired (после снятия pending).
    const labPanelSource = readLabPanelSource();
    expect(labPanelSource).toContain('usePendingAwareSessionExpiry({');
    expect(labPanelSource).not.toContain('useSessionTimeoutWarning({');
    expect(labPanelSource.match(/window\.location\.href = '\/login';/g)?.length).toBe(1);
    const hookSource = readComponent('../../hooks/usePendingAwareSessionExpiry.ts');
    // Истечение поверх pending — контролируемое ожидание, redirect ровно
    // один раз после завершения последней операции.
    expect(hookSource).toContain('setRedirectPending(true)');
    expect(hookSource).toContain('onExpiredRef.current();');
    // Не-dismissable диалог «операция завершается, затем переход».
    expect(labPanelSource).toContain('sessionRedirectPending && (');
    expect(labPanelSource).toContain('lp_sessiya_istekla_zavershenie');
  });

  it('normalizes a missing or unknown ?tab= to the canonical Queue home and keeps the rollback tab explicit (review round 6)', () => {
    // PR 3351 (review round 6, P2): canonical /lab (defaultItem: 'queue' в
    // routeRegistry) обязан означать ровно то, что откроется после reload:
    // URL /lab без ?tab= — вкладка очереди. Прежний sync молча пропускал
    // «нет таба», и shell-переходы (Header brand, Command Palette) на
    // canonical /lab рассинхронизировали адрес и экран.
    const labPanelSource = readLabPanelSource();
    expect(labPanelSource).toContain('function resolveLabTabId(');
    expect(labPanelSource).toContain('const LAB_TAB_IDS = [\'queue\', \'templates\', \'reports\'] as const;');
    // Ранний выход «нет таба → ничего не делать» удалён.
    expect(labPanelSource).not.toContain('if (!nextTab) {');
    // Нормализация применяется и к initial state, и к tab-sync эффекту.
    expect(labPanelSource.match(/resolveLabTabId\(/g)?.length).toBeGreaterThanOrEqual(3);
    expect(labPanelSource).toContain('const requestedTab = searchParams.get(\'tab\');');
    // URL с валидным tab закрывает память pre-intent вкладки — canonical
    // /lab при shell-переходах (brand = home = очередь) её не наследует.
    expect(labPanelSource).toContain('preUrlIntentTabRef.current = null;');
    // WF-15 восстанавливает tab из pre-intent памяти, когда внешний
    // tab-less URL (или sentinel-collapse POP) оставляет адрес без tab.
    expect(labPanelSource).toContain('params.set(\'tab\', intentTab);');

    // Rollback внешнего намерения обязан явно владеть tab: после
    // нормализации «нет tab → queue» откат без явного tab молча
    // переключал бы пользователя на вкладку очереди (dirty report на
    // /lab?tab=reports → внешний /lab?instance=89 без tab → отмена →
    // очередь вместо reports). Приоритет: валидный tab адреса → вкладка
    // до начала urlIntent → текущая вкладка → 'queue'.
    expect(labPanelSource).toContain('function resolveRollbackTabId(');
    expect(labPanelSource).toContain('preUrlIntentTabRef.current = activeTabRef.current;');
    expect(labPanelSource).toContain('params.set(\'tab\', resolveRollbackTabId(');
    // Захват pre-intent вкладки — в urlIntent-ветке loadInstance (синхронно
    // ДО guard-диалога: tab-sync effect этого рендера уже мог закоммитить
    // нормализацию), потребление — в onCancel отката после
    // syncUrlToCurrentContext (URL снова явно владеет tab).
    const urlIntentCapture = labPanelSource.indexOf('if (options.urlIntent) {');
    const captureWrite = labPanelSource.indexOf('preUrlIntentTabRef.current = activeTabRef.current;', urlIntentCapture);
    expect(captureWrite).toBeGreaterThan(urlIntentCapture);
    expect(labPanelSource).toContain('preUrlIntentTabRef.current = null;');
  });

  it('blocks BOTH guard levels while report CREATE is in flight: context transitions and document/route leave (review round 8)', () => {
    const workbenchSource = fs.readFileSync(
      path.resolve(__dirname, '../../components/laboratory/LabReportWorkbench.tsx'),
      'utf8',
    );
    // PR #3351 (review round 7→8, P1): round 7 держал CREATE вне
    // контекстного уровня (latest-wins: поздний ответ отбрасывается по
    // operation-context). Round 8 признаёт это небезопасным для
    // неидемпотентного POST /lab/report-instances: серверный side effect
    // коммитится ДО решения UI, а отброшенный ответ терял и созданный
    // бланк, и обновление read-model — оператор повторял CREATE и получал
    // дубль. Теперь CREATE блокирует ОБА уровня наравне с save/autosave/
    // finalize/revise/print.
    expect(workbenchSource)
      .toContain('const reportBlocksContextTransition = saving || autoSaving;');
    expect(workbenchSource).toContain('const reportBlocksDocumentLeave = saving || autoSaving;');
    expect(workbenchSource).toContain('blocksContextTransition: reportBlocksContextTransition,');
    expect(workbenchSource).toContain('blocksDocumentLeave: reportBlocksDocumentLeave,');
    // Stale-ветка (onInstanceChange отклонил поздний ответ) не теряет
    // server outcome: фоновая reconcile read-model + уведомление с
    // пациентом созданного бланка (defense-in-depth — вход в ветку
    // закрыт блокировкой контекстных переходов).
    const createHandler = extractBlock(
      workbenchSource,
      'const handleCreateInstance = useCallback',
      '  // STRAT#1: init-instance effect',
    );
    expect(createHandler).toContain('if (!accepted) {');
    expect(createHandler)
      .toContain('await onRefreshHistory?.(selectedAppointment.patient_id as string | number);');
    expect(createHandler).toContain('t(\'success.report_created_for_patient\'');
  });

  it('splits pending protection into two registries: context transitions vs full document/route leave (review round 7)', () => {
    const source = readLabPanelSource();
    // Контекстный реестр — прежний sourceIds-скоуп guardTransition
    // (pending report не запрещает смену шаблона и наоборот).
    expect(source).toContain('const pendingOperationSourcesRef = useRef(new Set<string>());');
    // Документ-уровневый реестр — то, что видит провайдер
    // (guardRouteLeave/sentinel/beforeunload/session-expiry через
    // setPendingOperationSources).
    expect(source).toContain('const documentLeavePendingSourcesRef = useRef(new Set<string>());');
    expect(source).toContain('if (state?.blocksContextTransition) pendingOperationSourcesRef.current.add(source);');
    expect(source).toContain('if (state?.blocksDocumentLeave) documentLeavePendingSourcesRef.current.add(source);');
    expect(source)
      .toContain('setPendingOperationSources([...documentLeavePendingSourcesRef.current]);');
    // Сигнатура pending-коллбека — split-состояние (не boolean).
    expect(source).toContain('(state: LabOperationPendingState | null) => setOperationSourcePending(\'report\', state)');
    expect(source).toContain('(state: LabOperationPendingState | null) => setOperationSourcePending(\'template\', state)');

    // PR 3351 (review round 7→8, P1): ДВА сигнала на уровне провайдера.
    // Round 8: CREATE входит в ОБА — sentinel (browser Back) вооружается
    // и в его полёте; URL-контракт collapse (stale twin) держит
    // отложенная запись WF-15 по historyGuardEngaged, а не исключение
    // CREATE из реестра.
    expect(source).toContain('setHistoryGuardPendingSources([...pendingOperationSourcesRef.current]);');

    const guardSource = fs.readFileSync(
      path.resolve(__dirname, '../../components/laboratory/LabDirtyGuardContext.tsx'),
      'utf8',
    );
    // Sentinel-хост получает ОБА сигнала: документ-уровень — для
    // beforeunload (dirty ИЛИ любая операция, включая CREATE)...
    expect(guardSource).toContain('hasPendingOperations={hasPendingOperations}');
    expect(guardSource).toContain('hasHistoryGuardPending={hasHistoryGuardPending}');
    // ...history-guard — для arm/ disarm sentinel-а и popstate-решений
    // (round 8: включая CREATE).
    expect(guardSource).toContain('if (!hasDirtyRef.current() && !hasHistoryPendingRef.current) {');
    expect(guardSource).toContain('if (labLeaveSentinel.isArmed()) labLeaveSentinel.collapse();');
    expect(guardSource).toContain('const hasHistoryPendingRef = useRef(hasHistoryGuardPending);');
    // Провайдер публикует оба агрегата (флипы 0↔n).
    expect(guardSource).toContain('const hasHistoryGuardPending = historyGuardPendingSources.length > 0;');
    expect(guardSource).toContain('setHistoryGuardPendingSources: (sources: string[]) => void;');

    // Оба workbench-а блокируют оба уровня на все операции.
    const templateSource = fs.readFileSync(
      path.resolve(__dirname, '../../components/laboratory/LabTemplateWorkbench.tsx'),
      'utf8',
    );
    expect(templateSource).toContain('saving ? LAB_OPERATION_PENDING_ALL : LAB_OPERATION_PENDING_NONE');
  });

  it('defers the ?instance URL write while the history guard is engaged and replays it after the collapse lands (review round 8)', () => {
    const source = readLabPanelSource();
    const guardSource = fs.readFileSync(
      path.resolve(__dirname, '../../components/laboratory/LabDirtyGuardContext.tsx'),
      'utf8',
    );

    // PR 3351 (review round 8, P1): провайдер публикует реактивный
    // «sentinel занят» (armed || collapsing) на каждой точке перехода.
    expect(guardSource).toContain('historyGuardEngaged: boolean;');
    expect(guardSource).toContain(
      'labLeaveSentinel.isArmed() || labLeaveSentinel.isCollapsing()',
    );
    // Публикация во ВСЕХ точках перехода: arm/collapse (layout-эффект),
    // finishCollapse/disarm (popstate-обработчик), уход с /lab.
    const syncSites = guardSource.split('syncHistoryGuardEngaged();').length - 1;
    expect(syncSites).toBeGreaterThanOrEqual(5);
    // Standalone-режим без провайдера — no-op false (URL не откладывается).
    expect(guardSource).toContain('historyGuardEngaged: false,');

    // WF-15 LabPanel: отложенная запись — ранний return по engaged +
    // деп для перезапуска после settle (флип в false приземлившегося
    // collapse). Отсутствие early-return/divergence — stale twin restore.
    expect(source).toContain('if (historyGuardEngaged) return;');
    expect(source).toContain(
      '}, [activeInstanceId, currentSearchParams, historyGuardEngaged, instanceParamId, selectedAppointment, location.search, navigateReplace]);',
    );
  });

  it('recovers the session-expiry UI after a token refresh: onSessionRecovered clears the stuck warning (review round 8)', () => {
    const source = readLabPanelSource();
    const wrapperSource = fs.readFileSync(
      path.resolve(__dirname, '../../hooks/usePendingAwareSessionExpiry.ts'),
      'utf8',
    );
    const pollSource = fs.readFileSync(
      path.resolve(__dirname, '../../hooks/useSessionTimeoutWarning.ts'),
      'utf8',
    );

    // PR 3351 (review round 8, P2): LabPanel снимает висящее предупреждение
    // по onSessionRecovered — восстановленная сессия не лжёт пользователю.
    expect(source).toContain('onSessionRecovered: () => setSessionWarning(null),');

    // Обёртка: (1) смена поколения токена из опроса → НЕМЕДЛЕННОЕ снятие
    // redirectPending + onSessionRecovered ещё до завершения операций
    // (round 9); (2) ветка завершения операций при валидном токене →
    // onSessionRecovered (+ отмена redirectPending).
    expect(wrapperSource).toContain('onSessionRecovered?: () => void;');
    expect(wrapperSource).toContain('onTokenChanged: () => {');
    expect(wrapperSource).toContain('if (!hasValidAccessTokenNow()) return;');
    expect(wrapperSource).toContain('setRedirectPending(false);');
    expect(wrapperSource).toContain('onSessionRecoveredRef.current?.();');

    // Опрос: отслеживание ПОКОЛЕНИЯ токена по значению — сброс
    // fired-флагов на смене (короткоживущий gen N+1 получает собственный
    // жизненный цикл предупреждения), коллбек только живой смене.
    expect(pollSource).toContain('onTokenChanged?: () => void;');
    expect(pollSource).toContain('const lastTokenRef = useRef<string | null>(null);');
    expect(pollSource).toContain('warningFiredRef.current = false;');
    expect(pollSource).toContain('expiredFiredRef.current = false;');
    expect(pollSource).toContain('if (previousToken && token) {');
  });

  it('captures the pre-intent rollback tab once per intent chain so a superseding intent cannot overwrite it (review round 7)', () => {
    const source = readLabPanelSource();
    // PR 3351 (review round 7, P2): второй tab-less intent, пришедший пока
    // первый ждёт решения в dirty-dialog, видел бы activeTab уже
    // нормализованным на queue — и Cancel возвращал бы на очередь вместо
    // исходной вкладки (reports). Захват — только когда цепочки ещё нет.
    expect(source).toContain('if (pendingUrlIntentRef.current == null) {');
    // Порядок внутри urlIntent-ветки loadInstance: проверка «цепочки нет»
    // ДО записи pre-intent вкладки и ДО перезаписи pendingUrlIntentRef
    // новым intent-ом (первое вхождение — ветка loadInstance, не коллбек
    // подтверждённого перехода внутри неё).
    const urlIntentBranch = source.indexOf('if (options.urlIntent) {');
    expect(urlIntentBranch).toBeGreaterThanOrEqual(0);
    const guardIndex = source.indexOf('if (pendingUrlIntentRef.current == null) {', urlIntentBranch);
    const captureWrite = source.indexOf('preUrlIntentTabRef.current = activeTabRef.current;', urlIntentBranch);
    const overwriteIndex = source.indexOf('pendingUrlIntentRef.current = { targetId: instanceId };', urlIntentBranch);
    expect(guardIndex).toBeGreaterThan(urlIntentBranch);
    expect(captureWrite).toBeGreaterThan(guardIndex);
    expect(overwriteIndex).toBeGreaterThan(captureWrite);
  });

  it('re-checks the live access token before the deferred session-expiry redirect (review round 7)', () => {
    const hookSource = fs.readFileSync(
      path.resolve(__dirname, '../../hooks/usePendingAwareSessionExpiry.ts'),
      'utf8',
    );
    // PR 3351 (review round 7, P2): за время ожидания pending-операций
    // токен мог быть обновлён (single-flight refresh в API-клиенте) —
    // валидный JWT отменяет отложенный logout.
    expect(hookSource).toContain('function hasValidAccessTokenNow()');
    // PR 3351 (review round 8, P2): валидный токен отменяет redirect И оповещает
    // восстановление (onSessionRecovered снимает висящее предупреждение).
    expect(hookSource).toContain('if (hasValidAccessTokenNow()) {');
    expect(hookSource).toContain('onSessionRecoveredRef.current?.();');
    // Переход выполняется только при НЕВАЛИДНОМ токене.
    const waitBlock = extractBlock(
      hookSource,
      'useEffect(() => {',
      '}, [redirectPending, pendingOperationsSignal]);',
    );
    const tokenCheckIndex = waitBlock.indexOf('if (hasValidAccessTokenNow()) {');
    const onExpiredIndex = waitBlock.indexOf('onExpiredRef.current();');
    expect(tokenCheckIndex).toBeGreaterThan(-1);
    expect(onExpiredIndex).toBeGreaterThan(tokenCheckIndex);
    // Парсер exp переиспользуется из опроса (единая семантика валидности).
    expect(hookSource).toContain('import useSessionTimeoutWarning, { getTokenExpiryMs } from \'./useSessionTimeoutWarning\';');
    const pollSource = fs.readFileSync(
      path.resolve(__dirname, '../../hooks/useSessionTimeoutWarning.ts'),
      'utf8',
    );
    expect(pollSource).toContain('export function getTokenExpiryMs(token: string)');
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

  it('sends a persistent Idempotency-Key for report CREATE: bind/proceed on retry, clear on confirmed outcome (review round 9)', () => {
    const workbenchSource = fs.readFileSync(
      path.resolve(__dirname, '../../components/laboratory/LabReportWorkbench.tsx'),
      'utf8',
    );
    const apiSource = fs.readFileSync(
      path.resolve(__dirname, '../../api/labReporting.ts'),
      'utf8',
    );
    const idempotencySource = fs.readFileSync(
      path.resolve(__dirname, '../../components/laboratory/createInstanceIdempotency.ts'),
      'utf8',
    );

    // PR 3351 (review round 9, P1): POST без ключа неидемпотентен — потерянный
    // после commit ответ заставлял оператора повторять CREATE (второй бланк).
    // Workbench: ключ резолвится ДО запроса, слот освобождается ПОСЛЕ 2xx.
    expect(workbenchSource).toContain('const idempotencyKey = resolveCreateInstanceIdempotencyKey(createPayload);');
    expect(workbenchSource).toContain('await labReportingApi.createInstance(createPayload, { idempotencyKey });');
    expect(workbenchSource).toContain('clearCreateInstanceIdempotencyKey(createPayload);');
    // api-клиент: Idempotency-Key — opt-in заголовок (middleware без него
    // пропускает POST без координации).
    expect(apiSource).toContain('options.idempotencyKey\n        ? { headers: { \'Idempotency-Key\': options.idempotencyKey } }');
    // Модуль: proceed (тот же payload → тот же ключ), rotate (изменённый
    // payload → новая операция), reload-safe sessionStorage-слоты.
    expect(idempotencySource).toContain('if (stored && stored.payload === snapshot) {');
    expect(idempotencySource).toContain('window.sessionStorage.getItem(slot)');
    expect(idempotencySource).toContain('export function clearCreateInstanceIdempotencyKey(');
  });

  it('canonical null-intent lands on the URL-owned tab: /lab stays strictly /lab on Queue (review round 9)', () => {
    const source = readLabPanelSource();
    // Блок подтверждённого null-intent: от входа в ветку до перехода к
    // instance-намерению (включает закрывающую запись pre-intent памяти).
    const nullIntentBlock = extractBlock(
      source,
      'if (instanceId == null) {',
      'void applyInstanceTransition(instanceId, { urlIntent: options.urlIntent });',
    );

    // PR 3351 (review round 9, P2): вкладкой владеет URL — безусловный
    // switchTab(\'reports\') дописывал ?tab=reports поверх canonical /lab.
    expect(nullIntentBlock).toContain('const urlOwnsValidTab = (LAB_TAB_IDS as readonly string[]).includes(urlTabParam ?? \'\');');
    expect(nullIntentBlock).toContain('resolveLabTabId(urlTabParam)');
    // Canonical /lab (tab-less): контекст пациента очищается (reload-parity,
    // иначе WF-15 дописал бы ?patient в «домашний» адрес), вкладка — queue
    // БЕЗ URL-записи, эпоха инвалидирует in-flight операции.
    expect(nullIntentBlock).toContain('labOperationEpochRef.current += 1;');
    expect(nullIntentBlock).toContain('setSelectedAppointment(null);');
    expect(nullIntentBlock).toContain('if (activeTabRef.current !== \'queue\') {');
    expect(nullIntentBlock).toContain('setActiveTab(\'queue\');');
    // Память pre-intent вкладки закрывается (WF-15 не воскрешает reports).
    expect(nullIntentBlock).toContain('preUrlIntentTabRef.current = null;');
    // Безусловного ухода на reports в подтверждённом null-intent больше нет.
    expect(nullIntentBlock).not.toContain('switchTab(\'reports\');');
  });

  it('«Продлить сессию» is a real single-flight refresh: closes the warning only after a NEW valid token lands (review round 9)', () => {
    const source = readLabPanelSource();
    const clientSource = fs.readFileSync(
      path.resolve(__dirname, '../../api/client.ts'),
      'utf8',
    );

    // PR 3351 (review round 9, P2): прежняя кнопка только прятала overlay —
    // JWT не ротировался. Теперь: канонический refresh + проверка, что в
    // хранилище появилось НОВОЕ значение с будущим exp.
    expect(clientSource).toContain('async function forceRefreshToken(): Promise<string | null> {');
    expect(clientSource).toContain('  forceRefreshToken,');
    expect(source).toContain('const handleExtendSession = useCallback(async () => {');
    expect(source).toContain('const newToken = await forceRefreshToken();');
    expect(source).toContain('tokenAfter !== tokenBefore');
    expect(source).toContain('(getTokenExpiryMs(tokenAfter) ?? 0) > Date.now()');
    // Неудача: предупреждение остаётся открытым с явной ошибкой (не
    // «притворяется» успешным), кнопка блокируется в полёте.
    expect(source).toContain('setSessionExtendError(t(\'misc.lp_session_extend_failed\'));');
    expect(source).toContain('disabled={sessionExtending}');
    expect(source).toContain('role="alert"');
  });
});
