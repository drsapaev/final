import type { CSSProperties } from "react";

import { useTranslation } from '../../i18n/useTranslation';
import { useLocation, useNavigate } from 'react-router-dom';
import { ArrowLeftRight, LayoutDashboard, LineChart } from 'lucide-react';
import { getCanonicalRouteById, getEffectiveRouteByPath } from '../../routing/routeSelectors';

const SWITCHER_ROUTE_IDS = ['admin-dashboard', 'admin-analytics'];

const getRoutePresentation = (t) => ({
  'admin-dashboard': {
    description: t('admin2.ars_desc_dashboard'),
    icon: LayoutDashboard,
  },
  'admin-analytics': {
    description: t('admin2.ars_desc_analytics'),
    icon: LineChart,
  },
});

const buildSwitcherRoutes = (t) => SWITCHER_ROUTE_IDS
  .map((routeId) => {
    const route = getCanonicalRouteById(routeId);
    const presentation = getRoutePresentation(t)[routeId];

    if (!route || !presentation) {
      return null;
    }

    return {
      id: route.id,
      path: route.path,
      label: ((typeof route.nav === "object" && route.nav ? route.nav : null) as { label?: string } | null)?.label || route.title,
      description: presentation.description,
      icon: presentation.icon,
    };
  })
  .filter(Boolean);

const switcherStyle = {
  display: 'grid',
  gap: 'var(--mac-spacing-3)',
  padding: 'var(--mac-spacing-4)',
  borderRadius: 'var(--mac-radius-xl)',
  border: '1px solid var(--mac-card-border)',
  background: 'linear-gradient(135deg, color-mix(in srgb, var(--mac-card-bg), white 10%) 0%, var(--mac-card-bg) 100%)',
  boxShadow: 'var(--mac-shadow-sm)',
  // UX Audit Stage 3 (Dashboard issue 4.2): sticky position.
  // Раньше switcher пропадал при прокрутке вниз — теперь остаётся видимым.
  position: 'sticky',
  top: 'var(--mac-spacing-3)',
  zIndex: 10,
};

const switcherLabelStyle = {
  display: 'flex',
  alignItems: 'center',
  gap: 'var(--mac-spacing-2)',
  color: 'var(--mac-text-secondary)',
  fontSize: 'var(--mac-font-size-sm)',
  fontWeight: 'var(--mac-font-weight-semibold)',
};

const routeGridStyle = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
  gap: 'var(--mac-spacing-2)',
};

const routeTextStyle = {
  display: 'grid',
  gap: '3px',
  minWidth: 0,
};

const routeTitleStyle = {
  fontSize: 'var(--mac-font-size-base)',
  fontWeight: 'var(--mac-font-weight-bold)',
};

const routeDescriptionStyle = {
  fontSize: 'var(--mac-font-size-xs)',
  lineHeight: 1.4,
  color: 'var(--mac-text-secondary)',
};

const getRouteButtonStyle = (isActive) => ({
  display: 'flex',
  alignItems: 'center',
  gap: 'var(--mac-spacing-3)',
  padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
  borderRadius: 'var(--mac-radius-lg)',
  border: '1px solid',
  borderColor: isActive ? 'var(--mac-accent-blue)' : 'var(--mac-card-border)',
  background: isActive ? 'color-mix(in srgb, var(--mac-accent-blue), transparent 88%)' : 'var(--mac-card-bg)',
  color: 'var(--mac-text-primary)',
  cursor: 'pointer',
  textAlign: 'left',
  boxShadow: isActive ? 'var(--mac-shadow-md)' : 'var(--mac-shadow-sm)',
});

const getRouteIconStyle = (isActive) => ({
  width: '38px',
  height: '38px',
  borderRadius: 'var(--mac-radius-md)',
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: isActive ? 'var(--mac-accent-blue)' : 'color-mix(in srgb, var(--mac-card-border), white 44%)',
  color: isActive ? 'var(--mac-text-on-accent, white)' : 'var(--mac-text-secondary)',
  flex: '0 0 auto',
});

interface AdminRouteSwitcherProps {
  /** Optional override for the active route id; if omitted, derived from location. */
  current?: string;
}

export default function AdminRouteSwitcher({ current }: AdminRouteSwitcherProps = {}) {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const navigate = useNavigate();
  const location = useLocation();

  const currentRoute = getEffectiveRouteByPath(location.pathname);
  const activeId = current ?? (SWITCHER_ROUTE_IDS.includes(currentRoute?.id) ? currentRoute.id : 'admin-dashboard');
  const switcherRoutes = buildSwitcherRoutes(t);

  return (
    <section
      style={switcherStyle as CSSProperties}
      aria-label={t('admin2.ars_aria')}
    >
      <div style={switcherLabelStyle as CSSProperties}>
        <ArrowLeftRight size={14} aria-hidden="true" />
        {/* UX Audit Admin #2.1: переименовано для соответствия фактическому функционалу (только 2 маршрута). */}
        {t('admin2.ars_title')}
      </div>
      <div style={routeGridStyle as CSSProperties}>
        {switcherRoutes.map((route) => {
          const Icon = route.icon;
          const isActive = activeId === route.id;

          return (
            <button
              key={route.id}
              type="button"
              onClick={() => navigate(route.path)}
              style={getRouteButtonStyle(isActive) as CSSProperties}
              aria-current={isActive ? 'page' : undefined}
            >
              <span style={getRouteIconStyle(isActive) as CSSProperties}>
                <Icon size={18} aria-hidden="true" />
              </span>
              <span style={routeTextStyle}>
                <span style={routeTitleStyle}>{route.label}</span>
                <span style={routeDescriptionStyle}>
                  {route.description}
                </span>
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
