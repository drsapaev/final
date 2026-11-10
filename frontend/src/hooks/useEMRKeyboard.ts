/**
 * useEMRKeyboard - Keyboard shortcuts for EMR v2
 * 
 * Shortcuts:
 * - Ctrl+S: Force save
 * - Ctrl+Z: Undo
 * - Ctrl+Shift+Z / Ctrl+Y: Redo
 * - Ctrl+Enter: Sign (with confirmation)
 */

import { useEffect, useCallback } from 'react';

/**
 * useEMRKeyboard Hook
 * 
 * @param {Object} options
 * @param {Function} options.onSave - Save callback
 * @param {Function} options.onUndo - Undo callback
 * @param {Function} options.onRedo - Redo callback
 * @param {Function} options.onSign - Sign callback (optional)
 * @param {boolean} options.canUndo - Can perform undo
 * @param {boolean} options.canRedo - Can perform redo
 * @param {boolean} options.canSave - Can perform save
 * @param {boolean} options.canSign - Can perform sign
 * @param {boolean} options.enabled - Enable shortcuts (default: true)
 */
export function useEMRKeyboard({
  onSave,
  onUndo,
  onRedo,
  onSign,
  canUndo = true,
  canRedo = true,
  canSave = true,
  canSign = false,
  enabled = true
}: {
  onSave?: () => void;
  onUndo?: () => void;
  onRedo?: () => void;
  onSign?: () => void;
  canUndo?: boolean;
  canRedo?: boolean;
  canSave?: boolean;
  canSign?: boolean;
  enabled?: boolean;
}) {
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (!enabled) return;

    // EMRKEY-FE-001 (audit 3886, round 30): Ctrl+Z / Ctrl+Shift+Z / Ctrl+Y are
    // the NATIVE per-field text-editing undo/redo inside any editable control.
    // The document-wide reducer history must never hijack them: a doctor
    // pressing Ctrl+Z in a diagnosis textarea expects the last typed word to
    // disappear, not the whole EMR state to rewind to an earlier snapshot
    // (which silently rolls back unrelated clinical fields). Whole-document
    // undo/redo therefore stays available ONLY when the focus is outside
    // editable controls — plus through the explicit toolbar buttons, which
    // call onUndo/onRedo directly regardless of focus.
    const target = e.target as HTMLElement;
    const isTypingInInput = target.tagName === 'INPUT' ||
      target.tagName === 'TEXTAREA' ||
      target.tagName === 'SELECT' ||
      target.isContentEditable;

    // Check for Ctrl/Cmd key
    const isCtrl = e.ctrlKey || e.metaKey;

    const isUndoKey = isCtrl && (e.key === 'z' || e.key === 'я') && !e.shiftKey; // 'я' for Russian keyboard
    const isRedoKey = isCtrl && (((e.key === 'z' || e.key === 'я') && e.shiftKey) || e.key === 'y' || e.key === 'н'); // 'н' for Russian keyboard

    if (isTypingInInput && (isUndoKey || isRedoKey)) {
      // Native per-field undo/redo stays untouched inside text inputs —
      // no preventDefault, no reducer dispatch, even inside .emr-section.
      return;
    }

    // QW-2 (UX audit): Ignore hotkeys when typing in input/textarea/select/contenteditable.
    // The previous code had `void (target.id?.startsWith('emr-') || target.closest?.('.emr-section'))`
    // which was a no-op — it computed the expression but discarded the result. The check never
    // actually prevented hotkeys from firing inside form fields.
    // Now we properly skip hotkeys when the user is typing in ANY input field, UNLESS the target
    // is inside an EMR section (where Ctrl+S/Enter still work for EMR autosave/sign; undo/redo
    // keys are always left to the browser inside text inputs — EMRKEY-FE-001 above).
    const isInsideEMR = target.closest?.('.emr-section') ||
      target.id?.startsWith('emr-') ||
      target.closest?.('[data-emr-field]');

    if (isTypingInInput && !isInsideEMR) {
      return; // Don't intercept hotkeys in non-EMR form fields
    }

    if (!isCtrl) return;

    // Ctrl+S: Save
    if (e.key === 's' || e.key === 'ы') {// 'ы' for Russian keyboard
      e.preventDefault();
      if (canSave && onSave) {
        onSave();
      }
      return;
    }

    // Ctrl+Z: Undo — document-wide reducer history, only when the focus is
    // OUTSIDE editable controls (handled above). EMRKEY-FE-001: preventDefault
    // only when the action is actually available — an unavailable action must
    // not swallow the event.
    if ((e.key === 'z' || e.key === 'я') && !e.shiftKey) {// 'я' for Russian keyboard
      if (!canUndo || !onUndo) return;
      e.preventDefault();
      onUndo();
      return;
    }

    // Ctrl+Shift+Z or Ctrl+Y: Redo
    if ((e.key === 'z' || e.key === 'я') && e.shiftKey) {// 'я' for Russian keyboard
      if (!canRedo || !onRedo) return;
      e.preventDefault();
      onRedo();
      return;
    }

    if (e.key === 'y' || e.key === 'н') {// 'н' for Russian keyboard
      if (!canRedo || !onRedo) return;
      e.preventDefault();
      onRedo();
      return;
    }

    // Ctrl+Enter: Sign (with confirmation)
    if (e.key === 'Enter' && canSign && onSign) {
      e.preventDefault();
      onSign();
      return;
    }
  }, [enabled, onSave, onUndo, onRedo, onSign, canUndo, canRedo, canSave, canSign]);

  useEffect(() => {
    if (!enabled) return;

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [enabled, handleKeyDown]);

  // Return info about available shortcuts (for UI hints)
  return {
    shortcuts: [
    { key: 'Ctrl+S', action: 'Сохранить', available: canSave },
    { key: 'Ctrl+Z', action: 'Отменить', available: canUndo },
    { key: 'Ctrl+Shift+Z', action: 'Повторить', available: canRedo },
    { key: 'Ctrl+Enter', action: 'Подписать', available: canSign }].
    filter((s) => s.available)
  };
}

export default useEMRKeyboard;