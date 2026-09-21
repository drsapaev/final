import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import type { NavigateOptions, To } from 'react-router-dom';
import {
  useDirtyTransitionGuard,
  type DirtyTransitionGuard,
} from './hooks/useDirtyTransitionGuard';
import { findRouteByPath } from '../../routing/routeRegistry';
import notifyService from '../../services/notify';
import { useTranslation } from '../../i18n/useTranslation';

/**
 * PR 3351 (review round 2, P1): route-level leave guard для /lab.
 *
 * Проблема: useDirtyTransitionGuard покрывает только переходы, которые
 * инициирует сама LabPanel (смена пациента/отчёта/шаблона, URL instance,
 * Escape). Обычная SPA-навигация (Header, Profile, Command Palette, sidebar,
 * logout, browser Back) размонтирует LabPanel БЕЗ диалога — beforeunload
 * при React Router-навигации не вызывается, и несохранённый черновик
 * теряется молча. Logout опаснее всех: auth.clearToken() выполнялся ДО
 * навигации, поэтому даже добавленный позже блокер не смог бы безопасно
 * отменить выход.
 *
 * Решение — три части с ОДНИМ реестром dirty-источников и ОДНИМ диалогом
 * (тот же useDirtyTransitionGuard, поднятый на уровень App):
 *
 * 1. LabDirtyGuardProvider монтируется в App над AppContent и владеет
 *    экземпляром useDirtyTransitionGuard. LabPanel берёт guard из контекста
 *    (fallback — собственный экземпляр для unit-тестов без провайдера).
 *
 * 2. useGuardedLabNavigate() — обёртка useNavigate для App Shell: переход
 *    за пределы /lab при dirty-черновиках проходит через guardRouteLeave
 *    (pending-блок + диалог по ВСЕМ источникам — уход с /lab уничтожает
 *    каждый draft). onLeave-коллбек (logout: auth.clearToken) выполняется
 *    ТОЛЬКО после подтверждённого перехода.
 *
 * 3. Browser Back/Forward: React Router v7 в режиме BrowserRouter не имеет
 *    useBlocker, а patching pushState не останавливает внутренний setState
 *    роутера. Используется sentinel-запись в history: пока есть dirty-источник
 *    ИЛИ незавершённая операция (PR 3351, review round 3: pending-only тоже
 *    блокирует уход), поверх текущей /lab-записи пушится дубликат (тот же
 *    URL, marker в state). Browser Back вытесняет sentinel — URL остаётся
 *    /lab, роутер видит POP на тот же маршрут (LabPanel НЕ размонтируется),
 *    а наш popstate-listener показывает guard-диалог. Подтверждение →
 *    navigate(-2) (sentinel + дубликат) — реальный уход; отмена →
 *    пользователь и черновик на месте.
 *
 *    PR 3351 (review round 3, P2): sentinel больше не оставляет фантомную
 *    запись в истории. Когда блокирующее состояние исчезает (draft чист и
 *    операций нет), collapse() уходит с синтетической записи назад
 *    (history.back) — единственный способ «удалить» запись в History API;
 *    popstate от этого перехода глотается (sentinel уже разоружён).
 *    Подтверждённый SPA-уход заменяет sentinel-запись (navigate replace),
 *    поэтому Back возвращает на /lab без второго дубля.
 *
 * Инвариант sentinel: запись ПОД sentinel никогда не мутирует после arm
 * (replaceState действует на текущую запись, т.е. на сам sentinel), поэтому
 * «вытесненный sentinel» опознаётся по landing href === sentinel href.
 * Если роутер заменил URL текущей (sentinel) записи, sentinel перевзвешивается
 * (disarm + arm) — сравнение остаётся осмысленным.
 */

/**
 * PR 3351 (review round 3, P1): route identity, а не префикс пути.
 *
 * «Остаться в /lab» = «прийти на маршрут, который рендерит LabPanel и
 * сохраняет её состояние». Реестр маршрутов содержит только точный путь
 * '/lab': '/lab/results' (deep-link уведомлений lab_results) не совпадает
 * ни с одним маршрутом, попадает в wildcard-redirect на /not-found и
 * размонтирует панель — такой переход обязан проходить через guard, как и
 * любой другой уход. Префиксная проверка startsWith('/lab/') ошибочно
 * считала его безопасным внутренним переходом.
 */
