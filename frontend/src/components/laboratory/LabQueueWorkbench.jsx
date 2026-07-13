import PropTypes from 'prop-types';
import { useState } from 'react';
import {
  Badge, Button, Card, CardContent, CardHeader, CardTitle, Icon, Alert,
  Input } from '../ui/macos';
import {
  formatLabStatus,
  formatPaymentStatus,
  formatSeverityLabel,
  formatSpecialtyLabel,
  getLabStatusVariant
} from './labUiLabels';

// P-05 fix: маскирование PII (номера телефона) в карточках очереди.
// Лабораторное помещение — публичное пространство, экран видят другие
// пациенты и сотрудники. Раскрытие — по клику, с обратной маской.
// Маска сохраняет последние 2 цифры (для опознания пациента) и страну.
function maskPhone(phone) {
  if (!phone || typeof phone !== 'string') return '';
  const trimmed = phone.trim();
  if (!trimmed) return '';
  // Сохраняем +country code (до первого пробела) и последние 2 цифры
  const digits = trimmed.replace(/\D/g, '');
  if (digits.length < 4) return '***';
  const lastTwo = digits.slice(-2);
  // Если есть +country — сохраняем её
  const countryMatch = trimmed.match(/^\+\d{1,3}/);
  const country = countryMatch ? countryMatch[0] : '+';
  return `${country} ***-**-${lastTwo}`;
}

// P-05 fix: компонент-обёртка для переключения маска/открыто.
// Раскрытие может быть ограничено ролью через prop canReveal.
function MaskedPhone({ phone, canReveal = true }) {
  const [revealed, setRevealed] = useState(false);
  if (!phone) return <span style={{ color: 'var(--mac-text-secondary)' }}>не указан</span>;
  if (!canReveal) {
    return <span>{maskPhone(phone)}</span>;
  }
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        setRevealed((v) => !v);
      }}
      title={revealed ? 'Скрыть номер' : 'Показать номер (доступ ограничен)'}
      aria-label={revealed ? 'Скрыть номер телефона' : 'Показать номер телефона'}
      style={{
        background: 'none',
        border: 'none',
        padding: 0,
        cursor: 'pointer',
        color: 'inherit',
        font: 'inherit',
        textDecoration: 'underline dotted',
        textUnderlineOffset: '2px',
      }}
    >
      {revealed ? phone : maskPhone(phone)}
    </button>
  );
}

MaskedPhone.propTypes = {
  phone: PropTypes.string,
  canReveal: PropTypes.bool,
};

const cardGridStyle = {
  display: 'grid',
  gap: 'var(--mac-spacing-4)'
};

const queueCardStyle = {
  border: '1px solid var(--mac-border)',
  borderRadius: 'var(--mac-radius-xl)',
  background: 'var(--mac-bg-primary)',
  padding: 'var(--mac-spacing-4)',
  display: 'grid',
  gap: 'var(--mac-spacing-3)'
};

