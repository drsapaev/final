import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';

import { getVisit, rescheduleVisit } from '../api';
import RescheduleDialog from '../components/RescheduleDialog';
import { Button, MacOSCard, Badge } from '../components/ui/macos';
import MacOSEmptyState from '../components/ui/macos/MacOSEmptyState';

import { getErrorMessage } from '../utils/errorHandler';
import logger from '../utils/logger';
import { getCanonicalRouteById } from '../routing/routeSelectors.js';

const clinicalAppointmentsPath = getCanonicalRouteById('clinical-appointments')?.path || '/clinical/appointments';

function normalizeVisitDetailPayload(data) {
  if (!data) return null;
  const baseVisit = data.visit && typeof data.visit === 'object' ? data.visit : data;
  const services = Array.isArray(data.services) ? data.services : baseVisit.services;
  return {
    ...baseVisit,
    services: Array.isArray(services) ? services : [],
  };
}

function resolvePatientName(visit) {
  return (
    visit?.patient?.full_name ||
    visit?.patient_fio ||
    visit?.patient_name ||
    (visit?.patient_id ? `Пациент #${visit.patient_id}` : '—')
  );
}

function resolveDoctorName(visit) {
  const doctorName = visit?.doctor?.name || visit?.doctor_name;
  const cabinet = visit?.doctor?.cabinet || visit?.room;
  if (doctorName && cabinet) return `${doctorName} / ${cabinet}`;
  return doctorName || cabinet || (visit?.doctor_id ? `Врач #${visit.doctor_id}` : '—');
}

function resolveVisitSchedule(visit) {
  return visit?.scheduled_at || visit?.planned_date || visit?.visit_date || null;
}

function resolveStatusLabel(status) {
  const labels = {
    pending: 'Ожидает',
    confirmed: 'Подтверждена',
    paid: 'Оплачена',
    in_visit: 'На приёме',
    completed: 'Завершена',
    cancelled: 'Отменена',
    no_show: 'Неявка',
  };
  return labels[status] || status || '—';
}

function resolveStatusVariant(status) {
  if (status === 'completed' || status === 'paid') return 'success';
  if (status === 'cancelled' || status === 'no_show') return 'error';
  if (status === 'in_visit' || status === 'confirmed') return 'warning';
  return 'default';
}

/**
 * VisitDetails page — macOS native redesign
 * - Shows visit information in MacOSCard layout
 * - Allows opening RescheduleDialog
 * - Quick actions: reschedule to tomorrow (one-click)
 *
 * Route: clinical-visit-details in routeRegistry
 */
