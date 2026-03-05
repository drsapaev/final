import { useEffect, useMemo, useState, useCallback } from 'react';
import RoleGate from '../components/RoleGate.jsx';
import { api } from '../api/client.js';

function todayStr() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${dd}`;
}

/**
 * Расписание: просмотр слотов (чтение).
 * Совместимо с GET /schedule?date=YYYY-MM-DD&limit=...
 */
export default function Scheduler() {
  const [date, setDate] = useState(todayStr());
  const [rows, setRows] = useState([]);
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  const load = useCallback(async () => {
    setBusy(true);
    setErr('');
    try {
      // Пытаемся обеими формами параметров: date и d — поддержка разных реализаций.
      let res = await api.get('/schedule', { params: { date, limit: 200 } });
      if (!res || !Array.isArray(res) && !Array.isArray(res?.items)) {
        res = await api.get('/schedule', { params: { d: date, limit: 200 } });
      }
      const items = Array.isArray(res?.items) ? res.items : Array.isArray(res) ? res : [];
      setRows(items);
    } catch (e) {
      setErr(e?.data?.detail || e?.message || 'Ошибка загрузки расписания');
    } finally {
      setBusy(false);
    }
  }, [date]);

  useEffect(() => {load();}, [load]);

  const filtered = useMemo(() => {
    if (!q) return rows;
    const qq = q.toLowerCase();
    return rows.filter((s) =>
    String(s.doctor_name || s.doctor || '').toLowerCase().includes(qq) ||
    String(s.room || '').toLowerCase().includes(qq) ||
    String(s.status || '').toLowerCase().includes(qq)
    );
  }, [q, rows]);

  return (
    <div>
      <RoleGate roles={['Admin', 'Registrar', 'Doctor']}>
        <div className="legacy-page-shell">
          <h2 style={{ margin: 0 }}>Расписание</h2>

          <div className="legacy-toolbar">
            <label>
              Дата:&nbsp;
              <input className="legacy-input" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </label>
            <input className="legacy-input" placeholder="Поиск по врачу/кабинету/статусу" value={q} onChange={(e) => setQ(e.target.value)} style={{ minWidth: 260 }} />
            <button className="legacy-button" onClick={load} disabled={busy}>{busy ? 'Загрузка' : 'Обновить'}</button>
          </div>

          {err && <div className="legacy-error">{String(err)}</div>}

          <div className="legacy-table-wrap">
            <table className="legacy-table">
              <thead>
                <tr>
                  <th>Врач</th>
                  <th>Кабинет</th>
                  <th>Время</th>
                  <th>Статус</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((s, i) =>
                <tr key={s.id || i}>
                    <td>{s.doctor_name || s.doctor || '—'}</td>
                    <td>{s.room || '—'}</td>
                    <td>
                      {s.time || s.slot || s.start_time ? s.time || s.slot || s.start_time : '—'}
                      {s.end_time ? ` — ${s.end_time}` : ''}
                    </td>
                    <td>{s.status || (s.available ? 'available' : '—')}</td>
                  </tr>
                )}
                {filtered.length === 0 &&
                <tr><td colSpan={4}>Нет записей</td></tr>
                }
              </tbody>
            </table>
          </div>
        </div>
      </RoleGate>
    </div>);

}
