// src/api/health.js
// Мини-обёртки для служебных эндпойнтов здоровья/активации.
// ВАЖНО: никаких импортов из "../api" (во избежание циклов).

import { api } from './client';

/**
 * Проверка состояния сервера (если эндпойнт реализован).
 * Ожидаемый путь: GET /health
 * @returns {Promise<any>}
 */
export async function getHealth() {
  const res = await api.get('/health');
  return res.data;
}

/**
 * Статус активации системы (если эндпойнт реализован).
 * Ожидаемый путь: GET /activation/status
 * @returns {Promise<any>}
 */
export async function getActivationStatus() {
  const res = await api.get('/activation/status');
  return res.data;
}
