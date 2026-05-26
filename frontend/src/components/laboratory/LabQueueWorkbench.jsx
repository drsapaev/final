import PropTypes from 'prop-types';
import { Badge, Button, Card, CardContent, CardHeader, CardTitle, Icon, Alert } from '../ui/macos';
import {
  formatLabStatus,
  formatPaymentStatus,
  formatSeverityLabel,
  formatSpecialtyLabel,
  getLabStatusVariant
} from './labUiLabels';

const cardGridStyle = {
  display: 'grid',
  gap: '16px'
};

const queueCardStyle = {
  border: '1px solid var(--mac-border)',
  borderRadius: '16px',
  background: 'var(--mac-bg-primary)',
  padding: '16px',
  display: 'grid',
  gap: '12px'
};

const metaRowStyle = {
  display: 'flex',
  flexWrap: 'wrap',
  gap: '8px',
  alignItems: 'center'
};

const activeQueueStatuses = new Set([
  'waiting',
  'confirmed',
  'pending',
  'called',
  'in_progress'
]);

function formatServices(appointment) {
  const serviceDetails = appointment?.service_details || [];
  if (serviceDetails.length > 0) {
    return serviceDetails
      .map((item) => item?.name || item?.code)
      .filter(Boolean)
      .join(', ');
  }
  const services = appointment?.all_patient_services?.length
    ? appointment.all_patient_services
    : appointment?.services || [];
  if (!services.length) {
    return 'Нет данных об услугах';
  }
  return services.join(', ');
}

function historySeverityBadge(item) {
  if ((item.critical_findings_count || 0) > 0) {
    return { label: 'critical', variant: 'danger' };
  }
  if ((item.max_flag_severity || 0) >= 200) {
    return { label: 'flagged', variant: 'warning' };
  }
  if ((item.max_flag_severity || 0) >= 100) {
    return { label: 'warning', variant: 'warning' };
  }
  return { label: 'clean', variant: 'success' };
}

