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
 *    PR 3351 (review round 4, P2): sentinel-контракт «внутренние /lab-
 *    переходы не создают history-записей» (все писатели используют replace)
 *    теперь двусторонне защищён. Вытеснение sentinel'а (browser Back)
 *    опознаётся по ДВОЙНИКУ — записи с тем же router-idx без маркера:
 *    arm() пушит копию состояния записи-двойника, поэтому href-сравнение
 *    больше не нужно (после любого in-lab replace — смена ?instance / ?tab
 *    — URL записи-двойника расходится с sentinel-URL, и прежняя href-
 *    эвристика молча глотала Back как «in-lab дрейф»). А push-дрейф —
 *    писатель, запутивший запись ПОВЕРХ вооружённого sentinel'а —
 *    опознаётся по росту history.length и перевзвешивает sentinel поверх
 *    нового верха, вместо remark'а чужой записи (двойной маркер → «мёртвые»
 *    Back-нажатия после Save).
 *
 *    Маркер sentinel'а переживает router-replace СИНХРОННО — декоратором
 *    history.replaceState (installSentinelHistoryPatch): смена ?tab через
 *    sidebar / ?instance через navigateReplace заменяет ТЕКУЩУЮ (sentinel)
 *    запись новым router-состоянием и затирает маркер; render-based remark
 *    полагался на коммит рендера, а React 18 может прервать transition-
 *    рендер (следующая навигация supersede) — маркер терялся навсегда,
 *    collapse() не находил sentinel-запись и фантом оставался в истории.
 *    Декоратор merge-ит маркер прямо в полёт replaceState: armed + текущая
 *    запись — sentinel + цель остаётся in-lab → маркер и sentinelHref
 *    синхронны с любой заменой URL, независимо от React.
 *
 *    PR 3351 (review round 5, P1): push поверх sentinel'а закрыт СИСТЕМНО,
 *    на уровне guarded navigator-а: переход с lab-маршрута на тот же
 *    lab-маршрут (Header brand → /lab, Command Palette → Lab Panel) —
 *    replace (идентичный URL — полный no-op), независимо от автора вызова.
 *    Дельта -2 подтверждённого ухода больше не зависит от дисциплины
 *    отдельных writers: вторая /lab-запись не создаётся ни при armed
 *    sentinel, ни до его вооружения.
 *
 *    PR 3351 (review round 5, P2): прямой вход в /lab без реальной
 *    предыдущей записи (новая вкладка). arm() фиксирует наличие
 *    предшественника под twin-записью (router idx документа начинается
 *    с 0; fallback — history.length до пуша). Вытеснение sentinel'а без
 *    предшественника абсорбируется БЕЗ destructive-диалога: подтверждённому
 *    уходу некуда приземляться (go(-2) за границей history — no-op), а
 *    Discard уже необратимо сбросил бы черновик. Для остальных случаев
 *    подтверждённый уход проверяет фактическое приземление и завершает
 *    переход принудительным SPA-переходом на последнюю не-lab страницу
 *    сессии, если traversal не состоялся — leaveIntent не зависает.
 *
 *    PR 3351 (review round 6, P1): полная защита документа (refresh /
 *    закрытие вкладки) тоже живёт ЗДЕСЬ, на уровне провайдера, и
 *    срабатывает при dirty-черновиках ИЛИ незавершённых операциях.
 *    Прежние per-workbench beforeunload-хуки закрывали только dirty-state:
 *    pending-only мутация (clone чистого шаблона, finalize/print чистого
 *    отчёта) терялась без предупреждения — браузер обрывал неидемпотентный
 *    POST, ответ пропадал, и оператор повторял clone, создавая вторую
 *    копию. Условие проверяется ВНУТРИ обработчика (render-time рефы
 *    актуальны всегда), поэтому слушатель установлен один раз и не
 *    зависит от перерисовок провайдера.
 *
 *    PR 3351 (review round 7, P1): pending-защита разделена на ДВА сигнала.
 *    Полный уход (beforeunload/guardRouteLeave/session-expiry) блокируется
 *    при ЛЮБОЙ незавершённой операции — включая report CREATE (review
 *    round 7: неидемпотентный POST /lab/report-instances). Но sentinel
 *    (browser Back) вооружается только операциями, блокирующими и
 *    КОНТЕКСТНЫЕ переходы (save/finalize/print/autosave/шаблонные операции):
 *    для latest-wins CREATE in-lab Back — легитимный контекстный переход,
 *    а вооружение sentinel-а рвало бы URL-контракт: in-lab replace (create
 *    применил новый ?instance) меняет запись sentinel-а, twin ниже неё
 *    хранит до-create URL, и collapse после завершения операции уводил бы
 *    history.back()-ом на устаревший twin — URL и активный отчёт молча
 *    откатывались на предыдущий бланк (stale restore). Поэтому сигналы
 *    разнесены: hasPendingOperations (документ/маршрут/сессия) и
 *    hasHistoryGuardPending (sentinel/popstate).
 *
 * Инвариант sentinel: запись ПОД sentinel никогда не мутирует после arm
 * (replaceState действует на текущую запись, т.е. на сам sentinel). Вытесненный
 * sentinel опознаётся по двойнику (PR 3351, review round 4): запись на одну
 * ниже с тем же router-idx и без маркера. Если роутер заменил URL текущей
 * (sentinel) записи, sentinel переотмечается (remark) — сравнение по idx
 * остаётся осмысленным.
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

