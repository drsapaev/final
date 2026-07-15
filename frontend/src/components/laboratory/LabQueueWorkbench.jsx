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
// L-H-4 fix: миграция inline-стилей в CSS (.lqw-masked-phone*).
// Раскрытие может быть ограничено ролью через prop canReveal.
//
// UX-AUDIT-FIX11: усилена аффорданса кликабельности. Ранее пользователь
// не понимал, что маску можно раскрыть кликом — title появлялся только
// при hover, на тач-устройствах не показывался вовсе. Теперь:
//   1) Добавлена иконка eye/eye.slash перед номером — визуальный cue
//      «здесь есть действие».
//   2) CSS-класс .lqw-masked-phone с hover-эффектом (color shift).
//   3) :focus-visible для keyboard-навигации.
//   4) title показывает действие («Показать» / «Скрыть»).
// Соответствует Nielsen Heuristic #6 (Recognition rather than Recall).
function MaskedPhone({ phone, canReveal = true }) {
  const [revealed, setRevealed] = useState(false);
  if (!phone) return <span className="lqw-masked-phone-empty">не указан</span>;
  if (!canReveal) {
    return (
      <span className="lqw-masked-phone-readonly" title="Доступ к номеру ограничен ролью">
        <Icon name="eye.slash" size={12} aria-hidden="true" />
        <span className="lqw-masked-phone-text">{maskPhone(phone)}</span>
      </span>
    );
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
      aria-pressed={revealed}
      className={`lqw-masked-phone ${revealed ? 'lqw-masked-phone-revealed' : ''}`}
    >
      <Icon name={revealed ? 'eye.slash' : 'eye'} size={12} aria-hidden="true" />
      <span className="lqw-masked-phone-text">{revealed ? phone : maskPhone(phone)}</span>
    </button>
  );
}

