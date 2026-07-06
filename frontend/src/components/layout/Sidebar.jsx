import { NavLink, useLocation } from 'react-router-dom';
import auth from '../../stores/auth.js';
import { useTheme } from '../../contexts/ThemeContext.jsx';
import { getCanonicalRouteById, getRoleHomeRoute } from '../../routing/routeSelectors.js';

const cashierHomeRoute = getRoleHomeRoute('cashier');
const cardiologyHomeRoute = getCanonicalRouteById('doctor-cardiology')?.path || getRoleHomeRoute('cardio');
const dermatologyHomeRoute = getCanonicalRouteById('doctor-dermatology')?.path || getRoleHomeRoute('derma');
const dentistryHomeRoute = getCanonicalRouteById('doctor-dentistry')?.path || getRoleHomeRoute('dentist');
const labHomeRoute = getRoleHomeRoute('lab');
const registrarHomeRoute = getRoleHomeRoute('registrar');

const ADMIN_NAV_ITEM_SOURCES = [
  { routeId: 'admin-dashboard', label: 'Админ: Дашборд' },
  { routeId: 'admin-users', label: 'Админ: Пользователи' },
  { routeId: 'admin-analytics', label: 'Админ: Аналитика' },
  { routeId: 'admin-settings', label: 'Админ: Настройки' },
  { routeId: 'admin-security', label: 'Админ: Безопасность' },
];

const adminNavItems = ADMIN_NAV_ITEM_SOURCES
  .map(({ routeId, label }) => {
    const route = getCanonicalRouteById(routeId);

    if (!route) {
      return null;
    }

    return { to: route.path, label };
  })
  .filter(Boolean);

export default function Sidebar() {
  const { getColor, getSpacing } = useTheme();
  const st = auth.getState();
  const profile = st.profile || st.user || {};
  const role = String(profile?.role || profile?.role_name || '').toLowerCase();
  const location = useLocation();
  const isCardioRoute = location.pathname.startsWith(cardiologyHomeRoute);
  const isDermaRoute = location.pathname.startsWith(dermatologyHomeRoute);
  const isDentistRoute = location.pathname.startsWith(dentistryHomeRoute);
  const isLabRoute = location.pathname.startsWith(labHomeRoute);

  const common = [];

  const byRole = [];
  
  // Если мы на специализированной странице, показываем ТОЛЬКО кнопки этой специальности
  if (isCardioRoute) {
    byRole.push(
      { to: `${cardiologyHomeRoute}?tab=queue`, label: 'Очередь' },
      { to: `${cardiologyHomeRoute}?tab=appointments`, label: 'Записи' },
      { to: `${cardiologyHomeRoute}?tab=visit`, label: 'Прием' },
      { to: `${cardiologyHomeRoute}?tab=ecg`, label: 'ЭКГ' },
      { to: `${cardiologyHomeRoute}?tab=blood`, label: 'Анализы' },
      { to: `${cardiologyHomeRoute}?tab=ai`, label: 'AI Помощник' },
      { to: `${cardiologyHomeRoute}?tab=services`, label: 'Услуги' },
      { to: `${cardiologyHomeRoute}?tab=history`, label: 'История' }
    );
  } else if (isDermaRoute) {
    byRole.push(
      { to: `${dermatologyHomeRoute}?tab=queue`, label: 'Очередь' },
      { to: `${dermatologyHomeRoute}?tab=appointments`, label: 'Записи' },
      { to: `${dermatologyHomeRoute}?tab=visit`, label: 'Прием' },
      { to: `${dermatologyHomeRoute}?tab=patients`, label: 'Пациенты' },
      { to: `${dermatologyHomeRoute}?tab=photos`, label: 'Фото' },
      { to: `${dermatologyHomeRoute}?tab=skin`, label: 'Осмотр кожи' },
      { to: `${dermatologyHomeRoute}?tab=cosmetic`, label: 'Косметология' },
      { to: `${dermatologyHomeRoute}?tab=ai`, label: 'AI Помощник' },
      { to: `${dermatologyHomeRoute}?tab=services`, label: 'Услуги' },
      { to: `${dermatologyHomeRoute}?tab=history`, label: 'История' }
    );
  } else if (isDentistRoute) {
    byRole.push(
      { to: `${dentistryHomeRoute}?tab=dashboard`, label: 'Дашборд' },
      { to: `${dentistryHomeRoute}?tab=patients`, label: 'Пациенты' },
      { to: `${dentistryHomeRoute}?tab=appointments`, label: 'Записи' },
      { to: `${dentistryHomeRoute}?tab=examinations`, label: 'Осмотры' },
      { to: `${dentistryHomeRoute}?tab=diagnoses`, label: 'Диагнозы' },
      { to: `${dentistryHomeRoute}?tab=visits`, label: 'Протоколы' },
      { to: `${dentistryHomeRoute}?tab=photos`, label: 'Архив' },
      { to: `${dentistryHomeRoute}?tab=templates`, label: 'Шаблоны' },
      { to: `${dentistryHomeRoute}?tab=reports`, label: 'Отчеты' },
      { to: `${dentistryHomeRoute}?tab=dental-chart`, label: 'Схемы зубов' },
      { to: `${dentistryHomeRoute}?tab=treatment-plans`, label: 'Планы лечения' },
      { to: `${dentistryHomeRoute}?tab=prosthetics`, label: 'Протезирование' },
      { to: `${dentistryHomeRoute}?tab=ai-assistant`, label: 'AI Помощник' }
    );
  } else if (isLabRoute) {
    byRole.push(
      { to: `${labHomeRoute}?tab=tests`, label: 'Анализы' },
      { to: `${labHomeRoute}?tab=appointments`, label: 'Записи' },
      { to: `${labHomeRoute}?tab=results`, label: 'Результаты' },
      { to: `${labHomeRoute}?tab=patients`, label: 'Пациенты' },
      { to: `${labHomeRoute}?tab=reports`, label: 'Отчеты' },
      { to: `${labHomeRoute}?tab=ai`, label: 'AI Анализ' }
    );
  } else {
    // Обычная логика для других страниц
    if (role === 'admin') {
      byRole.push(...adminNavItems);
    }
    if (role === 'registrar') {
      byRole.push(
        { to: registrarHomeRoute, label: 'Панель регистратора' },
        { to: cashierHomeRoute, label: 'Касса' }
      );
    }
    if (role === 'doctor') {
      // По требованию: не показывать «Панель врача»
    }
    if (role === 'lab') {
      byRole.push(
        { to: labHomeRoute, label: 'Лаборатория' }
      );
    }
    if (role === 'cashier') {
      byRole.push(
        { to: cashierHomeRoute, label: 'Касса' }
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
              borderRadius: 'var(--mac-radius-md)',
              color: isActive ? getColor('surface') : getColor('textSecondary'),
              background: isActive ? getColor('primary', 500) : 'transparent',
              textDecoration: 'none',
              transition: 'all 0.2s ease',
              fontSize: getSpacing('base'),
              fontWeight: 'var(--mac-font-weight-medium)',
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