/**
 * PR 3351 (review round 5, P2): задержка перед проверкой фактического
 * приземления подтверждённого browser-Back ухода (navigate(-2)). In-bounds
 * traversal дёшев: popstate + router-рендер успевают уложиться в десятки
 * мс; 300 мс — запас, исключающий гонку с легитимным переходом.
 */
const CONFIRMED_LEAVE_COMPLETION_TIMEOUT_MS = 300;

const labLeaveSentinel = {
  armed: false,
  sentinelHref: null as string | null,
  /**
   * PR 3351 (review round 4, P2): router-idx записи sentinel. arm() пушит
   * копию состояния текущей записи (тот же usr/key/idx) — «двойник» на одну
   * запись ниже. Вытеснение (browser Back) = pop на двойник: тот же idx,
   * нет маркера. Хранится отдельно от href: in-lab replace-писатели меняют
   * URL sentinel-записи, но не idx (роутер replace сохраняет idx), поэтому
   * idx-сравнение переживает смену ?instance / ?tab, а href-сравнение — нет.
   */
  sentinelIdx: null as number | null,
  /**
   * PR 3351 (review round 4, P2): history.length сразу после arm(). Рост
   * длины при дрейфе href = push ПОВЕРХ вооружённого sentinel'а (писатель
   * нарушил replace-контракт): remark пометил бы чужую запись и оставил бы
   * под ней старый маркер. replace-дрейф длину не меняет.
   */
  armedLength: null as number | null,
  /**
   * PR 3351 (review round 5, P2): существует ли РЕАЛЬНАЯ запись ПОД
   * twin-записью — туда, куда должен приземлиться подтверждённый уход
   * (navigate(-2): sentinel → twin → предыдущая страница). При прямом
   * входе в /lab в новой вкладке под twin НИЧЕГО нет: go(-2) за границей
   * history — no-op, а destructive Discard уже сбросил бы черновик.
   *
   * Вычисляется ОДИН раз при первом arm «lab-заезда» (до появления
   * собственных synthetic-записей) и живёт до фактического ухода с /lab
   * (layout-эффект сбрасывает на не-lab рендере): пересчёт на каждом arm
   * ломался о собственные записи sentinel'а — после абсорбции/коллапса
   * история содержит forward-слот старого sentinel'а (length ≥ 2) даже
   * при прямом входе без предшественника, и второй Back снова открывал бы
   * dead-end диалог. Критерии первого arm: router idx обнуляется на первом
   * entry документа (react-router getUrlBasedHistory инициализирует
   * fresh-load состояние replaceState'ом {idx: 0}), поэтому idx > 0
   * гарантирует запись под twin; idx === 0 + history.length > 1 — внешняя
   * (кросс-документная) запись под twin; idx === 0 + length === 1 —
   * настоящий прямой вход без предшественника. Записи без router-состояния
   * (внешний pushState urlIntent-флоу) — консервативный fallback на длину.
   */
  stayHasPredecessor: null as boolean | null,
  resetStayPredecessor() {
    labLeaveSentinel.stayHasPredecessor = null;
  },
  /** Предшественник, зафиксированный текущим (вооружённым) arm-циклом. */
  armedWithPredecessor: false,
  hadRealPredecessor() {
    return labLeaveSentinel.armedWithPredecessor;
  },
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
    // PR 3351 (review round 4, P2): маркер обязан переживать router-
    // replace — декоратор ставится лениво при первом arm (идемпотентно).
    installSentinelHistoryPatch();
    if (labLeaveSentinel.armed) return;
    // PR 3351 (review round 5, P2): предшественник вычисляется при ПЕРВОМ
    // arm lab-заезда (до появления собственных synthetic-записей) и
    // переиспользуется для перевзвешиваний внутри заезда.
    if (labLeaveSentinel.stayHasPredecessor === null) {
      const twinState = window.history.state as Record<string, unknown> | null;
      const twinIdx = typeof twinState?.idx === 'number' ? twinState.idx : null;
      const lengthBeforeArm = window.history.length;
      // Записи без router-состояния (внешний pushState urlIntent-флоу) —
      // консервативный fallback на длину: единственная запись до пуша
      // означает прямой вход без предшественника.
      labLeaveSentinel.stayHasPredecessor = (twinIdx ?? 0) > 0 || lengthBeforeArm > 1;
    }
    window.history.pushState(labLeaveSentinel.sentinelState(), '', url);
    labLeaveSentinel.armed = true;
    labLeaveSentinel.sentinelHref = url;
    // PR 3351 (review round 4, P2): idx копируется из записи-двойника —
    // по нему popstate-обработчик отличает вытеснение от in-lab дрейфа.
    const armedState = window.history.state as Record<string, unknown> | null;
    labLeaveSentinel.sentinelIdx = typeof armedState?.idx === 'number' ? armedState.idx : null;
    labLeaveSentinel.armedLength = window.history.length;
    labLeaveSentinel.armedWithPredecessor = labLeaveSentinel.stayHasPredecessor;
  },
  /**
   * Роутер заменил URL текущей (sentinel) записи (navigateReplace внутри
   * /lab). НЕ пушим новую запись — переотмечаем ту же: инвариант «запись под
   * sentinel смежна с дельтой -2 до реальной предыдущей страницы» сохраняется.
   * replaceState действует на ту же запись — idx не меняется (роутер
   * replace пишет прежний idx), sentinelIdx остаётся корректным.
   */
  remark(url: string) {
    window.history.replaceState(labLeaveSentinel.sentinelState(), '', url);
    labLeaveSentinel.sentinelHref = url;
  },
  disarm() {
    labLeaveSentinel.armed = false;
    labLeaveSentinel.sentinelHref = null;
    labLeaveSentinel.sentinelIdx = null;
    labLeaveSentinel.armedLength = null;
    labLeaveSentinel.armedWithPredecessor = false;
  },
  /**
   * PR 3351 (review round 4, P2): pop приземлился на «двойника» — запись
   * на одну ниже sentinel с тем же router-idx и без маркера. Это
   * вытеснение sentinel'а (browser Back), а не in-lab дрейф: arm() пушит
   * копию состояния текущей записи, поэтому idx двойника === sentinel-idx.
   * Прежняя href-эвристика ломалась после ЛЮБОГО in-lab replace (смена
   * ?instance через navigateReplace или ?tab через sidebar): URL двойника
   * расходился с sentinel-URL, Back молча абсорбировался как «дрейф»,
   * а следующий Back мог уйти с /lab БЕЗ диалога. Для записей без router-
   * состояния (внешние pushState) — консервативный href-fallback.
   */
  isDisplacedTwin() {
    const landedState = window.history.state as Record<string, unknown> | null;
    const landedIdx = typeof landedState?.idx === 'number' ? landedState.idx : null;
    if (labLeaveSentinel.sentinelIdx !== null && landedIdx !== null) {
      return landedIdx === labLeaveSentinel.sentinelIdx;
    }
    return window.location.href === labLeaveSentinel.sentinelHref;
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

/**
 * PR 3351 (review round 4, P2): синхронный декоратор history.replaceState.
 *
 * Все внутренние /lab-писатели (sidebar ?tab, navigateReplace ?instance)
 * заменяют ТЕКУЩУЮ запись — при вооружённом sentinel это сама sentinel-
 * запись, и router-replace затирает маркер в history.state новым
 * состоянием {usr, key, idx}. Render-based remark в layout-эффекте
 * востанавливал маркер ПОСЛЕ коммита рендера — но React 18 имеет право
 * прервать transition-рендер (следующая навигация supersede предыдущую),
 * и тогда промежуточная замена вообще не рендерится: маркер терялся
 * навсегда, collapse() не находил sentinel-запись (disarm без back) и
 * «мёртвый» дубль оставался в истории — первый Back после Save
 * приземлялся на фантом. Декоратор решает проблему на уровне самого
 * History API: замена armed-sentinel-записи на IN-LAB URL происходит с
 * маркером и синхронным sentinelHref — независимо от React. Leave-replace
 * (цель вне /lab: подтверждённый уход через navigate replace) проходит
 * БЕЗ маркера — запись назначения не наследует sentinel-личность.
 */
let sentinelHistoryPatchInstalled = false;

function installSentinelHistoryPatch() {
  if (sentinelHistoryPatchInstalled || typeof window === 'undefined') return;
  sentinelHistoryPatchInstalled = true;
  const originalReplaceState = window.history.replaceState.bind(window.history);
  window.history.replaceState = (
    data: unknown,
    unused: string,
    url?: string | URL | null,
  ): void => {
    const targetPathname = url == null
      ? window.location.pathname
      : new URL(String(url), window.location.href).pathname;
    const isSentinelReplace = labLeaveSentinel.isArmed()
      && labLeaveSentinel.isSentinelEntry()
      && isLabRoutePath(targetPathname);
    if (isSentinelReplace && data != null && typeof data === 'object') {
      originalReplaceState(
        { ...(data as Record<string, unknown>), [SENTINEL_STATE_KEY]: true },
        unused,
        url,
      );
      if (url != null) {
        labLeaveSentinel.sentinelHref = new URL(String(url), window.location.href).href;
      }
      return;
    }
    originalReplaceState(data, unused, url);
  };
}

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
   *
   * PR 3351 (review round 7, P1): это ДОКУМЕНТ-уровневый сигнал (полный
   * уход: beforeunload, guardRouteLeave, session-expiry) — включает report
   * CREATE. Сигнал sentinel-а (browser Back) — отдельный,
   * hasHistoryGuardPending (см. ниже): CREATE его не блокирует.
   */
  hasPendingOperations: boolean;
  /**
   * PR 3351 (review round 7, P1): pending-источники, вооружающие sentinel
   * (browser Back) — операции, блокирующие и контекстные переходы
   * (save/finalize/print/autosave/шаблонные операции), БЕЗ latest-wins
   * report CREATE. Для create in-lab Back — легитимная навигация
   * (latest-wins по operation-context), а вооружение sentinel-а ломало бы
   * URL-контракт: collapse после завершения уходит history.back()-ом на
   * twin-запись с до-create URL и молча откатывает активный отчёт.
   */
  setHistoryGuardPendingSources: (sources: string[]) => void;
  /** Реактивный агрегат history-guard-источников (флипы 0↔n). */
  hasHistoryGuardPending: boolean;
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

  // PR 3351 (review round 7, P1): второй pending-сигнал — для sentinel-а
  // (browser Back). Те же флипы 0↔n, но состав уже: только операции,
  // блокирующие контекстные переходы (без latest-wins report CREATE —
  // иначе collapse sentinel-а после in-lab replace откатывал бы URL/отчёт
  // на до-create запись). См. комментарий к типу контекста.
  const historyGuardPendingSourcesRef = useRef<string[]>([]);
  const [historyGuardPendingSources, setHistoryGuardPendingSourcesState] = useState<string[]>([]);
  const setHistoryGuardPendingSources = useCallback((sources: string[]) => {
    historyGuardPendingSourcesRef.current = sources;
    setHistoryGuardPendingSourcesState((previous) => (
      (previous.length === 0) === (sources.length === 0) ? previous : sources
    ));
  }, []);
  const hasHistoryGuardPending = historyGuardPendingSources.length > 0;

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
    setHistoryGuardPendingSources,
    hasHistoryGuardPending,
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
    setHistoryGuardPendingSources,
    hasHistoryGuardPending,
    guardRouteLeave,
  ]);

  return (
    <LabDirtyGuardContext.Provider value={value}>
      {children}
      <LabLeaveRouteGuard
        hasDirtySources={guard.hasDirtySources}
        hasPendingOperations={hasPendingOperations}
        hasHistoryGuardPending={hasHistoryGuardPending}
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
  hasHistoryGuardPending,
  guardRouteLeave,
}: {
  hasDirtySources: () => boolean;
  /** ДОКУМЕНТ-уровень (beforeunload): dirty ИЛИ любая операция, включая report CREATE. */
  hasPendingOperations: boolean;
  /** Sentinel (browser Back): dirty ИЛИ операции, блокирующие контекстные переходы (без CREATE). */
  hasHistoryGuardPending: boolean;
  guardRouteLeave: (leave: () => void) => boolean;
}) {
  const navigate = useNavigate();
  // render-time присваивание (тот же паттерн, что cancelRef в guard-хуке):
  // popstate-listener всегда видит актуальные коллбеки без пересборки.
  const hasDirtyRef = useRef(hasDirtySources);
  hasDirtyRef.current = hasDirtySources;
  // ДОКУМЕНТ-уровневый pending (доc review round 7: включает report CREATE)
  // — питает ТОЛЬКО beforeunload (refresh/закрытие вкладки).
  const hasPendingRef = useRef(hasPendingOperations);
  hasPendingRef.current = hasPendingOperations;
  // PR 3351 (review round 7, P1): sentinel-arming сигнал — dirty ИЛИ
  // контекстно-блокирующие операции (save/finalize/print/autosave/шаблонные),
  // БЕЗ latest-wins report CREATE: для create in-lab Back — легитимная
  // навигация, а collapse вооружённого sentinel-а после in-lab replace
  // (create применил новый ?instance) уводил бы history.back()-ом на
  // twin-запись с до-create URL — URL и активный отчёт молча откатывались
  // (stale restore предыдущего бланка). Документ-уровень (refresh/close,
  // route-leave, session-expiry) при этом CREATE блокирует.
  const hasHistoryPendingRef = useRef(hasHistoryGuardPending);
  hasHistoryPendingRef.current = hasHistoryGuardPending;
  const guardRouteLeaveRef = useRef(guardRouteLeave);
  guardRouteLeaveRef.current = guardRouteLeave;

  // PR 3351 (review round 6, P1): beforeunload на уровне общего провайдера —
  // полная защита документа при dirty-черновиках ИЛИ незавершённых
  // операциях. Это заменяет per-workbench-хуки, которые ставили слушатель
  // только по dirty-state: pending-only мутация (clone чистого шаблона,
  // publish/finalize/print чистого отчёта) не блокировала refresh/закрытие
  // — неидемпотентный POST обрывался, ответ терялся, и оператор повторял
  // операцию, создавая дубль. Условие проверяется внутри обработчика по
  // render-time рефам (см. hasDirtyRef/hasPendingRef выше): слушатель не
  // нужно перевешивать на флипах состояния, он всегда видит актуальный
  // реестр. Вне /lab реестр пуст (источники снимаются при unmount), и
  // обработчик молча пропускает unload.
  useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!hasDirtyRef.current() && !hasPendingRef.current) return;
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, []);

  const location = useLocation();
  // PR 3351 (review round 5, P2): последняя не-lab страница SPA-сессии —
  // цель гарантированного завершения подтверждённого ухода, если
  // navigate(-2) не смог приземлиться (go за границей history — no-op).
  // Присваивание в render (тот же паттерн, что hasDirtyRef): popstate-
  // listener и таймер fallback-а всегда видят актуальное значение.
  const lastNonLabLocationRef = useRef<{ pathname: string; search: string } | null>(null);
  if (!isLabRoutePath(location.pathname)) {
    lastNonLabLocationRef.current = { pathname: location.pathname, search: location.search };
  }

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
      // PR 3351 (review round 5, P2): lab-заезд завершён — предшественник
      // следующего заезда будет вычислен заново.
      labLeaveSentinel.resetStayPredecessor();
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
    // PR 3351 (review round 7, P1): pending здесь — history-guard сигнал
    // (контекстно-блокирующие операции, БЕЗ latest-wins report CREATE):
    // см. комментарий к hasHistoryPendingRef выше.
    if (!hasDirtyRef.current() && !hasHistoryPendingRef.current) {
      // Блокирующее состояние исчезло: не просто disarm — убираем фантомную
      // запись, иначе первый browser Back молча приземлится на дубликат /lab.
      if (labLeaveSentinel.isArmed()) labLeaveSentinel.collapse();
      return;
    }
    if (
      labLeaveSentinel.isArmed()
      && window.location.href !== labLeaveSentinel.getHref()
    ) {
      // PR 3351 (review round 5): pop-приземление на ДВОЙНИКА — это
      // вытеснение sentinel'а (browser Back), а не дрейф. React 19
      // коммитит POP-рендер СИНХРОННО внутри dispatch popstate — ДО нашего
      // popstate-обработчика, — и прежняя drift-ветка remark'ом помечала
      // twin-запись (например, после brand-роллбека, когда URL sentinel'а
      // разошёлся с URL двойника): обработчик затем видел «landed on
      // sentinel» и глотал Back без диалога, а guard съезжал вниз —
      // следующий Back покидал /lab молча. Twin-подпись (тот же router-idx
      // без маркера) достоверно отличает вытеснение от replace-дрейфа
      // (replace сохраняет idx, но маркер merge-ит декоратор) и от внешнего
      // pushState (нет router-idx) — решение остаётся за popstate-
      // обработчиком.
      const landedState = window.history.state as Record<string, unknown> | null;
      const landedIdx = typeof landedState?.idx === 'number' ? landedState.idx : null;
      const poppedOntoTwin = !labLeaveSentinel.isSentinelEntry()
        && labLeaveSentinel.sentinelIdx !== null
        && landedIdx === labLeaveSentinel.sentinelIdx;
      if (poppedOntoTwin) return;
      // PR 3351 (review round 4, P2): дрейф href при вооружённом sentinel —
      // это replace текущей (sentinel) записи ИЛИ чужой push поверх неё.
      // Replace (роутер: смена ?instance / ?tab): длина истории не меняется —
      // переотмечаем ту же запись. Push поверх sentinel (писатель нарушил
      // replace-контракт): длина выросла, запись с router-idx — remark пометил
      // бы ЧУЖУЮ запись и оставил бы старый маркер под ней (двойной маркер
      // глотает Back после Save, «мёртвые» нажатия). Перевзвешиваем sentinel
      // поверх нового верха: guard остаётся активным, twin-детекция корректно
      // опознает вытеснение. Внешние pushState без router-состояния (urlIntent
      // флоу панели) остаются на remark-пути — прежнее поведение.
      const routerPushedAboveSentinel = labLeaveSentinel.armedLength !== null
        && window.history.length > labLeaveSentinel.armedLength
        && typeof (window.history.state as Record<string, unknown> | null)?.idx === 'number';
      if (routerPushedAboveSentinel) {
        labLeaveSentinel.disarm();
      } else {
        // Роутер заменил URL текущей (sentinel) записи — переотмечаем ту же
        // запись (replaceState), чтобы запись под sentinel осталась смежной
        // с реальной предыдущей страницей, а сравнение landing-idx в
        // popstate-обработчике — верным.
        labLeaveSentinel.remark(window.location.href);
      }
    }
    labLeaveSentinel.arm(window.location.href);
    // location в deps не нужен: эффект идемпотентен и выполняется на каждом
    // рендере, включая рендеры после смены location.
  });

  // Browser Back/Forward: блокируем уход с /lab при dirty-черновиках
  // ИЛИ незавершённых операциях (PR 3351, review round 3).
  useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    /**
     * PR 3351 (review round 5, P2): подтверждённый browser-Back уход обязан
     * ЗАВЕРШИТЬСЯ. navigate(-2) — no-op, когда под twin-записью нет реальной
     * записи (вытесненные forward-записи, exotic-состояния history): popstate
     * не приходит, роутер не перерисовывается, leaveIntent зависает, а
     * черновик уже сброшен Discard-ом — приложение уничтожило данные, не
     * выполнив обещанный переход. Проверяем фактическое приземление после
     * traversal-а: всё ещё на lab-маршруте → принудительный SPA-переход на
     * последнюю не-lab страницу сессии (replace), который гарантированно
     * завершает leave-flow (layout-эффект видит не-lab pathname и снимает
     * leaveIntent).
     */
    const scheduleConfirmedLeaveCompletion = () => {
      window.setTimeout(() => {
        // Переход уже приземлился (layout-эффект снял leaveIntent) —
        // или документ выгружается (кросс-документный -2) — ничего не делаем.
        if (!labLeaveSentinel.isLeaveIntent()) return;
        if (!isLabRoutePath(window.location.pathname)) return;
        const fallback = lastNonLabLocationRef.current;
        navigate(
          fallback ? { pathname: fallback.pathname, search: fallback.search } : '/health',
          { replace: true },
        );
      }, CONFIRMED_LEAVE_COMPLETION_TIMEOUT_MS);
    };
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
      // PR 3351 (review round 7, P1): тот же сигнал, что вооружал sentinel
      // (history-guard: контекстно-блокирующие операции, без CREATE) —
      // чем вооружились, тем и разоружаемся.
      if (!hasDirtyRef.current() && !hasHistoryPendingRef.current) {
        labLeaveSentinel.disarm();
        return;
      }
      if (labLeaveSentinel.isDisplacedTwin()) {
        // PR 3351 (review round 5, P2): прямой вход без реальной предыдущей
        // записи. Подтверждённому уходу некуда приземляться (go(-2) за
        // границей history — no-op), а destructive Discard уже необратимо
        // сбросил бы черновик — destructive-диалог для несуществующего
        // назначения не открываем. Back абсорбируется перевзвешиванием
        // sentinel (тот же механизм, что второй Back при открытом
        // диалоге): панель смонтирована, черновик жив, уйти можно
        // SPA-навигацией (Header/Profile/Logout через guard-диалог).
        const hasRealPredecessor = labLeaveSentinel.hadRealPredecessor();
        // Sentinel вытеснен — это была попытка уйти с /lab. Перепушиваем
        // sentinel (второй Back при открытом диалоге тоже должен
        // абсорбироваться) и спрашиваем пользователя.
        labLeaveSentinel.disarm();
        labLeaveSentinel.arm(window.location.href);
        if (!hasRealPredecessor) return;
        guardRouteLeaveRef.current(() => {
          labLeaveSentinel.disarm();
          // Sentinel + дублированная /lab-запись → реальная предыдущая
          // страница. Внутренние переходы /lab используют replace (не
          // создают записей), поэтому дельта всегда ровно две записи;
          // fallback ниже гарантирует завершение, если traversal
          // не приземлился (round 5, P2).
          navigate(-2);
          scheduleConfirmedLeaveCompletion();
        });
        return;
      }
      // In-lab URL-изменение (другой ?instance/?patient из внешнего
      // pushState+popstate): диалогом владеет urlIntent-флоу панели
      // (report-скоуп). Перевзвешиваем sentinel поверх нового URL.
      labLeaveSentinel.disarm();
      labLeaveSentinel.arm(window.location.href);
    };
    window.addEventListener('popstate', handlePopState as EventListener);
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
    setHistoryGuardPendingSources: () => {},
    hasHistoryGuardPending: false,
    guardRouteLeave: (leave: () => void) => standalone.guardTransition(leave),
    notifyDirtyStateChange: standalone.notifyDirtyStateChange,
  }), [ctx, standalone]);
}

