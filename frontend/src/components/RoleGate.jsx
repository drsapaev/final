import React, { useEffect, useState } from 'react';
import auth from '../stores/auth';

/**
 * Ограничивает доступ по ролям.
 * Поддерживает оба пропса: `allow` и `roles` (алиасы).
 * МЯГКИЙ РЕЖИМ: если пользователь залогинен, но роль из профиля распознать нельзя,
 *               контент не блокируем (чтобы не ломать UX).
 *
 * Props:
 *  - allow?: string[]
 *  - roles?: string[]        // алиас allow
 *  - fallback?: ReactNode    // что показать при запрете (по умолчанию — предупреждающий бокс)
 *  - children
 */
export default function RoleGate({ allow = [], roles, fallback, children }) {
  // Читаем состояние из стора и подписываемся на изменения
  const [st, setSt] = useState(auth.getState());
  useEffect(() => auth.subscribe(setSt), []);

  const needArr = (Array.isArray(roles) ? roles : allow) || [];
  const need = new Set(
    needArr
      .map((r) => String(r || '').trim().toLowerCase())
      .filter(Boolean)
  );

  // Если ограничений нет — показываем всегда
  if (need.size === 0) return children;

  // Не залогинен — блокируем (пусть RequireAuth решает редирект на /login)
  if (!st.token) {
    return fallback !== undefined ? fallback : denyBox([], Array.from(need));
  }

  const p = st.profile || null;

  // Собираем набор ролей пользователя из разных полей профиля
  const have = new Set();
  if (p) {
    if (p.role) have.add(String(p.role).toLowerCase());
    if (p.role_name) have.add(String(p.role_name).toLowerCase());
    if (Array.isArray(p.roles)) p.roles.forEach((r) => have.add(String(r).toLowerCase()));
    if (p.is_superuser || p.is_admin || p.admin) have.add('admin');
  }

  // Совпадение по ролям — пропускаем
  for (const n of need) {
    if (have.has(n)) return children;
  }

  // МЯГКИЙ РЕЖИМ: если роли не распознаны (have пустой), не блокируем
  if (have.size === 0) return children;

  // Иначе — запрет
  return fallback !== undefined ? fallback : denyBox(Array.from(have), Array.from(need));
}

function denyBox(have, need) {
  const roleLabel = have.length ? have.join(', ') : '—';
  return (
    <div style={box}>
      <div style={cap}>Доступ ограничен</div>
      <div>
        Ваша роль: <b>{roleLabel}</b>. Требуется одна из: <code>{need.join(', ')}</code>
      </div>
    </div>
  );
}

const box = {
  border: '1px solid #fecaca',
  background: '#fef2f2',
  color: '#7f1d1d',
  borderRadius: 8,
  padding: 12,
};
const cap = { fontWeight: 700, marginBottom: 6, fontSize: 14 };


