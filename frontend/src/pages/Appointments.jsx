import { useEffect, useMemo, useState, useCallback } from 'react';
import Nav from '../components/layout/Nav.jsx';
import RoleGate from '../components/RoleGate.jsx';
import AppointmentFlow from '../components/AppointmentFlow.jsx';
import EnhancedAppointmentsTable from '../components/tables/EnhancedAppointmentsTable.jsx';
import { api } from '../api/client.js';

import logger from '../utils/logger';
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
  const [useAdvancedTable, setUseAdvancedTable] = useState(false);
  const [selectedAppointments, setSelectedAppointments] = useState(new Set());

  const load = useCallback(async () => {
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
  }, [date]);

  useEffect(() => { load(); }, [load]);

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
        <div className="legacy-page-shell">
          <h2 style={{ margin: 0 }}>Записи</h2>

          <div className="legacy-toolbar">
            <label>
              Дата:&nbsp;
              <input className="legacy-input" type="date" value={date} onChange={(e)=>setDate(e.target.value)} />
            </label>
            <input className="legacy-input" placeholder="Поиск по пациенту/врачу/статусу/ID" value={q} onChange={(e)=>setQ(e.target.value)} style={{ minWidth: 260 }} />
            <button className="legacy-button" onClick={load} disabled={busy}>{busy ? 'Загрузка' : 'Обновить'}</button>
            <label>
              <input 
                type="checkbox" 
                checked={useAdvancedTable} 
                onChange={(e) => setUseAdvancedTable(e.target.checked)} 
              />
              &nbsp;Расширенная таблица
            </label>
          </div>

          {err && <div className="legacy-error">{String(err)}</div>}

          {useAdvancedTable ? (
            <EnhancedAppointmentsTable
              appointments={filtered}
              appointmentsSelected={selectedAppointments}
              setAppointmentsSelected={setSelectedAppointments}
              updateAppointmentStatus={(id, status) => logger.log('Update status:', id, status)}
              setShowWizard={(show) => logger.log('Show wizard:', show)}
            />
          ) : (
            <div className="legacy-table-wrap">
              <table className="legacy-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Пациент</th>
                  <th>Врач</th>
                  <th>Время</th>
                  <th>Статус</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((a, i) => (
                  <tr key={a.id || i}>
                    <td>{a.id}</td>
                    <td>{a.patient_name || a.patient?.full_name || '—'}</td>
                    <td>{a.doctor_name || a.doctor || '—'}</td>
                    <td>
                      {(a.time || a.slot || a.start_time) ? (a.time || a.slot || a.start_time) : '—'}
                      {(a.end_time ? ` — ${a.end_time}` : '')}
                    </td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        {a.status || '—'}
                        {a.status && (
                          <AppointmentFlow 
                            appointment={a}
                            onStartVisit={(appointment) => logger.log('Start visit:', appointment)}
                            onPayment={(appointment) => logger.log('Payment:', appointment)}
                          />
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
                {filtered.length === 0 && (
                  <tr><td colSpan={5}>Нет записей</td></tr>
                )}
              </tbody>
              </table>
            </div>
          )}
        </div>
      </RoleGate>
    </div>
  );
}

