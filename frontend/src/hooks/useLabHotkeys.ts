/**
 * useLabHotkeys — keyboard shortcuts for LabPanel.
 *
 * H-2 fix: previously LabPanel had no panel-level hotkeys (only a narrow
 * Ctrl+S inside LabReportWorkbench). Peer panels (CardiologistPanel,
 * RegistrarPanel) all have dedicated hotkey hooks.
 *
 * Supported shortcuts (only when not focused in input/textarea):
 * - Ctrl+1: switch to queue tab
 * - Ctrl+2: switch to templates tab
 * - Ctrl+3: switch to reports tab
 * - F5: refresh queue data
 * - Escape: clear selected appointment / close report editor
 *
 * @param {Object} handlers
 * @param {Function} handlers.switchTab - switches tab (updates URL)
 * @param {Function} handlers.refreshData - reloads queue
 * @param {Function} handlers.clearSelection - clears selectedAppointment
 * @param {boolean} handlers.disabled - suspends panel shortcuts while a modal owns keyboard input
 */
import { useEffect, useRef } from 'react';
import logger from '../utils/logger';

const LAB_TAB_MAP = {
  '1': 'queue',
  '2': 'templates',
  '3': 'reports',
};

export const useLabHotkeys = ({
  switchTab,
  refreshData,
  clearSelection,
  disabled = false,
}: {
  switchTab?: (tab: string) => void;
  refreshData?: () => void;
  clearSelection?: () => void;
  disabled?: boolean;
}) => {
  // Keep one document listener and read the current render synchronously.
  // A modal can become visible before an effect cleanup/rebind runs; a stale
  // listener must not handle the same Escape that the modal owns.
  const handlersRef = useRef({ switchTab, refreshData, clearSelection, disabled });
  handlersRef.current = { switchTab, refreshData, clearSelection, disabled };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.defaultPrevented) return;
      const {
        switchTab: currentSwitchTab,
        refreshData: currentRefreshData,
        clearSelection: currentClearSelection,
        disabled: currentDisabled,
      } = handlersRef.current;
      // Dialogs own Escape and every other shortcut while they are open.
      // Checking the DOM also covers nested confirm dialogs whose state is
      // local to report/template workbenches and not exposed to LabPanel.
      if (currentDisabled || document.querySelector('[role="dialog"]')) return;
      // Ignore shortcuts when user is typing in an input/textarea
      const target = e.target as HTMLElement;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') {
        return;
      }

      const isCtrl = e.ctrlKey || e.metaKey;

      // Tab switching: Ctrl+1 through Ctrl+3
      if (isCtrl && ['1', '2', '3'].includes(e.key)) {
        e.preventDefault();
        const tab = LAB_TAB_MAP[e.key as keyof typeof LAB_TAB_MAP];
        if (tab && currentSwitchTab) {
          currentSwitchTab(tab);
          logger.info(`[LabHotkeys] Switched to tab: ${tab}`);
        }
        return;
      }

      // F5: refresh data
      if (e.key === 'F5') {
        e.preventDefault();
        if (currentRefreshData) {
          currentRefreshData();
          logger.info('[LabHotkeys] Data refreshed');
        }
        return;
      }

      // Escape is one caller-owned transition. The caller decides which
      // context and tab are cleared so a dirty guard can keep it atomic.
      if (e.key === 'Escape') {
        if (currentClearSelection) {
          currentClearSelection();
        }
        return;
      }
    };

    // Capture runs before Modal's document-level bubble listener can close and
    // unmount the dialog during the same native Escape event.
    document.addEventListener('keydown', handleKeyDown, true);
    return () => {
      document.removeEventListener('keydown', handleKeyDown, true);
    };
  }, []);
};
