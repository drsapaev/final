import axios from 'axios';
import { tokenManager } from './tokenManager';

// Используем общий базовый URL как в api/client.js
const API_BASE = import.meta.env?.VITE_API_BASE || 'http://localhost:8000/api/v1';

// Создаем экземпляр axios с базовой конфигурацией
const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Интерцептор для добавления токена авторизации
api.interceptors.request.use(
  (config) => {
    // Используем централизованный tokenManager
    const token = tokenManager.getAccessToken();
    if (token) {
      config.headers = config.headers || {};
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Интерцептор для обработки ответов
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    if (error.response?.status === 401) {
      // Токен истек или недействителен - очищаем через tokenManager
      tokenManager.clearAll();
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export { api };
export default api;
