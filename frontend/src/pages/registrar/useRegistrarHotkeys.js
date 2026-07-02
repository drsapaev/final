/**
 * Registrar Panel — keyboard shortcuts hook.
 *
 * Decomposition step: extracted from RegistrarPanel.jsx (lines 1414-1453).
 *
 * Supported shortcuts (only when not focused in input/textarea):
 * - Ctrl+P: prevent default browser print (no-op handler; reserved)
 * - Ctrl+K: open new-appointment wizard
 * - Ctrl+1: switch to welcome view (searchParams ?view=welcome)
 * - Ctrl+2: switch to 'appointments' tab
 * - Ctrl+3: switch to 'cardio' tab
 * - Ctrl+4: switch to 'derma' tab
 * - Ctrl+5: switch to queue view (searchParams ?view=queue)
 * - Escape: close wizard / slots modal if open
 *
 * Removed in QW-01 (audit): Ctrl+A, Ctrl+D, Alt+1, Alt+2, Alt+3
 * (bulk-action hotkeys — UI was unreachable after checkboxes were disabled).
 *
 * @param {Object} handlers
 * @param {Function} handlers.setShowWizard - opens wizard when called with true
 * @param {Function} handlers.setActiveTab - switches department tab
 * @param {Function} handlers.setSearchParams - updates URL search params
 * @param {boolean} handlers.showWizard - whether wizard is currently open
 * @param {boolean} handlers.showSlotsModal - whether slots modal is open
 * @param {Array} handlers.appointments - current appointments list (dep only)
 */
import { useEffect } from 'react';
import logger from '../../utils/logger';

export const useRegistrarHotkeys = ({
  setShowWizard,
  setActiveTab,
  setSearchParams,
  showWizard,
  showSlotsModal,
  appointments,
}) => {
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Debug: log all key presses
      logger.info('Key pressed:', e.key, 'Ctrl:', e.ctrlKey, 'Alt:', e.altKey, 'Target:', e.target.tagName);

      // Ignore shortcuts when user is typing in an input/textarea
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
        logger.info('Ignoring key press in input/textarea');
        return;
      }

      if (e.key === 'Enter') {
        // Enter в мастере обрабатывается отдельно в полях ввода
        // Здесь не обрабатываем, чтобы избежать конфликтов
      } else if (e.ctrlKey) {
        if (e.key === 'p') {
          e.preventDefault();
        } else if (e.key === 'k') {
          e.preventDefault();
          setShowWizard(true);
        } else if (e.key === '1') {
          e.preventDefault();
          setSearchParams({ view: 'welcome' });
        } else if (e.key === '2') {
          setActiveTab('appointments');
        } else if (e.key === '3') {
          setActiveTab('cardio');
        } else if (e.key === '4') {
          setActiveTab('derma');
        } else if (e.key === '5') {
          e.preventDefault();
          setSearchParams({ view: 'queue' });
        }
        // QW-01 fix: removed Ctrl+A (select all) and Ctrl+D (deselect)
        // hotkeys — bulk-action UI was unreachable and these only created
        // dead state. Browser native Ctrl+A (select text) now works normally.
      } else if (e.altKey) {
        // QW-01 fix: removed Alt+1/Alt+2/Alt+3 bulk-action hotkeys.
        // No bulk-action UI exists anymore; these were dead shortcuts.
      } else if (e.key === 'Escape') {
        if (showWizard) setShowWizard(false);
        if (showSlotsModal) setShowSlotsModal(false);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [showWizard, showSlotsModal, appointments, setShowWizard, setActiveTab, setSearchParams]);
};

export default useRegistrarHotkeys;
