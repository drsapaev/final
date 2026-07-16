// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

/**
 * HistoryTab — R-15 (UX audit): extracted from CardiologistPanelUnified.
 *
 * Renders the "История" (history) tab content:
 *   1. Empty state when no patient is selected
 *   2. Patient timeline with filterable entries (ECG, blood tests, files)
 *   3. File preview/download actions
 *
 * All state and business logic stays in the parent. This component receives
 * the pre-built filteredHistoryEntries, historyFilterOptions, and file action
 * callbacks via props.
 */

import PropTypes from 'prop-types';
import { Calendar, Eye, Download, FileText } from 'lucide-react';
import { Button, Badge, MacOSCard, MacOSEmptyState } from '../ui/macos';
import { formatRegistrarDate } from '../../utils/dateUtils';
import { useTranslation } from '../../i18n/useTranslation';

/**
 * @param {Object} props
 * @param {Object|null} props.selectedPatient - Currently selected patient
 * @param {string} props.selectedPatientLabel - Display name for the patient
 * @param {Array} props.filteredHistoryEntries - Pre-filtered history entries
 * @param {Array} props.historyFilterOptions - Filter dropdown options
 * @param {string} props.historyFilter - Current filter value
 * @param {Function} props.setHistoryFilter - Set filter callback
 * @param {Function} props.canPreviewAttachment - Check if file is previewable
 * @param {Function} props.downloadPatientFile - Download file callback
 * @param {Function} props.previewPatientFile - Preview file callback
 * @param {Function} props.getColor - Theme color getter
 * @param {Function} props.getFontSize - Theme font size getter
 * @param {Function} props.getSpacing - Theme spacing getter
 */