function VisitDetails() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [visit, setVisit] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [dialogOpen, setDialogOpen] = useState(false);

  useEffect(() => {
    if (!id) return;
    let mounted = true;
    setLoading(true);
    setError('');
    getVisit(id).
    then((data) => {
      if (!mounted) return;
      setVisit(normalizeVisitDetailPayload(data));
    }).
    catch((err) => {
      logger.error('getVisit error:', err);
      setError(getErrorMessage(err, 'Не удалось загрузить приём. Проверьте соединение и попробуйте снова.'));
    }).
    finally(() => {
      if (mounted) setLoading(false);
    });
    return () => {
      mounted = false;
    };
  }, [id]);

  const handleRescheduled = (updated) => {
    setVisit((prev) => ({ ...(prev || {}), ...(updated || {}) }));
  };

  const rescheduleTomorrow = async () => {
    if (!visit) return;
    setLoading(true);
    setError('');
    try {
      const scheduledAt = resolveVisitSchedule(visit);
      const baseDate = scheduledAt ? new Date(scheduledAt) : new Date();
      const tomorrow = new Date(baseDate);
      tomorrow.setDate(baseDate.getDate() + 1);
      const iso = tomorrow.toISOString();
      const res = await rescheduleVisit(visit.id, iso);
      setVisit((prev) => normalizeVisitDetailPayload({ ...(prev || {}), scheduled_at: iso, ...(res || {}) }));
    } catch (err) {
      logger.error('rescheduleTomorrow error:', err);
      setError(getErrorMessage(err, 'Не удалось перенести приём. Проверьте соединение и попробуйте снова.'));
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div style={{ padding: 'var(--mac-spacing-6)' }}>
        <div style={{ color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-base)' }}>
          Загрузка приёма...
        </div>
      </div>
    );
  }

  if (!visit) {
    return (
      <div style={{ padding: 'var(--mac-spacing-6)' }}>
        <MacOSEmptyState
          icon="alert.circle"
          title="Приём не найден"
          description={error || 'Запись не найдена или была удалена.'}
          action={
            <Link to="/">
              <Button variant="outline" size="small">Вернуться на главную</Button>
            </Link>
          }
        />
      </div>
    );
  }

  return (
    <div style={{ padding: 'var(--mac-spacing-6)', maxWidth: '48rem', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: 'var(--mac-spacing-4)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h1 style={{ fontSize: 'var(--mac-font-size-2xl)', fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-primary)', margin: 0 }}>
          Детали приёма #{visit.id}
        </h1>
        <div style={{ display: 'flex', gap: 'var(--mac-spacing-2)' }}>
          <Button
            variant="outline"
            size="small"
            onClick={() => setDialogOpen(true)}>
            Перенести
          </Button>
          <Button
            variant="primary"
            size="small"
            onClick={rescheduleTomorrow}
            disabled={loading}>
            На завтра
          </Button>
        </div>
      </div>

      {/* Visit info card */}
      <MacOSCard style={{ padding: 'var(--mac-spacing-5)', marginBottom: 'var(--mac-spacing-4)' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--mac-spacing-4)' }}>
          <div>
            <div style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)', marginBottom: 'var(--mac-spacing-1)' }}>
              Пациент
            </div>
            <div style={{ fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-primary)' }}>
              {resolvePatientName(visit)}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)', marginBottom: 'var(--mac-spacing-1)' }}>
              Статус
            </div>
            <Badge variant={resolveStatusVariant(visit.status)}>
              {resolveStatusLabel(visit.status)}
            </Badge>
          </div>
          <div>
            <div style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)', marginBottom: 'var(--mac-spacing-1)' }}>
              Запланировано
            </div>
            <div style={{ fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-primary)' }}>
              {resolveVisitSchedule(visit) ? new Date(resolveVisitSchedule(visit)).toLocaleString() : '—'}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)', marginBottom: 'var(--mac-spacing-1)' }}>
              Врач / кабинет
            </div>
            <div style={{ fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-primary)' }}>
              {resolveDoctorName(visit)}
            </div>
          </div>
        </div>

        {visit.notes && (
          <div style={{ marginTop: 'var(--mac-spacing-4)' }}>
            <div style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)', marginBottom: 'var(--mac-spacing-1)' }}>
              Примечание
            </div>
            <div style={{ color: 'var(--mac-text-primary)' }}>
              {visit.notes}
            </div>
          </div>
        )}

        {visit.services && visit.services.length > 0 && (
          <div style={{ marginTop: 'var(--mac-spacing-4)' }}>
            <div style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)', marginBottom: 'var(--mac-spacing-1)' }}>
              Услуги
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--mac-spacing-2)' }}>
              {visit.services.map((service, idx) => (
                <Badge key={idx} variant="default">
                  {service.name || service.service_name || `Услуга #${service.id || idx}`}
                </Badge>
              ))}
            </div>
          </div>
        )}
      </MacOSCard>

      {/* Actions */}
      <div style={{ display: 'flex', gap: 'var(--mac-spacing-2)' }}>
        <Button
          variant="outline"
          size="small"
          onClick={() => navigate(-1)}>
          Назад
        </Button>
        <Link to={clinicalAppointmentsPath}>
          <Button variant="outline" size="small">
            Список приёмов
          </Button>
        </Link>
      </div>

      <RescheduleDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        visit={visit}
        onRescheduled={(u) => { handleRescheduled(u); setDialogOpen(false); }} />
    </div>
  );
}

export default VisitDetails;
