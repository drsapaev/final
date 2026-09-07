/**
 * useWizardSafeClose — Fix F (wizard search & safe close).
 *
 * Extracted from AppointmentWizardV2 (PR-45 LOC ceiling discipline).
 *
 * Dirty-aware close for the registration wizard: an explicit close of a
 * filled form must not silently destroy typed input, so a confirmation is
 * shown first. While a save is in flight, closing is blocked entirely so
 * the UI never implies a cancellation of a still-running request.
 *
 * The hook is transport-agnostic: the wizard wires it to the header X
 * buttons and its own Escape handling.
 */
import { useCallback, useRef } from 'react';
import { toast } from 'react-toastify';

interface UseWizardSafeCloseOptions {
  /** True while the wizard submit request is in flight. */
  isProcessing: boolean;
  /** True when the form holds any user-entered data. */
  hasContent: boolean;
  /** Confirmation dialog from the shared useConfirm hook. */
  confirm: (options: Record<string, unknown>) => Promise<boolean>;
  /** i18n translate function. */
  t: (key: string, options?: Record<string, unknown>) => string;
  /** Wizard close callback (parent-owned visibility state). */
  onClose?: () => void;
}

export function useWizardSafeClose({
  isProcessing,
  hasContent,
  confirm,
  t,
  onClose,
}: UseWizardSafeCloseOptions) {
  // Mirrors keep the stable requestClose callback free of stale closures.
  const isProcessingRef = useRef(isProcessing);
  isProcessingRef.current = isProcessing;
  const hasContentRef = useRef(hasContent);
  hasContentRef.current = hasContent;
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  const requestClose = useCallback(async () => {
    if (isProcessingRef.current) {
      // Never fake a cancellation while the save request is still running.
      toast.info(t('misc.aw_save_in_progress'));
      return;
    }
    if (hasContentRef.current) {
      const confirmed = await confirm({
        title: t('misc.aw_close_unsaved_title'),
        message: t('misc.aw_close_unsaved_message'),
        confirmLabel: t('misc.aw_close_unsaved_confirm'),
        cancelLabel: t('misc.cancel'),
        intent: 'danger',
      });
      if (!confirmed) return;
    }
    onCloseRef.current?.();
  }, [confirm, t]);

  const requestCloseRef = useRef<() => void>(() => {});
  requestCloseRef.current = () => void requestClose();

  return requestCloseRef;
}

export default useWizardSafeClose;
