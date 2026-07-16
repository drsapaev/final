import PropTypes from 'prop-types';
import { useState, useEffect } from 'react';
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
// STRAT#14: i18n.t() для i18n — filter/sort/title/badge labels мигрированы.
// STRAT#28: QueueCard extracted and wrapped in React.memo for performance.
import QueueCard from './QueueCard';
// STRAT#27: VirtualizedQueueList for 1000+ entries via @tanstack/react-virtual.
import VirtualizedQueueList from './VirtualizedQueueList';
import { useTranslation } from '../../i18n/useTranslation';
import i18n from '../../i18n';

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
  if (!phone) return <span className="lqw-masked-phone-empty">{i18n.t('pii.phone_not_set')}</span>;
  if (!canReveal) {
    return (
      <span className="lqw-masked-phone-readonly" title={i18n.t('pii.phone_restricted')}>
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
      title={revealed ? i18n.t('pii.hide_phone') : i18n.t('pii.show_phone')}
      aria-label={revealed ? i18n.t('pii.hide_phone_aria') : i18n.t('pii.show_phone_aria')}
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
    return i18n.t('pii.no_services');
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
  reportHistory = [],
  // STRAT#8: server-side pagination props (от LabPanel, добавлены в STRAT#7).
  // Когда hasMore=true, кнопка «Показать ещё» вызывает onLoadMore (server-side).
  // Когда hasMore=false, fallback на client-side visibleCount (FIX#13).
  onLoadMore,
  hasMore = false,
  loadingMore = false,
  queueTotal = 0,
}) {
  const { t } = useTranslation();
  // QW-8 fix: локальный state поиска и фильтра статусов.
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  // PR-64 / Medium-14: client-side sorting
  const [sortBy, setSortBy] = useState('default'); // default | name | time

  // UX-AUDIT-FIX13: пагинация очереди. Ранее sortedAppointments.map(...)
  // рендерил ВСЕ записи одновременно — при 100+ анализов в день это
  // вызывало тормоза рендера и высокий memory footprint. Теперь
  // показываем по PAGE_SIZE=20 записей, с кнопкой «Показать ещё».
  // Сбрасываем visibleCount при изменении фильтра/поиска/sortBy.
  const PAGE_SIZE = 20;
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  // Сбрасываем пагинацию при изменении любого фильтра.
  useEffect(() => {
    setVisibleCount(PAGE_SIZE);
  }, [searchQuery, statusFilter, sortBy]);

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
            {i18n.t('queue.title')}
          </CardTitle>
          <div className="lqw-meta-row">
            <Badge variant="info">{i18n.t('queue.total')}: {appointments.length}</Badge>
            <Badge variant="warning">
              {i18n.t('queue.in_progress')}: {appointments.filter((item) => activeQueueStatuses.has(item.status)).length}
            </Badge>
            <Button variant="outline" onClick={onRefresh} disabled={loading}>
              <Icon name="arrow.clockwise" size={16} />
              {i18n.t('common.refresh')}
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
                placeholder={i18n.t('queue.search_placeholder')}
                aria-label={i18n.t('queue.search_aria')}
                className="lqw-search-input"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery('')}
                  aria-label={i18n.t('queue.search_clear')}
                  className="lqw-search-clear"
                >
                  ×
                </button>
              )}
            </div>
            <div
              role="group"
              aria-label={i18n.t('queue.filter_group_aria')}
              className="lqw-status-filter-group"
            >
              {[
                { key: 'all',        label: i18n.t('queue.filter_all') },
                { key: 'active',     label: i18n.t('queue.filter_active') },
                { key: 'completed',  label: i18n.t('queue.filter_completed') },
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
            <span className="lqw-sort-label">{i18n.t('queue.sort_label')}</span>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              aria-label={i18n.t('queue.sort_aria')}
              className="macos-input lqw-sort-select"
            >
              <option value="default">{i18n.t('queue.sort_default')}</option>
              <option value="name">{i18n.t('queue.sort_name')}</option>
              <option value="time">{i18n.t('queue.sort_time')}</option>
            </select>
          </div>
          {/* QW-8 fix: индикатор количества отфильтрованных записей. */}
          {(searchQuery || statusFilter !== 'all') && (
            <div className="lqw-filter-count">
              {i18n.t('queue.filter_count')}: {filteredAppointments.length} / {appointments.length}
              {searchQuery && ` · ${i18n.t('queue.filter_count_search')}: «${searchQuery}»`}
              {statusFilter !== 'all' && ` · ${i18n.t('queue.filter_count_filter')}: ${
                { active: i18n.t('queue.filter_active').toLowerCase(), completed: i18n.t('queue.filter_completed').toLowerCase() }[statusFilter]
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
                ? i18n.t('queue.no_entries')
                : i18n.t('queue.no_matches')}
            </Alert>
          ) : (
            /* STRAT#27: virtualized rendering replaces .slice().map() + load-more IIFE.
               VirtualizedQueueList handles both performance (only visible cards render)
               and server-side pagination (infinite scroll + manual load-more button). */
            <VirtualizedQueueList
              appointments={sortedAppointments}
              selectedAppointment={selectedAppointment}
              onOpenAppointment={onOpenAppointment}
              onLoadMore={onLoadMore}
              hasMore={hasMore}
              loadingMore={loadingMore}
              queueTotal={queueTotal}
            />
          )}
        </CardContent>
      </Card>

      {selectedAppointment && (
        <Card variant="filled" padding="none">
          <CardHeader className="lqw-card-header">
            <CardTitle className="lqw-card-title">
              <Icon name="clock.arrow.circlepath" size={20} />
              {i18n.t('queue.history_title')}
            </CardTitle>
          </CardHeader>
          <CardContent className="lqw-card-content">
            {reportHistory.length === 0 ? (
              <Alert severity="info">{i18n.t('queue.history_empty')}</Alert>
            ) : (
              <div className="lqw-card-grid">
                {reportHistory.map((item) => (
                  <div key={item.id} className="lqw-history-card">
                    <div className="lqw-history-info">
                      <div className="lqw-history-title">
                        {item.template?.name || `${i18n.t('queue.history_report_number')} #${item.id}`}
                      </div>
                      <div className="lqw-history-meta">
                        {i18n.t('queue.history_created')}: {new Date(item.created_at).toLocaleString()} | {i18n.t('queue.history_status')}: {formatLabStatus(item.status)}
                      </div>
                    </div>
                    <div className="lqw-history-badges">
                      <Badge variant={getLabStatusVariant(item.status)}>
                        {formatLabStatus(item.status)}
                      </Badge>
                      <Badge variant={historySeverityBadge(item).variant}>
                        {formatSeverityLabel(historySeverityBadge(item).label)}
                      </Badge>
                      {item.flagged_findings_count > 0 && <Badge variant="info">{item.flagged_findings_count} {i18n.t('queue.history_flags')}</Badge>}
                      {item.critical_findings_count > 0 && <Badge variant="danger">{item.critical_findings_count} {i18n.t('queue.history_critical')}</Badge>}
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
  reportHistory: PropTypes.array,
  // STRAT#8: server-side pagination props
  onLoadMore: PropTypes.func,
  hasMore: PropTypes.bool,
  loadingMore: PropTypes.bool,
  queueTotal: PropTypes.number,
};
