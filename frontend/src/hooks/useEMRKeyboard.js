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
    enabled = true,
}) {
    const handleKeyDown = useCallback((e) => {
        if (!enabled) return;

        // Ignore if typing in input/textarea (unless it's our EMR fields)
        const target = e.target;
        const isEMRField = target.id?.startsWith('emr-') ||
            target.closest?.('.emr-section');

        // Check for Ctrl/Cmd key
        const isCtrl = e.ctrlKey || e.metaKey;

        if (!isCtrl) return;

        // Ctrl+S: Save
        if (e.key === 's' || e.key === 'ы') { // 'ы' for Russian keyboard
            e.preventDefault();
            if (canSave && onSave) {
                onSave();
            }
            return;
        }

        // Ctrl+Z: Undo
        if ((e.key === 'z' || e.key === 'я') && !e.shiftKey) { // 'я' for Russian keyboard
            e.preventDefault();
            if (canUndo && onUndo) {
                onUndo();
            }
            return;
        }

        // Ctrl+Shift+Z or Ctrl+Y: Redo
        if ((e.key === 'z' || e.key === 'я') && e.shiftKey) {
            e.preventDefault();
            if (canRedo && onRedo) {
                onRedo();
            }
            return;
        }

        if (e.key === 'y' || e.key === 'н') { // 'н' for Russian keyboard
            e.preventDefault();
            if (canRedo && onRedo) {
                onRedo();
            }
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
            { key: 'Ctrl+Enter', action: 'Подписать', available: canSign },
        ].filter(s => s.available),
    };
}

export default useEMRKeyboard;
