import React, { useEffect, useMemo, useState } from 'react';
import Nav from '../components/layout/Nav.jsx';
import RoleGate from '../components/RoleGate.jsx';
import { api } from '../api/client.js';
import { getActivationStatus } from '../api';
import { useTheme } from '../contexts/ThemeContext';

export default function Activation() {
  const { isDark, isLight, getColor, getSpacing } = useTheme();
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState(null);
  const [rows, setRows] = useState([]);
  const [filterStatus, setFilterStatus] = useState('');
  const [err, setErr] = useState('');

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
        api
          .get('/activation/list', { params: { status: filterStatus || undefined, limit: 200 } })
          .catch(() => ({ items: [] })),
      ]);
      setStatus(st || null);
      setRows((lst && lst.items) || []);
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
    return () => { mounted = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div>
      <Nav />
      <main className="p-4 max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-2xl font-semibold">Активация</h1>
          <div className="flex items-center gap-2">
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="border rounded px-2 py-1 text-sm"
            >
              <option value="">Все</option>
              <option value="active">Активные</option>
              <option value="pending">Ожидают</option>
              <option value="disabled">Отключены</option>
            </select>
            <button onClick={loadAll} className="px-3 py-1.5 border rounded text-sm bg-white hover:bg-gray-50">
              Обновить
            </button>
          </div>
        </div>

        {err && (
          <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded p-2 mb-4">
            {err}
          </div>
        )}

        <section className="mb-6">
          <h2 className="text-lg font-medium mb-2">Статус</h2>
          {loading ? (
            <div>Загрузка статуса…</div>
          ) : status ? (
            <pre className="text-sm bg-gray-50 border border-gray-200 rounded p-3 overflow-auto">
              {typeof status === 'string' ? status : JSON.stringify(status, null, 2)}
            </pre>
          ) : (
            <div className="text-sm text-gray-700">
              Эндпоинт статуса активации на сервере не найден. Вероятно, функция не используется — всё в порядке.
            </div>
          )}
        </section>

        <RoleGate roles={['Admin']}>
          <section>
            <h2 className="text-lg font-medium mb-2">Список</h2>
            {loading ? (
              <div>Загрузка…</div>
            ) : filtered.length ? (
              <div className="overflow-auto border border-gray-200 rounded">
                <table className="min-w-full text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="text-left px-3 py-2 border-b">ID</th>
                      <th className="text-left px-3 py-2 border-b">Имя</th>
                      <th className="text-left px-3 py-2 border-b">Статус</th>
                      <th className="text-left px-3 py-2 border-b">Обновлён</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((r) => (
                      <tr key={r.id}>
                        <td className="px-3 py-2 border-b">{r.id}</td>
                        <td className="px-3 py-2 border-b">{r.name || r.title || '—'}</td>
                        <td className="px-3 py-2 border-b">{r.status || '—'}</td>
                        <td className="px-3 py-2 border-b">
                          {r.updated_at ? new Date(r.updated_at).toLocaleString() : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-sm text-gray-700">Нет данных.</div>
            )}
          </section>
        </RoleGate>
      </main>
    </div>
  );
}

