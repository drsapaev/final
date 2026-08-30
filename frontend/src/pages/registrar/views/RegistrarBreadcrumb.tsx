/**
 * Registrar Panel — breadcrumb wayfinding (view composition).
 *
 * PR-UI-13-5: extracted verbatim from RegistrarPanel.tsx JSX — the R-03 fix
 * breadcrumb (current view, selected department from queue profiles, search
 * query, wizard state). Pure presentation; navigation callback is delegated.
 */
import { Icon } from '../../../components/ui/macos';

interface RegistrarBreadcrumbProps {
  activeTab: string | null;
  queueProfiles: { key?: string; title?: string }[];
  searchQuery: string;
  wizardEditMode: boolean;
  showWizard: boolean;
  /** Root-crumb click: navigate to the canonical welcome path. */
  onNavigateToWelcome: () => void;
  tI18n: (key: string, options?: Record<string, unknown>) => string;
}

const RegistrarBreadcrumb = ({
  activeTab,
  queueProfiles,
  searchQuery,
  wizardEditMode,
  showWizard,
  onNavigateToWelcome,
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
        <Icon name="chevron.right" size="small" className="registrar-breadcrumb-separator" aria-hidden="true" />
        <span>{queueProfiles.find(p => p.key === activeTab)?.title || activeTab}</span>
      </>
    )}
    {searchQuery && (
      <>
        <Icon name="chevron.right" size="small" className="registrar-breadcrumb-separator" aria-hidden="true" />
        <span>{tI18n('registrarPanel.rp_breadcrumb_search', { query: searchQuery })}</span>
      </>
    )}
    {showWizard && (
      <>
        <Icon name="chevron.right" size="small" className="registrar-breadcrumb-separator" aria-hidden="true" />
        <span>{wizardEditMode ? tI18n('registrarPanel.rp_breadcrumb_edit') : tI18n('registrarPanel.rp_breadcrumb_new')}</span>
      </>
    )}
  </nav>
);

export default RegistrarBreadcrumb;