export function isLabRoutePath(pathname: string): boolean {
  return findRouteByPath(pathname)?.component === 'LabPanel';
}

// ─── Sentinel controller ─────────────────────────────────────────────────────

const SENTINEL_STATE_KEY = '__labLeaveGuardSentinel';

const labLeaveSentinel = {
  armed: false,
  sentinelHref: null as string | null,
  /** PR 3351 (review round 3, P2): ждём popstate от collapse-back(). */
  collapsing: false,
  /**
   * PR 3351 (review round 3, P2): открыт route-leave диалог (или выполняется
   * его save/discard). В этом окне черновики могут стать clean ещё ДО
   * navigate — collapse должен быть подавлен, иначе back() вытолкнул бы
   * sentinel и replace-переход затёр бы РЕАЛЬНУЮ /lab-запись.
   */
  leaveIntent: false,
  isArmed: () => labLeaveSentinel.armed,
  getHref: () => labLeaveSentinel.sentinelHref,
  isCollapsing: () => labLeaveSentinel.collapsing,
  isLeaveIntent: () => labLeaveSentinel.leaveIntent,
  beginLeaveIntent() {
    labLeaveSentinel.leaveIntent = true;
  },
  endLeaveIntent() {
    labLeaveSentinel.leaveIntent = false;
  },
  /**
   * Состояние записи = состояние роутера (usr/key/idx) + маркер: POP на
   * sentinel-запись не ломает delta-вычисления React Router.
   */
  sentinelState() {
    return {
      ...((window.history.state as Record<string, unknown> | null) ?? {}),
      [SENTINEL_STATE_KEY]: true,
    };
  },
  arm(url: string) {
    // Новый arm-цикл отменяет незавершённый collapse: pushState обрывает
    // отложенный traversal, флаг должен быть сброшен вручную.
    labLeaveSentinel.collapsing = false;
    if (labLeaveSentinel.armed) return;
    window.history.pushState(labLeaveSentinel.sentinelState(), '', url);
    labLeaveSentinel.armed = true;
    labLeaveSentinel.sentinelHref = url;
  },
  /**
   * Роутер заменил URL текущей (sentinel) записи (navigateReplace внутри
   * /lab). НЕ пушим новую запись — переотмечаем ту же: инвариант «запись под
   * sentinel смежна с дельтой -2 до реальной предыдущей страницы» сохраняется.
   */
  remark(url: string) {
    window.history.replaceState(labLeaveSentinel.sentinelState(), '', url);
    labLeaveSentinel.sentinelHref = url;
  },
  disarm() {
    labLeaveSentinel.armed = false;
    labLeaveSentinel.sentinelHref = null;
  },
  /**
   * PR 3351 (review round 3, P2): disarm + очистка фантомной записи.
   *
   * disarm() оставлял синтетический дубликат /lab в истории: первый browser
   * Back после Save молча приземлялся на него («ничего не произошло»), и
   * только второй уходил на предыдущую страницу; после подтверждённого
   * SPA-ухода Back сначала попадал на sentinel-копию. Удалить запись в
   * History API нельзя — можно только уйти с неё: history.back() с текущей
   * sentinel-записи возвращает индекс на реальный /lab, а popstate от этого
   * перехода глотается обработчиком (collapsing-флаг): sentinel уже
   * разоружён, URL не меняется, роутер видит POP с нулевой дельтой.
   * Идемпотентен: повторный вызов до прихода popstate игнорируется.
   */
  collapse() {
    const onSentinelEntry = labLeaveSentinel.isSentinelEntry();
    labLeaveSentinel.armed = false;
    labLeaveSentinel.sentinelHref = null;
    if (!onSentinelEntry || labLeaveSentinel.collapsing) return;
    labLeaveSentinel.collapsing = true;
    window.history.back();
  },
  finishCollapse() {
    labLeaveSentinel.collapsing = false;
  },
  isSentinelEntry() {
    return Boolean(
      (window.history.state as Record<string, unknown> | null)?.[SENTINEL_STATE_KEY],
    );
  },
};