export default function LabQueueWorkbench({
  appointments,
  loading = false,
  onRefresh,
  onOpenAppointment,
  selectedAppointment = null,
  reportHistory = []
}) {
  return (
    <div style={{ display: 'grid', gap: '16px' }}>
      <Card variant="filled" padding="none">
        <CardHeader
          style={{
            background: 'var(--mac-bg-tertiary)',
            borderBottom: '1px solid var(--mac-border)',
            padding: '16px'
          }}
        >
          <CardTitle
            style={{
              margin: 0,
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}
          >
            <Icon name="testtube.2" size={20} />
            Очередь лаборатории
          </CardTitle>
          <div style={metaRowStyle}>
            <Badge variant="info">Всего: {appointments.length}</Badge>
            <Badge variant="warning">
              В работе: {appointments.filter((item) => activeQueueStatuses.has(item.status)).length}
            </Badge>
            <Button variant="outline" onClick={onRefresh} disabled={loading}>
              <Icon name="arrow.clockwise" size={16} />
              Обновить
            </Button>
          </div>
        </CardHeader>
        <CardContent style={{ padding: '16px', background: 'var(--mac-bg-secondary)' }}>
          {loading ? (
            <div style={{ padding: '24px', textAlign: 'center', color: 'var(--mac-text-secondary)' }}>
              Загрузка лабораторной очереди...
            </div>
          ) : appointments.length === 0 ? (
            <Alert severity="info">На сегодня не найдено лабораторных записей.</Alert>
          ) : (
            <div style={cardGridStyle}>
              {appointments.map((appointment) => {
                const isSelected = selectedAppointment?.id === appointment.id;
                return (
                  <div
                    key={appointment.id}
                    style={{
                      ...queueCardStyle,
                      borderColor: isSelected ? 'var(--mac-accent)' : 'var(--mac-border)',
                      boxShadow: isSelected ? '0 0 0 2px color-mix(in oklab, var(--mac-accent) 20%, transparent)' : 'none'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-start' }}>
                      <div style={{ display: 'grid', gap: '8px' }}>
                        <div style={{ fontSize: '18px', fontWeight: 600, color: 'var(--mac-text-primary)' }}>
                          {appointment.patient_fio || 'Пациент без имени'}
                        </div>
                      <div style={{ color: 'var(--mac-text-secondary)', fontSize: '14px' }}>
                        Визит: {appointment.visit_id || 'не привязан'} | Телефон: {appointment.patient_phone || 'не указан'}
                      </div>
                    </div>
                      <Badge variant={getLabStatusVariant(appointment.status)}>
                        {formatLabStatus(appointment.status)}
                      </Badge>
                    </div>

                    <div style={{ color: 'var(--mac-text-secondary)', fontSize: '14px', lineHeight: 1.5 }}>
                      <strong style={{ color: 'var(--mac-text-primary)' }}>Услуги:</strong> {formatServices(appointment)}
                    </div>

                    <div style={metaRowStyle}>
                      <Badge variant="primary">{formatSpecialtyLabel(appointment.specialty)}</Badge>
                      {appointment.payment_status && <Badge variant="info">Оплата: {formatPaymentStatus(appointment.payment_status)}</Badge>}
                      {appointment.appointment_time && <Badge variant="success">{appointment.appointment_time}</Badge>}
                      {appointment.report_template_name && <Badge variant="info">{appointment.report_template_name}</Badge>}
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'center' }}>
                      <div style={{ color: 'var(--mac-text-secondary)', fontSize: '13px' }}>
                        Пациент ID: {appointment.patient_id}
                      </div>
                      <Button variant="primary" onClick={() => onOpenAppointment(appointment)}>
                        <Icon name="doc.text" size={16} />
                        {appointment.report_instance_id ? 'Открыть бланк' : 'Открыть в редакторе'}
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {selectedAppointment && (
        <Card variant="filled" padding="none">
          <CardHeader
            style={{
              background: 'var(--mac-bg-tertiary)',
              borderBottom: '1px solid var(--mac-border)',
              padding: '16px'
            }}
          >
            <CardTitle style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Icon name="clock.arrow.circlepath" size={20} />
              История бланков пациента
            </CardTitle>
          </CardHeader>
          <CardContent style={{ padding: '16px', background: 'var(--mac-bg-secondary)' }}>
            {reportHistory.length === 0 ? (
              <Alert severity="info">Для выбранного пациента ещё нет лабораторных бланков.</Alert>
            ) : (
              <div style={{ display: 'grid', gap: '12px' }}>
                {reportHistory.map((item) => (
                  <div
                    key={item.id}
                    style={{
                      border: '1px solid var(--mac-border)',
                      borderRadius: '14px',
                      padding: '12px 14px',
                      background: 'var(--mac-bg-primary)',
                      display: 'flex',
                      justifyContent: 'space-between',
                      gap: '12px',
                      alignItems: 'center'
                    }}
                  >
                    <div style={{ display: 'grid', gap: '4px' }}>
                      <div style={{ fontWeight: 600, color: 'var(--mac-text-primary)' }}>
                        {item.template?.name || `Бланк #${item.id}`}
                      </div>
                      <div style={{ color: 'var(--mac-text-secondary)', fontSize: '13px' }}>
                        Создан: {new Date(item.created_at).toLocaleString()} | Статус: {formatLabStatus(item.status)}
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                      <Badge variant={getLabStatusVariant(item.status)}>
                        {formatLabStatus(item.status)}
                      </Badge>
                      <Badge variant={historySeverityBadge(item).variant}>
                        {formatSeverityLabel(historySeverityBadge(item).label)}
                      </Badge>
                      {item.flagged_findings_count > 0 && <Badge variant="info">{item.flagged_findings_count} флагов</Badge>}
                      {item.critical_findings_count > 0 && <Badge variant="danger">{item.critical_findings_count} критич.</Badge>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

LabQueueWorkbench.propTypes = {
  appointments: PropTypes.array.isRequired,
  loading: PropTypes.bool,
  onRefresh: PropTypes.func.isRequired,
  onOpenAppointment: PropTypes.func.isRequired,
  selectedAppointment: PropTypes.object,
  reportHistory: PropTypes.array
};
