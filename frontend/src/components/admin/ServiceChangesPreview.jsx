import PropTypes from 'prop-types';
import { AlertCircle, ArrowRight, Check, X } from 'lucide-react';
import { MacOSCard, MacOSButton, MacOSBadge } from '../ui/macos';

const ServiceChangesPreview = ({ oldService, newService, onConfirm, onCancel }) => {
  const formatFieldName = (field) => {
    const fieldNames = {
      name: 'Название',
      code: 'Код',
      service_code: 'Код услуги',
      price: 'Цена',
      currency: 'Валюта',
      category_id: 'Категория',
      category_code: 'Код категории',
      duration_minutes: 'Длительность (мин)',
      doctor_id: 'Врач',
      department_key: 'Отделение',
      queue_tag: 'Тег очереди',
      requires_doctor: 'Требует врача',
      is_consultation: 'Консультация',
      allow_doctor_price_override: 'Переопределение цены',
      active: 'Активность'
    };
    return fieldNames[field] || field;
  };

  const formatValue = (value, field) => {
    if (value === null || value === undefined || value === '') return '—';
    if (typeof value === 'boolean') return value ? 'Да' : 'Нет';
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

  if (changes.length === 0) {
    return (
      <MacOSCard variant="default" style={{ padding: '24px' }}>
        <div style={{ textAlign: 'center' }}>
          <AlertCircle size={48} style={{ color: 'var(--mac-text-tertiary)', marginBottom: '16px' }} />
          <h3 style={{
            fontSize: '16px',
            fontWeight: '600',
            color: 'var(--mac-text-primary)',
            margin: '0 0 8px 0'
          }}>
            Нет изменений
          </h3>
          <p style={{
            fontSize: '14px',
            color: 'var(--mac-text-secondary)',
            margin: '0 0 20px 0'
          }}>
            Вы не внесли никаких изменений в услугу
          </p>
          <MacOSButton onClick={onCancel}>
            Закрыть
          </MacOSButton>
        </div>
      </MacOSCard>
    );
  }

  return (
    <MacOSCard variant="default" style={{ padding: '0' }}>
      {/* Header */}
      <div style={{
        padding: '20px 24px',
        borderBottom: '1px solid var(--mac-border)',
        backgroundColor: hasImportantChanges ? 'rgba(245, 158, 11, 0.05)' : 'transparent'
      }}>
        <h3 style={{
          fontSize: '18px',
          fontWeight: '600',
          color: 'var(--mac-text-primary)',
          margin: '0 0 8px 0'
        }}>
          Предпросмотр изменений
        </h3>
        <p style={{
          fontSize: '14px',
          color: 'var(--mac-text-secondary)',
          margin: 0
        }}>
          Проверьте изменения перед сохранением
        </p>
        {hasImportantChanges && (
          <div style={{
            marginTop: '12px',
            padding: '8px 12px',
            backgroundColor: 'rgba(245, 158, 11, 0.1)',
            borderRadius: '6px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <AlertCircle size={16} style={{ color: 'var(--mac-warning)' }} />
            <span style={{ fontSize: '13px', color: 'var(--mac-warning)', fontWeight: '500' }}>
              Обнаружены важные изменения
            </span>
          </div>
        )}
      </div>

      {/* Changes List */}
      <div style={{ padding: '16px 24px', maxHeight: '400px', overflowY: 'auto' }}>
        {changes.map((change, index) => (
          <div
            key={change.field}
            style={{
              padding: '16px',
              marginBottom: index < changes.length - 1 ? '12px' : 0,
              backgroundColor: change.isImportant
                ? 'rgba(245, 158, 11, 0.05)'
                : 'var(--mac-bg-secondary)',
              borderRadius: '8px',
              border: change.isImportant
                ? '1px solid rgba(245, 158, 11, 0.2)'
                : '1px solid var(--mac-border)'
            }}
          >
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              marginBottom: '12px'
            }}>
              <span style={{
                fontSize: '14px',
                fontWeight: '600',
                color: 'var(--mac-text-primary)'
              }}>
                {formatFieldName(change.field)}
              </span>
              {change.isImportant && (
                <MacOSBadge variant="warning" size="sm">
                  Важное
                </MacOSBadge>
              )}
            </div>

            <div style={{
              display: 'grid',
              gridTemplateColumns: '1fr auto 1fr',
              gap: '16px',
              alignItems: 'center'
            }}>
              {/* Old Value */}
              <div style={{
                padding: '12px',
                backgroundColor: 'var(--mac-bg-primary)',
                borderRadius: '6px',
                border: '1px solid var(--mac-border)'
              }}>
                <div style={{
                  fontSize: '11px',
                  fontWeight: '600',
                  color: 'var(--mac-text-tertiary)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.5px',
                  marginBottom: '6px'
                }}>
                  Было
                </div>
                <div style={{
                  fontSize: '14px',
                  color: 'var(--mac-text-secondary)',
                  textDecoration: 'line-through',
                  wordBreak: 'break-word'
                }}>
                  {formatValue(change.oldValue, change.field)}
                </div>
              </div>

              {/* Arrow */}
              <ArrowRight size={20} style={{ color: 'var(--mac-accent)', flexShrink: 0 }} />

              {/* New Value */}
              <div style={{
                padding: '12px',
                backgroundColor: 'rgba(16, 185, 129, 0.05)',
                borderRadius: '6px',
                border: '1px solid rgba(16, 185, 129, 0.2)'
              }}>
                <div style={{
                  fontSize: '11px',
                  fontWeight: '600',
                  color: 'var(--mac-success)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.5px',
                  marginBottom: '6px'
                }}>
                  Станет
                </div>
                <div style={{
                  fontSize: '14px',
                  color: 'var(--mac-success)',
                  fontWeight: '600',
                  wordBreak: 'break-word'
                }}>
                  {formatValue(change.newValue, change.field)}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Footer */}
      <div style={{
        padding: '16px 24px',
        borderTop: '1px solid var(--mac-border)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        backgroundColor: 'var(--mac-bg-secondary)'
      }}>
        <div style={{ fontSize: '13px', color: 'var(--mac-text-secondary)' }}>
          Изменений: <strong>{changes.length}</strong>
          {hasImportantChanges && (
            <span style={{ color: 'var(--mac-warning)', marginLeft: '8px' }}>
              • Важных: <strong>{changes.filter(c => c.isImportant).length}</strong>
            </span>
          )}
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <MacOSButton variant="outline" onClick={onCancel}>
            <X size={16} style={{ marginRight: '8px' }} />
            Отменить
          </MacOSButton>
          <MacOSButton onClick={onConfirm}>
            <Check size={16} style={{ marginRight: '8px' }} />
            Подтвердить изменения
          </MacOSButton>
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
