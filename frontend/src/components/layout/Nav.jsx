import { useEffect, useState } from 'react';
import { NavLink, useNavigate, useLocation } from 'react-router-dom';
import auth, { setProfile } from '../../stores/auth.js';
import RoleGate from '../RoleGate.jsx';
import { useTheme } from '../../contexts/ThemeContext';

export default function Nav() {void
  useTheme();
  const [st, setSt] = useState(auth.getState());
  const navigate = useNavigate();
  const { pathname } = useLocation();

  useEffect(() => {
    const unsub = auth.subscribe(setSt);
    return () => unsub();
  }, []);

  const user = st.profile || st.user || null;
  const role = user?.role || 'Guest';

  // Маршруты приложения — при необходимости синхронизируй с src/App.jsx
  const routes = [
  { key: 'Health', to: '/', label: 'Health', roles: ['Admin', 'Registrar', 'Doctor', 'Lab', 'Cashier', 'User'] },
  { key: 'Doctor', to: '/doctor-panel', label: 'Врач', roles: ['Admin', 'Doctor'] },
  { key: 'Cashier', to: '/cashier-panel', label: 'Касса', roles: ['Admin', 'Cashier'] },
  { key: 'Scheduler', to: '/scheduler', label: 'Расписание', roles: ['Admin', 'Registrar', 'Doctor'] },
  { key: 'Admin', to: '/admin', label: 'Админ', roles: ['Admin'] },
  { key: 'RegistrarPanel', to: '/registrar-panel', label: 'Панель регистратора', roles: ['Admin', 'Registrar'] },
  { key: 'Cardiologist', to: '/cardiologist', label: 'Кардиолог', roles: ['Admin', 'Doctor'] },
  { key: 'Dermatologist', to: '/dermatologist', label: 'Дерматолог', roles: ['Admin', 'Doctor'] },
  { key: 'Dentist', to: '/dentist', label: 'Стоматолог', roles: ['Admin', 'Doctor'] },
  { key: 'LabPanel', to: '/lab-panel', label: 'Лаборатория', roles: ['Admin', 'Lab'] },
  { key: 'Audit', to: '/audit', label: 'Аудит', roles: ['Admin'] },
  { key: 'Activation', to: '/activation', label: 'Activation', roles: ['Admin'] },
  { key: 'Settings', to: '/settings', label: 'Настройки', roles: ['Admin'] }];

  return (
    <div className="legacy-nav-bar">
      {/* Заголовок приложения вынесён в AppShell — чтобы не дублировать */}
      <div style={{ fontWeight: 700, marginRight: 12, opacity: 0.85 }} aria-hidden="true"> </div>

      <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 6 }}>
        {routes.map((it) =>
        <RoleGate key={it.key} roles={it.roles}>
            <NavLink
            to={it.to}
            style={({ isActive }) => ({
              padding: '8px 12px',
              borderRadius: 10,
              border: `1px solid ${isActive ? 'var(--mac-nav-item-active-border)' : 'var(--mac-border)'}`,
              marginRight: 6,
              textDecoration: 'none',
              background: isActive ? 'var(--mac-nav-item-active)' : 'var(--mac-bg-primary)',
              color: isActive ? 'var(--mac-nav-item-active-text)' : 'var(--mac-text-primary)',
              boxShadow: isActive ? 'var(--mac-shadow-sm)' : 'none'
            })}
            aria-current={pathname === it.to ? 'page' : undefined}>
            
              {it.label}
            </NavLink>
          </RoleGate>
        )}
      </div>

      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
        {user ?
        <>
            <span style={{ opacity: 0.8 }}>
              {user.full_name || user.username || 'Пользователь'} · {role}
            </span>
            <button
            onClick={() => {
              auth.clearToken();
              setProfile(null);
              navigate('/login');
            }}
            className="legacy-button">
            
              Выйти
            </button>
          </> :

        <button
          onClick={() => navigate('/login')}
          className="legacy-button">
          
            Войти
          </button>
        }
      </div>
    </div>);

}
