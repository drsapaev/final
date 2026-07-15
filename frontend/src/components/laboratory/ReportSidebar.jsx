import PropTypes from 'prop-types';
// STRAT#25: ReportSidebar — extracted from LabReportWorkbench.
// Объединяет LabReportHistoryPanel и LabReportAIAnalysis в одном
// sidebar-компоненте. Ранее оба рендерились inline в разных местах
// LabReportWorkbench (AI — внутри editor card, History — после card).
// Теперь sidebar — единая точка для supplementary content.
import LabReportHistoryPanel from './LabReportHistoryPanel';
import LabReportAIAnalysis from './LabReportAIAnalysis';
import { useTranslation } from '../../i18n/adapter';

/**
 * STRAT#25: ReportSidebar — supplementary content panel for lab report workbench.
 *
 * Renders two sub-components:
 *   1. LabReportAIAnalysis — AI interpretation button + dialog (shown when
 *      there's an active instance with results)
 *   2. LabReportHistoryPanel — recent reports browser or per-patient history
 *      (shown when there are recent reports or a selected appointment)
 *
 * Previously these were rendered inline in different locations within
 * LabReportWorkbench. Now they're grouped into a sidebar for clearer
 * separation of editor vs supplementary content.
 *
 * Props:
 *   - activeInstance: current LabReportInstance (for AI analysis)
 *   - notify: parent notify callback (for AI error messages)
 *   - showRecentReportsBrowser: boolean — whether to show recent reports mode
 *   - recentReports: array of recent LabReportInstance summaries
 *   - reportHistory: array of per-patient report history
 *   - historySeverityFilter: current severity filter ('all'|'clean'|'flagged'|'critical')
 *   - onSeverityFilterChange: (filter) => void
 *   - onOpenInstance: (instanceId) => void
 */
export default function ReportSidebar({
  activeInstance,
  notify,
  showRecentReportsBrowser,
  recentReports,
  reportHistory,
  historySeverityFilter,
  onSeverityFilterChange,
  onOpenInstance,
}) {
  const showHistory = showRecentReportsBrowser || reportHistory.length > 0;
  const showAI = Boolean(activeInstance);

  if (!showHistory && !showAI) {
    return null;
  }

  return (
    <>
      {showAI && (
        <LabReportAIAnalysis
          activeInstance={activeInstance}
          notify={notify}
        />
      )}
      {showHistory && (
        <LabReportHistoryPanel
          showRecentReportsBrowser={showRecentReportsBrowser}
          recentReports={recentReports}
          reportHistory={reportHistory}
          historySeverityFilter={historySeverityFilter}
          onSeverityFilterChange={onSeverityFilterChange}
          activeInstanceId={activeInstance?.id}
          onOpenInstance={onOpenInstance}
        />
      )}
    </>
  );
}

ReportSidebar.propTypes = {
  activeInstance: PropTypes.object,
  notify: PropTypes.func,
  showRecentReportsBrowser: PropTypes.bool,
  recentReports: PropTypes.array,
  reportHistory: PropTypes.array,
  historySeverityFilter: PropTypes.string,
  onSeverityFilterChange: PropTypes.func,
  onOpenInstance: PropTypes.func,
};
