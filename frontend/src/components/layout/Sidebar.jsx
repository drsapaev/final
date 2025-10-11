import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import auth from '../../stores/auth.js';

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
  const location = useLocation();
  const isCardioRoute = location.pathname.startsWith('/cardiologist');

  const common = [];

  const byRole = [];
  if (role === 'admin') {
    byRole.push(
      { to: '/admin', label: 'Админ: Дашборд' },
      { to: '/admin/users', label: 'Админ: Пользователи' },
      { to: '/admin/analytics', label: 'Админ: Аналитика' },
      { to: '/admin/settings', label: 'Админ: Настройки' },
      { to: '/admin/security', label: 'Админ: Безопасность' }
    );
  }
  if (role === 'registrar') {
    byRole.push(
      { to: '/registrar-panel', label: 'Панель регистратора' },
      { to: '/cashier-panel', label: 'Касса' }
    );
  }
  if (role === 'doctor') {
    // По требованию: не показывать «Панель врача»
  }

  // Специализированные кнопки для кардиолога
  if (isCardioRoute || role === 'cardio' || role === 'cardiologist') {
    byRole.push(
      { to: '/cardiologist?tab=queue', label: 'Очередь' },
      { to: '/cardiologist?tab=appointments', label: 'Записи' },
      { to: '/cardiologist?tab=visit', label: 'Прием' },
      { to: '/cardiologist?tab=ecg', label: 'ЭКГ' },
      { to: '/cardiologist?tab=blood', label: 'Анализы' },
      { to: '/cardiologist?tab=ai', label: 'AI Помощник' },
      { to: '/cardiologist?tab=services', label: 'Услуги' },
      { to: '/cardiologist?tab=history', label: 'История' }
    );
  }
  if (role === 'lab') {
    byRole.push(
      { to: '/lab-panel', label: 'Лаборатория' }
    );
  }
  if (role === 'cashier') {
    byRole.push(
      { to: '/cashier-panel', label: 'Касса' }
    );
  }
  if (role === 'nurse') {
    // Требуемые элементы для медсестры отсутствуют в списке — ничего не добавляем
  }

  const items = [...byRole, ...common];

  return (
    <aside style={{ width: 240, borderRight: '1px solid var(--border-color)', padding: 12, background: 'var(--bg-primary)' }}>
      <div style={{ display: 'grid', gap: 6 }}>
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