// ─── Context ─────────────────────────────────────────────────────────────────

export interface LabDirtyGuardContextValue {
  /** true — рендер внутри LabDirtyGuardProvider (route-level guard активен). */
  isProvided: boolean;
  registerDirtySource: DirtyTransitionGuard['registerDirtySource'];
  guardTransition: DirtyTransitionGuard['guardTransition'];
  dismissPendingTransition: DirtyTransitionGuard['dismissPendingTransition'];
  /**
   * В provided-режиме null: диалог рендерит сам провайдер (поверх App Shell).
   * В fallback-режиме (unit-тесты без провайдера) — локальный диалог.
   */
  guardDialog: React.ReactNode;
  isDialogOpen: boolean;
  hasDirtySources: () => boolean;
  /** PR 3351: sync pending-источников из LabPanel на уровень App. */
  setPendingOperationSources: (sources: string[]) => void;
  /**
   * PR 3351 (review round 3, P1): реактивное агрегированное pending-состояние.
   * Перерисовывает потребителей (и sentinel-хост) на флипах 0↔n —
   * pending-only операция (clone чистого шаблона, finalize/print чистого
   * отчёта) обязана блокировать уход с /lab так же, как dirty-черновик.
   */
  hasPendingOperations: boolean;
  /**
   * Route-level leave guard: pending-блок (любая незавершённая операция) +
   * dirty-диалог по ВСЕМ источникам (уход с /lab уничтожает каждый draft).
   */
  guardRouteLeave: (leave: () => void) => boolean;
  /** Вызывается workbench'ами при изменении их dirty-состояния. */
  notifyDirtyStateChange: () => void;
}

const LabDirtyGuardContext = createContext<LabDirtyGuardContextValue | null>(null);

// ─── Provider ────────────────────────────────────────────────────────────────

