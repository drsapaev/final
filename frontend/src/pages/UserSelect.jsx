import { useEffect, useState } from 'react';
import { api } from '../api/client';  // PR-54: replace raw fetch
import { useNavigate } from 'react-router-dom';
import tokenManager from '../utils/tokenManager';
import { roleToRoute } from '../constants/routes';
import {
  AppEmpty, AppError, AppLoading, Button, Card, CardContent, CardHeader,
} from '../components/ui/macos';
import { useTranslation } from '../i18n/useTranslation';

export default function UserSelect() {
  const { t } = useTranslation();
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
        const r = await api.get('/admin/users');
        if (r.status >= 400) throw new Error(`HTTP ${r.status}`);
        const data = r.data;
        setItems(Array.isArray(data) ? data : []);
      } catch (e) {
        setErr(e.message || 'Ошибка загрузки');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <Card style={{ maxWidth: 860 }}>
      <CardHeader>
        <h1 style={{ fontSize: 24, fontWeight: 800, margin: 0, color: 'var(--mac-text-primary)' }}>Выбор пользователя</h1>
        <div style={{ color: 'var(--mac-text-secondary)', fontSize: 13, marginTop: 8 }}>Доступно администратору. Нажмите, чтобы перейти к роли.</div>
      </CardHeader>
      <CardContent>
      {err && <AppError title="Не удалось загрузить пользователей" description={err} style={{ marginBottom: 12 }} />}
      {loading ? (
        <AppLoading
          title="Загрузка пользователей"
          description="Получаем список доступных пользователей."
          ariaLabel="Загружаем список пользователей"
          size="sm"
        />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {items.map(u => (
            <div
              key={u.id}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                gap: 12,
                padding: '12px 14px',
                border: '1px solid var(--mac-card-border)',
                borderRadius: 'var(--mac-radius-md)',
                background: 'var(--mac-card-bg)'
              }}>
              <div>
                <div style={{ fontWeight: 'var(--mac-font-weight-bold)', color: 'var(--mac-text-primary)' }}>{u.full_name || u.username}</div>
                <div style={{ fontSize: 12, color: 'var(--mac-text-secondary)' }}>{u.role || '—'} · {u.email || '—'}</div>
              </div>
              <div>
                <Button type="button" variant="outline" size="small" onClick={() => navigate(roleToRoute(u.role))}>
                  Перейти
                </Button>
              </div>
            </div>
          ))}
          {items.length === 0 && <AppEmpty title="Пользователи не найдены" description="Нет пользователей, доступных для выбора роли." />}
        </div>
      )}
      </CardContent>
    </Card>
  );
}
