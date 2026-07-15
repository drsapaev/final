import PropTypes from 'prop-types';
import { useCallback, useRef } from 'react';
import {
  Alert, Badge, Button, Card, CardContent, CardHeader, CardTitle, Icon,
} from '../ui/macos';
import {
  formatLabStatus,
  formatSeverityLabel,
  getLabStatusVariant,
} from './labUiLabels';
import { historySeverityState, matchesHistoryFilter } from './utils/labReportNormalize';
// STRAT#21: t() для i18n — history panel strings мигрированы.
import { t } from './utils/labTranslations';
import { useTranslation } from '../../i18n/adapter';

/**
 * P-04 fix: LabReportHistoryPanel выделен из LabReportWorkbench.
 *
 * Отвечает за отображение двух списков (взаимоисключающих):
 *   - showRecentReportsBrowser=true: недавние бланки (когда нет выбранного пациента)
 *   - showRecentReportsBrowser=false: история бланков выбранного пациента
 *
 * Включает фильтр по severity (Все / Без флагов / С флагами / Критические)
 * и кнопки-карточки для открытия бланка.
 */
const SEVERITY_FILTER_IDS = ['all', 'clean', 'flagged', 'critical'];
const SEVERITY_FILTER_KEY_MAP = {
  all: 'queue.history_severity_all',
  clean: 'queue.history_severity_clean',
  flagged: 'queue.history_severity_flagged',
  critical: 'queue.history_severity_critical',
};

function sortHistoryItems(items) {
  const { t } = useTranslation();
  return [...items].sort((left, right) => {
    const leftSeverity = historySeverityState(left);
    const rightSeverity = historySeverityState(right);
    if (rightSeverity.order !== leftSeverity.order) {
      return rightSeverity.order - leftSeverity.order;
    }
    return new Date(right.created_at).getTime() - new Date(left.created_at).getTime();
  });
}

export default function LabReportHistoryPanel({
  showRecentReportsBrowser = false,
  recentReports = [],
  reportHistory = [],
  historySeverityFilter = 'all',
  onSeverityFilterChange,
  activeInstanceId = null,
  onOpenInstance,
}) {
  const sourceItems = showRecentReportsBrowser ? recentReports : reportHistory;
  const filteredItems = sortHistoryItems(
    sourceItems.filter((item) => matchesHistoryFilter(item, historySeverityFilter))
  );

  const title = showRecentReportsBrowser
    ? t('queue.history_recent_title')
    : t('queue.history_patient_title');

  const emptyText = showRecentReportsBrowser
    ? t('queue.history_no_saved')
    : t('queue.history_no_matches');

  // L-L-5 fix: keyboard-навигация между карточками (ArrowUp/Down).
  // Список карточек хранится в ref — при ArrowDown/Up перемещаем фокус.
  const cardRefsRef = useRef([]);
  const handleCardKeyDown = useCallback((event, index) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      const next = Math.min(index + 1, filteredItems.length - 1);
      cardRefsRef.current[next]?.focus();
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      const prev = Math.max(index - 1, 0);
      cardRefsRef.current[prev]?.focus();
    } else if (event.key === 'Home') {
      event.preventDefault();
      cardRefsRef.current[0]?.focus();
    } else if (event.key === 'End') {
      event.preventDefault();
      cardRefsRef.current[filteredItems.length - 1]?.focus();
    }
  }, [filteredItems.length]);

  return (
    <Card variant="filled" padding="none">
      <CardHeader style={{ background: 'var(--mac-bg-tertiary)', borderBottom: '1px solid var(--mac-border)', padding: 'var(--mac-spacing-4)' }}>
        <CardTitle style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}>
          <Icon name="clock.arrow.circlepath" size={20} />
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent style={{ padding: 'var(--mac-spacing-4)', background: 'var(--mac-bg-secondary)', display: 'grid', gap: 'var(--mac-spacing-3)' }}>
        {/* Фильтр по severity */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--mac-spacing-2)' }}>
          {SEVERITY_FILTER_IDS.map((filterId) => (
            <Button
              key={filterId}
              variant={historySeverityFilter === filterId ? 'primary' : 'outline'}
              onClick={() => onSeverityFilterChange(filterId)}
            >
              {t(SEVERITY_FILTER_KEY_MAP[filterId])}
            </Button>
          ))}
        </div>

        {filteredItems.length === 0 ? (
          <Alert severity="info">{emptyText}</Alert>
        ) : (
          filteredItems.map((item, index) => {
            const severity = historySeverityState(item);
            const patientLabel = item.patient_snapshot?.full_name || `${t('queue.history_patient_number')} #${item.patient_id}`;
            return (
              <button
                key={item.id}
                type="button"
                ref={(el) => { cardRefsRef.current[index] = el; }}
                onClick={() => onOpenInstance(item.id)}
                // L-L-5 fix: ArrowUp/Down/Home/End для навигации между карточками.
                onKeyDown={(e) => handleCardKeyDown(e, index)}
                aria-label={`${t('queue.history_report_number')} ${item.template?.name || `#${item.id}`}, ${patientLabel}, ${formatLabStatus(item.status)}`}
                style={{
                  border: '1px solid var(--mac-border)',
                  borderRadius: '14px',
                  background: activeInstanceId === item.id
                    ? 'color-mix(in oklab, var(--mac-accent) 10%, var(--mac-bg-primary))'
                    : 'var(--mac-bg-primary)',
                  padding: '12px 14px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  gap: 'var(--mac-spacing-3)',
                  alignItems: 'center',
                  cursor: 'pointer',
                }}
              >
                <div style={{ display: 'grid', gap: 'var(--mac-spacing-1)', textAlign: 'left' }}>
                  <div style={{ fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-primary)' }}>
                    {item.template?.name || `${t('queue.history_report_number')} #${item.id}`}
                  </div>
                  <div style={{ color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-sm)' }}>
                    {showRecentReportsBrowser
                      ? `${patientLabel} | ${new Date(item.created_at).toLocaleString()}`
                      : new Date(item.created_at).toLocaleString()}
                  </div>
                  {showRecentReportsBrowser && (
                    <div style={{ color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-xs)' }}>
                      {t('queue.history_visit')}: {item.visit_id || t('queue.history_no_visit')}
                    </div>
                  )}
                </div>
                <div style={{
                  display: 'flex',
                  gap: 'var(--mac-spacing-2)',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  justifyContent: 'flex-end',
                }}>
                  <Badge variant={getLabStatusVariant(item.status)}>
                    {formatLabStatus(item.status)}
                  </Badge>
                  <Badge variant={severity.variant}>
                    {formatSeverityLabel(severity.label)}
                  </Badge>
                  {item.flagged_findings_count > 0 && (
                    <Badge variant="info">{item.flagged_findings_count} {t('queue.history_flags')}</Badge>
                  )}
                  {item.critical_findings_count > 0 && (
                    <Badge variant="danger">{item.critical_findings_count} {t('queue.history_critical')}</Badge>
                  )}
                </div>
              </button>
            );
          })
        )}
      </CardContent>
    </Card>
  );
}

LabReportHistoryPanel.propTypes = {
  showRecentReportsBrowser: PropTypes.bool,
  recentReports: PropTypes.array,
  reportHistory: PropTypes.array,
  historySeverityFilter: PropTypes.string,
  onSeverityFilterChange: PropTypes.func.isRequired,
  activeInstanceId: PropTypes.number,
  onOpenInstance: PropTypes.func.isRequired,
};
