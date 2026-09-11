/**
 * Registrar Panel — breadcrumb wayfinding (view composition).
 *
 * PR-UI-13-5: extracted verbatim from RegistrarPanel.tsx JSX — the R-03 fix
 * breadcrumb (current view, selected department from queue profiles, search
 * query, wizard state). Pure presentation; navigation callback is delegated.
 *
 * REG-NS-1 follow-up (Codex P2): the registrar sidebar no longer renders, so
 * the shared-clinical destinations from SIDEBAR_PRESETS.registrar that are
 * not registrar-panel views (/registrar/queue, /clinical/appointments,
 * /clinical/search) keep visible, touch-reachable (44px hit area) entry
 * points in this row — rendered on every registrar route and viewport,
 * with the sidebar's own localized nav.* labels.
 */
import { Calendar, ChevronRight, Search, Users } from 'lucide-react';
;
// RQ-20 (срез RQ-20.a): the department crumb resolves its title through the
// shared helper so it always matches the worklist header and the tab button
// (the panel passes TabItem objects, whose display title is `label`).
import { resolveRegistrarTabLabel } from '../registrarHelpers';

interface RegistrarBreadcrumbProps {
  activeTab: string | null;
  // RQ-20 (срез RQ-20.a): TabItem objects carry a localized `label`; the
  // raw backend shape carries `title` — both accepted by the shared helper.
  queueProfiles: { key?: string; label?: string; title?: string }[];
  searchQuery: string;
  wizardEditMode: boolean;
  showWizard: boolean;
  /** Root-crumb click: navigate to the canonical welcome path. */
  onNavigateToWelcome: () => void;
  /** REG-NS-1: sidebar replacement — shared Appointments screen. */
  onNavigateToAppointments: () => void;
  /** REG-NS-1: sidebar replacement — online queue screen. */
  onNavigateToQueue: () => void;
  /** REG-NS-1: sidebar replacement — patient search. */
  onNavigateToPatients: () => void;
  tI18n: (key: string, options?: Record<string, unknown>) => string;
}

const RegistrarBreadcrumb = ({
  activeTab,
  queueProfiles,
  searchQuery,
  wizardEditMode,
  showWizard,
  onNavigateToWelcome,
  onNavigateToAppointments,
  onNavigateToQueue,
  onNavigateToPatients,
  tI18n,
}: RegistrarBreadcrumbProps) => (
  <nav aria-label={tI18n('registrarPanel.rp_aria_breadcrumb_nav')} className="registrar-breadcrumb-nav">
    <button
      type="button"
      onClick={onNavigateToWelcome}
      className="registrar-breadcrumb-link"
    >
      {tI18n('registrarPanel.rp_breadcrumb_root')}
    </button>
    {activeTab && (
      <>
        <ChevronRight size={16} className="registrar-breadcrumb-separator" aria-hidden="true" />
        {/* RQ-20 (срез RQ-20.a): resolve through the shared helper — the
            previous `?.title || activeTab` lookup never matched the TabItem
            objects (they carry `label`), so every backend-driven tab showed
            its raw key in the wayfinding crumb. */}
        <span>{resolveRegistrarTabLabel(activeTab, queueProfiles, (key) => tI18n('registrarPanel.' + key))}</span>
      </>
    )}
    {searchQuery && (
      <>
        <ChevronRight size={16} className="registrar-breadcrumb-separator" aria-hidden="true" />
        <span>{tI18n('registrarPanel.rp_breadcrumb_search', { query: searchQuery })}</span>
      </>
    )}
    {showWizard && (
      <>
        <ChevronRight size={16} className="registrar-breadcrumb-separator" aria-hidden="true" />
        <span>{wizardEditMode ? tI18n('registrarPanel.rp_breadcrumb_edit') : tI18n('registrarPanel.rp_breadcrumb_new')}</span>
      </>
    )}
    <span className="registrar-breadcrumb-quicklinks">
      <button
        type="button"
        className="registrar-breadcrumb-link registrar-breadcrumb-quicklink"
        onClick={onNavigateToQueue}
      >
        <Users size={14} aria-hidden="true" />
        <span>{tI18n('nav.queue')}</span>
      </button>
      <button
        type="button"
        className="registrar-breadcrumb-link registrar-breadcrumb-quicklink"
        onClick={onNavigateToAppointments}
      >
        <Calendar size={14} aria-hidden="true" />
        <span>{tI18n('nav.appointments')}</span>
      </button>
      <button
        type="button"
        className="registrar-breadcrumb-link registrar-breadcrumb-quicklink"
        onClick={onNavigateToPatients}
      >
        <Search size={14} aria-hidden="true" />
        <span>{tI18n('nav.patients')}</span>
      </button>
    </span>
  </nav>
);

export default RegistrarBreadcrumb;
