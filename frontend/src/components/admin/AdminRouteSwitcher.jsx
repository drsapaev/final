import { useLocation, useNavigate } from 'react-router-dom';
import { ArrowLeftRight, LayoutDashboard, LineChart } from 'lucide-react';

const ROUTES = [
  {
    id: 'dashboard',
    path: '/admin',
    label: 'Обзор',
    description: 'Сводка по клинике и операционные карточки',
    icon: LayoutDashboard,
  },
  {
    id: 'analytics',
    path: '/admin/analytics',
    label: 'Аналитика',
    description: 'Подробные разрезы, KPI и прогнозы',
    icon: LineChart,
  },
];

export default function AdminRouteSwitcher({ current }) {
  const navigate = useNavigate();
  const location = useLocation();

  const activeId = current || (location.pathname.startsWith('/admin/analytics') ? 'analytics' : 'dashboard');

  return (
    <section
      style={{
        display: 'grid',
        gap: '12px',
        padding: '16px',
        borderRadius: '18px',
        border: '1px solid var(--mac-card-border)',
        background: 'linear-gradient(135deg, color-mix(in srgb, var(--mac-card-bg), white 10%) 0%, var(--mac-card-bg) 100%)',
        boxShadow: 'var(--mac-shadow-sm)',
      }}
      aria-label="Навигация между разделами админки"
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: 'var(--text-secondary)', fontSize: '13px', fontWeight: 600 }}>
        <ArrowLeftRight size={14} />
        Быстрый переход между экранами
      </div>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '10px',
        }}
      >
        {ROUTES.map((route) => {
          const Icon = route.icon;
          const isActive = activeId === route.id;

          return (
            <button
              key={route.id}
              onClick={() => navigate(route.path)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '14px 16px',
                borderRadius: '14px',
                border: '1px solid',
                borderColor: isActive ? '#2563eb' : 'var(--border-color)',
                background: isActive ? 'color-mix(in srgb, var(--mac-accent-blue), transparent 88%)' : 'var(--mac-card-bg)',
                color: 'var(--mac-text-primary)',
                cursor: 'pointer',
                textAlign: 'left',
                boxShadow: isActive ? '0 10px 20px rgba(37, 99, 235, 0.12)' : 'none',
              }}
            >
              <span
                style={{
                  width: '38px',
                  height: '38px',
                  borderRadius: '12px',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: isActive ? '#2563eb' : 'color-mix(in srgb, var(--mac-card-border), white 44%)',
                  color: isActive ? '#fff' : 'var(--text-secondary)',
                  flex: '0 0 auto',
                }}
              >
                <Icon size={18} />
              </span>
              <span style={{ display: 'grid', gap: '3px', minWidth: 0 }}>
                <span style={{ fontSize: '15px', fontWeight: 700 }}>{route.label}</span>
                <span style={{ fontSize: '12px', lineHeight: 1.4, color: 'var(--text-secondary)' }}>
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
