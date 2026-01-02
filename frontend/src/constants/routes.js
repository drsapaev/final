// Централизованная конфигурация маршрутов и ролей
// Синхронизировано с docs/ROLES_AND_ROUTING.md

/**
 * Маппинг ролей на маршруты
 * @param {string} role - роль пользователя
 * @returns {string} маршрут для роли
 */
export function roleToRoute(role) {
  const roleLower = String(role || '').toLowerCase();

  switch (roleLower) {
    case 'admin': return '/admin';
    case 'registrar':
    case 'receptionist': // DB uses 'Receptionist', UI uses 'registrar'
      return '/registrar-panel';
    case 'lab': return '/lab-panel';
    case 'doctor': return '/doctor-panel';
    case 'cashier': return '/cashier-panel';
    case 'cardio': return '/cardiologist';
    case 'derma': return '/dermatologist';
    case 'dentist': return '/dentist';
    case 'patient': return '/patient-panel';
    default: return '/search';
  }
}

/**
 * Маппинг маршрутов на требуемые роли
 * @param {string} route - маршрут
 * @returns {string[]} массив ролей, которые могут получить доступ к маршруту
 */
export function routeToRoles(route) {
  const routeMap = {
    '/admin': ['Admin'],
    '/admin/analytics': ['Admin'],
    '/admin/users': ['Admin'],
    '/admin/doctors': ['Admin'],
    '/admin/services': ['Admin'],
    '/admin/patients': ['Admin'],
    '/admin/appointments': ['Admin'],
    '/admin/clinic-settings': ['Admin'],
    '/admin/queue-settings': ['Admin'],
    '/admin/ai-settings': ['Admin'],
    '/admin/telegram-settings': ['Admin'],
    '/admin/display-settings': ['Admin'],
    '/admin/activation': ['Admin'],
    '/admin/finance': ['Admin'],
    '/admin/reports': ['Admin'],
    '/admin/settings': ['Admin'],
    '/admin/security': ['Admin'],
    '/registrar-panel': ['Admin', 'Registrar', 'Receptionist'],
    '/doctor-panel': ['Admin', 'Doctor'],
    '/cardiologist': ['Admin', 'Doctor', 'cardio'],
    '/dermatologist': ['Admin', 'Doctor', 'derma'],
    '/dentist': ['Admin', 'Doctor', 'dentist'],
    '/lab-panel': ['Admin', 'Lab'],
    '/cashier-panel': ['Admin', 'Cashier'],
    '/patient-panel': ['Admin', 'Patient', 'Registrar', 'Receptionist', 'Doctor'],
    '/queue-board': [], // Публичный маршрут
    '/display-board': [], // Публичный маршрут
    '/settings': ['Admin'],
    '/audit': ['Admin'],
    '/scheduler': ['Admin', 'Doctor', 'Registrar', 'Receptionist'],
    '/appointments': ['Admin', 'Registrar', 'Receptionist'],
    '/analytics': ['Admin'],
    '/search': ['Admin', 'Doctor', 'Registrar', 'Receptionist', 'Lab', 'Cashier'],
  };

  return routeMap[route] || [];
}

/**
 * Проверяет, имеет ли пользователь доступ к маршруту
 * @param {object} profile - профиль пользователя
 * @param {string} route - маршрут
 * @returns {boolean} true если доступ разрешен
 */
export function hasRouteAccess(profile, route) {
  if (!profile) return false;

  const requiredRoles = routeToRoles(route);
  if (requiredRoles.length === 0) return true; // Публичный маршрут

  const userRoles = [];

  // Собираем роли пользователя
  if (profile.role) userRoles.push(String(profile.role).toLowerCase());
  if (profile.role_name) userRoles.push(String(profile.role_name).toLowerCase());
  if (Array.isArray(profile.roles)) {
    profile.roles.forEach(r => userRoles.push(String(r).toLowerCase()));
  }
  if (profile.is_superuser || profile.is_admin || profile.admin) {
    userRoles.push('admin');
  }

  // Проверяем совпадение ролей
  return requiredRoles.some(requiredRole =>
    userRoles.includes(String(requiredRole).toLowerCase())
  );
}

/**
 * Получает маршрут для роли с учетом профиля
 * @param {object} profile - профиль пользователя
 * @returns {string} маршрут для роли
 */
export function getRouteForProfile(profile) {
  if (!profile) return '/search';

  // Проверяем множественные роли
  const rolesArr = Array.isArray(profile.roles) ? profile.roles.map(r => String(r).toLowerCase()) : [];
  const roleLower = String(profile.role || profile.role_name || '').toLowerCase();

  // Специализированный маппинг для известных пользователей
  // Требование: при входе cardio@example.com показывать панель кардиолога
  const usernameLower = String(profile.username || '').toLowerCase();
  if (usernameLower === 'cardio@example.com') return '/cardiologist';
  if (usernameLower === 'derma@example.com') return '/dermatologist';
  if (usernameLower === 'dentist@example.com') return '/dentist';
  if (usernameLower === 'registrar@example.com') return '/registrar-panel';

  // Приоритет: admin > специализированные роли > общие роли
  if (rolesArr.includes('admin') || roleLower === 'admin') return '/admin';

  if (roleLower) {
    const route = roleToRoute(roleLower);
    if (route && route !== '/search') return route;
  }

  // Проверяем специализированные роли
  for (const r of rolesArr) {
    const route = roleToRoute(r);
    if (route && route !== '/search') return route;
  }

  return '/search';
}

/**
 * Конфигурация ролей для UI
 */
export const ROLE_OPTIONS = [
  { key: 'admin', label: 'Администратор', username: 'admin@example.com', route: '/admin' },
  { key: 'registrar', label: 'Регистратура', username: 'registrar@example.com', route: '/registrar-panel' },
  { key: 'lab', label: 'Лаборатория', username: 'lab@example.com', route: '/lab-panel' },
  { key: 'doctor', label: 'Врач', username: 'doctor@example.com', route: '/doctor-panel' },
  { key: 'cashier', label: 'Касса', username: 'cashier@example.com', route: '/cashier-panel' },
  { key: 'cardio', label: 'Кардиолог', username: 'cardio@example.com', route: '/cardiologist' },
  { key: 'derma', label: 'Дерматолог', username: 'derma@example.com', route: '/dermatologist' },
  { key: 'dentist', label: 'Стоматолог', username: 'dentist@example.com', route: '/dentist' },
];
