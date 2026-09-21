import { useCallback, useLayoutEffect, useRef, useState } from 'react';
import { Button, Modal } from '../../ui/macos';
import { ModalContent, ModalFooter, ModalHeader, ModalTitle } from '../../ui/macos/Modal';
import { useTranslation } from '../../../i18n/useTranslation';

/**
 * PR5: useDirtyTransitionGuard — единый guard для переходов панели
 * лаборатории, уничтожающих введённый draft (смена пациента, открытие
 * другого отчёта, выбор другого шаблона, Escape/clearSelection,
 * восстановление из URL).
 *
 * Источники dirty-состояния регистрируют себя через registerDirtySource
 * (дочерние workbench'и знают только про свой draft — панель не должна
 * дублировать их логику):
 *   registerDirtySource({
 *     id: 'report',
 *     isDirty: () => boolean,
 *     save: async () => void,
 *     discard: () => void, // reset draft to its loaded baseline
 *   })
 *
 * Переход оборачивается в guardTransition(transition, options):
 *   - sourceIds ограничивает проверку переходом затрагиваемыми
 *     источниками: смена шаблона не должна спрашивать про dirty-отчёт и
 *     наоборот. Без sourceIds проверяются все источники (полный уход из
 *     контекста — например, внешняя URL-навигация);
 *   - нет dirty-drafts среди затронутых источников → переход выполняется
 *     сразу;
 *   - есть dirty → показывается единый диалог с тремя действиями:
 *       «Сохранить и перейти» — последовательно сохраняет dirty
 *         источники из области перехода и выполняет его; неудача
 *         сохранения оставляет пользователя на месте (ошибку показывает
 *         сам источник);
 *       «Выйти без сохранения» — СНАЧАЛА сбрасывает dirty-источники из
 *         области перехода к их baseline (discard), затем выполняет
 *         переход. Если загрузка новой цели завершится ошибкой,
 *         сброшенный draft не может «воскреснуть» и сохраниться
 *         autosave — выбор Discard остаётся необратимым;
 *       «Отмена» — ничего не делает: пользователь и введённые значения
 *         остаются на месте.
 *
 * Escape принадлежит самому диалогу: onKeyDown на корне модального окна
 * обрабатывает Escape ДО любого пассивного document-listener и без
 * closeOnEscape (document-level listener Modal). Это детерминированно:
 * то же нажатие Escape, которое ОТКРЫЛО диалог через capture-listener
 * hotkeys, не может его закрыть — react не доставит synthetic event в
 * только что смонтированное окно, а document-listener'а просто нет.
 *
 * Возвращает guardDialog — JSX-элемент, который вызывающий рендерит рядом
 * с собой (паттерн useConfirm из components/common/ConfirmDialog).
 */

export interface DirtyDraftSource {
  id: string;
  isDirty: () => boolean;
  save: () => Promise<void>;
  /**
   * Сброс черновика к baseline загруженной цели. Вызывается только по
   * явному выбору «Выйти без сохранения». Источник без discard
   * (опциональность сохранена для тестовых дублеров) просто продолжает
   * переход — панель не должна падать на legacy-источнике.
   */
  discard?: () => void;
}

export interface DirtyGuardTransitionOptions {
  onCancel?: () => void | Promise<void>;
  /**
   * Идентификаторы источников, чьи drafts уничтожает этот переход.
   * Опущено → переход затрагивает все зарегистрированные источники.
   */
  sourceIds?: string[];
}

export interface DirtyTransitionGuard {
  registerDirtySource: (source: DirtyDraftSource) => () => void;
  guardTransition: (
    transition: () => void | Promise<void>,
    options?: DirtyGuardTransitionOptions,
  ) => boolean;
  dismissPendingTransition: () => void;
  guardDialog: React.ReactNode;
  isDialogOpen: boolean;
  /**
   * PR 3351 (route-level leave guard): true когда хотя бы один
   * зарегистрированный источник сейчас dirty. Читается на уровне App Shell
   * (guarded navigate) до того, как переход начнётся.
   */
  hasDirtySources: () => boolean;
  /**
   * PR 3351: источники вызывают это при каждом изменении своего dirty-состояния
   * (workbench'и — из эффекта, обновляющего их isDirty-ref, т.е. на каждом
   * рендере). Перерисовка происходит только при реальном флипе агрегированного
   * значения — notify с каждого рендера не может зациклить обновления.
   */
  notifyDirtyStateChange: () => void;
}

