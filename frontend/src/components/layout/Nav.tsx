// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { useEffect, useState } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import auth, { setProfile } from '../../stores/auth.js';
import { getVisibleRoutesForShell, isInternalDemoEnabled } from '../../routing/routeSelectors.js';
import { useTranslation } from '../../i18n/useTranslation';

export default function Nav() {
  const { t } = useTranslation();
  const [state, setState] = useState(auth.getState());
  const navigate = useNavigate();
  const { pathname } = useLocation();

  useEffect(() => auth.subscribe(setState), []);

  const user = state.profile || state.user || null;
  const routes = getVisibleRoutesForShell('app-shell', user, {
    internalDemoEnabled: isInternalDemoEnabled(),
  }).filter((route) => route.nav?.menu);

  return (
    <div className="clinic-ops-nav-bar">
      <div style={{ fontWeight: 'var(--mac-font-weight-bold)', marginRight: 12, opacity: 0.85 }} aria-hidden="true"> </div>

      <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 6 }}>
        {routes.map((route) => (
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
            {route.nav?.label || route.title}
          </NavLink>
        ))}
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
