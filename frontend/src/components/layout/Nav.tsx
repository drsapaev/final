import { useEffect, useState } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import auth, { setProfile } from '../../stores/auth';
import type { AuthState } from '../../stores/auth';
import { getVisibleRoutesForShell, isInternalDemoEnabled } from '../../routing/routeSelectors';
import { useTranslation } from '../../i18n/useTranslation';

interface UserProfile {
  id?: number | null;
  full_name?: string;
  username?: string;
  role?: string;
  role_name?: string;
  specialty?: string;
  [key: string]: unknown;
}

interface RouteNavMeta {
  label?: string;
  icon?: string;
  menu?: boolean;
  sidebar?: boolean;
  order?: number;
  section?: string;
  [key: string]: unknown;
}

interface VisibleRoute {
  id: string;
  path: string;
  title: string;
  nav?: boolean | RouteNavMeta;
  [key: string]: unknown;
}

export default function Nav() {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string) => string;
  void t;
  const [state, setState] = useState<AuthState>(auth.getState());
  const navigate = useNavigate();
  const { pathname } = useLocation();

  useEffect(() => auth.subscribe(setState), []);

  const user = (state.profile || null) as UserProfile | null;
  const routes = getVisibleRoutesForShell('app-shell', user, {
    internalDemoEnabled: isInternalDemoEnabled(),
  }).filter((route: VisibleRoute) => {
    const nav = route.nav;
    if (typeof nav === 'object' && nav !== null) {
      return (nav as RouteNavMeta).menu;
    }
    return false;
  }) as VisibleRoute[];

  return (
    <div className="clinic-ops-nav-bar">
      <div style={{ fontWeight: 'var(--mac-font-weight-bold)', marginRight: 12, opacity: 0.85 }} aria-hidden="true"> </div>

      <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 6 }}>
        {routes.map((route) => {
          const navMeta = typeof route.nav === 'object' ? (route.nav as RouteNavMeta) : undefined;
          return (
            <NavLink
              key={route.id}
              to={route.path}
              style={({ isActive }) => ({
                padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
                borderRadius: 10,
                border: `1px solid ${isActive ? 'var(--mac-nav-item-active-border)' : 'var(--mac-border)'}`,
                marginRight: 6,
                textDecoration: 'none',
                background: isActive ? 'var(--mac-nav-item-active)' : 'var(--mac-bg-primary)',
                color: isActive ? 'var(--mac-nav-item-active-text)' : 'var(--mac-text-primary)',
                boxShadow: isActive ? 'var(--mac-shadow-sm)' : 'none',
              })}
              aria-current={pathname === route.path ? 'page' : undefined}
            >
              {navMeta?.label || route.title}
            </NavLink>
          );
        })}
      </div>

      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
        {user ? (
          <>
            <span style={{ opacity: 0.8 }}>
              {user.full_name || user.username || 'Пользователь'} · {user.role || user.role_name || 'staff'}
            </span>
            <button
              onClick={() => {
                auth.clearToken();
                setProfile(null);
                navigate('/login');
              }}
              className="clinic-ops-button"
            >
              Выйти
            </button>
          </>
        ) : (
          <button onClick={() => navigate('/login')} className="clinic-ops-button">
            Войти
          </button>
        )}
      </div>
    </div>
  );
}
