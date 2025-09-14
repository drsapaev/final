import React, { useEffect, useMemo, useState } from 'react';
import Nav from '../components/layout/Nav.jsx';
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
 * Записи (Appointments): просмотр записей на дату (чтение).
 * Совместимо с GET /appointments?date=YYYY-MM-DD&limit=...
 * Для минимальных перезаписей реализуем только чтение и поиск.
 */
export default function Appointments() {
  const [page, setPage] = useState('Appointments');
  const [date, setDate] = useState(todayStr());
  const [rows, setRows] = useState([]);
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  async function load() {
    setBusy(true);
    setErr('');
    try {
      let res = await api.get('/appointments', { params: { date, limit: 200 } });
      if (!res || (!Array.isArray(res) && !Array.isArray(res?.items))) {
        // fallback на другой ключ параметра
        res = await api.get('/appointments', { params: { d: date, limit: 200 } });
      }
      const items = Array.isArray(res?.items) ? res.items : Array.isArray(res) ? res : [];
      setRows(items);
    } catch (e) {
      setErr(e?.data?.detail || e?.message || 'Ошибка загрузки записей');
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { load(); }, [date]);

  const filtered = useMemo(() => {
    if (!q) return rows;
    const qq = q.toLowerCase();
    return rows.filter(a =>
      String(a.patient_name || a.patient?.full_name || '').toLowerCase().includes(qq) ||
      String(a.doctor_name || a.doctor || '').toLowerCase().includes(qq) ||
      String(a.id || '').toLowerCase().includes(qq) ||
      String(a.status || '').toLowerCase().includes(qq)
    );
  }, [q, rows]);

  return (
    <div>
      <Nav active={page} onNavigate={setPage} />
      <RoleGate roles={['Admin', 'Registrar', 'Doctor']}>
        <div style={{ padding: 16, display: 'grid', gap: 12 }}>
          <h2 style={{ margin: 0 }}>Записи</h2>

          <div style={panel}>
            <label>
              Дата:&nbsp;
              <input type="date" value={date} onChange={(e)=>setDate(e.target.value)} style={inp}/>
            </label>
            <input placeholder="Поиск по пациенту/врачу/статусу/ID" value={q} onChange={(e)=>setQ(e.target.value)} style={{ ...inp, minWidth: 260 }}/>
            <button onClick={load} disabled={busy} style={btn}>{busy ? 'Загрузка' : 'Обновить'}</button>
          </div>

          {err && <div style={errBox}>{String(err)}</div>}

          <div style={{ overflow: 'auto', border: '1px solid #eee', borderRadius: 12, background: '#fff' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th style={th}>ID</th>
                  <th style={th}>Пациент</th>
                  <th style={th}>Врач</th>
                  <th style={th}>Время</th>
                  <th style={th}>Статус</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((a, i) => (
                  <tr key={a.id || i}>
                    <td style={td}>{a.id}</td>
                    <td style={td}>{a.patient_name || a.patient?.full_name || '—'}</td>
                    <td style={td}>{a.doctor_name || a.doctor || '—'}</td>
                    <td style={td}>
                      {(a.time || a.slot || a.start_time) ? (a.time || a.slot || a.start_time) : '—'}
                      {(a.end_time ? ` — ${a.end_time}` : '')}
                    </td>
                    <td style={td}>{a.status || '—'}</td>
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

