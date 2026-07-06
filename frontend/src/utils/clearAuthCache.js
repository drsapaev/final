import logger from '../utils/logger';
import tokenManager from './tokenManager';

/**
 * Утилита для очистки кэша аутентификации
 * Используется при проблемах с маршрутизацией из-за устаревших данных
 *
 * AUTH-REAUDIT-28 P0 fix: ранее очищались только `auth_token` и `auth_profile`,
 * но `refresh_token` и `user` оставались. Теперь делегируем в tokenManager.clearAll()
 * (он знает точный список ключей), и дополнительно чистим `auth_profile` —
 * отдельный legacy-ключ, который не входит в зону ответственности tokenManager.
 */

export function clearAuthCache() {
  try {
    // Полная очистка токенов + user через единый SSOT
    tokenManager.clearAll();

    // Legacy-ключи (auth_profile) — не входят в tokenManager.
    localStorage.removeItem('auth_profile');
    sessionStorage.removeItem('auth_token');
    sessionStorage.removeItem('auth_profile');

    logger.log('Auth cache cleared successfully');
    return true;
  } catch (error) {
    logger.error('Failed to clear auth cache:', error);
    return false;
  }
}

/**
 * Проверяет, есть ли устаревшие данные в кэше
 */
export function hasStaleAuthCache() {
  try {
    const profile = localStorage.getItem('auth_profile');
    if (!profile) return false;

    const profileData = JSON.parse(profile);
    const role = profileData?.role;

    // Проверяем на устаревшие роли или неправильные маршруты
    const validRoles = ['admin', 'registrar', 'receptionist', 'lab', 'doctor', 'cashier', 'cardio', 'derma', 'dentist'];
    return !validRoles.includes(role?.toLowerCase());
  } catch (error) {
    logger.error('Error checking auth cache:', error);
    return true; // Если ошибка, считаем кэш устаревшим
  }
}

/**
 * Автоматически очищает кэш при обнаружении проблем
 */
export function autoClearStaleCache() {
  if (hasStaleAuthCache()) {
    logger.warn('Stale auth cache detected, clearing...');
    clearAuthCache();
    return true;
  }
  return false;
}
