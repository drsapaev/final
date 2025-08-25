// Auth store с совместимостью под ожидаемый API (zustand-like):
// - state: { token, profile }
// - methods: getState(), setState(partial), subscribe(listener)
// - helpers: getToken(), setToken(), clearToken(), getProfile(), setProfile()
// - default export: auth (объект со всеми методами)
//
// Хранение: localStorage (ключи TOKEN_KEY/PROFILE_KEY) + in-memory state.
// Подписчики получают ПОЛНЫЙ state { token, profile } при каждом изменении.

import { me } from "../api/client.js";

const TOKEN_KEY = "auth_token";
const PROFILE_KEY = "auth_profile";

// ---------- utils: storage ----------
function readTokenFromStorage() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

function writeTokenToStorage(token) {
  try {
    if (token == null) localStorage.removeItem(TOKEN_KEY);
    else localStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* ignore */
  }
}

function readProfileFromStorage() {
  try {
    const raw = localStorage.getItem(PROFILE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function writeProfileToStorage(profile) {
  try {
    if (profile == null) localStorage.removeItem(PROFILE_KEY);
    else localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
  } catch {
    /* ignore */
  }
}

// ---------- in-memory state + pub/sub ----------
let state = {
  token: readTokenFromStorage(),
  profile: readProfileFromStorage(),
};

const subscribers = new Set();

/** Возвращает ТЕКУЩЕЕ состояние (копию) */
export function getState() {
  return { ...state };
}

/** Мержит частичное состояние, синхронизирует storage и уведомляет подписчиков */
export function setState(partial) {
  const next = { ...state, ...(partial || {}) };

  // синхронизируем хранилище, если ключи присутствуют в partial
  if (Object.prototype.hasOwnProperty.call(partial || {}, "token")) {
    writeTokenToStorage(next.token);
  }
  if (Object.prototype.hasOwnProperty.call(partial || {}, "profile")) {
    writeProfileToStorage(next.profile);
  }

  state = next;
  notify();
}

/** Подписка: listener(state) -> unsubscribe */
export function subscribe(listener) {
  if (typeof listener !== "function") return () => {};
  subscribers.add(listener);
  // можно сразу отправить снапшот, если нужно:
  // try { listener(getState()); } catch {}
  return () => subscribers.delete(listener);
}

function notify() {
  const snapshot = getState();
  for (const cb of subscribers) {
    try {
      cb(snapshot);
    } catch {
      /* ignore subscriber errors */
    }
  }
}

// ---------- public helpers (совместимые с текущим кодом) ----------
export function getToken() {
  return getState().token;
}

export function setToken(tokenOrObj) {
  // принимаем либо строку токена, либо объект { access_token }
  let token = null;
  if (typeof tokenOrObj === "string") token = tokenOrObj;
  else if (tokenOrObj && tokenOrObj.access_token) token = tokenOrObj.access_token;

  setState({ token });
}

export function clearToken() {
  setState({ token: null, profile: null });
}

/** Сохраняет профиль (и уведомляет подписчиков) */
export function setProfile(profile) {
  setState({ profile: profile ?? null });
}

/**
 * getProfile(force = false)
 * - Если токена нет — НЕ дергаем /me (избегаем 401-спама) и возвращаем null.
 * - Если есть кэш и force=false — используем кэш.
 * - Иначе зовём /me, сохраняем профиль и возвращаем его.
 * - При 401/403 или сетевых ошибках возвращает null, чтобы UI не падал.
 */
export async function getProfile(force = false) {
  try {
    // NEW: без токена не запрашиваем /me, чтобы не получать 401 в консоли
    const token = getToken();
    if (!token) return null;

    if (!force) {
      const cached = getState().profile;
      if (cached) return cached;
    }
    const profile = await me();
    setProfile(profile || null);
    return profile || null;
  } catch (err) {
    if (err && (err.status === 401 || err.status === 403)) {
      return null;
    }
    console.warn("getProfile failed:", err?.status || err?.message || err);
    return null;
  }
}

// ---------- default export (удобный объект, как раньше) ----------
export const auth = {
  // zustand-like
  getState,
  setState,
  subscribe,

  // helpers
  getToken,
  setToken,
  clearToken,
  getProfile,
  setProfile,
};

export default auth;

