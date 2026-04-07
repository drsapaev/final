import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import tokenManager from '../utils/tokenManager';
import { roleToRoute } from '../constants/routes';

export default function UserSelect() {
  const [items, setItems] = useState([]);
  const [err, setErr] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    (async () => {
      setLoading(true);
      setErr('');
      try {
        const token = tokenManager.getAccessToken();
        const r = await fetch('/api/v1/admin/users', { headers: { Authorization: `Bearer ${token}` } });
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
    <div className="theme-page-shell" style={{ maxWidth: 860 }}>
      <h1 style={{ fontSize: 24, fontWeight: 800, marginBottom: 12 }}>Выбор пользователя</h1>
      <div className="legacy-muted" style={{ marginBottom: 12 }}>Доступно администратору. Нажмите, чтобы перейти к роли.</div>
      {err && <div className="legacy-error">{err}</div>}
      {loading ? (
        <div>Загрузка…</div>
      ) : (
        <div className="legacy-list">
          {items.map(u => (
            <div key={u.id} className="legacy-list-item">
              <div>
                <div style={{ fontWeight: 700 }}>{u.full_name || u.username}</div>
                <div className="legacy-muted" style={{ fontSize: 12 }}>{u.role || '—'} · {u.email || '—'}</div>
              </div>
              <div>
                <button className="legacy-button" onClick={() => navigate(roleToRoute(u.role))}>Перейти</button>
              </div>
            </div>
          ))}
          {items.length === 0 && <div className="legacy-muted">Пользователи не найдены</div>}
        </div>
      )}
    </div>
  );
}
