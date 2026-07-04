import { useLocation, useNavigate } from 'react-router-dom';
import { ArrowLeftRight, LayoutDashboard, LineChart } from 'lucide-react';
import { getCanonicalRouteById, getEffectiveRouteByPath } from '../../routing/routeSelectors.js';

const SWITCHER_ROUTE_IDS = ['admin-dashboard', 'admin-analytics'];

const ROUTE_PRESENTATION_BY_ID = {
  'admin-dashboard': {
    description: 'Сводка по клинике и операционные карточки',
    icon: LayoutDashboard,
  },
  'admin-analytics': {
    description: 'Подробные разрезы, KPI и прогнозы',
    icon: LineChart,
  },
};

const switcherRoutes = SWITCHER_ROUTE_IDS
  .map((routeId) => {
    const route = getCanonicalRouteById(routeId);
    const presentation = ROUTE_PRESENTATION_BY_ID[routeId];

    if (!route || !presentation) {
      return null;
    }

    return {
      id: route.id,
      path: route.path,
      label: route.nav?.label || route.title,
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

export default function AdminRouteSwitcher() {
  const navigate = useNavigate();
  const location = useLocation();

  const currentRoute = getEffectiveRouteByPath(location.pathname);
  const activeId = SWITCHER_ROUTE_IDS.includes(currentRoute?.id) ? currentRoute.id : 'admin-dashboard';

  return (
    <section
      style={switcherStyle}
      aria-label="Навигация между разделами админки"
    >
      <div style={switcherLabelStyle}>
        <ArrowLeftRight size={14} aria-hidden="true" />
        Быстрый переход между экранами
      </div>
      <div style={routeGridStyle}>
        {switcherRoutes.map((route) => {
          const Icon = route.icon;
          const isActive = activeId === route.id;

          return (
            <button
              key={route.id}
              type="button"
              onClick={() => navigate(route.path)}
              style={getRouteButtonStyle(isActive)}
              aria-current={isActive ? 'page' : undefined}
            >
              <span style={getRouteIconStyle(isActive)}>
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
