import React from 'react';
import { NavLink } from 'react-router-dom';
import auth from '../stores/auth.js';

const item = {
  display: 'block',
  padding: '8px 10px',
  borderRadius: 8,
  color: 'var(--text-secondary)',
  textDecoration: 'none',
  transition: 'all 0.2s ease',
};

export default function Sidebar() {
  const st = auth.getState();
  const profile = st.profile || st.user || {};
  const role = String(profile?.role || profile?.role_name || '').toLowerCase();

  const common = [];

  const byRole = [];
  if (role === 'admin') {
    byRole.push(
      { to: '/admin', label: 'Админ' },
      { to: '/user-select', label: 'Пользователи' },
      { to: '/analytics', label: 'Аналитика' }
    );
  }
  if (role === 'registrar') {
    byRole.push(
      { to: '/registrar-panel', label: 'Панель регистратора' }
    );
  }
  if (role === 'doctor') {
    byRole.push(
      { to: '/doctor-panel', label: 'Панель врача' }
    );
  }
  if (role === 'lab') {
    byRole.push({ to: '/lab-panel', label: 'Лаборатория' });
  }
  if (role === 'cashier') {
    byRole.push({ to: '/cashier-panel', label: 'Касса' });
  }

  const items = [...byRole, ...common];

  return (
    <aside style={{ width: 240, borderRight: '1px solid var(--border-color)', padding: 12, background: 'var(--bg-primary)' }}>
      <div style={{ display: 'grid', gap: 6 }}>
        {/* Общие пункты для демонстрации */}
        <NavLink
          key="patient-panel"
          to="/patient-panel"
          style={({ isActive }) => ({
            ...item,
            background: isActive ? 'var(--text-primary)' : 'transparent',
            color: isActive ? 'var(--bg-primary)' : 'var(--text-secondary)',
          })}
        >Пациент</NavLink>
        {items.map(x => (
          <NavLink
            key={x.to}
            to={x.to}
            style={({ isActive }) => ({
              ...item,
              background: isActive ? 'var(--text-primary)' : 'transparent',
              color: isActive ? 'var(--bg-primary)' : 'var(--text-secondary)',
            })}
          >
            {x.label}
          </NavLink>
        ))}
      </div>
    </aside>
  );
}
