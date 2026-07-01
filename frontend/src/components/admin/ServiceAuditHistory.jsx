import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { servicesService } from '../../api/services';
import logger from '../../utils/logger';
import {
  History,
  User,
  Clock,
  Edit,
  Plus,
  Trash2,
  Power,
  PowerOff,
  AlertCircle,
  RefreshCw,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import {
  MacOSCard,
  Button,
  Badge,
  AppEmpty,
  AppError,
  AppLoading,
} from '../ui/macos';

const ServiceAuditHistory = ({ serviceId, serviceName }) => {
  const [loading, setLoading] = useState(true);
  const [history, setHistory] = useState([]);
  const [errorMessage, setErrorMessage] = useState('');
  const [expandedItems, setExpandedItems] = useState(new Set());
  const historyRegionLabel = serviceName
    ? `История изменений услуги: ${serviceName}`
    : 'История изменений услуги';
  const refreshHistoryLabel = serviceName
    ? `Обновить историю изменений услуги ${serviceName}`
    : 'Обновить историю изменений услуги';
  const historyTitleId = `service-audit-history-title-${serviceId}`;

  useEffect(() => {
    if (serviceId) {
      loadHistory();
    }
  }, [serviceId]);

  const loadHistory = async () => {
    try {
      setLoading(true);
      setErrorMessage('');
      const response = await servicesService.getServiceHistory(serviceId, { limit: 100 });
      setHistory(response);
    } catch (error) {
      setErrorMessage(
        error?.response?.data?.detail ||
          error?.data?.detail ||
          error?.message ||
          'Не удалось загрузить историю изменений.'
      );
      logger.error('Ошибка загрузки истории:', error);
    } finally {
      setLoading(false);
    }
  };

  const toggleExpand = (itemId) => {
    const newExpanded = new Set(expandedItems);
    if (newExpanded.has(itemId)) {
      newExpanded.delete(itemId);
    } else {
      newExpanded.add(itemId);
    }
    setExpandedItems(newExpanded);
  };

  const getActionIcon = (action) => {
    switch (action) {
      case 'create':
        return Plus;
      case 'update':
        return Edit;
      case 'delete':
        return Trash2;
      case 'activate':
        return Power;
      case 'deactivate':
        return PowerOff;
      default:
        return AlertCircle;
    }
  };

  const getActionColor = (action) => {
    switch (action) {
      case 'create':
        return 'var(--mac-success)';
      case 'update':
        return 'var(--mac-info)';
      case 'delete':
      case 'deactivate':
        return 'var(--mac-error)';
      case 'activate':
        return 'var(--mac-success)';
      default:
        return 'var(--mac-text-secondary)';
    }
  };

  const getActionLabel = (action) => {
    const labels = {
      create: 'Создание',
      update: 'Изменение',
      delete: 'Удаление',
      activate: 'Активация',
      deactivate: 'Деактивация'
    };
    return labels[action] || action;
  };

  const formatFieldName = (field) => {
    const fieldNames = {
      name: 'Название',
      code: 'Код',
      service_code: 'Код услуги',
      price: 'Цена',
      currency: 'Валюта',
      category_id: 'Категория',
      category_code: 'Код категории',
      duration_minutes: 'Длительность',
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

  const formatValue = (value) => {
    if (value === null || value === undefined) return '—';
    if (typeof value === 'boolean') return value ? 'Да' : 'Нет';
    if (typeof value === 'number') return value.toString();
    return String(value);
  };

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return new Intl.DateTimeFormat('ru-RU', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    }).format(date);
  };

  if (loading) {
    return (
      <MacOSCard
        variant="default"
        role="region"
        aria-label={historyRegionLabel}
        aria-busy={true}
        style={{ padding: '24px' }}
      >
        <AppLoading
          title="Загрузка истории изменений..."
          ariaLabel={historyRegionLabel}
          style={{ minHeight: 200 }}
        />
      </MacOSCard>
    );
  }

  if (errorMessage) {
    return (
      <MacOSCard
        variant="default"
        role="region"
        aria-label={historyRegionLabel}
        style={{ padding: '24px' }}
      >
        <AppError
          title="Не удалось загрузить историю изменений"
          description={errorMessage}
          action={
            <Button
              variant="outline"
              size="sm"
              aria-label={`Повторить загрузку. ${refreshHistoryLabel}`}
              onClick={loadHistory}
            >
              <RefreshCw size={14} style={{ marginRight: '6px' }} />
              Повторить
            </Button>
          }
        />
      </MacOSCard>
    );
  }

  if (history.length === 0) {
    return (
      <MacOSCard
        variant="default"
        role="region"
        aria-label={historyRegionLabel}
        style={{ padding: '24px' }}
      >
        <AppEmpty
          icon={History}
          title="История изменений пуста"
          description="Изменения услуги будут отображаться здесь."
        />
      </MacOSCard>
    );
  }

  return (
    <MacOSCard
      variant="default"
      role="region"
      aria-labelledby={historyTitleId}
      style={{ padding: '0' }}
    >
      <div style={{
        padding: '20px 24px',
        borderBottom: '1px solid var(--mac-border)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <History size={20} style={{ color: 'var(--mac-accent)' }} />
          <div>
            <h3 id={historyTitleId} style={{
              fontSize: '16px',
              fontWeight: '600',
              color: 'var(--mac-text-primary)',
              margin: 0
            }}>
              История изменений
            </h3>
            {serviceName && (
              <p style={{
                fontSize: '13px',
                color: 'var(--mac-text-secondary)',
                margin: '2px 0 0 0'
              }}>
                {serviceName}
              </p>
            )}
          </div>
        </div>
        <Button
          variant="outline"
          size="sm"
          aria-label={refreshHistoryLabel}
          onClick={loadHistory}
        >
          <RefreshCw size={14} style={{ marginRight: '6px' }} />
          Обновить
        </Button>
      </div>

      <div
        role="list"
        aria-label={historyRegionLabel}
        style={{ maxHeight: '600px', overflowY: 'auto' }}
      >
        {history.map((item, index) => {
          const ActionIcon = getActionIcon(item.action);
          const isExpanded = expandedItems.has(item.id);
          const hasChanges = item.changes && Object.keys(item.changes).length > 0;
          const changesPanelId = `service-audit-history-changes-${item.id}`;
          const changesCount = hasChanges ? Object.keys(item.changes).length : 0;
          const changesToggleLabel = isExpanded
            ? `Скрыть изменения записи ${getActionLabel(item.action)}`
            : `Показать изменения записи ${getActionLabel(item.action)} (${changesCount})`;

          return (
            <div
              key={item.id}
              role="listitem"
              style={{
                padding: '16px 24px',
                borderBottom: index < history.length - 1 ? '1px solid var(--mac-border)' : 'none',
                transition: 'background-color 0.2s ease'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                <div
                  style={{
                    width: '32px',
                    height: '32px',
                    borderRadius: '8px',
                    backgroundColor: `${getActionColor(item.action)}15`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0
                  }}
                >
                  <ActionIcon size={16} style={{ color: getActionColor(item.action) }} />
                </div>

                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                    <span style={{
                      fontSize: '14px',
                      fontWeight: '600',
                      color: 'var(--mac-text-primary)'
                    }}>
                      {getActionLabel(item.action)}
                    </span>
                    <Badge variant="outline" size="sm">
                      {item.action}
                    </Badge>
                  </div>

                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    fontSize: '13px',
                    color: 'var(--mac-text-secondary)',
                    marginBottom: hasChanges ? '8px' : '0'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <User size={12} />
                      <span>{item.user_name || 'Система'}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Clock size={12} />
                      <span>{formatDate(item.created_at)}</span>
                    </div>
                  </div>

                  {item.comment && (
                    <div style={{
                      fontSize: '13px',
                      color: 'var(--mac-text-secondary)',
                      fontStyle: 'italic',
                      marginBottom: hasChanges ? '8px' : '0'
                    }}>
                      {item.comment}
                    </div>
                  )}

                  {hasChanges && (
                    <>
                      <button
                        type="button"
                        onClick={() => toggleExpand(item.id)}
                        aria-expanded={isExpanded}
                        aria-controls={isExpanded ? changesPanelId : undefined}
                        aria-label={changesToggleLabel}
                        style={{
                          background: 'none',
                          border: 'none',
                          padding: '4px 0',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px',
                          fontSize: '13px',
                          color: 'var(--mac-accent)',
                          fontWeight: '500'
                        }}
                      >
                        {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                        {isExpanded ? 'Скрыть изменения' : `Показать изменения (${changesCount})`}
                      </button>

                      {isExpanded && (
                        <div
                          id={changesPanelId}
                          role="region"
                          aria-label={changesToggleLabel}
                          style={{
                            marginTop: '8px',
                            padding: '12px',
                            backgroundColor: 'var(--mac-bg-secondary)',
                            borderRadius: '8px'
                          }}
                        >
                          {Object.entries(item.changes).map(([field, change]) => (
                            <div
                              key={field}
                              style={{
                                display: 'grid',
                                gridTemplateColumns: '140px 1fr 1fr',
                                gap: '12px',
                                padding: '8px 0',
                                borderBottom: '1px solid var(--mac-border)',
                                fontSize: '13px'
                              }}
                            >
                              <div style={{
                                fontWeight: '600',
                                color: 'var(--mac-text-primary)'
                              }}>
                                {formatFieldName(field)}
                              </div>
                              <div style={{
                                color: 'var(--mac-error)',
                                textDecoration: 'line-through'
                              }}>
                                {formatValue(change.old)}
                              </div>
                              <div style={{
                                color: 'var(--mac-success)',
                                fontWeight: '500'
                              }}>
                                {formatValue(change.new)}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </MacOSCard>
  );
};

ServiceAuditHistory.propTypes = {
  serviceId: PropTypes.number.isRequired,
  serviceName: PropTypes.string
};

export default ServiceAuditHistory;
