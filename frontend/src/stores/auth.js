// src/stores/auth.js
// Стор авторизации без внешних библиотек.
// Экспортирует функции и объект-обёртку auth (для совместимости со старым кодом).

import { me, setAuthToken } from "../api"; // barrel src/api/index.js

const TOKEN_KEY = "auth_token";
const PROFILE_KEY = "auth_profile";

let token = null;
let profile = null;
const listeners = new Set();

/** Инициализация из localStorage при загрузке модуля */
try {
  const t = localStorage.getItem(TOKEN_KEY);
  if (t) {
    token = t;
    setAuthToken(token);
  }
  const p = localStorage.getItem(PROFILE_KEY);
  if (p) {
    profile = JSON.parse(p);
  }
} catch {}

/** Подписка на изменения стора */
export function subscribe(fn) {
  listeners.add(fn);
  try {
    fn(getState());
  } catch {}
  return () => unsubscribe(fn);
}

export function unsubscribe(fn) {
  listeners.delete(fn);
}

function notify() {
  const state = getState();
  for (const fn of listeners) {
    try {
      fn(state);
    } catch {}
  }
}

/** Текущий токен */
export function getToken() {
  return token;
}

/** Установить токен */
export function setToken(nextToken) {
  token = nextToken || null;
  try {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  } catch {}
  setAuthToken(token);
  notify();
}

/** Очистить токен и профиль */
export function clearToken() {
  token = null;
  profile = null;
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(PROFILE_KEY);
  } catch {}
  setAuthToken(null);
  notify();
}

/** Синхронно получить профиль из стора */
export function getProfileSync() {
  return profile;
}

/** (НОВОЕ) Установить профиль вручную — совместимость со старым кодом */
export function setProfile(nextProfile) {
  profile = nextProfile || null;
  try {
    if (profile) {
      localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
    } else {
      localStorage.removeItem(PROFILE_KEY);
    }
  } catch {}
  notify();
}

/**
 * Загрузить профиль с бэкенда (GET /me).
 * @param {boolean} force — игнорировать кэш и запросить заново
 */
export async function getProfile(force = false) {
  if (!force && profile) return profile;
  const t = getToken();
  if (!t) {
    clearToken();
    throw new Error("Not authenticated");
  }
  setAuthToken(t);
  const data = await me(); // { id, username, ... }
  setProfile(data); // единая точка установки профиля
  return profile;
}

/** Снэпшот состояния */
export function getState() {
  return {
    token,
    profile,
    isAuthenticated: !!token,
  };
}

/** Объект-обёртка для совместимости с импортами вида `import { auth } ...` */
export const auth = {
  subscribe,
  unsubscribe,
  getToken,
  setToken,
  clearToken,
  getProfile,
  getProfileSync,
  setProfile,
  getState,
};

export default auth;
