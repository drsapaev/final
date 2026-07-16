import { useTranslation } from '../../i18n/useTranslation';
import { useState } from 'react';
import PropTypes from 'prop-types';
import { api } from '../../api/client';
import logger from '../../utils/logger';
import {
  CheckSquare,
  X,
  Save,
  AlertCircle,
  DollarSign,
  Clock,
  Tag,
  Power
} from 'lucide-react';
import {
  MacOSCard,
  Button,
  Input,
  Checkbox,
  Select,
} from '../ui/macos';
import { notify } from '../../services/notify.js';

const ServiceBatchEdit = ({ selectedServices, categories, onComplete, onCancel }) => {
  const { t } = useTranslation();
  const [updates, setUpdates] = useState({});
  const [comment, setComment] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const availableFields = [
    { key: 'price', label: t('admin2.sbe_field_price'), type: 'number', icon: DollarSign },
    { key: 'currency', label: t('admin2.sbe_field_currency'), type: 'select', options: ['UZS', 'USD'], icon: Tag },
    { key: 'duration_minutes', label: t('admin2.sbe_field_duration'), type: 'number', icon: Clock },
    { key: 'category_id', label: t('admin2.sbe_field_category'), type: 'select', options: categories, icon: Tag },
    { key: 'active', label: t('admin2.sbe_field_active'), type: 'boolean', icon: Power },
    { key: 'requires_doctor', label: t('admin2.sbe_field_requires_doctor'), type: 'boolean', icon: CheckSquare },
    { key: 'is_consultation', label: t('admin2.sbe_field_consultation'), type: 'boolean', icon: CheckSquare },
    { key: 'allow_doctor_price_override', label: t('admin2.sbe_field_price_override'), type: 'boolean', icon: CheckSquare }
  ];

  const [selectedFields, setSelectedFields] = useState(new Set());

  const toggleField = (fieldKey) => {
    const newSelected = new Set(selectedFields);
    if (newSelected.has(fieldKey)) {
      newSelected.delete(fieldKey);
      const newUpdates = { ...updates };
      delete newUpdates[fieldKey];
      setUpdates(newUpdates);
    } else {
      newSelected.add(fieldKey);
    }
    setSelectedFields(newSelected);
  };

  const handleFieldChange = (fieldKey, value) => {
    setUpdates(prev => ({ ...prev, [fieldKey]: value }));
  };

  const handleSubmit = async () => {
    if (Object.keys(updates).length === 0) {
      notify.warning(t('admin2.select_field_warning'));
      return;
    }

    try {
      setLoading(true);
      const response = await api.post('/services/admin/batch-update', {
        service_ids: selectedServices.map(s => s.id),
        updates,
        comment: comment || undefined
      });

      setResult(response.data);

      if (response.data.failed_count === 0) {
        setTimeout(() => {
          onComplete();
        }, 2000);
      }
    } catch (error) {
      logger.error('Ошибка batch обновления:', error);
      notify.error(t('admin2.batch_update_error'));
    } finally {
      setLoading(false);
    }
  };

  if (result) {
    return (
      <MacOSCard variant="default" className="admin-p-24">
        <div className="admin-text-center">
          {result.failed_count === 0 ? (
            <>
              <div className="admin-w-64-h-64-radius-50pct-bgc-rgba-16-185-129-0-1-d-flex-ai-center-jc-center-m-0-auto-16px">
                <CheckSquare size={32} className="admin-success" />
              </div>
              <h3 className="admin-fs-18-fw-600-primary-m-0-0-8px-0-2">
                {t('admin2.sbe_success_title')}
              </h3>
              <p className="admin-fs-14-secondary-m-0-0-20px-0-1">
                {t('admin2.sbe_updated_count', { count: result.updated_count })}
              </p>
            </>
          ) : (
            <>
              <div className="admin-w-64-h-64-radius-50pct-bgc-rgba-245-158-11-0-1-d-flex-ai-center-jc-center-m-0-auto-16px">
                <AlertCircle size={32} className="admin-warning" />
              </div>
              <h3 className="admin-fs-18-fw-600-primary-m-0-0-8px-0-1">
                {t('admin2.sbe_partial_title')}
              </h3>
              <p className="admin-fs-14-secondary-m-0-0-20px-0">
                {t('admin2.sbe_partial_summary', { success: result.updated_count, failed: result.failed_count })}
              </p>
              {result.failed_services.length > 0 && (
                <div className="admin-ta-left-p-12-bgc-bg-secondary-radius-8-mb-20">
                  <h4 className="admin-fs-13-fw-600-mb-8">
                    {t('admin2.sbe_errors_title')}
                  </h4>
                  {result.failed_services.map((fail, idx) => (
                    <div key={idx} className="admin-fs-12-error-mb-4">
                      {t('admin2.sbe_error_line', { id: fail.service_id, error: fail.error })}
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
          <Button onClick={onComplete}>
            {t('admin2.sbe_close')}
          </Button>
        </div>
      </MacOSCard>
    );
  }

  return (
    <MacOSCard variant="default" className="admin-p-0">
      <div className="admin-p-20px-24px-bd-b-1px-solid-var-mac-bo">
        <h3 className="admin-fs-18-fw-600-primary-m-0-0-8px-0">
          {t('admin2.sbe_title')}
        </h3>
        <p className="admin-fs-14-secondary-m-0">
          {t('admin2.sbe_selected_count', { count: selectedServices.length })}
        </p>
      </div>

      <div className="admin-p-24-maxh-500-ovy-auto">
        <div className="admin-mb-20">
          <label className="admin-d-block-fs-14-fw-600-primary-mb-12">
            {t('admin2.sbe_select_fields')}
          </label>
          <div className="admin-d-grid-gtc-repeat-auto-fill-min-gap-8">
            {availableFields.map(field => {
              const FieldIcon = field.icon;
              return (
                <button
                  key={field.key}
                  onClick={() => toggleField(field.key)}
                  className="admin-p-10px-12px-radius-8-cur-pointer-d-flex-ai-center-gap-8-fs-13-primary-tr-all-0-2s-ease-bd-dyn-bgc-dyn" style={{ '--admin-bd0': selectedFields.has(field.key)
                      ? '2px solid var(--mac-accent)'
                      : '1px solid var(--mac-border)', '--admin-bgc1': selectedFields.has(field.key)
                      ? 'rgba(59, 130, 246, 0.05)'
                      : 'var(--mac-bg-primary)' }}
                >
                  <FieldIcon size={16} className="admin-col-dyn" style={{ '--admin-col0': selectedFields.has(field.key) ? 'var(--mac-accent)' : 'var(--mac-text-secondary)' }} />
                  {field.label}
                </button>
              );
            })}
          </div>
        </div>

        {selectedFields.size > 0 && (
          <div className="admin-p-16-bgc-bg-secondary-radius-8-mb-20">
            <h4 className="admin-fs-14-fw-600-primary-mb-16">
              {t('admin2.sbe_new_values')}
            </h4>
            <div className="admin-flex-col-12">
              {Array.from(selectedFields).map(fieldKey => {
                const field = availableFields.find(f => f.key === fieldKey);
                if (!field) return null;

                if (field.type === 'number') {
                  return (
                    <div key={fieldKey}>
                      <label className="admin-d-block-fs-13-fw-500-primary-mb-6-2">
                        {field.label}
                      </label>
                      <Input
                        type="number"
                        value={updates[fieldKey] || ''}
                        onChange={(e) => handleFieldChange(fieldKey, parseFloat(e.target.value) || 0)}
                        placeholder={t('admin2.sbe_input_placeholder', { label: field.label.toLowerCase() })}
                      />
                    </div>
                  );
                }

                if (field.type === 'select') {
                  const options = fieldKey === 'category_id'
                    ? field.options.map(cat => ({ value: String(cat.id), label: cat.name_ru }))
                    : field.options.map(opt => ({ value: opt, label: opt }));

                  return (
                    <div key={fieldKey}>
                      <label className="admin-d-block-fs-13-fw-500-primary-mb-6-1">
                        {field.label}
                      </label>
                      <Select
                        value={updates[fieldKey] || ''}
                        onChange={(value) => handleFieldChange(fieldKey, value)}
                        options={[
                          { value: '', label: t('admin2.sbe_select_placeholder', { label: field.label.toLowerCase() }) },
                          ...options
                        ]}
                        size="large"
                      />
                    </div>
                  );
                }

                if (field.type === 'boolean') {
                  return (
                    <Checkbox
                      key={fieldKey}
                      id={fieldKey}
                      checked={updates[fieldKey] || false}
                      onChange={(checked) => handleFieldChange(fieldKey, checked)}
                      label={field.label}
                    />
                  );
                }

                return null;
              })}
            </div>
          </div>
        )}

        <div>
          <label className="admin-d-block-fs-13-fw-500-primary-mb-6">
            {t('admin2.sbe_comment_label')}
          </label>
          <Input
            type="text"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder={t('admin2.sbe_comment_placeholder')}
          />
        </div>
      </div>

      <div className="admin-p-16px-24px-bd-t-1px-solid-var-mac-bo-d-flex-jc-end-gap-12">
        <Button variant="outline" onClick={onCancel} disabled={loading}>
          <X size={16} className="admin-mr-8" />
          {t('admin2.sbe_cancel')}
        </Button>
        <Button
          onClick={handleSubmit}
          disabled={loading || selectedFields.size === 0}
        >
          <Save size={16} className="admin-mr-8" />
          {loading ? t('admin2.sbe_saving') : t('admin2.sbe_update_count', { count: selectedServices.length })}
        </Button>
      </div>
    </MacOSCard>
  );
};

ServiceBatchEdit.propTypes = {
  selectedServices: PropTypes.array.isRequired,
  categories: PropTypes.array.isRequired,
  onComplete: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired
};

export default ServiceBatchEdit;