interface PendingDirtyTransition {
  run: () => void | Promise<void>;
  onCancel?: () => void | Promise<void>;
  sourceIds: string[] | null;
}

/** Источники, входящие в область перехода. null — все зарегистрированные. */
function selectScopedSources(
  sources: Map<string, DirtyDraftSource>,
  sourceIds: string[] | null,
): DirtyDraftSource[] {
  const all = [...sources.values()];
  if (!sourceIds) return all;
  const scope = new Set(sourceIds);
  return all.filter((source) => scope.has(source.id));
}

export function useDirtyTransitionGuard(options?: {
  title?: string;
  message?: string;
}): DirtyTransitionGuard {
  const { t } = useTranslation();
  const sourcesRef = useRef<Map<string, DirtyDraftSource>>(new Map());
  const pendingTransitionRef = useRef<PendingDirtyTransition | null>(null);
  const [pendingTransition, setPendingTransition] = useState<PendingDirtyTransition | null>(null);
  const [busy, setBusy] = useState(false);
  // PR 3351 (route-level leave guard): версия dirty-состояния. Бампается
  // только при флипе агрегированного значения — провайдер уровня App Shell
  // перерисовывается (и перевзвешивает sentinel) на флипах, а не на каждый
  // keystroke.
  const [, bumpDirtyVersion] = useState(0);
  const lastNotifiedDirtyRef = useRef(false);

  const hasDirtySources = useCallback(() => (
    [...sourcesRef.current.values()].some((source) => source.isDirty())
  ), []);

  const notifyDirtyStateChange = useCallback(() => {
    const dirty = [...sourcesRef.current.values()].some((source) => source.isDirty());
    if (dirty === lastNotifiedDirtyRef.current) return;
    lastNotifiedDirtyRef.current = dirty;
    bumpDirtyVersion((version) => version + 1);
  }, []);

  const registerDirtySource = useCallback((source: DirtyDraftSource) => {
    sourcesRef.current.set(source.id, source);
    notifyDirtyStateChange();
    return () => {
      sourcesRef.current.delete(source.id);
      // Источник с dirty-черновиком размонтировался (подтверждённый уход с
      // /lab): агрегированное значение могло смениться — sentinel должен
      // перевзвестись.
      notifyDirtyStateChange();
    };
  }, [notifyDirtyStateChange]);

  const guardTransition = useCallback((
    transition: () => void | Promise<void>,
    transitionOptions?: DirtyGuardTransitionOptions,
  ) => {
    const affected = selectScopedSources(
      sourcesRef.current,
      transitionOptions?.sourceIds ?? null,
    );
    const hasDirty = affected.some((source) => source.isDirty());
    if (!hasDirty) {
      pendingTransitionRef.current = null;
      setPendingTransition(null);
      void transition();
      return true;
    }
    const pending: PendingDirtyTransition = {
      run: transition,
      onCancel: transitionOptions?.onCancel,
      sourceIds: transitionOptions?.sourceIds ?? null,
    };
    pendingTransitionRef.current = pending;
    setPendingTransition(pending);
    return false;
  }, []);

  const finishWithSave = async () => {
    const transition = pendingTransitionRef.current;
    if (!transition) return;
    setBusy(true);
    try {
      for (const source of selectScopedSources(sourcesRef.current, transition.sourceIds)) {
        if (source.isDirty()) {
          await source.save();
          if (pendingTransitionRef.current !== transition) return;
        }
      }
      if (pendingTransitionRef.current !== transition) return;
      pendingTransitionRef.current = null;
      setPendingTransition(null);
      await transition.run();
    } catch {
      // Ошибку сохранения уже показал источник (notify/inline).
      // Пользователь остаётся на месте с введённым draft.
    } finally {
      setBusy(false);
    }
  };

  const discardAndContinue = async () => {
    const transition = pendingTransitionRef.current;
    if (!transition) return;
    pendingTransitionRef.current = null;
    setPendingTransition(null);
    setBusy(true);
    try {
      // Сначала сбрасываем затронутые dirty-источники. Выбор Discard
      // необратим: даже если переход ниже упадёт (например, загрузка
      // нового отчёта завершится ошибкой), сброшенный draft не сможет
      // сохраниться autosave от старого контекста.
      for (const source of selectScopedSources(sourcesRef.current, transition.sourceIds)) {
        if (source.isDirty()) {
          source.discard?.();
        }
      }
      await transition.run();
    } finally {
      setBusy(false);
    }
  };

  const dismissPendingTransition = useCallback(() => {
    pendingTransitionRef.current = null;
    setPendingTransition(null);
  }, []);

  // Кнопка «Отмена» и Escape — одно и то же действие. Выделено в callback,
  // чтобы document-listener и кнопки использовали одну реализение.
  const cancel = () => {
    if (busy) return;
    const onCancel = pendingTransitionRef.current?.onCancel;
    pendingTransitionRef.current = null;
    setPendingTransition(null);
    void onCancel?.();
  };
  const cancelRef = useRef(cancel);
  // Обновляем ref прямо в render: пассивный effect мог бы отстать от
  // первого нажатия Escape (scheduler macrotask), а render-присваивание
  // атомарно вместе с коммитом.
  cancelRef.current = cancel;

  // Детерминированное владение Escape (PR 3351):
  // - listener на document в CAPTURE-фазе: закрывает диалог при Escape при
  //   любой позиции фокуса (в т.ч. body до requestAnimationFrame-автофокуса
  //   Modal), раньше пассивных bubble-listener-ов;
  // - то самое нажатие Escape, которое ОТКРЫЛО диалог (capture-listener
  //   hotkeys → setState → монтирование), НЕ может его закрыть: capture-фаза
  //   document уже прошла, а capture-listener не вызывается в bubble-фазе;
  // - closeOnEscape у Modal отключён — пассивный document-listener Modal
  //   не участвует (он ловил то же событие, которое открыло диалог).
  // useLayoutEffect (не useEffect): listener обязан быть прикреплён в том же
  // коммите, что и видимый диалог — пассивный effect доливается отдельным
  // macrotask-ом scheduler-а, и быстрый Escape (например, из Playwright
  // сразу после toBeVisible) успевал прибыть ДО прикрепления и терялся.
  useLayoutEffect(() => {
    if (!pendingTransition) return undefined;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape' || event.defaultPrevented) return;
      if (busy) return;
      event.preventDefault();
      event.stopPropagation();
      cancelRef.current();
    };
    document.addEventListener('keydown', handleKeyDown, true);
    return () => {
      document.removeEventListener('keydown', handleKeyDown, true);
    };
  }, [busy, pendingTransition]);

  const guardDialog = pendingTransition ? (
    <Modal isOpen onClose={cancel} closeOnEscape={false}>
      <ModalHeader>
        <ModalTitle>{options?.title ?? t('confirm.unsaved_title')}</ModalTitle>
      </ModalHeader>
      <ModalContent>
        {options?.message ?? t('confirm.unsaved_message')}
      </ModalContent>
      <ModalFooter>
        <Button variant="outline" size="default" onClick={cancel} disabled={busy}>
          {t('confirm.cancel')}
        </Button>
        <Button variant="ghost" size="default" onClick={() => { void discardAndContinue(); }} disabled={busy}>
          {t('confirm.unsaved_discard_and_continue')}
        </Button>
        <Button variant="primary" size="default" onClick={() => { void finishWithSave(); }} disabled={busy}>
          {t('confirm.unsaved_save_and_continue')}
        </Button>
      </ModalFooter>
    </Modal>
  ) : null;


  return {
    registerDirtySource,
    guardTransition,
    dismissPendingTransition,
    guardDialog,
    isDialogOpen: pendingTransition !== null,
    hasDirtySources,
    notifyDirtyStateChange,
  };
}

export default useDirtyTransitionGuard;
