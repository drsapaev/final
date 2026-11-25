import { useEffect, useMemo, useState, useCallback, useRef } from 'react';
import RoleGate from '../components/RoleGate';
import AppointmentFlow from '../components/AppointmentFlow';
import EnhancedAppointmentsTable from '../components/tables/EnhancedAppointmentsTable';
import {
  AppEmpty, AppError, Button, Card, CardContent, CardHeader, Checkbox, Input,
} from '../components/ui/macos';
import { api } from '../api/client';
import { getCalendarDoctorId, listRescheduledCalendarVisits } from '../api/appointments';

import logger from '../utils/logger';
import auth from '../stores/auth';
import { getLocalDateString } from '../utils/dateUtils';
import { useTranslation } from '../i18n/useTranslation';
import type { CSSProperties } from 'react';
import type { CalendarRescheduledVisit } from '../types/domain/clinic';

interface AppointmentRow {
  id?: string | number;
  patient_name?: string;
  patient?: { full_name?: string; [key: string]: unknown } | null;
  doctor_name?: string;
  doctor?: string;
  time?: string;
  slot?: string;
  start_time?: string;
  end_time?: string;
  status?: string;
  [key: string]: unknown;
}

/** Read-only scheduled appointments, filtered by the clinic calendar day. */
export default function Appointments() {
  const { t: rawT } = useTranslation();
  const t = rawT;
  const [date, setDate] = useState(getLocalDateString);
  const [rows, setRows] = useState<AppointmentRow[]>([]);
  const [movedVisits, setMovedVisits] = useState<CalendarRescheduledVisit[]>([]);
  const latestRequest = useRef(0);
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [movedErr, setMovedErr] = useState<string | null>(null);
  const [useAdvancedTable, setUseAdvancedTable] = useState(false);
  const [selectedAppointments, setSelectedAppointments] = useState<Set<unknown>>(new Set<unknown>());

  const load = useCallback(async () => {
    const requestId = ++latestRequest.current;
    setErr(null);
    setMovedErr(null);
    if (!date) {
      setRows([]);
      setMovedVisits([]);
      setBusy(false);
      return;
    }

    setBusy(true);
    try {
      const profile = auth.getState().profile;
      const role = String(profile?.role ?? profile?.role_name ?? '').toLowerCase();
      let doctorId: number | undefined;
      if (role === 'doctor' && profile?.is_superuser !== true) {
        if (profile?.id == null) throw new Error('Doctor profile could not be loaded');
        doctorId = await getCalendarDoctorId(profile.id);
      }
      if (requestId !== latestRequest.current) return;
      const [scheduled, moved] = await Promise.allSettled([
        api.get<AppointmentRow[]>('/appointments', {
          params: { date_from: date, date_to: date, limit: 200, ...(doctorId == null ? {} : { doctor_id: doctorId }) },
        }),
        listRescheduledCalendarVisits(date, doctorId),
      ]);
      if (requestId === latestRequest.current) {
        setRows(scheduled.status === 'fulfilled' ? scheduled.value.data : []);
        setMovedVisits(moved.status === 'fulfilled' ? moved.value : []);
        if (scheduled.status === 'rejected') setErr('');
        if (moved.status === 'rejected') setMovedErr('');
      }
    } catch (e) {
      if (requestId !== latestRequest.current) return;
      const err = e as { data?: { detail?: string }; message?: string };
      setRows([]);
      setMovedVisits([]);
      setErr(err?.data?.detail || err?.message || '');
    } finally {
      if (requestId === latestRequest.current) setBusy(false);
    }
  }, [date]);

  useEffect(() => {
    void load();
    return () => { latestRequest.current += 1; };
  }, [load]);

  const changeDate = (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const nextDate = event.target.value;
    if (nextDate === date) return;
    latestRequest.current += 1;
    setRows([]);
    setMovedVisits([]);
    setErr(null);
    setMovedErr(null);
    setBusy(Boolean(nextDate));
    setDate(nextDate);
  };

  const filtered = useMemo(() => {
    if (!q) return rows;
    const qq = q.toLowerCase();
    return rows.filter((a: AppointmentRow) =>
      String(a.patient_name || a.patient?.full_name || '').toLowerCase().includes(qq) ||
      String(a.doctor_name || a.doctor || '').toLowerCase().includes(qq) ||
      String(a.id || '').toLowerCase().includes(qq) ||
      String(a.status || '').toLowerCase().includes(qq)
    );
  }, [q, rows]);
  const movedFiltered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return movedVisits.filter(row => [row.patientName, row.doctorName, row.status, String(row.visitId)]
      .some(value => value?.toLowerCase().includes(needle)));
  }, [movedVisits, q]);
  const isFilteredEmpty = q.trim().length > 0 && rows.length + movedVisits.length > 0
    && filtered.length + movedFiltered.length === 0;
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
                {filtered.length + movedFiltered.length} из {rows.length + movedVisits.length}
              </span>
            </div>
          </CardHeader>

          <CardContent>
          <div style={toolbarStyle}>
            <label style={fieldStyle}>
              Дата:&nbsp;
              <Input type="date" value={date} onChange={changeDate} />
            </label>
            <Input
              placeholder={t('misc.appo_poisk_po_patsientu_vrachu_st')}
              value={q}
              onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>)=>setQ(e.target.value)}
              style={{ minWidth: 260 }}
              aria-label={t('misc.appo_poisk_po_zapisyam')}
            />
            <Button type="button" variant="outline" size="small" onClick={load} disabled={busy} loading={busy}>
              Обновить
            </Button>
            <Checkbox
              checked={useAdvancedTable}
              onChange={(next: boolean) => setUseAdvancedTable(next)}
              label={t('misc.appo_rasshirennaya_tablitsa')}
            />
          </div>

          {err !== null && (
            <AppError
              title={t('misc.appo_ne_udalos_zagruzit_zapisi')}
              description={err || t('misc.appo_oshibka_zagruzki_zapisey')}
              action={
                <Button type="button" variant="outline" size="small" onClick={load} disabled={busy} loading={busy}>
                  Повторить
                </Button>
              }
            />
          )}

          {useAdvancedTable ? (
            <EnhancedAppointmentsTable
              // PR-UI-12-4 fix (pre-existing dead-prop bug): EAT's canonical
              // rows prop is `data` (every other consumer — registrar
              // WelcomeView, cardiology AppointmentsTab, doctor panels —
              // passes it); the legacy `appointments` prop exists in EAT's
              // interface but is never destructured, so the "Расширенная
              // таблица" toggle has always rendered an EMPTY table on this
              // screen. Passing `data` makes the advanced table actually
              // render — required for the PR-UI-12-4 sticky-header wiring on
              // the Appointments surface to be observable.
              data={filtered}
              appointmentsSelected={selectedAppointments}
              setAppointmentsSelected={setSelectedAppointments}
              updateAppointmentStatus={(id: unknown, status: unknown) => logger.log('Update status:', id, status)}
              setShowWizard={(show: boolean) => logger.log('Show wizard:', show)}
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
                {filtered.map((a: AppointmentRow, i: number) => (
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
                            onStartVisit={(appointment: import('../components/AppointmentFlow').AppointmentFlowAppointment) => logger.log('Start visit:', appointment)}
                            onPayment={(appointment: import('../components/AppointmentFlow').AppointmentFlowAppointment) => logger.log('Payment:', appointment)}
                          />
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
                {!busy && err === null && movedErr === null && filtered.length + movedFiltered.length === 0 && (
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
          {movedErr !== null && (
            <AppError
              title={t('misc.srch_section_visits')}
              description={t('misc.appo_ne_udalos_zagruzit_zapisi')}
              action={
                <Button type="button" variant="outline" size="small" onClick={load} disabled={busy}>
                  Повторить
                </Button>
              }
            />
          )}
          {movedFiltered.length > 0 && (
            <section aria-labelledby="rescheduled-visits-title">
              <h3 id="rescheduled-visits-title">{t('misc.srch_section_visits')}</h3>
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
                  {movedFiltered.map(row => (
                    <tr key={row.visitId}>
                      <td>{row.visitId}</td>
                      <td>{row.patientName || '—'}</td>
                      <td>{row.doctorName || '—'}</td>
                      <td>{row.scheduledTime || t('admin2.appt_time_not_specified')}</td>
                      <td>{row.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}
          </CardContent>
        </Card>
      </RoleGate>
    </div>
  );
}

