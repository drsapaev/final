import React, { useEffect, useMemo, useState } from 'react';
import RoleGate from '../components/RoleGate.jsx';
import { api, getApiBase } from '../api/client.js';

/**
 * Касса: список начислений/платежей (по умолчанию — неоплаченные).
 * Совместимо с GET /payments?status=unpaid&limit=...
 * Печать счета через /print/invoice.pdf?visit_id=...
 */
export default function Cashier() {
  const [page, setPage] = useState('Cashier');
  const [status, setStatus] = useState('unpaid');
  const [rows, setRows] = useState([]);
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  async function load() {
    setBusy(true);
    setErr('');
    try {
      const res = await api.get('/payments', { params: { status, limit: 100 } });
      const items = Array.isArray(res?.items) ? res.items : Array.isArray(res) ? res : [];
      setRows(items);
    } catch (e) {
      setErr(e?.data?.detail || e?.message || 'Ошибка загрузки платежей');
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { load(); }, [status]);

  const filtered = useMemo(() => {
    if (!q) return rows;
    const qq = q.toLowerCase();
    return rows.filter(p =>
      String(p.patient_name || p.patient?.full_name || '').toLowerCase().includes(qq) ||
      String(p.id || '').toLowerCase().includes(qq) ||
      String(p.status || '').toLowerCase().includes(qq)
    );
  }, [q, rows]);

  async function printInvoice(p) {
    try {
      const base = new URL(getApiBase());
      const url = `${base.origin}${base.pathname.replace(/\/+$/, '')}/print/invoice.pdf?visit_id=${encodeURIComponent(p.visit_id || p.id)}`;
      const r = await fetch(url, { headers: { Accept: 'application/pdf' } });
      const buf = await r.arrayBuffer();
      const blob = new Blob([buf], { type: 'application/pdf' });
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = `invoice_${p.visit_id || p.id}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(link.href);
    } catch (e) {
      alert('Не удалось напечатать счет');
    }
  }

  return (
    <div>
      <RoleGate roles={['Admin', 'Cashier']}>
        <div style={{ padding: 16, display: 'grid', gap: 12 }}>
          <h2 style={{ margin: 0 }}>Касса</h2>

          <div style={panel}>
            <label>
              Статус:&nbsp;
              <select value={status} onChange={(e)=>setStatus(e.target.value)} style={inp}>
                <option value="">все</option>
                <option value="unpaid">неоплачено</option>
                <option value="paid">оплачено</option>
                <option value="void">возврат/аннулир.</option>
              </select>
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
                  <th style={th}>Сумма</th>
                  <th style={th}>Статус</th>
                  <th style={th}>Действия</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(p => (
                  <tr key={p.id}>
                    <td style={td}>{p.id}</td>
                    <td style={td}>{p.patient_name || p.patient?.full_name || '—'}</td>
                    <td style={td}>{p.amount != null ? Number(p.amount).toFixed(0) : '—'}</td>
                    <td style={td}>{p.status || '—'}</td>
                    <td style={td}>
                      <button onClick={() => printInvoice(p)} style={btnSmall}>Печать счёта</button>
                    </td>
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
const btnSmall = { padding: '4px 8px', borderRadius: 8, border: '1px solid #ddd', background: '#fff', cursor: 'pointer' };
const th = { textAlign: 'left', padding: 10, borderBottom: '1px solid #eee', fontWeight: 700, whiteSpace: 'nowrap' };
const td = { padding: 10, borderBottom: '1px solid #f3f4f6', verticalAlign: 'top' };
const errBox = { color: '#7f1d1d', background: '#fee2e2', border: '1px solid #fecaca', borderRadius: 8, padding: 8 };

