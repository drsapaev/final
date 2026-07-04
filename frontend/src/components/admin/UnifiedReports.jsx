import ReportsManager from './ReportsManager';
import ErrorBoundary from '../common/ErrorBoundary';

// IA PR-3: UnifiedReports consolidated — was 2 tabs (manager + generator).
// ReportGenerator removed (its richer form was never wired with props; the
// basic generate tab in ReportsManager covers the same workflow). ReportsManager
// already has 3 internal tabs (generate / files / settings) — no need for an
// outer tab wrapper.
const UnifiedReports = () => (
  <div className="admin-unified-root-no-color">
    <ErrorBoundary>
      <ReportsManager />
    </ErrorBoundary>
  </div>
);

export default UnifiedReports;
