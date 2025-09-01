import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { getApiBase, api } from '../api/client';
import { setToken, setProfile } from '../stores/auth';
import auth from '../stores/auth.js';

/**
 * Логин по OAuth2 Password (FastAPI):
 * POST /login с application/x-www-form-urlencoded полями:
 *   username, password, grant_type=password, scope, client_id, client_secret
 */
export default function Login() {
  const roleOptions = [
    { key: 'admin', label: 'Администратор', username: 'admin', route: '/admin' },
    { key: 'registrar', label: 'Регистратура', username: 'registrar', route: '/registrar-panel' },
    { key: 'lab', label: 'Лаборатория', username: 'lab', route: '/lab-panel' },
    { key: 'cardio', label: 'Кардиолог', username: 'cardio', route: '/cardiologist' },
    { key: 'derma', label: 'Дерматолог', username: 'derma', route: '/dermatologist' },
    { key: 'dentist', label: 'Стоматолог', username: 'dentist', route: '/dentist' },
    { key: 'doctor', label: 'Врач', username: 'doctor', route: '/doctor' },
    { key: 'cashier', label: 'Касса', username: 'cashier', route: '/cashier' },
  ];

  const [selectedRoleKey, setSelectedRoleKey] = useState('admin');
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('admin123');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from?.pathname || '/';

  function onSelectRole(k) {
    setSelectedRoleKey(k);
    const found = roleOptions.find(r => r.key === k);
    if (found) setUsername(found.username);
  }

  async function performLogin(u, p) {
    try {
      const response = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ username: u, password: p, grant_type: 'password' }).toString(),
      });
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }
      const data = await response.json();
      const token = data?.access_token;
      if (!token) throw new Error('В ответе не найден access_token');
      setToken(token);
      try {
        const meRes = await fetch('/api/v1/auth/me', { headers: { Authorization: `Bearer ${token}` } });
        if (meRes.ok) setProfile(await meRes.json()); else setProfile(null);
      } catch {
        // Игнорируем ошибки получения профиля
        setProfile(null);
      }
    } catch (error) {
      console.error('Login error:', error);
      throw error;
    }
  }

  function pickRouteForRoleCached(defaultPath) {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) return defaultPath;
      // профиль сохранён в сторах; берём роль из auth.getState()
      const state = auth.getState ? auth.getState() : { profile: null };
      const role = String(state?.profile?.role || '').toLowerCase();
      if (role === 'admin') return '/admin'; // или "/user-select"
      if (role === 'registrar') return '/registrar-panel';
      if (role === 'lab') return '/lab-panel';
      if (role === 'doctor') return '/doctor';
      if (role === 'cashier') return '/cashier';
      return '/search';
    } catch {
      // Игнорируем ошибки доступа к localStorage
      return defaultPath;
    }
  }

  async function onLoginClick(e) {
    e?.preventDefault?.();
    if (busy) return;
    setBusy(true);
    setErr('');
    try {
      await performLogin(username, password);
      const fromClean = from || '/';
      const roleTarget = pickRouteForRoleCached('/search');
      const target = (fromClean !== '/' && fromClean !== '/login') ? fromClean : roleTarget;
      navigate(target, { replace: true });
    } catch (e2) {
      setErr(e2?.message || 'Ошибка входа');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={wrap}>
      <div style={card}>
        <h2 style={{ margin: 0, marginBottom: 8 }}>Вход</h2>
        {err ? <div style={errBox}>{err}</div> : null}
        <div style={{ display: 'grid', gap: 10 }}>
          <label style={lbl}>
            <span>Выбрать логин</span>
            <select
              value={selectedRoleKey}
              onChange={(e) => onSelectRole(e.target.value)}
              style={{ ...inp, padding: '8px 10px' }}
              disabled={busy}
            >
              {roleOptions.map((opt) => (
                <option key={opt.key} value={opt.key}>{opt.label}</option>
              ))}
            </select>
          </label>
          <label style={lbl}>
            <span>Логин</span>
            <input value={username} onChange={(e) => setUsername(e.target.value)} style={inp} autoComplete="username" disabled readOnly />
          </label>
          <label style={lbl}>
            <span>Пароль</span>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} style={inp} autoComplete="current-password" disabled={busy} />
          </label>
          <button type="button" disabled={busy} onClick={onLoginClick} style={btnPrimary}>
            {busy ? 'Входим...' : 'Войти'}
          </button>
        </div>
        <small style={{ opacity: 0.8, lineHeight: 1.4, display: 'block', marginTop: 10 }}>
          По умолчанию админ создаётся скриптом <code>create_admin.py</code> (admin/admin123).
        </small>
      </div>
    </div>
  );
}

/* стили */
const wrap = { minHeight: '100vh', display: 'grid', placeItems: 'center', background: '#f8fafc', padding: 16 };
const card = { width: 'min(420px, 94vw)', background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, boxShadow: '0 10px 30px rgba(0,0,0,.06)', padding: 16 };
const lbl = { display: 'grid', gap: 6, fontSize: 14 };
const inp = { padding: '10px 12px', border: '1px solid #e5e7eb', borderRadius: 8, outline: 'none' };
const btnPrimary = { padding: '10px 12px', borderRadius: 10, border: '1px solid #0284c7', background: '#0ea5e9', color: 'white', cursor: 'pointer' };
const errBox = { color: '#7f1d1d', background: '#fee2e2', border: '1px solid #fecaca', borderRadius: 8, padding: 8, whiteSpace: 'pre-wrap', marginBottom: 10 };

