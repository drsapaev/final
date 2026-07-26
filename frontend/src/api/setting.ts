// Настройки: чтение по категории
import { apiRequest } from './client';

/** GET /settings?category=... (endpoint добавлен на бэке) */
export async function getSettings(
  category: string,
  { limit = 100, offset = 0 }: { limit?: number; offset?: number } = {}
) {
  if (!category) throw new Error('category is required');
  return apiRequest('GET', '/settings', { params: { category, limit, offset } });
}
