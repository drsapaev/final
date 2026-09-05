/**
 * Registrar Panel — breadcrumb wayfinding (view composition).
 *
 * PR-UI-13-5: extracted verbatim from RegistrarPanel.tsx JSX — the R-03 fix
 * breadcrumb (current view, selected department from queue profiles, search
 * query, wizard state). Pure presentation; navigation callback is delegated.
 *
 * REG-NS-1 follow-up (Codex P2): the registrar sidebar no longer renders, so
 * the two shared-clinical destinations from SIDEBAR_PRESETS.registrar that are
 * not registrar-panel views (/clinical/appointments, /clinical/search) keep a
 * visible, touch-reachable entry point in this row — rendered on every
 * registrar route and viewport.
 */
import { Calendar, ChevronRight, Search } from 'lucide-react';
;

interface RegistrarBreadcrumbProps {
  activeTab: string | null;
  queueProfiles: { key?: string; title?: string }[];
  searchQuery: string;
  wizardEditMode: boolean;
  showWizard: boolean;
  /** Root-crumb click: navigate to the canonical welcome path. */
  onNavigateToWelcome: () => void;
  /** REG-NS-1: sidebar replacement — shared Appointments screen. */
  onNavigateToAppointments: () => void;
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
        <span>{queueProfiles.find(p => p.key === activeTab)?.title || activeTab}</span>
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
        className="registrar-breadcrumb-quicklink"
        onClick={onNavigateToAppointments}
      >
        <Calendar size={14} aria-hidden="true" />
        <span>{tI18n('nav.appointments')}</span>
      </button>
      <button
        type="button"
        className="registrar-breadcrumb-quicklink"
        onClick={onNavigateToPatients}
      >
        <Search size={14} aria-hidden="true" />
        <span>{tI18n('nav.patients')}</span>
      </button>
    </span>
  </nav>
);

export default RegistrarBreadcrumb;