export function LabDirtyGuardProvider({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const guard = useDirtyTransitionGuard();
  const pendingOperationSourcesRef = useRef<string[]>([]);
  // PR 3351 (review round 3, P1): pending стал реактивным. Раньше источники
  // жили только в ref — провайдер не перерисовывался на флипах pending, и
  // sentinel не вооружался при pending-only операции (dirty=false). Стейт
  // обновляется ТОЛЬКО на флипе агрегированного boolean (0↔n) — состав
  // источников читается из ref, лишних перерисовок нет.
  const [pendingOperationSources, setPendingOperationSourcesState] = useState<string[]>([]);

  const setPendingOperationSources = useCallback((sources: string[]) => {
    pendingOperationSourcesRef.current = sources;
    setPendingOperationSourcesState((previous) => (
      (previous.length === 0) === (sources.length === 0) ? previous : sources
    ));
  }, []);
  const hasPendingOperations = pendingOperationSources.length > 0;

  // Уход с /lab блокируется при любой незавершённой операции (save/finalize/
  // print/autosave любого источника) — переход посреди записи мог бы создать
  // повторную запись или потерять ответ; затем — dirty-диалог по всем
  // источникам (без sourceIds). При чистом состоянии guardTransition
  // выполняет переход сразу — guardRouteLeave безопасен для ЛЮБОГО ухода.
  const guardRouteLeave = useCallback((leave: () => void) => {
    if (pendingOperationSourcesRef.current.length > 0) {
      notifyService.info(t('workbench.saving'));
      return false;
    }
    // PR 3351 (review round 3, P2): пока route-leave решение не завершено
    // (диалог открыт ИЛИ подтверждённый переход ещё в полёте), жизненным
    // циклом sentinel'а владеет leave-flow. leaveIntent снимается ТОЛЬКО
    // когда переход фактически приземлился (layout-эффект видит не-lab
    // pathname) или диалог отменён — НЕ в finally leave(): между discard и
    // приземлением POP(/replace) рендеры ещё видят /lab и STALE-dirty
    // (isDirtyRef workbench'а обновляется в useEffect позже layout-эффектов)
    // и успевали ре-армаить уже разоружённый sentinel лишней записью,
    // коллапс которой отменял сам подтверждённый переход.
    labLeaveSentinel.beginLeaveIntent();
    const decided = guard.guardTransition(
      () => {
        try {
          leave();
        } catch {
          // Переход не выполнен — возвращаем sentinel обычному циклу.
          labLeaveSentinel.endLeaveIntent();
        }
      },
      { onCancel: () => { labLeaveSentinel.endLeaveIntent(); } },
    );
    return decided;
    // guard.guardTransition стабилен (useCallback без deps внутри хука):
    // деп по нестабильному объекту guard пересоздавал бы коллбек на каждом
    // рендере провайдера и ронял мемоизацию value контекста.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [guard.guardTransition, t]);

  // Идентичность value меняется ТОЛЬКО при флипе isDialogOpen — keystroke-и
  // не перерисовывают потребителей контекста (guardDialog рендерится здесь,
  // а не передаётся через value).
  const value = useMemo<LabDirtyGuardContextValue>(() => ({
    isProvided: true,
    registerDirtySource: guard.registerDirtySource,
    guardTransition: guard.guardTransition,
    dismissPendingTransition: guard.dismissPendingTransition,
    guardDialog: null,
    isDialogOpen: guard.isDialogOpen,
    hasDirtySources: guard.hasDirtySources,
    setPendingOperationSources,
    hasPendingOperations,
    guardRouteLeave,
    notifyDirtyStateChange: guard.notifyDirtyStateChange,
  }), [
    guard.registerDirtySource,
    guard.guardTransition,
    guard.dismissPendingTransition,
    guard.isDialogOpen,
    guard.hasDirtySources,
    guard.notifyDirtyStateChange,
    setPendingOperationSources,
    hasPendingOperations,
    guardRouteLeave,
  ]);

  return (
    <LabDirtyGuardContext.Provider value={value}>
      {children}
      <LabLeaveRouteGuard
        hasDirtySources={guard.hasDirtySources}
        hasPendingOperations={hasPendingOperations}
        guardRouteLeave={guardRouteLeave}
      />
      {guard.guardDialog}
    </LabDirtyGuardContext.Provider>
  );
}

// ─── Route-leave host (sentinel + popstate) ──────────────────────────────────

function LabLeaveRouteGuard({
  hasDirtySources,
  hasPendingOperations,
  guardRouteLeave,
}: {
  hasDirtySources: () => boolean;
  hasPendingOperations: boolean;
  guardRouteLeave: (leave: () => void) => boolean;
}) {
  const navigate = useNavigate();
  // render-time присваивание (тот же паттерн, что cancelRef в guard-хуке):
  // popstate-listener всегда видит актуальные коллбеки без пересборки.
  const hasDirtyRef = useRef(hasDirtySources);
  hasDirtyRef.current = hasDirtySources;
  // PR 3351 (review round 3, P1): pending-состояние участвует в решении
  // sentinel-а: незавершённая операция блокирует browser Back так же,
  // как dirty-черновик (clone чистого шаблона не идемпотентен).
  const hasPendingRef = useRef(hasPendingOperations);
  hasPendingRef.current = hasPendingOperations;
  const guardRouteLeaveRef = useRef(guardRouteLeave);
  guardRouteLeaveRef.current = guardRouteLeave;
  const location = useLocation();

  // Arm/disarm sentinel. Эффект без deps — выполняется на каждом рендере
  // хоста (провайдер перерисовывается на флипах dirty/pending), операции
  // идемпотентны.
  useLayoutEffect(() => {
    if (typeof window === 'undefined') return;
    // PR 3351 (review round 3, P1): route identity — только точный маршрут
    // LabPanel сохраняет панель; '/lab/results' сюда не попадает.
    if (!isLabRoutePath(window.location.pathname)) {
      labLeaveSentinel.disarm();
      // PR 3351 (review round 3, P2): подтверждённый уход приземлился —
      // leave-flow закончился, sentinel возвращается обычному циклу.
      labLeaveSentinel.endLeaveIntent();
      return;
    }
    // PR 3351 (review round 3, P2): пока route-leave решение в полёте
    // (диалог открыт или выполняется его save/discard/navigate), жизненным
    // циклом sentinel'а владеет leave-flow — эффект полностью пассивен.
    // Иначе: рендер со STALE-dirty (isDirtyRef workbench'а обновляется в
    // useEffect позже layout-эффектов) ре-армил уже разоружённый sentinel
    // лишней записью, а последующий clean-рендер коллапсировал её —
    // конкурирующий traversal отменял navigate(-2) подтверждённого ухода.
    if (labLeaveSentinel.isLeaveIntent()) return;
    // PR 3351 (review round 3, P1): sentinel активен при dirty ИЛИ pending.
    if (!hasDirtyRef.current() && !hasPendingRef.current) {
      // Блокирующее состояние исчезло: не просто disarm — убираем фантомную
      // запись, иначе первый browser Back молча приземлится на дубликат /lab.
      if (labLeaveSentinel.isArmed()) labLeaveSentinel.collapse();
      return;
    }
    if (
      labLeaveSentinel.isArmed()
      && window.location.href !== labLeaveSentinel.getHref()
    ) {
      // Роутер заменил URL текущей (sentinel) записи — переотмечаем ту же
      // запись (replaceState), чтобы запись под sentinel осталась смежной
      // с реальной предыдущей страницей, а сравнение landing href в
      // popstate-обработчике — верным.
      labLeaveSentinel.remark(window.location.href);
    }
    labLeaveSentinel.arm(window.location.href);
    // location в deps не нужен: эффект идемпотентен и выполняется на каждом
    // рендере, включая рендеры после смены location.
  });

  // Browser Back/Forward: блокируем уход с /lab при dirty-черновиках
  // ИЛИ незавершённых операциях (PR 3351, review round 3).
  useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    const handlePopState = () => {
      // PR 3351 (review round 3, P2): pop от collapse — возврат с фантомной
      // sentinel-записи на реальный /lab. Глотаем: sentinel разоружён, URL
      // не меняется, роутер обрабатывает POP с нулевой дельтой.
      if (labLeaveSentinel.isCollapsing()) {
        labLeaveSentinel.finishCollapse();
        return;
      }
      if (!labLeaveSentinel.isArmed()) return;
      // Ленднули на sentinel-запись (forward-pop на неё или in-lab pop под
      // устаревшим sentinel): React Router сохраняет LabPanel смонтированной;
      // изменением ?instance владеет urlIntent-флоу самой панели.
      if (labLeaveSentinel.isSentinelEntry()) return;
      // PR 3351 (review round 3, P1): route identity — точный маршрут
      // LabPanel, а не любой /lab/*.
      if (!isLabRoutePath(window.location.pathname)) {
        // Защитная ветка: при вооружённом sentinel недостижима (pop
        // абсорбируется на /lab). Разоружаем и отдаём поп роутеру.
        labLeaveSentinel.disarm();
        return;
      }
      // PR 3351 (review round 3, P1): pending-only тоже блокирует уход —
      // sentinel вооружён при dirty||pending, решение через guardRouteLeave.
      if (!hasDirtyRef.current() && !hasPendingRef.current) {
        labLeaveSentinel.disarm();
        return;
      }
      if (window.location.href === labLeaveSentinel.getHref()) {
        // Sentinel вытеснен — это была попытка уйти с /lab. Перепушиваем
        // sentinel (второй Back при открытом диалоге тоже должен
        // абсорбироваться) и спрашиваем пользователя.
        labLeaveSentinel.disarm();
        labLeaveSentinel.arm(window.location.href);
        guardRouteLeaveRef.current(() => {
          labLeaveSentinel.disarm();
          // Sentinel + дублированная /lab-запись → реальная предыдущая
          // страница. Внутренние переходы /lab используют replace (не
          // создают записей), поэтому дельта всегда ровно две записи.
          navigate(-2);
        });
        return;
      }
      // In-lab URL-изменение (другой ?instance/?patient из внешнего
      // pushState+popstate): диалогом владеет urlIntent-флоу панели
      // (report-скоуп). Перевзвешиваем sentinel поверх нового URL.
      labLeaveSentinel.disarm();
      labLeaveSentinel.arm(window.location.href);
    };
    window.addEventListener('popstate', handlePopState);
    return () => {
      window.removeEventListener('popstate', handlePopState);
    };
  }, [navigate, location.pathname]);

  return null;
}

// ─── Consumer hooks ──────────────────────────────────────────────────────────

/**
 * Guard лабораторной панели. Внутри LabDirtyGuardProvider — общий экземпляр
 * уровня App (route-level leave guard активен). Без провайдера — standalone
 * экземпляр (unit-тесты / встраиваемые рендеры): переходы панели работают,
 * route-level возможности вырождены в no-op.
 */
export function useLabDirtyGuard(): LabDirtyGuardContextValue {
  const ctx = useContext(LabDirtyGuardContext);
  const standalone = useDirtyTransitionGuard();
  return useMemo<LabDirtyGuardContextValue>(() => (ctx ?? {
    isProvided: false,
    registerDirtySource: standalone.registerDirtySource,
    guardTransition: standalone.guardTransition,
    dismissPendingTransition: standalone.dismissPendingTransition,
    guardDialog: standalone.guardDialog,
    isDialogOpen: standalone.isDialogOpen,
    hasDirtySources: standalone.hasDirtySources,
    setPendingOperationSources: () => {},
    hasPendingOperations: false,
    guardRouteLeave: (leave: () => void) => standalone.guardTransition(leave),
    notifyDirtyStateChange: standalone.notifyDirtyStateChange,
  }), [ctx, standalone]);
}

/**
 * PR 3351: useNavigate, который не даёт молча уйти с /lab при несохранённых
 * черновиках ИЛИ незавершённых операциях. Используется App Shell-ом (Header,
 * sidebar, Command Palette, глобальный поиск, центр уведомлений) вместо
 * useNavigate.
 *
 * Числовые дельты (navigate(-1)) проходят напрямую: блокировкой владеет
 * sentinel — pop вытесняет его, land происходит на том же /lab URL, и
 * guard-диалог показывает popstate-обработчик. guardRouteLeave здесь был бы
 * ошибочен: подтверждение выполнило бы discard/save, а navigate(-1) всё
 * равно вернул бы пользователя на /lab (запись под sentinel).
 */
export function useGuardedLabNavigate() {
  const navigate = useNavigate();
  const { guardRouteLeave } = useLabDirtyGuard();
  const guardRouteLeaveRef = useRef(guardRouteLeave);
  guardRouteLeaveRef.current = guardRouteLeave;

  return useCallback((
    to: To | number,
    options?: NavigateOptions & { onLeave?: () => void },
  ) => {
    const { onLeave, ...navigateOptions } = options ?? {};
    if (typeof to === 'number') {
      // Числовая дельта: второй overload NavigateFunction — без options.
      navigate(to);
      return;
    }
    const targetPathname = typeof to === 'string'
      ? new URL(to, window.location.origin).pathname
      : (to.pathname ?? window.location.pathname);
    // PR 3351 (review round 3, P1): route identity — точный маршрут LabPanel.
    // '/lab/results' не зарегистрирован (wildcard → /not-found размонтирует
    // панель), поэтому это уход, а не внутренний переход.
    const leavesLabRoute = !isLabRoutePath(targetPathname);
    if (!leavesLabRoute) {
      onLeave?.();
      navigate(to as To, navigateOptions);
      return;
    }
    // PR 3351 (review round 3, P1): ЛЮБОЙ уход с /lab проходит через
    // guardRouteLeave — не только при dirty-черновиках. Pending-only
    // операция (clone чистого шаблона, finalize/print чистого отчёта)
    // блокируется pending-веткой; при полностью чистом состоянии
    // guardTransition выполняет переход сразу, без диалога.
    guardRouteLeaveRef.current(() => {
      // PR 3351 (review round 3, P2): подтверждённый уход ЗАМЕНЯЕТ
      // синтетическую sentinel-запись (navigate replace) вместо push поверх
      // неё — Back возвращает пользователя на реальный /lab без второго
      // дубля. Без armed-sentinel — обычная семантика вызывающего кода.
      const replaceSentinelEntry = labLeaveSentinel.isArmed()
        && labLeaveSentinel.isSentinelEntry();
      labLeaveSentinel.disarm();
      onLeave?.();
      navigate(to as To, {
        ...navigateOptions,
        replace: replaceSentinelEntry || navigateOptions.replace === true,
      });
    });
  }, [navigate]);
}