MaskedPhone.propTypes = {
  phone: PropTypes.string,
  canReveal: PropTypes.bool,
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
    <div className="lqw-root">
      <Card variant="filled" padding="none">
        <CardHeader className="lqw-card-header">
          <CardTitle className="lqw-card-title">
            <Icon name="testtube.2" size={20} />
            Очередь лаборатории
          </CardTitle>
          <div className="lqw-meta-row">
            <Badge variant="info">Всего: {appointments.length}</Badge>
            <Badge variant="warning">
              В работе: {appointments.filter((item) => activeQueueStatuses.has(item.status)).length}
            </Badge>
            <Button variant="outline" onClick={onRefresh} disabled={loading}>
              <Icon name="arrow.clockwise" size={16} />
              Обновить
            </Button>
          </div>
          {/* QW-8 fix: панель поиска и фильтра статусов. L-H-4: CSS-классы. */}
          <div className="lqw-search-filter-row">
            <div className="lqw-search-wrapper">
              <Icon
                name="magnifyingglass"
                size={14}
                className="lqw-search-icon"
              />
              <Input
                type="search"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Поиск по ФИО, телефону, ID…"
                aria-label="Поиск по очереди лаборатории"
                className="lqw-search-input"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery('')}
                  aria-label="Очистить поиск"
                  className="lqw-search-clear"
                >
                  ×
                </button>
              )}
            </div>
            <div
              role="group"
              aria-label="Фильтр по статусу"
              className="lqw-status-filter-group"
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
                  className={`lqw-status-filter-btn ${statusFilter === opt.key ? 'lqw-status-filter-btn-active' : ''}`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
          {/* PR-64 / Medium-14: sort controls */}
          <div className="lqw-sort-row">
            <span className="lqw-sort-label">Сортировать:</span>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              aria-label="Сортировка очереди"
              className="macos-input lqw-sort-select"
            >
              <option value="default">По умолчанию</option>
              <option value="name">По имени</option>
              <option value="time">По времени</option>
            </select>
          </div>
          {/* QW-8 fix: индикатор количества отфильтрованных записей. */}
          {(searchQuery || statusFilter !== 'all') && (
            <div className="lqw-filter-count">
              Показано: {filteredAppointments.length} из {appointments.length}
              {searchQuery && ` · поиск: «${searchQuery}»`}
              {statusFilter !== 'all' && ` · фильтр: ${
                { active: 'в работе', completed: 'завершены' }[statusFilter]
              }`}
            </div>
          )}
        </CardHeader>
        <CardContent className="lqw-card-content">
          {loading ? (
            // QW-3 fix: skeleton-загрузка вместо текста «Загрузка…».
            // L-H-4: используется CSS-класс .lqw-skeleton с @media (prefers-reduced-motion).
            // L-M-4 fix: при prefers-reduced-motion skeleton остаётся статичным
            // (без мигания), но структура всё ещё видна — лучше, чем белый экран.
            <div className="lqw-card-grid" aria-busy="true" aria-live="polite">
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  className="lqw-queue-card"
                  style={{ background: 'var(--mac-bg-tertiary)' }}
                >
                  <div className="lqw-card-top">
                    <div className="lqw-card-info" style={{ flex: 1 }}>
                      <div className="lqw-skeleton" style={{ height: '18px', width: '60%' }} />
                      <div className="lqw-skeleton" style={{ height: '14px', width: '80%' }} />
                      <div className="lqw-skeleton" style={{ height: '14px', width: '50%' }} />
                    </div>
                    <div className="lqw-skeleton" style={{ height: '22px', width: '80px', borderRadius: '11px' }} />
                  </div>
                </div>
              ))}
            </div>
          ) : filteredAppointments.length === 0 ? (
            <Alert severity="info">
              {appointments.length === 0
                ? 'На сегодня не найдено лабораторных записей.'
                : 'Ничего не найдено. Измените поисковый запрос или фильтр.'}
            </Alert>
          ) : (
            <div className="lqw-card-grid">
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
                    className={`lqw-queue-card ${isSelected ? 'lqw-queue-card-selected' : ''}`}
                  >
                    <div className="lqw-card-top">
                      <div className="lqw-card-info">
                        <div className="lqw-card-name">
                          {appointment.patient_fio || 'Пациент без имени'}
                        </div>
                        <div className="lqw-card-meta">
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

                    <div className="lqw-card-services">
                      <strong>Услуги:</strong> {formatServices(appointment)}
                    </div>

                    <div className="lqw-meta-row">
                      <Badge variant="primary">{formatSpecialtyLabel(appointment.specialty)}</Badge>
                      {appointment.payment_status && <Badge variant="info">Оплата: {formatPaymentStatus(appointment.payment_status)}</Badge>}
                      {/* PR-60 / Medium-13: was variant="success" (green implies positive status, but time is not a status) */}
                      {appointment.appointment_time && <Badge variant="default">{appointment.appointment_time}</Badge>}
                      {appointment.report_template_name && <Badge variant="info">{appointment.report_template_name}</Badge>}
                    </div>

                    <div className="lqw-card-bottom">
                      <div className="lqw-card-id">
                        {/* P-05 fix: patient_id — внутренний идентификатор, не нужен
                            лаборанту для работы. Скрываем по умолчанию, раскрытие —
                            по клику. Снижает риск утечки PII через скриншоты.
                            L-M-5 fix: используем CSS-класс .lqw-pii-* вместо inline
                            style-hack с ::-webkit-details-marker. */}
                        <details className="lqw-pii-details">
                          <summary
                            className="lqw-pii-summary"
                            aria-label="Показать внутренний ID пациента"
                          >
                            ID пациента ▸
                          </summary>
                          <span className="lqw-pii-value">
                            {appointment.patient_id}
                          </span>
                        </details>
                      </div>
                      {/* L-M-3 fix: убрана вложенная Button внутри role="button".
                          Карточка целиком кликабельна, отдельная кнопка избыточна
                          и создавала a11y anti-pattern (click bubbles to parent). */}
                      <Badge variant={appointment.report_instance_id ? 'success' : 'info'}>
                        <Icon name="doc.text" size={12} />
                        {appointment.report_instance_id ? 'Отчёт существует' : 'Новый отчёт'}
                      </Badge>
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
          <CardHeader className="lqw-card-header">
            <CardTitle className="lqw-card-title">
              <Icon name="clock.arrow.circlepath" size={20} />
              История отчётов пациента
            </CardTitle>
          </CardHeader>
          <CardContent className="lqw-card-content">
            {reportHistory.length === 0 ? (
              <Alert severity="info">Для выбранного пациента ещё нет лабораторных отчётов.</Alert>
            ) : (
              <div className="lqw-card-grid">
                {reportHistory.map((item) => (
                  <div key={item.id} className="lqw-history-card">
                    <div className="lqw-history-info">
                      <div className="lqw-history-title">
                        {item.template?.name || `Отчёт #${item.id}`}
                      </div>
                      <div className="lqw-history-meta">
                        Создан: {new Date(item.created_at).toLocaleString()} | Статус: {formatLabStatus(item.status)}
                      </div>
                    </div>
                    <div className="lqw-history-badges">
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
