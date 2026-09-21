import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  type ReactNode,
} from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import type { NavigateOptions, To } from 'react-router-dom';
import {
  useDirtyTransitionGuard,
  type DirtyTransitionGuard,
} from './hooks/useDirtyTransitionGuard';
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
 *    роутера. Используется sentinel-запись в history: пока есть dirty-источник,
 *    поверх текущей /lab-записи пушится дубликат (тот же URL, marker в state).
 *    Browser Back вытесняет sentinel — URL остаётся /lab, роутер видит POP на
 *    тот же маршрут (LabPanel НЕ размонтируется), а наш popstate-listener
 *    показывает guard-диалог. Подтверждение → navigate(-2) (sentinel +
 *    дубликат) — реальный уход; отмена → пользователь и черновик на месте.
 *
 * Инвариант sentinel: запись ПОД sentinel никогда не мутирует после arm
 * (replaceState действует на текущую запись, т.е. на сам sentinel), поэтому
 * «вытесненный sentinel» опознаётся по landing href === sentinel href.
 * Если роутер заменил URL текущей (sentinel) записи, sentinel перевзвешивается
 * (disarm + arm) — сравнение остаётся осмысленным.
 */

export function isLabPath(pathname: string): boolean {
  return pathname === '/lab' || pathname.startsWith('/lab/');
}

// ─── Sentinel controller ─────────────────────────────────────────────────────

const SENTINEL_STATE_KEY = '__labLeaveGuardSentinel';

const labLeaveSentinel = {
  armed: false,
  sentinelHref: null as string | null,
  isArmed: () => labLeaveSentinel.armed,
  getHref: () => labLeaveSentinel.sentinelHref,
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

  const setPendingOperationSources = useCallback((sources: string[]) => {
    pendingOperationSourcesRef.current = sources;
  }, []);

  // Уход с /lab блокируется при любой незавершённой операции (save/finalize/
  // print/autosave любого источника) — переход посреди записи мог бы создать
  // повторную запись или потерять ответ; затем — dirty-диалог по всем
  // источникам (без sourceIds).
  const guardRouteLeave = useCallback((leave: () => void) => {
    if (pendingOperationSourcesRef.current.length > 0) {
      notifyService.info(t('workbench.saving'));
      return false;
    }
    return guard.guardTransition(leave);
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
    guardRouteLeave,
  ]);

  return (
    <LabDirtyGuardContext.Provider value={value}>
      {children}
      <LabLeaveRouteGuard
        hasDirtySources={guard.hasDirtySources}
        guardRouteLeave={guardRouteLeave}
      />
      {guard.guardDialog}
    </LabDirtyGuardContext.Provider>
  );
}

// ─── Route-leave host (sentinel + popstate) ──────────────────────────────────

function LabLeaveRouteGuard({
  hasDirtySources,
  guardRouteLeave,
}: {
  hasDirtySources: () => boolean;
  guardRouteLeave: (leave: () => void) => boolean;
}) {
  const navigate = useNavigate();
  // render-time присваивание (тот же паттерн, что cancelRef в guard-хуке):
  // popstate-listener всегда видит актуальные коллбеки без пересборки.
  const hasDirtyRef = useRef(hasDirtySources);
  hasDirtyRef.current = hasDirtySources;
  const guardRouteLeaveRef = useRef(guardRouteLeave);
  guardRouteLeaveRef.current = guardRouteLeave;
  const location = useLocation();

  // Arm/disarm sentinel. Эффект без deps — выполняется на каждом рендере
  // хоста (провайдер перерисовывается на флипах dirty/pending), операции
  // идемпотентны.
  useLayoutEffect(() => {
    if (typeof window === 'undefined') return;
    if (!isLabPath(window.location.pathname)) {
      labLeaveSentinel.disarm();
      return;
    }
    if (!hasDirtyRef.current()) {
      labLeaveSentinel.disarm();
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

  // Browser Back/Forward: блокируем уход с /lab при dirty-черновиках.
  useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    const handlePopState = () => {
      if (!labLeaveSentinel.isArmed()) return;
      // Ленднули на sentinel-запись (forward-pop на неё или in-lab pop под
      // устаревшим sentinel): React Router сохраняет LabPanel смонтированной;
      // изменением ?instance владеет urlIntent-флоу самой панели.
      if (labLeaveSentinel.isSentinelEntry()) return;
      if (!isLabPath(window.location.pathname)) {
        // Защитная ветка: при вооружённом sentinel недостижима (pop
        // абсорбируется на /lab). Разоружаем и отдаём поп роутеру.
        labLeaveSentinel.disarm();
        return;
      }
      if (!hasDirtyRef.current()) {
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
    guardRouteLeave: (leave: () => void) => standalone.guardTransition(leave),
    notifyDirtyStateChange: standalone.notifyDirtyStateChange,
  }), [ctx, standalone]);
}

/**
 * PR 3351: useNavigate, который не даёт молча уйти с /lab при несохранённых
 * черновиках. Используется App Shell-ом (Header, sidebar, Command Palette,
 * глобальный поиск) вместо useNavigate.
 *
 * Числовые дельты (navigate(-1)) проходят напрямую: блокировкой владеет
 * sentinel — pop вытесняет его, land происходит на том же /lab URL, и
 * guard-диалог показывает popstate-обработчик. guardRouteLeave здесь был бы
 * ошибочен: подтверждение выполнило бы discard/save, а navigate(-1) всё
 * равно вернул бы пользователя на /lab (запись под sentinel).
 */
export function useGuardedLabNavigate() {
  const navigate = useNavigate();
  const { hasDirtySources, guardRouteLeave } = useLabDirtyGuard();
  const hasDirtyRef = useRef(hasDirtySources);
  hasDirtyRef.current = hasDirtySources;
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
    const leavesLab = !isLabPath(targetPathname);
    if (!leavesLab || !hasDirtyRef.current()) {
      onLeave?.();
      navigate(to as To, navigateOptions);
      return;
    }
    guardRouteLeaveRef.current(() => {
      labLeaveSentinel.disarm();
      onLeave?.();
      navigate(to as To, navigateOptions);
    });
  }, [navigate]);
}
