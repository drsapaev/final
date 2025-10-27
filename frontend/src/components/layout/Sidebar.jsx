import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import auth from '../../stores/auth.js';
import { useTheme } from '../../contexts/ThemeContext.jsx';

export default function Sidebar() {
  const { getColor, getSpacing } = useTheme();
  const st = auth.getState();
  const profile = st.profile || st.user || {};
  const role = String(profile?.role || profile?.role_name || '').toLowerCase();
  const location = useLocation();
  const isCardioRoute = location.pathname.startsWith('/cardiologist');
  const isDermaRoute = location.pathname.startsWith('/dermatologist');
  const isDentistRoute = location.pathname.startsWith('/dentist');
  const isLabRoute = location.pathname.startsWith('/lab-panel');

  const common = [];

  const byRole = [];
  
  // Если мы на специализированной странице, показываем ТОЛЬКО кнопки этой специальности
  if (isCardioRoute) {
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
  } else if (isDermaRoute) {
    byRole.push(
      { to: '/dermatologist?tab=queue', label: 'Очередь' },
      { to: '/dermatologist?tab=appointments', label: 'Записи' },
      { to: '/dermatologist?tab=visit', label: 'Прием' },
      { to: '/dermatologist?tab=patients', label: 'Пациенты' },
      { to: '/dermatologist?tab=photos', label: 'Фото' },
      { to: '/dermatologist?tab=skin', label: 'Осмотр кожи' },
      { to: '/dermatologist?tab=cosmetic', label: 'Косметология' },
      { to: '/dermatologist?tab=ai', label: 'AI Помощник' },
      { to: '/dermatologist?tab=services', label: 'Услуги' },
      { to: '/dermatologist?tab=history', label: 'История' }
    );
  } else if (isDentistRoute) {
    byRole.push(
      { to: '/dentist?tab=dashboard', label: 'Дашборд' },
      { to: '/dentist?tab=patients', label: 'Пациенты' },
      { to: '/dentist?tab=appointments', label: 'Записи' },
      { to: '/dentist?tab=examinations', label: 'Осмотры' },
      { to: '/dentist?tab=diagnoses', label: 'Диагнозы' },
      { to: '/dentist?tab=visits', label: 'Протоколы' },
      { to: '/dentist?tab=photos', label: 'Архив' },
      { to: '/dentist?tab=templates', label: 'Шаблоны' },
      { to: '/dentist?tab=reports', label: 'Отчеты' },
      { to: '/dentist?tab=dental-chart', label: 'Схемы зубов' },
      { to: '/dentist?tab=treatment-plans', label: 'Планы лечения' },
      { to: '/dentist?tab=prosthetics', label: 'Протезирование' },
      { to: '/dentist?tab=ai-assistant', label: 'AI Помощник' }
    );
  } else if (isLabRoute) {
    byRole.push(
      { to: '/lab-panel?tab=tests', label: 'Анализы' },
      { to: '/lab-panel?tab=appointments', label: 'Записи' },
      { to: '/lab-panel?tab=results', label: 'Результаты' },
      { to: '/lab-panel?tab=patients', label: 'Пациенты' },
      { to: '/lab-panel?tab=reports', label: 'Отчеты' },
      { to: '/lab-panel?tab=ai', label: 'AI Анализ' }
    );
  } else {
    // Обычная логика для других страниц
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
  }

  const items = [...byRole, ...common];

  return (
    <aside style={{
      width: 240,
      borderRight: `1px solid ${getColor('border')}`,
      padding: getSpacing('md'),
      background: getColor('surface')
    }}>
      <div style={{ display: 'grid', gap: getSpacing('sm') }}>
        {items.map(x => (
          <NavLink
            key={x.to}
            to={x.to}
            style={({ isActive }) => ({
              display: 'block',
              padding: `${getSpacing('sm')} ${getSpacing('md')}`,
              borderRadius: '8px',
              color: isActive ? getColor('surface') : getColor('textSecondary'),
              background: isActive ? getColor('primary', 500) : 'transparent',
              textDecoration: 'none',
              transition: 'all 0.2s ease',
              fontSize: getSpacing('base'),
              fontWeight: '500',
              border: isActive ? 'none' : `1px solid ${getColor('border')}`,
              ':hover': {
                background: isActive ? getColor('primary', 600) : getColor('primary', 50),
                color: isActive ? getColor('surface') : getColor('primary', 600),
                transform: 'translateX(4px)'
              }
            })}
          >
            {x.label}
          </NavLink>
        ))}
      </div>
    </aside>
  );
}

