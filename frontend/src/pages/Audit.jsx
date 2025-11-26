import React, { useEffect, useMemo, useState } from 'react';
import RoleGate from '../components/RoleGate.jsx';
import { api } from '../api/client.js';

/**
 * Аудит: список последних действий пользователей.
 * Совместимо с GET /audit?limit=...&offset=...
 */
export default function Audit() {
  const [page, setPage] = useState('Audit');
  const [rows, setRows] = useState([]);
  const [limit, setLimit] = useState(100);
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  async function load() {
    setBusy(true);
    setErr('');
    try {
      const res = await api.get('/audit', { params: { limit } });
      const items = Array.isArray(res?.items) ? res.items : Array.isArray(res) ? res : [];
      setRows(items);
    } catch (e) {
      setErr(e?.data?.detail || e?.message || 'Ошибка загрузки аудита');
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { load(); }, [limit]);

  const filtered = useMemo(() => {
    if (!q) return rows;
    const qq = q.toLowerCase();
    return rows.filter(a =>
      String(a.user || a.username || '').toLowerCase().includes(qq) ||
      String(a.action || '').toLowerCase().includes(qq) ||
      String(a.entity || '').toLowerCase().includes(qq) ||
      String(a.id || '').toLowerCase().includes(qq)
    );
  }, [q, rows]);

  return (
    <div>
      <RoleGate roles={['Admin']}>
        <div style={{ padding: 16, display: 'grid', gap: 12 }}>
          <h2 style={{ margin: 0 }}>Аудит</h2>

          <div style={panel}>
            <label>
              Порог:&nbsp;
              <input type="number" min={10} max={1000} value={limit} onChange={(e)=>setLimit(Number(e.target.value)||100)} style={inp}/>
            </label>
            <input placeholder="Поиск по пользователю/действию/сущности" value={q} onChange={(e)=>setQ(e.target.value)} style={{ ...inp, minWidth: 260 }}/>
            <button onClick={load} disabled={busy} style={btn}>{busy ? 'Загрузка' : 'Обновить'}</button>
          </div>

          {err && <div style={errBox}>{String(err)}</div>}

          <div style={{ overflow: 'auto', border: '1px solid #eee', borderRadius: 12, background: '#fff' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th style={th}>Время</th>
                  <th style={th}>Пользователь</th>
                  <th style={th}>Действие</th>
                  <th style={th}>Сущность</th>
                  <th style={th}>Детали</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((a, i) => (
                  <tr key={a.id || i}>
                    <td style={td}>{a.created_at || a.time || '—'}</td>
                    <td style={td}>{a.user || a.username || '—'}</td>
                    <td style={td}>{a.action || '—'}</td>
                    <td style={td}>{a.entity || a.table || '—'}</td>
                    <td style={td}><code style={{ fontSize: 12 }}>{a.details ? JSON.stringify(a.details) : '—'}</code></td>
                  </tr>
                ))}
                {filtered.length === 0 && (
                  <tr><td style={td} colSpan={5}>Нет записей</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </RoleGate>
    </div>
  );
}

const panel = { display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', border: '1px solid #eee', borderRadius: 12, padding: 12, background: '#fff' };
const inp = { padding: '6px 10px', border: '1px solid #ddd', borderRadius: 8, background: '#fff' };
const btn = { padding: '6px 10px', borderRadius: 8, border: '1px solid #ddd', background: '#fff', cursor: 'pointer' };
const th = { textAlign: 'left', padding: 10, borderBottom: '1px solid #eee', fontWeight: 700, whiteSpace: 'nowrap' };
const td = { padding: 10, borderBottom: '1px solid #f3f4f6', verticalAlign: 'top' };
const errBox = { color: '#7f1d1d', background: '#fee2e2', border: '1px solid #fecaca', borderRadius: 8, padding: 8 };

