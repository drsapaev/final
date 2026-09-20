import { useCallback, useRef, useState } from 'react';
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
 *   registerDirtySource({ id: 'report', isDirty: () => boolean, save: async () => void })
 *
 * Переход оборачивается в guardTransition(transition):
 *   - нет dirty-drafts → переход выполняется сразу;
 *   - есть dirty → показывается единый диалог с тремя действиями:
 *       «Сохранить и перейти» — последовательно сохраняет все dirty
 *         источники и выполняет переход; неудача сохранения оставляет
 *         пользователя на месте (ошибку показывает сам источник);
 *       «Выйти без сохранения» — переходит, ничего не сохраняя;
 *       «Отмена» — ничего не делает: пользователь и введённые значения
 *         остаются на месте.
 *
 * Возвращает guardDialog — JSX-элемент, который вызывающий рендерит рядом
 * с собой (паттерн useConfirm из components/common/ConfirmDialog).
 */

export interface DirtyDraftSource {
  id: string;
  isDirty: () => boolean;
  save: () => Promise<void>;
}

export interface DirtyTransitionGuard {
  registerDirtySource: (source: DirtyDraftSource) => () => void;
  guardTransition: (
    transition: () => void | Promise<void>,
    options?: { onCancel?: () => void | Promise<void> },
  ) => boolean;
  dismissPendingTransition: () => void;
  guardDialog: React.ReactNode;
  isDialogOpen: boolean;
}

interface PendingDirtyTransition {
  run: () => void | Promise<void>;
  onCancel?: () => void | Promise<void>;
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

  const registerDirtySource = useCallback((source: DirtyDraftSource) => {
    sourcesRef.current.set(source.id, source);
    return () => {
      sourcesRef.current.delete(source.id);
    };
  }, []);

  const guardTransition = useCallback((
    transition: () => void | Promise<void>,
    transitionOptions?: { onCancel?: () => void | Promise<void> },
  ) => {
    const hasDirty = [...sourcesRef.current.values()].some((source) => source.isDirty());
    if (!hasDirty) {
      pendingTransitionRef.current = null;
      setPendingTransition(null);
      void transition();
      return true;
    }
    const pending = { run: transition, onCancel: transitionOptions?.onCancel };
    pendingTransitionRef.current = pending;
    setPendingTransition(pending);
    return false;
  }, []);

  const finishWithSave = async () => {
    const transition = pendingTransitionRef.current;
    if (!transition) return;
    setBusy(true);
    try {
      for (const source of sourcesRef.current.values()) {
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
      await transition.run();
    } finally {
      setBusy(false);
    }
  };

  const cancel = () => {
    if (busy) return;
    const onCancel = pendingTransitionRef.current?.onCancel;
    pendingTransitionRef.current = null;
    setPendingTransition(null);
    void onCancel?.();
  };

  const dismissPendingTransition = useCallback(() => {
    pendingTransitionRef.current = null;
    setPendingTransition(null);
  }, []);

  const guardDialog = pendingTransition ? (
    <Modal isOpen onClose={cancel}>
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
  };
}

export default useDirtyTransitionGuard;
