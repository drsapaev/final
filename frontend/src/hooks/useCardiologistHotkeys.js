/**
 * useCardiologistHotkeys — keyboard shortcuts for CardiologistPanelUnified.
 *
 * H-8 fix: previously the cardiologist panel had zero keyboard shortcuts,
 * while RegistrarPanel had useRegistrarHotkeys (Ctrl+K, Ctrl+1-5, Esc).
 * A doctor doing 30+ visits/day cannot tab-switch / call-next /
 * complete-visit without leaving the keyboard.
 *
 * Supported shortcuts (only when not focused in input/textarea):
 * - Ctrl+1: switch to queue tab
 * - Ctrl+2: switch to appointments tab
 * - Ctrl+3: switch to visit tab
 * - Ctrl+4: switch to ecg tab
 * - Ctrl+5: switch to blood tab
 * - F5: refresh data (reload appointments)
 * - Escape: close any open modal
 *
 * @param {Object} handlers
 * @param {Function} handlers.setActiveTab - switches tab
 * @param {Function} handlers.refreshData - reloads appointments/queue
 * @param {Function} handlers.closeModal - closes any open modal
 */
import { useEffect } from 'react';
import logger from '../utils/logger';

export const useCardiologistHotkeys = ({
  setActiveTab,
  refreshData,
  closeModal,
}) => {
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Ignore shortcuts when user is typing in an input/textarea
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
        return;
      }

      const isCtrl = e.ctrlKey || e.metaKey;

      // Tab switching: Ctrl+1 through Ctrl+5
      if (isCtrl && ['1', '2', '3', '4', '5'].includes(e.key)) {
        e.preventDefault();
        const tabMap = {
          '1': 'queue',
          '2': 'appointments',
          '3': 'visit',
          '4': 'ecg',
          '5': 'blood',
        };
        const tab = tabMap[e.key];
        if (tab && setActiveTab) {
          setActiveTab(tab);
          logger.info(`[CardiologistHotkeys] Switched to tab: ${tab}`);
        }
        return;
      }

      // F5: refresh data
      if (e.key === 'F5') {
        e.preventDefault();
        if (refreshData) {
          refreshData();
          logger.info('[CardiologistHotkeys] Data refreshed');
        }
        return;
      }

      // Escape: close modal
      if (e.key === 'Escape') {
        if (closeModal) {
          closeModal();
        }
        return;
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [setActiveTab, refreshData, closeModal]);
};
