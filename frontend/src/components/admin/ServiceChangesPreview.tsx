import type { CSSProperties } from 'react';

import { useTranslation } from '../../i18n/useTranslation';
import PropTypes from 'prop-types';
import { AlertCircle, ArrowRight, Check, X } from 'lucide-react';
import {
  MacOSCard, Button, Badge, AppEmpty,
} from '../ui/macos';

const ServiceChangesPreview = ({ oldService, newService, onConfirm, onCancel }) => {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const formatFieldName = (field) => {
    const fieldNames = {
      name: t('admin2.scp_field_name'),
      code: t('admin2.scp_field_code'),
      service_code: t('admin2.scp_field_service_code'),
      price: t('admin2.scp_field_price'),
      currency: t('admin2.scp_field_currency'),
      category_id: t('admin2.scp_field_category_id'),
      category_code: t('admin2.scp_field_category_code'),
      duration_minutes: t('admin2.scp_field_duration_minutes'),
      doctor_id: t('admin2.scp_field_doctor_id'),
      department_key: t('admin2.scp_field_department_key'),
      queue_tag: t('admin2.scp_field_queue_tag'),
      requires_doctor: t('admin2.scp_field_requires_doctor'),
      is_consultation: t('admin2.scp_field_is_consultation'),
      allow_doctor_price_override: t('admin2.scp_field_allow_doctor_price_override'),
      active: t('admin2.scp_field_active')
    };
    return fieldNames[field] || field;
  };

  const formatValue = (value, field) => {
    if (value === null || value === undefined || value === '') return '—';
    if (typeof value === 'boolean') return value ? t('admin2.scp_value_yes') : t('admin2.scp_value_no');
    if (field === 'price' && typeof value === 'number') {
      return value.toLocaleString('ru-RU');
    }
    return String(value);
  };

  const calculateChanges = () => {
    const changes = [];
    const trackedFields = [
      'name',
      'code',
      'service_code',
      'price',
      'currency',
      'category_id',
      'category_code',
      'duration_minutes',
      'doctor_id',
      'department_key',
      'queue_tag',
      'requires_doctor',
      'is_consultation',
      'allow_doctor_price_override',
      'active'
    ];

    for (const field of trackedFields) {
      const oldVal = oldService?.[field];
      const newVal = newService?.[field];

      // Normalize for comparison
      const normalizedOld = oldVal === '' ? null : oldVal;
      const normalizedNew = newVal === '' ? null : newVal;

      if (normalizedOld !== normalizedNew) {
        changes.push({
          field,
          oldValue: oldVal,
          newValue: newVal,
          isImportant: ['name', 'code', 'service_code', 'price', 'active'].includes(field)
        });
      }
    }

    return changes;
  };

  const changes = calculateChanges();
  const hasImportantChanges = changes.some(c => c.isImportant);
  const importantChangesCount = changes.filter(c => c.isImportant).length;
  const previewTitleId = 'service-changes-preview-title';
  const previewDescriptionId = 'service-changes-preview-description';
  const changesListLabel = t('admin2.scp_changes_list_aria', { count: changes.length });

  if (changes.length === 0) {
    return (
      <MacOSCard
        variant="default"
        role="dialog"
        aria-modal="true"
        aria-label={t('admin2.scp_preview_aria_label')}
        className="admin-p-24"
      >
        <AppEmpty
          icon={AlertCircle}
          title={t('admin2.scp_no_changes_title')}
          description={t('admin2.scp_no_changes_desc')}
          action={
            <Button
              type="button"
              aria-label={t('admin2.scp_close_aria_label')}
              onClick={onCancel}
            >
              {t('admin2.scp_close')}
            </Button>
          }
        />
      </MacOSCard>
    );
  }

  return (
    <MacOSCard
      variant="default"
      role="dialog"
      aria-modal="true"
      aria-labelledby={previewTitleId}
      aria-describedby={previewDescriptionId}
      className="admin-p-0"
    >
      {/* Header */}
      <div className="admin-p-20px-24px-bd-b-1px-solid-var-mac-bo-bgc-dyn" style={{ '--admin-bgc0': hasImportantChanges ? 'rgba(245, 158, 11, 0.05)' : 'transparent' } as CSSProperties}>
        <h3 id={previewTitleId} className="admin-fs-18-fw-600-primary-m-0-0-8px-0">
          {t('admin2.scp_title')}
        </h3>
        <p id={previewDescriptionId} className="admin-fs-14-secondary-m-0">
          {t('admin2.scp_subtitle')}
        </p>
        {hasImportantChanges && (
          <div
            role="status"
            aria-live="polite"
            className="admin-mt-12-p-8px-12px-bgc-rgba-245-158-11-0-1-radius-6-d-flex-ai-center-gap-8">
            <AlertCircle aria-hidden="true" focusable="false" size={16} className="admin-warning" />
            <span className="admin-fs-13-warning-fw-500">
              {t('admin2.scp_important_changes_detected')}
            </span>
          </div>
        )}
      </div>

      {/* Changes List */}
      <div
        role="list"
        aria-label={changesListLabel}
        className="admin-p-16px-24px-maxh-400-ovy-auto"
      >
        {changes.map((change, index) => (
          <div
            key={change.field}
            role="listitem"
            aria-label={t('admin2.scp_change_aria', {
              field: formatFieldName(change.field),
              oldValue: formatValue(change.oldValue, change.field),
              newValue: formatValue(change.newValue, change.field)
            })}
            className="admin-p-16-radius-8-mb-dyn-bgc-dyn-bd-dyn" style={{ '--admin-mb0': index < changes.length - 1 ? '12px' : 0, '--admin-bgc1': change.isImportant
                ? 'rgba(245, 158, 11, 0.05)'
                : 'var(--mac-bg-secondary)', '--admin-bd2': change.isImportant
                ? '1px solid rgba(245, 158, 11, 0.2)'
                : '1px solid var(--mac-border)' } as CSSProperties}>
            <div className="admin-d-flex-ai-center-gap-8-mb-12">
              <span className="admin-fs-14-fw-600-primary">
                {formatFieldName(change.field)}
              </span>
              {change.isImportant && (
                <Badge variant="warning" size="small">
                  {t('admin2.scp_important_badge')}
                </Badge>
              )}
            </div>

            <div className="admin-d-grid-gtc-1fr-auto-1fr-gap-16-ai-center">
              {/* Old Value */}
              <div aria-label={t('admin2.scp_was_aria', { value: formatValue(change.oldValue, change.field) })} className="admin-p-12-bgc-bg-primary-radius-6-bd-1px-solid-var-mac-bo">
                <div className="admin-fs-11-fw-600-tertiary-tt-uppercase-ls-0p5-mb-6">
                  {t('admin2.scp_was')}
                </div>
                <div className="admin-fs-14-secondary-td-line-through-wb-break-word">
                  {formatValue(change.oldValue, change.field)}
                </div>
              </div>

              {/* Arrow */}
              <ArrowRight aria-hidden="true" size={20} className="admin-accent-fsk-0" />

              {/* New Value */}
              <div aria-label={t('admin2.scp_will_aria', { value: formatValue(change.newValue, change.field) })} className="admin-p-12-bgc-rgba-16-185-129-0-05-radius-6-bd-1px-solid-rgba-16-18">
                <div className="admin-fs-11-fw-600-success-tt-uppercase-ls-0p5-mb-6">
                  {t('admin2.scp_will')}
                </div>
                <div className="admin-fs-14-success-fw-600-wb-break-word">
                  {formatValue(change.newValue, change.field)}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="admin-p-16px-24px-bd-t-1px-solid-var-mac-bo-d-flex-jc-between-ai-center-bgc-bg-secondary">
        <div className="admin-fs-13-secondary-1">
          {t('admin2.scp_changes_count_label')} <strong>{changes.length}</strong>
          {hasImportantChanges && (
            <span className="admin-warning-ml-8">
              • {t('admin2.scp_important_count_label')} <strong>{importantChangesCount}</strong>
            </span>
          )}
        </div>
        <div className="admin-d-flex-gap-12">
          <Button
            type="button"
            variant="outline"
            aria-label={t('admin2.scp_cancel_aria_label')}
            onClick={onCancel}
          >
            <X aria-hidden="true" focusable="false" size={16} className="admin-mr-8" />
            {t('admin2.scp_cancel')}
          </Button>
          <Button
            type="button"
            aria-label={t('admin2.scp_confirm_aria', { count: changes.length })}
            onClick={onConfirm}
          >
            <Check aria-hidden="true" focusable="false" size={16} className="admin-mr-8" />
            {t('admin2.scp_confirm')}
          </Button>
        </div>
      </div>
    </MacOSCard>
  );
};

ServiceChangesPreview.propTypes = {
  oldService: PropTypes.object,
  newService: PropTypes.object.isRequired,
  onConfirm: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired
};

export default ServiceChangesPreview;
