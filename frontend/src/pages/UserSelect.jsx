import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

export default function UserSelect() {
  const [items, setItems] = useState([]);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    (async () => {
      setLoading(true);
      setErr("");
      try {
        const token = localStorage.getItem('auth_token');
        const r = await fetch('/api/v1/admin/users', { headers: { Authorization: `Bearer ${token}` }});
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data = await r.json();
        setItems(Array.isArray(data) ? data : []);
      } catch (e) {
        setErr(e.message || 'Ошибка загрузки');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div style={{ maxWidth: 800, margin: '20px auto', padding: 16 }}>
      <h1 style={{ fontSize: 24, fontWeight: 800, marginBottom: 12 }}>Выбор пользователя</h1>
      <div style={{ opacity: .7, marginBottom: 12 }}>Доступно администратору. Нажмите, чтобы перейти к роли.</div>
      {err && <div style={{ color: '#7f1d1d', background: '#fee2e2', border: '1px solid #fecaca', padding: 8, borderRadius: 8 }}>{err}</div>}
      {loading ? (
        <div>Загрузка…</div>
      ) : (
        <div style={{ display: 'grid', gap: 10 }}>
          {items.map(u => (
            <div key={u.id} style={{ border: '1px solid #eee', borderRadius: 10, padding: 12, background: '#fff', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontWeight: 700 }}>{u.full_name || u.username}</div>
                <div style={{ fontSize: 12, opacity: .7 }}>{u.role || '—'} · {u.email || '—'}</div>
              </div>
              <div>
                <button onClick={() => navigate(routeForRole(u.role))} style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #ddd', background: '#fff', cursor: 'pointer' }}>Перейти</button>
              </div>
            </div>
          ))}
          {items.length === 0 && <div style={{ opacity: .7 }}>Пользователи не найдены</div>}
        </div>
      )}
    </div>
  );
}

function routeForRole(role) {
  const r = String(role || '').toLowerCase();
  if (r === 'admin') return '/admin';
  if (r === 'registrar') return '/registrar-panel';
  if (r === 'lab') return '/lab-panel';
  if (r === 'doctor') return '/doctor';
  if (r === 'cashier') return '/cashier';
  return '/';
}
