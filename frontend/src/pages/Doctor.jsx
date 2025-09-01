import React, { useEffect, useMemo, useState } from 'react';
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
 * Экран врача: список визитов за день (только чтение).
 * Минимальные зависимости от API: GET /visits?d=YYYY-MM-DD&limit=... (или просто /visits).
 */
export default function Doctor() {
  const [page, setPage] = useState('Doctor');
  const [date, setDate] = useState(todayStr());
  const [rows, setRows] = useState([]);
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  async function load() {
    setBusy(true);
    setErr('');
    try {
      // Параметры максимально нейтральные: если backend не понимает d, просто вернёт все.
      const res = await api.get('/visits', { params: { d: date, limit: 100 } });
      const items = Array.isArray(res?.items) ? res.items : Array.isArray(res) ? res : [];
      setRows(items);
    } catch (e) {
      setErr(e?.data?.detail || e?.message || 'Ошибка загрузки списка визитов');
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { load(); }, [date]);

  const filtered = useMemo(() => {
    if (!q) return rows;
    const qq = q.toLowerCase();
    return rows.filter(v =>
      String(v.patient_name || v.patient?.full_name || v.patient?.name || '')
        .toLowerCase().includes(qq) ||
      String(v.id || '').toLowerCase().includes(qq) ||
      String(v.status || '').toLowerCase().includes(qq)
    );
  }, [q, rows]);

  return (
    <div>
      <RoleGate roles={['Admin', 'Doctor']}>
        <div style={{ padding: 16, display: 'grid', gap: 12 }}>
          <h2 style={{ margin: 0 }}>Врач</h2>

          <div style={panel}>
            <label>
              Дата:&nbsp;
              <input type="date" value={date} onChange={(e)=>setDate(e.target.value)} style={inp}/>
            </label>
            <input placeholder="Поиск по пациенту/статусу/ID" value={q} onChange={(e)=>setQ(e.target.value)} style={{ ...inp, minWidth: 240 }}/>
            <button onClick={load} disabled={busy} style={btn}>
              {busy ? 'Загрузка' : 'Обновить'}
            </button>
          </div>

          {err && <div style={errBox}>{String(err)}</div>}

          <div style={{ overflow: 'auto', border: '1px solid #eee', borderRadius: 12, background: '#fff' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th style={th}>ID</th>
                  <th style={th}>Пациент</th>
                  <th style={th}>Услуги</th>
                  <th style={th}>Статус</th>
                  <th style={th}>Время</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(v => (
                  <tr key={v.id}>
                    <td style={td}>{v.id}</td>
                    <td style={td}>{v.patient_name || v.patient?.full_name || v.patient?.name || '—'}</td>
                    <td style={td}>
                      {(v.services || v.items || []).map((s, i) => (
                        <span key={s.id || i}>
                          {s.name || s.title || s.code || 'усл.'}{i < (v.services||v.items||[]).length-1 ? ', ' : ''}
                        </span>
                      ))}
                    </td>
                    <td style={td}>{v.status || '—'}</td>
                    <td style={td}>{v.created_at || v.started_at || '—'}</td>
                  </tr>
                ))}
                {filtered.length === 0 && (
                  <tr>
                    <td style={td} colSpan={5}>Нет записей</td>
                  </tr>
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