export function HistoryTab({
  selectedPatient,
  selectedPatientLabel,
  filteredHistoryEntries = [],
  historyFilterOptions = [],
  historyFilter,
  setHistoryFilter,
  canPreviewAttachment,
  downloadPatientFile,
  previewPatientFile,
  getColor,
  getFontSize,
  getSpacing,
}) {
  const { t } = useTranslation();
  // Empty state: no patient selected
  if (!selectedPatient) {
    return (
      <MacOSCard style={{ padding: getSpacing('xl'), textAlign: 'center' }}>
        <Calendar size={48} style={{ margin: '0 auto 16px', color: getColor('textSecondary') }} />
        <h3 style={{ fontSize: getFontSize('lg'), fontWeight: 'var(--mac-font-weight-medium)', marginBottom: getSpacing('sm'), color: getColor('text') }}>
          {t('cardio.cardio_hist_empty_title')}
        </h3>
        <p className="cardio-text-secondary">{t('cardio.cardio_hist_empty_desc')}</p>
      </MacOSCard>
    );
  }

  return (
    <div style={{
      width: '100%',
      maxWidth: 'none',
      overflow: 'visible',
      display: 'flex',
      flexDirection: 'column',
      gap: getSpacing('xl'),
    }}>
      <MacOSCard className="cardio-card-padded">
        {/* Header */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: getSpacing('md'),
          flexWrap: 'wrap',
          marginBottom: getSpacing('lg'),
        }}>
          <div>
            <h3 style={{
              fontSize: getFontSize('lg'),
              fontWeight: 'var(--mac-font-weight-medium)',
              marginBottom: getSpacing('xs'),
              color: getColor('text'),
            }}>
              {t('cardio.cardio_hist_timeline_title')}
            </h3>
            <p className="cardio-text-secondary">{selectedPatientLabel}</p>
          </div>
        </div>

        {/* Filter buttons */}
        <div style={{ display: 'flex', gap: getSpacing('sm'), flexWrap: 'wrap', marginBottom: getSpacing('lg') }}>
          {historyFilterOptions.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setHistoryFilter(opt.value)}
              className={`cardio-filter-btn ${historyFilter === opt.value ? 'cardio-filter-btn-active' : ''}`}
              style={{
                padding: '6px 14px',
                borderRadius: 'var(--mac-radius-sm)',
                border: `1px solid ${historyFilter === opt.value ? getColor('accent') : getColor('border')}`,
                background: historyFilter === opt.value ? getColor('accent') : 'transparent',
                color: historyFilter === opt.value ? 'var(--mac-bg-primary)' : getColor('text'),
                cursor: 'pointer',
                fontSize: getFontSize('sm'),
                fontWeight: 'var(--mac-font-weight-medium)',
              }}
            >
              {opt.label} ({opt.count})
            </button>
          ))}
        </div>

        {/* History entries */}
        {filteredHistoryEntries.length === 0 ? (
          <MacOSEmptyState
            type="calendar"
            title={t('cardio.cardio_hist_filter_empty_title')}
            description={t('cardio.cardio_hist_filter_empty_desc')}
          />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: getSpacing('md') }}>
            {filteredHistoryEntries.map((entry) => (
              <div
                key={entry.id}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: getSpacing('md'),
                  padding: getSpacing('md'),
                  border: `1px solid ${getColor('border')}`,
                  borderRadius: 'var(--mac-radius-md)',
                  background: getColor('surface'),
                }}
              >
                {/* Icon by kind */}
                <div style={{ flexShrink: 0, marginTop: '2px' }}>
                  {entry.kind === 'ecg' && <Calendar size={18} style={{ color: getColor('secondary', 600) }} />}
                  {entry.kind === 'labs' && <FileText size={18} style={{ color: getColor('secondary', 600) }} />}
                  {entry.kind === 'attachments' && <FileText size={18} style={{ color: getColor('textSecondary') }} />}
                </div>

                {/* Content */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: getSpacing('sm') }}>
                    <div style={{ fontWeight: 'var(--mac-font-weight-medium)', fontSize: getFontSize('base'), color: getColor('text') }}>
                      {entry.title}
                    </div>
                    <Badge variant={entry.badgeVariant || 'info'}>
                      {entry.kind === 'ecg' ? t('cardio.cardio_hist_badge_ecg') : entry.kind === 'labs' ? t('cardio.cardio_hist_badge_labs') : t('cardio.cardio_hist_badge_attachments')}
                    </Badge>
                  </div>
                  <div style={{ fontSize: getFontSize('sm'), color: getColor('textSecondary'), marginTop: '2px' }}>
                    {entry.subtitle}
                  </div>
                  {entry.meta && (
                    <div style={{ fontSize: getFontSize('xs'), color: getColor('textSecondary'), marginTop: 'var(--mac-spacing-1)' }}>
                      {entry.meta}
                    </div>
                  )}

                  {/* File actions */}
                  {entry.file && (
                    <div style={{ display: 'flex', gap: getSpacing('sm'), marginTop: getSpacing('sm') }}>
                      {canPreviewAttachment(entry.file) && (
                        <Button
                          variant="outline"
                          onClick={() => previewPatientFile(entry.file)}
                          style={{ padding: '4px 10px', fontSize: getFontSize('xs') }}
                        >
                          <Eye size={12} className="cardio-icon-mr" /> {t('cardio.cardio_hist_view')}
                        </Button>
                      )}
                      <Button
                        variant="outline"
                        onClick={() => downloadPatientFile(entry.file)}
                        style={{ padding: '4px 10px', fontSize: getFontSize('xs') }}
                      >
                        <Download size={12} className="cardio-icon-mr" /> {t('cardio.cardio_hist_download')}
                      </Button>
                    </div>
                  )}
                </div>

                {/* Timestamp */}
                <div style={{ flexShrink: 0, fontSize: getFontSize('xs'), color: getColor('textSecondary') }}>
                  {entry.timestamp ? formatRegistrarDate(entry.timestamp, 'ru-RU') : '—'}
                </div>
              </div>
            ))}
          </div>
        )}
      </MacOSCard>
    </div>
  );
}

HistoryTab.propTypes = {
  selectedPatient: PropTypes.object,
  selectedPatientLabel: PropTypes.string,
  filteredHistoryEntries: PropTypes.array,
  historyFilterOptions: PropTypes.array,
  historyFilter: PropTypes.string.isRequired,
  setHistoryFilter: PropTypes.func.isRequired,
  canPreviewAttachment: PropTypes.func.isRequired,
  downloadPatientFile: PropTypes.func.isRequired,
  previewPatientFile: PropTypes.func.isRequired,
  getColor: PropTypes.func.isRequired,
  getFontSize: PropTypes.func.isRequired,
  getSpacing: PropTypes.func.isRequired,
};

export default HistoryTab;
