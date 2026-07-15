import { useEffect, useMemo, useState } from 'react';
import Nav from '../components/layout/Nav.jsx';
import RoleGate from '../components/RoleGate.jsx';
import {
  AppEmpty, AppError, AppLoading, Button, Select,
} from '../components/ui/macos';
import { api } from '../api/client.js';
import { getActivationStatus } from '../api';
import { useTheme } from '../contexts/ThemeContext';
import { useTranslation } from '../i18n/adapter';

export default function Activation() {
  const { t } = useTranslation();
  useTheme();
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState(null);
  const [rows, setRows] = useState([]);
  const [filterStatus, setFilterStatus] = useState('');
  const [err, setErr] = useState('');
  const statusFilterOptions = [
    { value: '', label: 'Все статусы' },
    { value: 'active', label: 'Активные' },
    { value: 'pending', label: 'Ожидают' },
    { value: 'disabled', label: 'Отключены' },
  ];

  const filtered = useMemo(() => {
    if (!filterStatus) return rows;
    return (rows || []).filter(
      (r) => String(r?.status || '').toLowerCase() === String(filterStatus).toLowerCase()
    );
  }, [rows, filterStatus]);

  async function loadAll() {
    setLoading(true);
    setErr('');
    try {
      const [st, lst] = await Promise.all([
      getActivationStatus(), // 404/405 -> null
      api.
      get('/activation/list', { params: { status: filterStatus || undefined, limit: 200 } }).
      catch(() => ({ items: [] }))]
      );
      setStatus(st || null);
      setRows(lst && lst.items || []);
    } catch (e) {
      setErr(e?.data?.detail || e?.message || 'Ошибка загрузки');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let mounted = true;
    (async () => {
      await loadAll();
      if (!mounted) return;
    })();
    return () => {mounted = false;};
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div>
      <Nav />
      <main className="p-4 max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-2xl font-semibold">Активация</h1>
          <div className="flex items-center gap-2">
            <Select
              id="activation-status-filter"
              label="Статус записи"
              options={statusFilterOptions}
              value={filterStatus}
              onChange={setFilterStatus}
              size="small"
              style={{ minWidth: 180 }}
            />
            <Button
              onClick={loadAll}
              disabled={loading}
              loading={loading}
              size="small"
              variant="outline">
              Обновить
            </Button>
          </div>
        </div>

        {err &&
        <AppError
          title="Ошибка загрузки"
          description={err}
          action={
            <Button onClick={loadAll} disabled={loading} loading={loading} size="small" variant="outline">
              Повторить
            </Button>
          }
          style={{ marginBottom: 'var(--mac-spacing-4)' }}
        />
        }

        <section className="mb-6">
          <h2 className="text-lg font-medium mb-2">{t('common.status')}</h2>
          {loading ?
          <AppLoading
            size="sm"
            title="Загрузка статуса..."
          /> :
          status ?
          <pre className="text-sm bg-gray-50 border border-gray-200 rounded p-3 overflow-auto">
              {typeof status === 'string' ? status : JSON.stringify(status, null, 2)}
            </pre> :

          <AppEmpty
            title="Статус активации недоступен"
            description="Эндпоинт статуса активации на сервере не найден. Вероятно, функция не используется - все в порядке."
          />
          }
        </section>

        <RoleGate roles={['Admin']}>
          <section>
            <h2 className="text-lg font-medium mb-2">Список</h2>
            {loading ?
            <AppLoading
              size="sm"
              title="Загрузка..."
            /> :
            filtered.length ?
            <div className="overflow-auto border border-gray-200 rounded">
                <div className="admin-table-wrapper">
<table className="min-w-full text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="text-left px-3 py-2 border-b">ID</th>
                      <th className="text-left px-3 py-2 border-b">Имя</th>
                      <th className="text-left px-3 py-2 border-b">{t('common.status')}</th>
                      <th className="text-left px-3 py-2 border-b">Обновлён</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((r) =>
                  <tr key={r.id}>
                        <td className="px-3 py-2 border-b">{r.id}</td>
                        <td className="px-3 py-2 border-b">{r.name || r.title || '—'}</td>
                        <td className="px-3 py-2 border-b">{r.status || '—'}</td>
                        <td className="px-3 py-2 border-b">
                          {r.updated_at ? new Date(r.updated_at).toLocaleString() : '—'}
                        </td>
                      </tr>
                  )}
                  </tbody>
                </table>
</div>
              </div> :

            <AppEmpty
              title={filterStatus ? 'Нет записей с выбранным статусом' : 'Нет данных'}
              description={
                filterStatus ?
                  'Поменяйте фильтр статуса или обновите список.' :
                  'Записи активации появятся здесь после загрузки.'
              }
            />
            }
          </section>
        </RoleGate>
      </main>
    </div>);

}
