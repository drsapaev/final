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
    ? t('admin2.sah_history_region_with_name', { name: serviceName })
    : t('admin2.sah_history_region');
  const refreshHistoryLabel = serviceName
    ? t('admin2.sah_refresh_aria_with_name', { name: serviceName })
    : t('admin2.sah_refresh_aria');
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
          t('admin2.sah_load_error')
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
      create: t('admin2.sah_action_create'),
      update: t('admin2.sah_action_update'),
      delete: t('admin2.sah_action_delete'),
      activate: t('admin2.sah_action_activate'),
      deactivate: t('admin2.sah_action_deactivate')
    };
    return labels[action] || action;
  };

  const formatFieldName = (field) => {
    const fieldNames = {
      name: t('admin2.sah_field_name'),
      code: t('admin2.sah_field_code'),
      service_code: t('admin2.sah_field_service_code'),
      price: t('admin2.sah_field_price'),
      currency: t('admin2.sah_field_currency'),
      category_id: t('admin2.sah_field_category_id'),
      category_code: t('admin2.sah_field_category_code'),
      duration_minutes: t('admin2.sah_field_duration_minutes'),
      doctor_id: t('admin2.sah_field_doctor_id'),
      department_key: t('admin2.sah_field_department_key'),
      queue_tag: t('admin2.sah_field_queue_tag'),
      requires_doctor: t('admin2.sah_field_requires_doctor'),
      is_consultation: t('admin2.sah_field_is_consultation'),
      allow_doctor_price_override: t('admin2.sah_field_allow_doctor_price_override'),
      active: t('admin2.sah_field_active')
    };
    return fieldNames[field] || field;
  };

  const formatValue = (value) => {
    if (value === null || value === undefined) return '—';
    if (typeof value === 'boolean') return value ? t('admin2.sah_value_yes') : t('admin2.sah_value_no');
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
          title={t('admin2.sah_loading_title')}
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
          title={t('admin2.sah_error_title')}
          description={errorMessage}
          action={
            <Button
              variant="outline"
              size="sm"
              aria-label={t('admin2.sah_retry_aria', { label: refreshHistoryLabel })}
              onClick={loadHistory}
            >
              <RefreshCw size={14} className="admin-mr-6" />
              {t('admin2.sah_retry')}
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
          title={t('admin2.sah_empty_title')}
          description={t('admin2.sah_empty_desc')}
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
              {t('admin2.sah_title')}
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
          {t('admin2.sah_refresh_btn')}
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
            ? t('admin2.sah_hide_changes_for_action', { action: getActionLabel(item.action) })
            : t('admin2.sah_show_changes_for_action', { action: getActionLabel(item.action), count: changesCount });

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
                      <span>{item.user_name || t('admin2.sah_system')}</span>
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
                        {isExpanded ? t('admin2.sah_hide_changes') : t('admin2.sah_show_changes', { count: changesCount })}
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