/**
 * PR 3351 (review round 5, P1): полный href цели навигации — для no-op
 * детекции «уже на этом URL» в in-lab переходах guarded navigator-а.
 * Строка резолвится против текущего href (относительные '?…'/'#…'),
 * объект собирается из pathname+search+hash.
 */
function resolveToHref(to: To): string {
  if (typeof to === 'string') {
    return new URL(to, window.location.href).href;
  }
  const pathname = to.pathname ?? window.location.pathname;
  const search = to.search ?? '';
  const hash = to.hash ?? '';
  const path = `${pathname}${search}${hash}`;
  return new URL(path, window.location.href).href;
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
      // PR 3351 (review round 5, P1): переход УЖЕ с lab-маршрута на тот же
      // lab-маршрут (LabPanel смонтирован) — это внутренняя перезапись URL,
      // и она НЕ может пушить запись поверх sentinel'а. Штатные shell-
      // писатели (Header brand → canonical /lab, Command Palette → Lab
      // Panel) делают это БЕЗ replace — push создавал вторую /lab-запись:
      // при вооружённом sentinel дельта -2 подтверждённого ухода вела на
      // устаревшую помеченную копию вместо реальной предыдущей страницы, а
      // push при чистом черновике оставлял /lab-запись под будущим arm.
      // Идентичный URL — полный no-op (навигация на уже открытый
      // canonical /lab ничего не должна менять в history).
      if (isLabRoutePath(window.location.pathname)) {
        if (resolveToHref(to) !== window.location.href) {
          onLeave?.();
          navigate(to as To, { ...navigateOptions, replace: true });
        } else {
          onLeave?.();
        }
        return;
      }
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
