import { useEffect, useMemo, useState, useCallback } from 'react';
import RoleGate from '../components/RoleGate';
import AppointmentFlowRaw from '../components/AppointmentFlow';
const AppointmentFlow = AppointmentFlowRaw as unknown as React.ComponentType<Record<string, unknown>>;
import EnhancedAppointmentsTable from '../components/tables/EnhancedAppointmentsTable';
import {
  AppEmpty, AppError, Button, Card, CardContent, CardHeader, Checkbox, Input,
} from '../components/ui/macos';
import { api } from '../api/client';

import logger from '../utils/logger';
import { useTranslation } from '../i18n/useTranslation';
import type { CSSProperties } from 'react';
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
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
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
      let res: any = await api.get('/appointments', { params: { date, limit: 200 } });
      if (!res || (!Array.isArray(res) && !Array.isArray(res?.items))) {
        // fallback на другой ключ параметра
        res = await api.get('/appointments', { params: { d: date, limit: 200 } });
      }
      const items = Array.isArray(res?.items) ? res.items : Array.isArray(res) ? res : [];
      setRows(items);
    } catch (e) {
      const err = e as { data?: { detail?: string }; message?: string };
      setErr(err?.data?.detail || err?.message || t('misc.appo_oshibka_zagruzki_zapisey'));
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
  const isFilteredEmpty = q.trim().length > 0 && rows.length > 0 && filtered.length === 0;
  const toolbarStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    flexWrap: 'wrap'
  };
  const fieldStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    color: 'var(--mac-text-secondary)',
    fontSize: 13
  };
  const tableWrapStyle: CSSProperties = {
    overflowX: 'auto',
    border: '1px solid var(--mac-card-border)',
    borderRadius: 8,
    background: 'var(--mac-card-bg)',
    marginTop: 16
  };
  const tableStyle: CSSProperties = {
    width: '100%',
    borderCollapse: 'collapse'
  };

  return (
    <div>
      <RoleGate roles={['Admin', 'Registrar', 'Doctor']}>
        <Card>
          <CardHeader>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
              <h2 style={{ margin: 0, color: 'var(--mac-text-primary)' }}>{t('misc.appo_zapisi')}</h2>
              <span style={{ color: 'var(--mac-text-secondary)', fontSize: 13 }}>
                {filtered.length} из {rows.length}
              </span>
            </div>
          </CardHeader>

          <CardContent>
          <div style={toolbarStyle}>
            <label style={fieldStyle}>
              Дата:&nbsp;
              <Input type="date" value={date} onChange={(e)=>setDate(e.target.value)} />
            </label>
            <Input
              placeholder={t('misc.appo_poisk_po_patsientu_vrachu_st')}
              value={q}
              onChange={(e)=>setQ(e.target.value)}
              style={{ minWidth: 260 }}
              aria-label={t('misc.appo_poisk_po_zapisyam')}
            />
            <Button type="button" variant="outline" size="small" onClick={load} disabled={busy} loading={busy}>
              Обновить
            </Button>
            <Checkbox
              checked={useAdvancedTable}
              onChange={(next) => setUseAdvancedTable(next)}
              label={t('misc.appo_rasshirennaya_tablitsa')}
            />
          </div>

          {err && (
            <AppError
              title={t('misc.appo_ne_udalos_zagruzit_zapisi')}
              description={String(err)}
              action={
                <Button type="button" variant="outline" size="small" onClick={load} disabled={busy} loading={busy}>
                  Повторить
                </Button>
              }
            />
          )}

          {useAdvancedTable ? (
            <EnhancedAppointmentsTable
              appointments={filtered}
              appointmentsSelected={selectedAppointments}
              setAppointmentsSelected={setSelectedAppointments}
              updateAppointmentStatus={(id, status) => logger.log('Update status:', id, status)}
              setShowWizard={(show) => logger.log('Show wizard:', show)}
            />
          ) : (
            <div style={tableWrapStyle}>
              <div className="admin-table-wrapper">
<table style={tableStyle}>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>{t('common.patient')}</th>
                  <th>{t('common.doctor')}</th>
                  <th>{t('common.time')}</th>
                  <th>{t('common.status')}</th>
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
                      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}>
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
                  <tr>
                    <td colSpan={5}>
                      <AppEmpty
                        title={isFilteredEmpty ? t('misc.appo_zapisi_ne_naydeny') : t('misc.appo_net_zapisey_na_vybrannuyu_da')}
                        description={
                          isFilteredEmpty ?
                            t('misc.appo_izmenite_poisk_po_patsientu_') :
                            t('misc.appo_esli_zapis_tolko_chto_sozdan')
                        }
                      />
                    </td>
                  </tr>
                )}
              </tbody>
              </table>
</div>
            </div>
          )}
          </CardContent>
        </Card>
      </RoleGate>
    </div>
  );
}