const metaRowStyle = {
  display: 'flex',
  flexWrap: 'wrap',
  gap: 'var(--mac-spacing-2)',
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
  // QW-8 fix: локальный state поиска и фильтра статусов.
  // Раньше при 30+ записях в очереди лаборант вынужден был скроллить
  // и визуально искать нужного пациента. Теперь — мгновенный поиск
  // по ФИО + фильтр по статусу (waiting/in_progress/completed).
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  // PR-64 / Medium-14: client-side sorting
  const [sortBy, setSortBy] = useState('default'); // default | name | time

  const normalizedSearch = searchQuery.trim().toLowerCase();
  const filteredAppointments = appointments.filter((appointment) => {
    // Фильтр по статусу
    if (statusFilter === 'active' && !activeQueueStatuses.has(appointment.status)) {
      return false;
    }
    if (statusFilter === 'completed' && !['completed', 'done'].includes(appointment.status)) {
      return false;
    }
    // Фильтр по поиску (ФИО, телефон, ID)
    if (normalizedSearch) {
      const haystack = [
        appointment.patient_fio,
        appointment.patient_phone,
        String(appointment.patient_id || ''),
        String(appointment.visit_id || ''),
      ].filter(Boolean).join(' ').toLowerCase();
      if (!haystack.includes(normalizedSearch)) return false;
    }
    return true;
  });

  // PR-64 / Medium-14: client-side sorting
  const sortedAppointments = [...filteredAppointments].sort((a, b) => {
    if (sortBy === 'name') {
      return (a.patient_fio || '').localeCompare(b.patient_fio || '', 'ru');
    }
    if (sortBy === 'time') {
      return (a.appointment_time || '').localeCompare(b.appointment_time || '');
    }
    return 0; // default = backend order
  });

  return (
    <div style={{ display: 'grid', gap: 'var(--mac-spacing-4)' }}>
      <Card variant="filled" padding="none">
        <CardHeader
          style={{
            background: 'var(--mac-bg-tertiary)',
            borderBottom: '1px solid var(--mac-border)',
            padding: 'var(--mac-spacing-4)'
          }}
        >
          <CardTitle
            style={{
              margin: 0,
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--mac-spacing-2)'
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
          {/* QW-8 fix: панель поиска и фильтра статусов. */}
          <div
            style={{
              display: 'flex',
              gap: 'var(--mac-spacing-3)',
              flexWrap: 'wrap',
              marginTop: 'var(--mac-spacing-3)',
              alignItems: 'center',
            }}
          >
            <div
              style={{
                position: 'relative',
                flex: '1 1 240px',
                minWidth: '200px',
              }}
            >
              <Icon
                name="magnifyingglass"
                size={14}
                styleAttr={{
                  position: 'absolute',
                  left: '10px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: 'var(--mac-text-muted)',
                  pointerEvents: 'none',
                }}
              />
              <Input
                type="search"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Поиск по ФИО, телефону, ID…"
                aria-label="Поиск по очереди лаборатории"
                style={{
                  width: '100%',
                  padding: '8px 12px 8px 32px',
                  borderRadius: 'var(--mac-radius-lg)',
                  border: '1px solid var(--mac-border)',
                  background: 'var(--mac-bg-primary)',
                  color: 'var(--mac-text-primary)',
                  fontSize: 'var(--mac-font-size-base)',
                  outline: 'none',
                }}
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery('')}
                  aria-label="Очистить поиск"
                  style={{
                    position: 'absolute',
                    right: '8px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    color: 'var(--mac-text-muted)',
                    padding: 'var(--mac-spacing-1)',
                    fontSize: 'var(--mac-font-size-lg)',
                    lineHeight: 1,
                  }}
                >
                  ×
                </button>
              )}
            </div>
            <div
              role="group"
              aria-label="Фильтр по статусу"
              style={{ display: 'flex', gap: 'var(--mac-spacing-1)' }}
            >
              {[
                { key: 'all',        label: 'Все' },
                { key: 'active',     label: 'В работе' },
                { key: 'completed',  label: 'Завершены' },
              ].map((opt) => (
                <button
                  key={opt.key}
                  type="button"
                  onClick={() => setStatusFilter(opt.key)}
                  aria-pressed={statusFilter === opt.key}
                  style={{
                    padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
                    borderRadius: 'var(--mac-radius-md)',
                    border: `1px solid ${statusFilter === opt.key ? 'var(--mac-accent)' : 'var(--mac-border)'}`,
                    background: statusFilter === opt.key ? 'var(--mac-accent)' : 'var(--mac-bg-primary)',
                    color: statusFilter === opt.key ? 'white' : 'var(--mac-text-primary)',
                    cursor: 'pointer',
                    fontSize: 'var(--mac-font-size-sm)',
                    fontWeight: statusFilter === opt.key ? 600 : 400,
                  }}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
          {/* PR-64 / Medium-14: sort controls */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}>
            <span style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-muted)' }}>Сортировать:</span>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              aria-label="Сортировка очереди"
              className="macos-input"
              style={{ fontSize: 'var(--mac-font-size-xs)', padding: '4px 8px', width: 'auto' }}
            >
              <option value="default">По умолчанию</option>
              <option value="name">По имени</option>
              <option value="time">По времени</option>
            </select>
          </div>
          {/* QW-8 fix: индикатор количества отфильтрованных записей. */}
          {(searchQuery || statusFilter !== 'all') && (
            <div
              style={{
                marginTop: 'var(--mac-spacing-2)',
                fontSize: 'var(--mac-font-size-xs)',
                color: 'var(--mac-text-muted)',
              }}
            >
              Показано: {filteredAppointments.length} из {appointments.length}
              {searchQuery && ` · поиск: «${searchQuery}»`}
              {statusFilter !== 'all' && ` · фильтр: ${
                { active: 'в работе', completed: 'завершены' }[statusFilter]
              }`}
            </div>
          )}
        </CardHeader>
        <CardContent style={{ padding: 'var(--mac-spacing-4)', background: 'var(--mac-bg-secondary)' }}>
          {loading ? (
            // QW-3 fix: skeleton-загрузка вместо текста «Загрузка…».
            // Skeleton показывает структуру будущих карточек и снижает
            // ощущение медлительности. 3 карточки-заглушки с shimmer-анимацией.
            <div style={cardGridStyle} aria-busy="true" aria-live="polite">
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  style={{
                    ...queueCardStyle,
                    background: 'var(--mac-bg-tertiary)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--mac-spacing-3)' }}>
                    <div style={{ display: 'grid', gap: 'var(--mac-spacing-2)', flex: 1 }}>
                      <div
                        style={{
                          height: '18px',
                          width: '60%',
                          borderRadius: 'var(--mac-radius-sm)',
                          background: 'linear-gradient(90deg, var(--mac-border) 25%, var(--mac-bg-secondary) 50%, var(--mac-border) 75%)',
                          backgroundSize: '200% 100%',
                          animation: 'lab-skeleton-shimmer 1.5s infinite',
                        }}
                      />
                      <div
                        style={{
                          height: '14px',
                          width: '80%',
                          borderRadius: 'var(--mac-radius-sm)',
                          background: 'linear-gradient(90deg, var(--mac-border) 25%, var(--mac-bg-secondary) 50%, var(--mac-border) 75%)',
                          backgroundSize: '200% 100%',
                          animation: 'lab-skeleton-shimmer 1.5s infinite',
                        }}
                      />
                      <div
                        style={{
                          height: '14px',
                          width: '50%',
                          borderRadius: 'var(--mac-radius-sm)',
                          background: 'linear-gradient(90deg, var(--mac-border) 25%, var(--mac-bg-secondary) 50%, var(--mac-border) 75%)',
                          backgroundSize: '200% 100%',
                          animation: 'lab-skeleton-shimmer 1.5s infinite',
                        }}
                      />
                    </div>
                    <div
                      style={{
                        height: '22px',
                        width: '80px',
                        borderRadius: '11px',
                        background: 'linear-gradient(90deg, var(--mac-border) 25%, var(--mac-bg-secondary) 50%, var(--mac-border) 75%)',
                        backgroundSize: '200% 100%',
                        animation: 'lab-skeleton-shimmer 1.5s infinite',
                      }}
                    />
                  </div>
                </div>
              ))}
              <style>{`
                @keyframes lab-skeleton-shimmer {
                  0% { background-position: 200% 0; }
                  100% { background-position: -200% 0; }
                }
                @media (prefers-reduced-motion: reduce) {
                  [style*="lab-skeleton-shimmer"] {
                    animation: none !important;
                  }
                }
              `}</style>
            </div>
          ) : filteredAppointments.length === 0 ? (
            <Alert severity="info">
              {appointments.length === 0
                ? 'На сегодня не найдено лабораторных записей.'
                : 'Ничего не найдено. Измените поисковый запрос или фильтр.'}
            </Alert>
          ) : (
            <div style={cardGridStyle}>
              {sortedAppointments.map((appointment) => {
                const isSelected = selectedAppointment?.id === appointment.id;
                return (
                  <div
                    key={appointment.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => onOpenAppointment(appointment)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        onOpenAppointment(appointment);
                      }
                    }}
                    style={{
                      ...queueCardStyle,
                      borderColor: isSelected ? 'var(--mac-accent)' : 'var(--mac-border)',
                      boxShadow: isSelected ? '0 0 0 2px color-mix(in oklab, var(--mac-accent) 20%, transparent)' : 'none',
                      cursor: 'pointer',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--mac-spacing-3)', alignItems: 'flex-start' }}>
                      <div style={{ display: 'grid', gap: 'var(--mac-spacing-2)' }}>
                        <div style={{ fontSize: 'var(--mac-font-size-xl)', fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-primary)' }}>
                          {appointment.patient_fio || 'Пациент без имени'}
                        </div>
                      <div style={{ color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-base)' }}>
                        Визит: {appointment.visit_id || 'не привязан'} | Телефон:{' '}
                        {/* P-05 fix: маскирование номера телефона в публичном
                            пространстве лаборатории. Раскрытие — по клику. */}
                        <MaskedPhone phone={appointment.patient_phone} />
                      </div>
                    </div>
                      <Badge variant={getLabStatusVariant(appointment.status)}>
                        {formatLabStatus(appointment.status)}
                      </Badge>
                    </div>

                    <div style={{ color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-base)', lineHeight: 1.5 }}>
                      <strong style={{ color: 'var(--mac-text-primary)' }}>Услуги:</strong> {formatServices(appointment)}
                    </div>

                    <div style={metaRowStyle}>
                      <Badge variant="primary">{formatSpecialtyLabel(appointment.specialty)}</Badge>
                      {appointment.payment_status && <Badge variant="info">Оплата: {formatPaymentStatus(appointment.payment_status)}</Badge>}
                      {/* PR-60 / Medium-13: was variant="success" (green implies positive status, but time is not a status) */}
                      {appointment.appointment_time && <Badge variant="default">{appointment.appointment_time}</Badge>}
                      {appointment.report_template_name && <Badge variant="info">{appointment.report_template_name}</Badge>}
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--mac-spacing-3)', alignItems: 'center' }}>
                      <div style={{ color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-sm)' }}>
                        {/* P-05 fix: patient_id — внутренний идентификатор, не нужен
                            лаборанту для работы. Скрываем по умолчанию, раскрытие —
                            по клику. Снижает риск утечки PII через скриншоты. */}
                        {/* PR-66 / Low-30: added custom marker + ::marker CSS reset */}
                        <details style={{ display: 'inline' }}>
                          <summary
                            style={{
                              display: 'inline-block',
                              cursor: 'pointer',
                              color: 'var(--mac-text-muted)',
                              listStyle: 'none',
                            }}
                            aria-label="Показать внутренний ID пациента"
                          >
                            <style>{`summary::-webkit-details-marker { display: none; } summary::marker { content: ''; }`}</style>
                            ID пациента ▸
                          </summary>
                          <span style={{ marginLeft: 6, fontFamily: 'monospace' }}>
                            {appointment.patient_id}
                          </span>
                        </details>
                      </div>
                      <Button variant="primary" onClick={() => onOpenAppointment(appointment)}>
                        <Icon name="doc.text" size={16} />
                        {appointment.report_instance_id ? 'Открыть отчёт' : 'Открыть в редакторе'}
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
              padding: 'var(--mac-spacing-4)'
            }}
          >
            <CardTitle style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}>
              <Icon name="clock.arrow.circlepath" size={20} />
              История отчётов пациента
            </CardTitle>
          </CardHeader>
          <CardContent style={{ padding: 'var(--mac-spacing-4)', background: 'var(--mac-bg-secondary)' }}>
            {reportHistory.length === 0 ? (
              <Alert severity="info">Для выбранного пациента ещё нет лабораторных отчётов.</Alert>
            ) : (
              <div style={{ display: 'grid', gap: 'var(--mac-spacing-3)' }}>
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
                      gap: 'var(--mac-spacing-3)',
                      alignItems: 'center'
                    }}
                  >
                    <div style={{ display: 'grid', gap: 'var(--mac-spacing-1)' }}>
                      <div style={{ fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-primary)' }}>
                        {item.template?.name || `Отчёт #${item.id}`}
                      </div>
                      <div style={{ color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-sm)' }}>
                        Создан: {new Date(item.created_at).toLocaleString()} | Статус: {formatLabStatus(item.status)}
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: 'var(--mac-spacing-2)', alignItems: 'center', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
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
