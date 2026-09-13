import { useCallback, useRef, useState } from 'react';
import { Button, Modal } from '../../ui/macos';
import { ModalContent, ModalFooter, ModalHeader, ModalTitle } from '../../ui/macos/Modal';

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
  guardTransition: (transition: () => void | Promise<void>) => void;
  guardDialog: React.ReactNode;
  isDialogOpen: boolean;
}

const SAVE_AND_CONTINUE = 'Сохранить и перейти';
const DISCARD_AND_CONTINUE = 'Выйти без сохранения';
const CANCEL = 'Отмена';

export function useDirtyTransitionGuard(options?: {
  title?: string;
  message?: string;
}): DirtyTransitionGuard {
  const sourcesRef = useRef<Map<string, DirtyDraftSource>>(new Map());
  const [pendingTransition, setPendingTransition] = useState<(() => void | Promise<void>) | null>(null);
  const [busy, setBusy] = useState(false);

  const registerDirtySource = useCallback((source: DirtyDraftSource) => {
    sourcesRef.current.set(source.id, source);
    return () => {
      sourcesRef.current.delete(source.id);
    };
  }, []);

  const guardTransition = useCallback((transition: () => void | Promise<void>) => {
    const hasDirty = [...sourcesRef.current.values()].some((source) => source.isDirty());
    if (!hasDirty) {
      void transition();
      return;
    }
    setPendingTransition(() => transition);
  }, []);

  const finishWithSave = async () => {
    const transition = pendingTransition;
    if (!transition) return;
    setBusy(true);
    try {
      for (const source of sourcesRef.current.values()) {
        if (source.isDirty()) {
          await source.save();
        }
      }
      setPendingTransition(null);
      await transition();
    } catch {
      // Ошибку сохранения уже показал источник (notify/inline).
      // Пользователь остаётся на месте с введённым draft.
    } finally {
      setBusy(false);
    }
  };

  const discardAndContinue = async () => {
    const transition = pendingTransition;
    if (!transition) return;
    setPendingTransition(null);
    setBusy(true);
    try {
      await transition();
    } finally {
      setBusy(false);
    }
  };

  const cancel = () => {
    if (busy) return;
    setPendingTransition(null);
  };

  const guardDialog = pendingTransition ? (
    <Modal isOpen onClose={cancel}>
      <ModalHeader>
        <ModalTitle>{options?.title ?? 'Несохранённые изменения'}</ModalTitle>
      </ModalHeader>
      <ModalContent>
        {options?.message ?? 'В бланке есть несохранённые изменения. Сохранить их перед переходом?'}
      </ModalContent>
      <ModalFooter>
        <Button variant="outline" size="default" onClick={cancel} disabled={busy}>
          {CANCEL}
        </Button>
        <Button variant="ghost" size="default" onClick={() => { void discardAndContinue(); }} disabled={busy}>
          {DISCARD_AND_CONTINUE}
        </Button>
        <Button variant="primary" size="default" onClick={() => { void finishWithSave(); }} disabled={busy}>
          {SAVE_AND_CONTINUE}
        </Button>
      </ModalFooter>
    </Modal>
  ) : null;


  return { registerDirtySource, guardTransition, guardDialog, isDialogOpen: pendingTransition !== null };
}

export default useDirtyTransitionGuard;
