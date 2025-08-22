// Auth store, совместимый и с простыми экспортами (setToken/setProfile),
// и с объектом auth для подписки и выхода.
// Основан на frontend/src/api/client.js (TOKEN_KEY="auth_token").

import {
  getToken as getTokenFromClient,
  setToken as setTokenInClient,
  clearToken as clearTokenInClient,
  login as apiLogin,
  me as apiMe,
} from "../api/client.js";

const listeners = new Set();

let state = {
  token: getTokenFromClient() || null,
  user: null,
  ready: false, // станет true после первичной попытки me()
};

function notify() {
  const snapshot = { ...state };
  for (const fn of listeners) {
    try { fn(snapshot); } catch {}
  }
}

// --- Примитивные операции (совместимые с твоим Login.jsx) ---

export function setToken(token) {
  try {
    setTokenInClient(token || null);
    state.token = token || null;
    notify();
  } catch {}
}

export function setProfile(profile) {
  state.user = profile || null;
  notify();
}

export function clearToken() {
  try {
    clearTokenInClient();
    state.token = null;
    notify();
  } catch {}
}

export function getProfile() {
  return state.user || null;
}

// --- Расширенный API (для остальных страниц) ---

export const auth = {
  getState() {
    return { ...state };
  },
  subscribe(fn) {
    listeners.add(fn);
    try { fn({ ...state }); } catch {}
    return () => listeners.delete(fn);
  },
  async login(username, password) {
    const token = await apiLogin(username, password);
    setToken(token);
    try {
      const u = await apiMe();
      setProfile(u || null);
    } catch {
      setProfile(null);
    }
    return token;
  },
  logout() {
    clearToken();
    state = { token: null, user: null, ready: true };
    notify();
  },
};

// --- Инициализация профиля по имеющемуся токену ---
(async function init() {
  const t = getTokenFromClient();
  if (!t) {
    state.ready = true;
    notify();
    return;
  }
  try {
    const u = await apiMe();
    state.user = u || null;
  } catch {
    clearTokenInClient();
    state.token = null;
    state.user = null;
  } finally {
    state.ready = true;
    notify();
  }
})();