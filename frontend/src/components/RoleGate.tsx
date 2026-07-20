
import React, { useEffect, useState, type ReactNode } from 'react';
import auth from '../stores/auth';

interface RoleGateProps {
  allow?: string[];
  roles?: string[];
  fallback?: ReactNode;
  children?: ReactNode;
}

/**
 * Ограничивает доступ по ролям.
 */
export default function RoleGate({ allow = [], roles, fallback, children }: RoleGateProps) {
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
  border: '1px solid var(--mac-error-border, color-mix(in srgb, var(--mac-error), transparent 70%))',
  background: 'var(--mac-error-bg)',
  color: 'var(--mac-error)',
  borderRadius: 8,
  padding: 12,
};
const cap = { fontWeight: 'var(--mac-font-weight-bold)', marginBottom: 6, fontSize: 14 };


