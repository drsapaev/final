import { Activity, Brain, Calendar, FileText, User, Users } from 'lucide-react';

import { Badge } from '../../../components/ui/macos';
import type { TranslateFn } from '../doctorStatus';
import type { DoctorStyles } from '../useDoctorStyles';

/**
 * PR-UI-15-2: the tab navigation row extracted verbatim from
 * pages/DoctorPanel.tsx (registrar/cashier decomposition precedent).
 * Includes the inactive-tab hover helper (verbatim).
 */
export default function DoctorTabsNav({
  activeTab,
  setDoctorTab,
  queueStatsWaiting,
  styles,
  t,
}: {
  activeTab: string;
  setDoctorTab: (tabId: string) => void;
  queueStatsWaiting: number | string | null | undefined;
  styles: DoctorStyles;
  t: TranslateFn;
}) {
  const { isMobile, tabsStyle, tabStyle, activeTabStyle, interactiveSurface, interactiveSurfaceHover } = styles;

  const handleInactiveTabHover = (event: React.MouseEvent<HTMLElement>, isActive: boolean, hovered: boolean) => {
    if (isActive) {
      return;
    }

    event.currentTarget.style.background = hovered ? interactiveSurfaceHover : interactiveSurface;
    event.currentTarget.style.transform = hovered ? 'translateY(-1px)' : 'translateY(0)';
  };

  return (
    <div style={tabsStyle}>
      <button
        aria-label={t("doctor.aria_open_tab", { name: t("doctor.tab_dashboard") })}
        style={activeTab === 'dashboard' ? activeTabStyle : tabStyle}
        onClick={() => setDoctorTab('dashboard')}
        onMouseEnter={(e: React.MouseEvent<HTMLElement>) => handleInactiveTabHover(e, activeTab === 'dashboard', true)}
        onMouseLeave={(e: React.MouseEvent<HTMLElement>) => handleInactiveTabHover(e, activeTab === 'dashboard', false)}>

        <Activity size={isMobile ? 16 : 20} />
        {!isMobile && <span>{t("doctor.tab_dashboard")}</span>}
      </button>

      <button
        aria-label={t("doctor.aria_open_tab", { name: t("doctor.tab_patients") })}
        style={activeTab === 'patients' ? activeTabStyle : tabStyle}
        onClick={() => setDoctorTab('patients')}
        onMouseEnter={(e: React.MouseEvent<HTMLElement>) => handleInactiveTabHover(e, activeTab === 'patients', true)}
        onMouseLeave={(e: React.MouseEvent<HTMLElement>) => handleInactiveTabHover(e, activeTab === 'patients', false)}>

        <User size={isMobile ? 16 : 20} />
        {!isMobile && <span>{t("doctor.tab_patients")}</span>}
      </button>

      <button
        aria-label={t("doctor.aria_open_tab", { name: t("doctor.tab_appointments") })}
        style={activeTab === 'appointments' ? activeTabStyle : tabStyle}
        onClick={() => setDoctorTab('appointments')}
        onMouseEnter={(e: React.MouseEvent<HTMLElement>) => handleInactiveTabHover(e, activeTab === 'appointments', true)}
        onMouseLeave={(e: React.MouseEvent<HTMLElement>) => handleInactiveTabHover(e, activeTab === 'appointments', false)}>

        <Calendar size={isMobile ? 16 : 20} />
        {!isMobile && <span>{t("doctor.tab_appointments")}</span>}
      </button>

      {/* ✅ НОВОЕ: Таб очереди */}
      <button
        aria-label={t("doctor.aria_open_tab", { name: t("doctor.tab_queue") })}
        style={activeTab === 'queue' ? activeTabStyle : tabStyle}
        onClick={() => setDoctorTab('queue')}
        onMouseEnter={(e: React.MouseEvent<HTMLElement>) => handleInactiveTabHover(e, activeTab === 'queue', true)}
        onMouseLeave={(e: React.MouseEvent<HTMLElement>) => handleInactiveTabHover(e, activeTab === 'queue', false)}>

        <Users size={isMobile ? 16 : 20} />
        {!isMobile && <span>{t("doctor.tab_queue")}</span>}
        {Number(queueStatsWaiting ?? 0) > 0 &&
        <Badge variant="warning" className="doctor-badge-ml">
            {queueStatsWaiting}
          </Badge>
        }
      </button>

      <button
        aria-label={t("doctor.aria_open_tab", { name: t("doctor.tab_ai") })}
        style={activeTab === 'ai' ? activeTabStyle : tabStyle}
        onClick={() => setDoctorTab('ai')}
        onMouseEnter={(e: React.MouseEvent<HTMLElement>) => handleInactiveTabHover(e, activeTab === 'ai', true)}
        onMouseLeave={(e: React.MouseEvent<HTMLElement>) => handleInactiveTabHover(e, activeTab === 'ai', false)}>

        <Brain size={isMobile ? 16 : 20} />
        {!isMobile && <span>AI Помощник</span>}
      </button>

      <button
        aria-label={t("doctor.aria_open_tab", { name: t("doctor.tab_reports") })}
        style={activeTab === 'reports' ? activeTabStyle : tabStyle}
        onClick={() => setDoctorTab('reports')}
        onMouseEnter={(e: React.MouseEvent<HTMLElement>) => handleInactiveTabHover(e, activeTab === 'reports', true)}
        onMouseLeave={(e: React.MouseEvent<HTMLElement>) => handleInactiveTabHover(e, activeTab === 'reports', false)}>

        <FileText size={isMobile ? 16 : 20} />
        {!isMobile && <span>{t("doctor.tab_reports")}</span>}
      </button>
    </div>
  );
}
