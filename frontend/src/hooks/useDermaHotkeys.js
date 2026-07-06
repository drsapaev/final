/**
 * useDermaHotkeys — keyboard shortcuts for DermatologistPanelUnified.
 *
 * Supported shortcuts (only when not focused in input/textarea):
 * - Ctrl+1: switch to queue tab
 * - Ctrl+2: switch to visit tab
 * - Ctrl+3: switch to patients tab
 * - Ctrl+4: switch to ai tab
 * - F5: refresh data
 * - Escape: clear selected patient
 */
import { useEffect } from 'react';
import logger from '../utils/logger';

const DERMA_TAB_MAP = {
  '1': 'queue',
  '2': 'visit',
  '3': 'patients',
  '4': 'ai',
};

export const useDermaHotkeys = ({
  handleTabChange,
  refreshData,
  clearSelection,
}) => {
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
        return;
      }

      const isCtrl = e.ctrlKey || e.metaKey;

      if (isCtrl && ['1', '2', '3', '4'].includes(e.key)) {
        e.preventDefault();
        const tab = DERMA_TAB_MAP[e.key];
        if (tab && handleTabChange) {
          handleTabChange(tab);
          logger.info(`[DermaHotkeys] Switched to tab: ${tab}`);
        }
        return;
      }

      if (e.key === 'F5') {
        e.preventDefault();
        if (refreshData) {
          refreshData();
          logger.info('[DermaHotkeys] Data refreshed');
        }
        return;
      }

      if (e.key === 'Escape') {
        if (clearSelection) {
          clearSelection();
        }
        return;
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [handleTabChange, refreshData, clearSelection]);
};
