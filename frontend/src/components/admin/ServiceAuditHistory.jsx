import { useTranslation } from '../../i18n/useTranslation';
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
  const { t } = useTranslation();
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
        className="admin-p-24"
      >
        <AppLoading
          title="Загрузка истории изменений..."
          ariaLabel={historyRegionLabel}
          className="admin-minh-200"
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
        className="admin-p-24"
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
              <RefreshCw size={14} className="admin-mr-6" />
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
        className="admin-p-24"
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
      className="admin-p-0"
    >
      <div className="admin-p-20px-24px-bd-b-1px-solid-var-mac-bo-d-flex-ai-center-jc-between">
        <div className="admin-flex-center-12">
          <History size={20} className="admin-accent" />
          <div>
            <h3 id={historyTitleId} className="admin-fs-16-fw-600-primary-m-0">
              История изменений
            </h3>
            {serviceName && (
              <p className="admin-fs-13-secondary-m-2px-0-0-0">
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
          <RefreshCw size={14} className="admin-mr-6" />
          Обновить
        </Button>
      </div>

      <div
        role="list"
        aria-label={historyRegionLabel}
        className="admin-maxh-600-ovy-auto"
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
              className="admin-p-16px-24px-tr-background-color-0-2-bd-b-dyn" style={{ '--admin-bd-b0': index < history.length - 1 ? '1px solid var(--mac-border)' : 'none' }}
            >
              <div className="admin-d-flex-ai-start-gap-12">
                <div
                  className="admin-w-32-h-32-radius-8-d-flex-ai-center-jc-center-fsk-0-bgc-dyn" style={{ '--admin-bgc0': `${getActionColor(item.action)}15` }}
                >
                  <ActionIcon size={16} className="admin-col-dyn" style={{ '--admin-col0': getActionColor(item.action) }} />
                </div>

                <div className="admin-flex-1-minw-0">
                  <div className="admin-d-flex-ai-center-gap-8-mb-4">
                    <span className="admin-fs-14-fw-600-primary-1">
                      {getActionLabel(item.action)}
                    </span>
                    <Badge variant="outline" size="sm">
                      {item.action}
                    </Badge>
                  </div>

                  <div className="admin-d-flex-ai-center-gap-12-fs-13-secondary-mb-dyn" style={{ '--admin-mb0': hasChanges ? '8px' : '0' }}>
                    <div className="admin-flex-center admin-gap-4">
                      <User size={12} />
                      <span>{item.user_name || 'Система'}</span>
                    </div>
                    <div className="admin-flex-center admin-gap-4">
                      <Clock size={12} />
                      <span>{formatDate(item.created_at)}</span>
                    </div>
                  </div>

                  {item.comment && (
                    <div className="admin-fs-13-secondary-fst-italic-mb-dyn" style={{ '--admin-mb0': hasChanges ? '8px' : '0' }}>
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
                        className="admin-bg-none-bd-none-p-4px-0-cur-pointer-d-flex-ai-center-gap-4-fs-13-accent-fw-500"
                      >
                        {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                        {isExpanded ? 'Скрыть изменения' : `Показать изменения (${changesCount})`}
                      </button>

                      {isExpanded && (
                        <div
                          id={changesPanelId}
                          role="region"
                          aria-label={changesToggleLabel}
                          className="admin-mt-8-p-12-bgc-bg-secondary-radius-8"
                        >
                          {Object.entries(item.changes).map(([field, change]) => (
                            <div
                              key={field}
                              className="admin-d-grid-gtc-140px-1fr-1fr-gap-12-p-8px-0-bd-b-1px-solid-var-mac-bo-fs-13"
                            >
                              <div className="admin-fw-600-primary">
                                {formatFieldName(field)}
                              </div>
                              <div className="admin-error-td-line-through">
                                {formatValue(change.old)}
                              </div>
                              <div className="admin-success-fw-500">
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
