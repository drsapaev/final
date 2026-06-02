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
  MacOSButton,
  MacOSInput,
  MacOSCheckbox,
  Select
} from '../ui/macos';

const ServiceBatchEdit = ({ selectedServices, categories, onComplete, onCancel }) => {
  const [updates, setUpdates] = useState({});
  const [comment, setComment] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const availableFields = [
    { key: 'price', label: 'Цена', type: 'number', icon: DollarSign },
    { key: 'currency', label: 'Валюта', type: 'select', options: ['UZS', 'USD'], icon: Tag },
    { key: 'duration_minutes', label: 'Длительность (мин)', type: 'number', icon: Clock },
    { key: 'category_id', label: 'Категория', type: 'select', options: categories, icon: Tag },
    { key: 'active', label: 'Активность', type: 'boolean', icon: Power },
    { key: 'requires_doctor', label: 'Требует врача', type: 'boolean', icon: CheckSquare },
    { key: 'is_consultation', label: 'Консультация', type: 'boolean', icon: CheckSquare },
    { key: 'allow_doctor_price_override', label: 'Переопределение цены', type: 'boolean', icon: CheckSquare }
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
      alert('Выберите хотя бы одно поле для изменения');
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
      alert('Ошибка при массовом обновлении услуг');
    } finally {
      setLoading(false);
    }
  };

  if (result) {
    return (
      <MacOSCard variant="default" style={{ padding: '24px' }}>
        <div style={{ textAlign: 'center' }}>
          {result.failed_count === 0 ? (
            <>
              <div style={{
                width: '64px',
                height: '64px',
                borderRadius: '50%',
                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 16px'
              }}>
                <CheckSquare size={32} style={{ color: 'var(--mac-success)' }} />
              </div>
              <h3 style={{
                fontSize: '18px',
                fontWeight: '600',
                color: 'var(--mac-text-primary)',
                margin: '0 0 8px 0'
              }}>
                Успешно обновлено
              </h3>
              <p style={{
                fontSize: '14px',
                color: 'var(--mac-text-secondary)',
                margin: '0 0 20px 0'
              }}>
                Обновлено услуг: {result.updated_count}
              </p>
            </>
          ) : (
            <>
              <div style={{
                width: '64px',
                height: '64px',
                borderRadius: '50%',
                backgroundColor: 'rgba(245, 158, 11, 0.1)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 16px'
              }}>
                <AlertCircle size={32} style={{ color: 'var(--mac-warning)' }} />
              </div>
              <h3 style={{
                fontSize: '18px',
                fontWeight: '600',
                color: 'var(--mac-text-primary)',
                margin: '0 0 8px 0'
              }}>
                Частично обновлено
              </h3>
              <p style={{
                fontSize: '14px',
                color: 'var(--mac-text-secondary)',
                margin: '0 0 20px 0'
              }}>
                Успешно: {result.updated_count} | Ошибки: {result.failed_count}
              </p>
              {result.failed_services.length > 0 && (
                <div style={{
                  textAlign: 'left',
                  padding: '12px',
                  backgroundColor: 'var(--mac-bg-secondary)',
                  borderRadius: '8px',
                  marginBottom: '20px'
                }}>
                  <h4 style={{ fontSize: '13px', fontWeight: '600', marginBottom: '8px' }}>
                    Ошибки:
                  </h4>
                  {result.failed_services.map((fail, idx) => (
                    <div key={idx} style={{ fontSize: '12px', color: 'var(--mac-error)', marginBottom: '4px' }}>
                      Услуга #{fail.service_id}: {fail.error}
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
          <MacOSButton onClick={onComplete}>
            Закрыть
          </MacOSButton>
        </div>
      </MacOSCard>
    );
  }

  return (
    <MacOSCard variant="default" style={{ padding: '0' }}>
      <div style={{
        padding: '20px 24px',
        borderBottom: '1px solid var(--mac-border)'
      }}>
        <h3 style={{
          fontSize: '18px',
          fontWeight: '600',
          color: 'var(--mac-text-primary)',
          margin: '0 0 8px 0'
        }}>
          Массовое редактирование
        </h3>
        <p style={{
          fontSize: '14px',
          color: 'var(--mac-text-secondary)',
          margin: 0
        }}>
          Выбрано услуг: <strong>{selectedServices.length}</strong>
        </p>
      </div>

      <div style={{ padding: '24px', maxHeight: '500px', overflowY: 'auto' }}>
        <div style={{ marginBottom: '20px' }}>
          <label style={{
            display: 'block',
            fontSize: '14px',
            fontWeight: '600',
            color: 'var(--mac-text-primary)',
            marginBottom: '12px'
          }}>
            Выберите поля для изменения:
          </label>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
            gap: '8px'
          }}>
            {availableFields.map(field => {
              const FieldIcon = field.icon;
              return (
                <button
                  key={field.key}
                  onClick={() => toggleField(field.key)}
                  style={{
                    padding: '10px 12px',
                    border: selectedFields.has(field.key)
                      ? '2px solid var(--mac-accent)'
                      : '1px solid var(--mac-border)',
                    borderRadius: '8px',
                    backgroundColor: selectedFields.has(field.key)
                      ? 'rgba(59, 130, 246, 0.05)'
                      : 'var(--mac-bg-primary)',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    fontSize: '13px',
                    color: 'var(--mac-text-primary)',
                    transition: 'all 0.2s ease'
                  }}
                >
                  <FieldIcon size={16} style={{
                    color: selectedFields.has(field.key) ? 'var(--mac-accent)' : 'var(--mac-text-secondary)'
                  }} />
                  {field.label}
                </button>
              );
            })}
          </div>
        </div>

        {selectedFields.size > 0 && (
          <div style={{
            padding: '16px',
            backgroundColor: 'var(--mac-bg-secondary)',
            borderRadius: '8px',
            marginBottom: '20px'
          }}>
            <h4 style={{
              fontSize: '14px',
              fontWeight: '600',
              color: 'var(--mac-text-primary)',
              marginBottom: '16px'
            }}>
              Новые значения:
            </h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {Array.from(selectedFields).map(fieldKey => {
                const field = availableFields.find(f => f.key === fieldKey);
                if (!field) return null;

                if (field.type === 'number') {
                  return (
                    <div key={fieldKey}>
                      <label style={{
                        display: 'block',
                        fontSize: '13px',
                        fontWeight: '500',
                        color: 'var(--mac-text-primary)',
                        marginBottom: '6px'
                      }}>
                        {field.label}
                      </label>
                      <MacOSInput
                        type="number"
                        value={updates[fieldKey] || ''}
                        onChange={(e) => handleFieldChange(fieldKey, parseFloat(e.target.value) || 0)}
                        placeholder={`Введите ${field.label.toLowerCase()}`}
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
                      <label style={{
                        display: 'block',
                        fontSize: '13px',
                        fontWeight: '500',
                        color: 'var(--mac-text-primary)',
                        marginBottom: '6px'
                      }}>
                        {field.label}
                      </label>
                      <Select
                        value={updates[fieldKey] || ''}
                        onChange={(value) => handleFieldChange(fieldKey, value)}
                        options={[
                          { value: '', label: `Выберите ${field.label.toLowerCase()}` },
                          ...options
                        ]}
                        size="large"
                      />
                    </div>
                  );
                }

                if (field.type === 'boolean') {
                  return (
                    <MacOSCheckbox
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
          <label style={{
            display: 'block',
            fontSize: '13px',
            fontWeight: '500',
            color: 'var(--mac-text-primary)',
            marginBottom: '6px'
          }}>
            Комментарий (опционально)
          </label>
          <MacOSInput
            type="text"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Причина массового изменения..."
          />
        </div>
      </div>

      <div style={{
        padding: '16px 24px',
        borderTop: '1px solid var(--mac-border)',
        display: 'flex',
        justifyContent: 'flex-end',
        gap: '12px'
      }}>
        <MacOSButton variant="outline" onClick={onCancel} disabled={loading}>
          <X size={16} style={{ marginRight: '8px' }} />
          Отменить
        </MacOSButton>
        <MacOSButton
          onClick={handleSubmit}
          disabled={loading || selectedFields.size === 0}
        >
          <Save size={16} style={{ marginRight: '8px' }} />
          {loading ? 'Сохранение...' : `Обновить ${selectedServices.length} услуг`}
        </MacOSButton>
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
