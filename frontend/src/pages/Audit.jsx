import { useEffect, useMemo, useState, useCallback } from 'react';
import RoleGate from '../components/RoleGate.jsx';
import { api } from '../api/client.js';
import { AppEmpty, AppError, AppLoading, Button } from '../components/ui/macos';

/**
 * Аудит: список последних действий пользователей.
 * Совместимо с GET /audit?limit=...&offset=...
 */
export default function Audit() {
  const [rows, setRows] = useState([]);
  const [limit, setLimit] = useState(100);
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  const load = useCallback(async () => {
    setBusy(true);
    setErr('');
    try {
      const res = await api.get('/audit', { params: { limit } });
      const payload = res?.data;
      const items = Array.isArray(payload) ? payload : Array.isArray(res) ? res : [];
      setRows(items);
    } catch (e) {
      setErr(e?.data?.detail || e?.message || 'Ошибка загрузки аудита');
    } finally {
      setBusy(false);
    }
  }, [limit]);

  useEffect(() => {load();}, [load]);

  const filtered = useMemo(() => {
    if (!q) return rows;
    const qq = q.toLowerCase();
    return rows.filter((a) =>
    String(a.user || a.username || a.actor_user_id || '').toLowerCase().includes(qq) ||
    String(a.action || '').toLowerCase().includes(qq) ||
    String(a.entity || a.table || a.entity_type || '').toLowerCase().includes(qq) ||
    String(a.id || '').toLowerCase().includes(qq)
    );
  }, [q, rows]);

  const stateCellStyle = { minHeight: '96px', padding: '16px' };
  const visuallyHiddenStyle = {
    position: 'absolute',
    width: '1px',
    height: '1px',
    padding: 0,
    margin: '-1px',
    overflow: 'hidden',
    clip: 'rect(0, 0, 0, 0)',
    whiteSpace: 'nowrap',
    border: 0
  };
  const limitInputId = 'audit-limit';
  const searchInputId = 'audit-search';
  const tableCaptionId = 'audit-table-caption';

  return (
    <div>
      <RoleGate roles={['Admin']}>
        <div className="legacy-page-shell">
          <h2 style={{ margin: 0 }}>Аудит</h2>

          <div className="legacy-toolbar">
            <label htmlFor={limitInputId}>
              Порог:&nbsp;
              <input
                id={limitInputId}
                className="legacy-input"
                type="number"
                min={10}
                max={1000}
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value) || 100)}
                aria-label="Количество записей аудита для загрузки"
              />
            </label>
            <label htmlFor={searchInputId} style={visuallyHiddenStyle}>
              Поиск по пользователю, действию, сущности или ID
            </label>
            <input
              id={searchInputId}
              className="legacy-input"
              placeholder="Поиск по пользователю/действию/сущности"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              style={{ minWidth: 260 }}
              aria-label="Поиск по журналу аудита"
            />
            <Button
              type="button"
              variant="outline"
              size="small"
              onClick={load}
              disabled={busy}
              loading={busy}
              aria-label="Обновить журнал аудита">
              Обновить
            </Button>
          </div>

          {err && (
            <AppError
              title="Ошибка загрузки аудита"
              description={String(err)}
              action={
                <Button
                  type="button"
                  variant="outline"
                  size="small"
                  onClick={load}
                  disabled={busy}
                  loading={busy}
                  aria-label="Повторить загрузку журнала аудита">
                  Повторить
                </Button>
              }
              style={{ marginBottom: 12 }}
            />
          )}

          <div className="legacy-table-wrap" aria-busy={busy} aria-describedby={tableCaptionId}>
            <table className="legacy-table">
              <caption id={tableCaptionId} style={visuallyHiddenStyle}>Журнал аудита</caption>
              <thead>
                <tr>
                  <th>Время</th>
                  <th>Пользователь</th>
                  <th>Действие</th>
                  <th>Сущность</th>
                  <th>Детали</th>
                </tr>
              </thead>
              <tbody>
                {busy && rows.length === 0 ? (
                  <tr>
                    <td colSpan={5}>
                      <AppLoading
                        title="Загрузка аудита"
                        description="Получаем последние действия пользователей."
                        ariaLabel="Загружаем журнал аудита"
                        size="sm"
                        style={stateCellStyle}
                      />
                    </td>
                  </tr>
                ) : (
                  <>
                    {filtered.map((a, i) =>
                    <tr key={a.id || i}>
                        <td>{a.created_at || a.time || '—'}</td>
                        <td>{a.user || a.username || a.actor_user_id || '—'}</td>
                        <td>{a.action || '—'}</td>
                        <td>{a.entity || a.table || a.entity_type || '—'}</td>
                        <td><code style={{ fontSize: 12 }}>{a.details ? JSON.stringify(a.details) : a.payload ? JSON.stringify(a.payload) : '—'}</code></td>
                      </tr>
                    )}
                    {filtered.length === 0 && (
                      <tr>
                        <td colSpan={5}>
                          <AppEmpty
                            title="Нет записей"
                            description={q ? 'По текущему поиску записи не найдены.' : 'Журнал аудита пока пуст.'}
                            style={stateCellStyle}
                          />
                        </td>
                      </tr>
                    )}
                  </>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </RoleGate>
    </div>);

}
