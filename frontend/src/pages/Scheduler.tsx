import { useEffect, useMemo, useState, useCallback } from 'react';
import RoleGate from '../components/RoleGate';
import { api } from '../api/client';
import { Input } from '../components/ui/macos';
import { useTranslation } from '../i18n/useTranslation';

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
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
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
      let res: any = await api.get('/schedule', { params: { date, limit: 200 } });
      if (!res || !Array.isArray(res) && !Array.isArray(res?.items)) {
        res = await api.get('/schedule', { params: { d: date, limit: 200 } });
      }
      const items = Array.isArray(res?.items) ? res.items : Array.isArray(res) ? res : [];
      setRows(items);
    } catch (e) {
      const err = e as { data?: { detail?: string }; message?: string };
      setErr(err?.data?.detail || err?.message || t('misc.sche_oshibka_zagruzki_raspisaniya'));
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
        <div className="clinic-ops-page-shell">
          <h2 style={{ margin: 0 }}>{t('misc.sche_raspisanie')}</h2>

          <div className="clinic-ops-toolbar">
            <label htmlFor="scheduler-date">
              Дата:&nbsp;
              <Input id="scheduler-date" className="clinic-ops-input" type="date" aria-label={t('misc.sche_data_raspisaniya')} value={date} onChange={(e) => setDate(e.target.value)} />
            </label>
            <Input className="clinic-ops-input" aria-label={t('misc.sche_poisk_po_vrachu_kabinetu_ili')} placeholder={t('misc.sche_poisk_po_vrachu_kabinetu_sta')} value={q} onChange={(e) => setQ(e.target.value)} style={{ minWidth: 260 }} />
            <button className="clinic-ops-button" onClick={load} disabled={busy}>{busy ? t('misc.sche_zagruzka') : t('misc.sche_obnovit')}</button>
          </div>

          {err && <div className="clinic-ops-error">{String(err)}</div>}

          <div className="clinic-ops-table-wrap">
            <div className="admin-table-wrapper">
<table className="clinic-ops-table">
              <thead>
                <tr>
                  <th>{t('common.doctor')}</th>
                  <th>{t('common.cabinet')}</th>
                  <th>{t('common.time')}</th>
                  <th>{t('common.status')}</th>
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
                    <td>{s.status || '—'}</td>
                  </tr>
                )}
                {filtered.length === 0 &&
                <tr><td colSpan={4}>{t('misc.sche_net_zapisey')}</td></tr>
                }
              </tbody>
            </table>
</div>
          </div>
        </div>
      </RoleGate>
    </div>);

}
