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
 */
import { useEffect } from 'react';
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
}) => {
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Ignore shortcuts when user is typing in an input/textarea
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
        return;
      }

      const isCtrl = e.ctrlKey || e.metaKey;

      // Tab switching: Ctrl+1 through Ctrl+3
      if (isCtrl && ['1', '2', '3'].includes(e.key)) {
        e.preventDefault();
        const tab = LAB_TAB_MAP[e.key];
        if (tab && switchTab) {
          switchTab(tab);
          logger.info(`[LabHotkeys] Switched to tab: ${tab}`);
        }
        return;
      }

      // F5: refresh data
      if (e.key === 'F5') {
        e.preventDefault();
        if (refreshData) {
          refreshData();
          logger.info('[LabHotkeys] Data refreshed');
        }
        return;
      }

      // Escape: clear selection AND switch to queue tab
      // PR-60 / High-11: was only clearing selection, leaving user on Reports tab with empty state
      if (e.key === 'Escape') {
        if (clearSelection) {
          clearSelection();
        }
        if (switchTab) {
          switchTab('queue');
        }
        return;
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [switchTab, refreshData, clearSelection]);
};
