import { useTranslation } from '../../i18n/useTranslation';
import { useState, useEffect, useCallback } from 'react';
import type { CSSProperties } from "react";
import PropTypes from 'prop-types';
import {
  MacOSCard,
  Button,
  Badge,
  Input,
  Checkbox,
  Select,
  Textarea,
  Skeleton,
  MacOSEmptyState,
} from '../ui/macos';
import {
  Plus,
  Edit,
  Trash2,
  Package,
  TrendingUp,
  Calendar,
  Clock,
  Percent,
  DollarSign,
  Users,
  BarChart3,
  Settings,
  Save,
  X,

  Play,
  Pause } from
'lucide-react';
import { toast } from 'react-toastify';

import { getApiOrigin } from '../../api/runtime';
import { api } from '../../api/client';
import logger from '../../utils/logger';
// P-013 fix: shared ConfirmDialog hook replacing native confirm() calls.
import { useConfirm } from '../common/ConfirmDialog';

// API base URL with fallback for development
void getApiOrigin();

// Module-level rule-type key-suffix map; resolved to translated labels via
// getRuleTypeLabel(ruleType, t) factory (DI pattern — see ServiceCatalog).
const PRICING_RULE_TYPE_KEYS = {
  time_based: 'dp_rule_type_time_based',
  volume_based: 'dp_rule_type_volume_based',
  seasonal: 'dp_rule_type_seasonal',
  loyalty: 'dp_rule_type_loyalty',
  package: 'dp_rule_type_package',
  dynamic: 'dp_rule_type_dynamic'
};

const getRuleTypeLabel = (ruleType, t) => {
  const key = PRICING_RULE_TYPE_KEYS[normalizePricingEnumValue(ruleType)];
  return key ? t(`admin2.${key}`) : ruleType;
};

const getRuleTypeOptions = (t) =>
  Object.entries(PRICING_RULE_TYPE_KEYS).map(([value, key]) => ({
    value,
    label: t(`admin2.${key}`)
  }));

// Module-level discount-type key-suffix map; resolved to translated labels via
// getDiscountTypeOptions(t) factory (DI pattern).
const DISCOUNT_TYPE_KEYS = [
  { value: 'percentage', key: 'dp_discount_type_percentage' },
  { value: 'fixed_amount', key: 'dp_discount_type_fixed_amount' },
  { value: 'buy_x_get_y', key: 'dp_discount_type_buy_x_get_y' },
  { value: 'tiered', key: 'dp_discount_type_tiered' }
];

const getDiscountTypeOptions = (t) =>
  DISCOUNT_TYPE_KEYS.map(({ value, key }) => ({
    value,
    label: t(`admin2.${key}`)
  }));

const normalizePricingEnumValue = (value) =>
  typeof value === 'string' ? value.toLowerCase() : value;

const normalizeServiceId = (value) => Number.parseInt(String(value), 10);

const getSelectedServiceIds = (value) =>
  Array.isArray(value)
    ? value.map(normalizeServiceId).filter((id) => !Number.isNaN(id))
    : [];

const toggleServiceId = (selectedIds, serviceId) => {
  const normalizedId = normalizeServiceId(serviceId);
  if (Number.isNaN(normalizedId)) {
    return getSelectedServiceIds(selectedIds);
  }

  const next = new Set(getSelectedServiceIds(selectedIds));
  if (next.has(normalizedId)) {
    next.delete(normalizedId);
  } else {
    next.add(normalizedId);
  }

  return Array.from(next);
};

const ServiceChecklist = ({ services = [], value = [], onChange }) => {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const selectedIds = getSelectedServiceIds(value);

  if (!services.length) {
    return (
      <div className="admin-checklist-empty">
        {t('admin2.dp_no_services')}
      </div>
    );
  }

  return (
    <div role="group" className="admin-checklist-container">
      <div className="admin-checklist-header">
        {selectedIds.length
          ? t('admin2.dp_selected_count', { count: selectedIds.length })
          : t('admin2.dp_not_selected')}
      </div>
      {services.map((service) => {
        const serviceId = normalizeServiceId(service.id);
        const checked = selectedIds.includes(serviceId);

        return (
          <div key={service.id} className="admin-checklist-item" style={{ '--admin-checklist-bg': checked ? 'var(--mac-accent-blue-light)' : 'var(--mac-bg-secondary)' } as CSSProperties}>
            <Checkbox
              checked={checked}
              onChange={() => onChange(toggleServiceId(selectedIds, service.id))}
              label={
                <span className="admin-flex-col-2">
                  <span>{service.name}</span>
                  <span className="admin-text-xs-secondary">
                    {service.price} {'\u20bd'}
                  </span>
                </span>
              }
            />
          </div>
        );
      })}
    </div>
  );
};

ServiceChecklist.propTypes = {
  services: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
      name: PropTypes.node,
      price: PropTypes.oneOfType([PropTypes.string, PropTypes.number])
    })
  ),
  value: PropTypes.arrayOf(PropTypes.oneOfType([PropTypes.string, PropTypes.number])),
  onChange: PropTypes.func.isRequired
};

const buildPricingRulePayload = (form) =>
  Object.fromEntries(
    Object.entries({
      ...form,
      rule_type: normalizePricingEnumValue(form.rule_type),
      discount_type: normalizePricingEnumValue(form.discount_type)
    }).filter(([, value]) => {
      if (value === '' || value === null || typeof value === 'undefined') {
        return false;
      }

      if (Array.isArray(value) && value.length === 0) {
        return false;
      }

      if (typeof value === 'number' && Number.isNaN(value)) {
        return false;
      }

      return true;
    })
  );

const DynamicPricingManager = () => {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  // P-013 fix: shared ConfirmDialog hook (replaces 2 native confirm() calls).
  const [confirmRaw, confirmDialog] = useConfirm();
  const confirm = confirmRaw as unknown as (opts: Record<string, unknown>) => Promise<boolean>;
  const [activeTab, setActiveTab] = useState('rules');
  const [pricingRules, setPricingRules] = useState([]);
  const [servicePackages, setServicePackages] = useState([]);
  const [services, setServices] = useState([]);
  const [analytics, setAnalytics] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [showCreateRule, setShowCreateRule] = useState(false);
  const [showCreatePackage, setShowCreatePackage] = useState(false);
  const [editingRule, setEditingRule] = useState(null); // P2 fix: restored value (was const [, setX]; UI not yet implemented)
  const [editingPackage, setEditingPackage] = useState(null); // P2 fix: restored value (same as above)

  // Форма для правила ценообразования
  const [ruleForm, setRuleForm] = useState({
    name: '',
    description: '',
    rule_type: 'time_based',
    discount_type: 'percentage',
    discount_value: 0,
    start_date: '',
    end_date: '',
    start_time: '',
    end_time: '',
    days_of_week: '',
    min_quantity: 1,
    max_quantity: '',
    min_amount: '',
    priority: 0,
    max_uses: '',
    service_ids: []
  });

  // Форма для пакета услуг
  const [packageForm, setPackageForm] = useState({
    name: '',
    description: '',
    service_ids: [],
    package_price: 0,
    valid_from: '',
    valid_to: '',
    max_purchases: '',
    per_patient_limit: ''
  });

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      // Загружаем услуги
      try {
        const response = (await api.get('/services')) as import('axios').AxiosResponse<Record<string, unknown>>;
        setServices(Array.isArray(response.data) ? response.data : []);
      } catch (e) {
        logger.error('Failed to load services:', e);
        setServices([]);
      }

      if (activeTab === 'rules') {
        // Загружаем правила ценообразования
        try {
          const response = (await api.get('/dynamic-pricing/pricing-rules')) as import('axios').AxiosResponse<Record<string, unknown>>;
          setPricingRules(Array.isArray(response.data) ? response.data : []);
        } catch (e) {
          logger.error('Failed to load pricing rules:', e);
          setPricingRules([]);
        }
      } else if (activeTab === 'packages') {
        // Загружаем пакеты услуг
        try {
          const response = (await api.get('/dynamic-pricing/service-packages')) as import('axios').AxiosResponse<Record<string, unknown>>;
          setServicePackages(Array.isArray(response.data) ? response.data : []);
        } catch (e) {
          logger.error('Failed to load packages:', e);
          setServicePackages([]);
        }
      } else if (activeTab === 'analytics') {
        // Загружаем аналитику
        try {
          const response = (await api.get('/dynamic-pricing/pricing-analytics')) as import('axios').AxiosResponse<Record<string, unknown>>;
          setAnalytics(response.data);
        } catch (e) {
          logger.error('Failed to load analytics:', e);
          setAnalytics(null);
        }
      }
    } catch (error) {
      logger.error('Ошибка загрузки данных:', error);
      toast.error(t('admin2.dp_load_error'));
    } finally {
      setLoading(false);
    }
  }, [activeTab, t]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleCreateRule = async () => {
    try {
      await api.post('/dynamic-pricing/pricing-rules', buildPricingRulePayload(ruleForm));
      toast.success(t('admin2.dp_rule_create_success'));
      setShowCreateRule(false);
      setRuleForm({
        name: '',
        description: '',
        rule_type: 'time_based',
        discount_type: 'percentage',
        discount_value: 0,
        start_date: '',
        end_date: '',
        start_time: '',
        end_time: '',
        days_of_week: '',
        min_quantity: 1,
        max_quantity: '',
        min_amount: '',
        priority: 0,
        max_uses: '',
        service_ids: []
      });
      loadData();
    } catch (error) {
      logger.error('Ошибка создания правила:', error);
      toast.error(error.response?.data?.detail || t('admin2.dp_rule_create_error'));
    }
  };

  const handleCreatePackage = async () => {
    try {
      await api.post('/dynamic-pricing/service-packages', packageForm);
      toast.success(t('admin2.dp_package_create_success'));
      setShowCreatePackage(false);
      setPackageForm({
        name: '',
        description: '',
        service_ids: [],
        package_price: 0,
        valid_from: '',
        valid_to: '',
        max_purchases: '',
        per_patient_limit: ''
      });
      loadData();
    } catch (error) {
      logger.error('Ошибка создания пакета:', error);
      toast.error(error.response?.data?.detail || t('admin2.dp_package_create_error'));
    }
  };

  const handleToggleRule = async (ruleId, isActive) => {
    try {
      await api.put(`/dynamic-pricing/pricing-rules/${ruleId}`, { is_active: !isActive });
      toast.success(isActive ? t('admin2.dp_rule_deactivated') : t('admin2.dp_rule_activated'));
      loadData();
    } catch (error) {
      logger.error('Ошибка изменения статуса правила:', error);
      toast.error(t('admin2.dp_rule_status_error'));
    }
  };

  const handleDeleteRule = async (ruleId) => {
    // P-013 fix: replaced native confirm() with shared useConfirm hook.
    const ok = await confirm({
      title: t('admin2.delete_rule_title'),
      message: t('admin2.dp_delete_rule_message'),
      description: t('admin2.dp_action_irreversible'),
      confirmLabel: t('admin2.delete_confirm'),
      cancelLabel: t('admin2.cancel'),
      intent: 'danger',
    });
    if (!ok) return;

    try {
      await api.delete(`/dynamic-pricing/pricing-rules/${ruleId}`);
      toast.success(t('admin2.dp_rule_deleted'));
      loadData();
    } catch (error) {
      logger.error('Ошибка удаления правила:', error);
      toast.error(t('admin2.dp_rule_delete_error'));
    }
  };

  const handleDeletePackage = async (packageId) => {
    // P-013 fix: replaced native confirm() with shared useConfirm hook.
    const ok = await confirm({
      title: t('admin2.delete_package_title'),
      message: t('admin2.dp_delete_package_message'),
      description: t('admin2.dp_action_irreversible'),
      confirmLabel: t('admin2.delete_confirm'),
      cancelLabel: t('admin2.cancel'),
      intent: 'danger',
    });
    if (!ok) return;

    try {
      await api.delete(`/dynamic-pricing/service-packages/${packageId}`);
      toast.success(t('admin2.dp_package_deleted'));
      loadData();
    } catch (error) {
      logger.error('Ошибка удаления пакета:', error);
      toast.error(t('admin2.dp_package_delete_error'));
    }
  };

  const handleUpdateDynamicPrices = async () => {
    try {
      const response = (await api.post('/dynamic-pricing/update-dynamic-prices')) as import('axios').AxiosResponse<Record<string, unknown>>;
      toast.success(t('admin2.dp_prices_updated', { updated: response.data.updated_count, total: response.data.total_services }));
    } catch (error) {
      logger.error('Ошибка обновления цен:', error);
      toast.error(t('admin2.dp_prices_update_error'));
    }
  };

  const renderRulesTab = () =>
  <div className="flex flex-col gap-6">
      {/* Заголовок и кнопки */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="admin-section-h3">
            {t('admin2.dp_rules_title')}
          </h3>
          <p className="admin-section-desc">
            {t('admin2.dp_rules_desc')}
          </p>
        </div>
        <div className="admin-flex-gap-8">
          <Button
          onClick={handleUpdateDynamicPrices}
          variant="outline"
          className="flex items-center justify-center gap-2">
          
            <TrendingUp size={16} />
            {t('admin2.dp_update_prices_btn')}
          </Button>
          <Button
          onClick={() => setShowCreateRule(true)}
          className="flex items-center justify-center gap-2">
          
            <Plus size={16} />
            {t('admin2.dp_create_rule_btn')}
          </Button>
        </div>
      </div>

      {/* Список правил */}
      <div className="admin-grid-gap-16">
        {pricingRules.length === 0 ?
      <MacOSEmptyState
        type="rule"
        title={t('admin2.dp_rules_empty_title')}
        description={t('admin2.dp_rules_empty_desc')}
        action={
        <Button onClick={() => setShowCreateRule(true)}>
                <Plus size={16} className="mr-2" />
                {t('admin2.dp_create_first_rule_btn')}
              </Button>
        } /> :


      pricingRules.map((rule) =>
      <MacOSCard key={rule.id} className="p-0">
              <div className="admin-card-header-flex-start">
                <div className="admin-flex-1">
                  <div className="admin-card-title-badges">
                    <h4 className="admin-rule-header">
                      {(rule as { name?: string })?.name}
                    </h4>
                    <Badge variant={rule.is_active ? 'success' : 'secondary'}>
                      {rule.is_active ? t('admin2.dp_rule_active') : t('admin2.dp_rule_inactive')}
                    </Badge>
                  <Badge variant="outline">
                      {getRuleTypeLabel(rule.rule_type, t)}
                    </Badge>
                  </div>

                  <p className="admin-rule-desc">
                    {rule.description}
                  </p>

                  <div className="admin-stats-row-info">
                    <span className="admin-flex-center-4">
                      <Percent size={12} />
                      {normalizePricingEnumValue(rule.discount_type) === 'percentage' ? t('admin2.dp_value_percent', { value: rule.discount_value }) : t('admin2.dp_value_currency', { value: rule.discount_value, currency: t('admin2.dp_currency') })}
                    </span>
                    <span className="admin-flex-center-4">
                      <Users size={12} />
                      {t('admin2.dp_uses_count', { count: rule.current_uses || 0 })}
                      {rule.max_uses && ` / ${rule.max_uses}`}
                    </span>
                    <span className="admin-flex-center-4">
                      <BarChart3 size={12} />
                      {t('admin2.dp_priority_value', { priority: rule.priority })}
                    </span>
                  </div>

                  {(rule.start_time || rule.end_time) &&
            <div className="admin-time-info">
                      <Clock size={12} />
                      {rule.start_time} - {rule.end_time}
                    </div>
            }
                </div>

                <div className="admin-flex-gap-8">
                  <Button
              variant="outline"
              onClick={() => handleToggleRule(rule.id, rule.is_active)}
              className="admin-icon-btn-32"
              title={rule.is_active ? t('admin2.dp_pause_rule_title') : t('admin2.dp_activate_rule_title')}
              type="button"
              aria-label={rule.is_active ? t('admin2.dp_pause_rule_aria', { name: (rule as { name?: string })?.name || rule.id }) : t('admin2.dp_activate_rule_aria', { name: (rule as { name?: string })?.name || rule.id })}>

                    {rule.is_active ? <Pause aria-hidden="true" size={16} /> : <Play aria-hidden="true" size={16} />}
                  </Button>
                  <Button
              variant="outline"
              onClick={() => setEditingRule(rule)}
              className="admin-icon-btn-32"
              title={t('admin2.dp_edit_rule_title')}
              type="button"
              aria-label={t('admin2.dp_edit_rule_aria', { name: (rule as { name?: string })?.name || rule.id })}>

                    <Edit aria-hidden="true" size={16} />
                  </Button>
                  <Button
              variant="outline"
              onClick={() => handleDeleteRule(rule.id)}
              className="admin-icon-btn-32"
              title={t('admin2.dp_delete_rule_title_btn')}
              type="button"
              aria-label={t('admin2.dp_delete_rule_aria', { name: (rule as { name?: string })?.name || rule.id })}>

                    <Trash2 aria-hidden="true" size={16} />
                  </Button>
                </div>
              </div>
            </MacOSCard>
      )
      }
      </div>

      {/* Форма создания правила */}
      {showCreateRule &&
    <MacOSCard className="p-6">
          <div className="admin-card-header-between">
            <h4 className="admin-section-h3-m0">
              {t('admin2.dp_create_rule_form_title')}
            </h4>
            <Button
              variant="outline"
              onClick={() => setShowCreateRule(false)}
              type="button"
              title={t('admin2.dp_close_rule_form')}
              aria-label={t('admin2.dp_close_rule_form')}>
              <X aria-hidden="true" size={16} />
            </Button>
          </div>

          <div className="admin-grid-form-2col">
            <div>
              <label className="block text-sm font-medium text-[var(--mac-text-secondary)] mb-2">
                {t('admin2.dp_label_name')}
              </label>
              <Input
            value={ruleForm.name}
            onChange={(e) => setRuleForm({ ...ruleForm, name: e.target.value })}
            placeholder={t('admin2.dp_rule_name_ph')} />
          
            </div>

            <div>
              <label className="block text-sm font-medium text-[var(--mac-text-secondary)] mb-2">
                {t('admin2.dp_label_rule_type')}
              </label>
              <Select
            value={ruleForm.rule_type}
            onChange={(value: unknown) => setRuleForm({ ...ruleForm, rule_type: String(value) })}
            options={getRuleTypeOptions(t)}
            size="large" />
            </div>

            <div>
              <label className="block text-sm font-medium text-[var(--mac-text-secondary)] mb-2">
                {t('admin2.dp_label_discount_type')}
              </label>
              <Select
            value={ruleForm.discount_type}
            onChange={(value: unknown) => setRuleForm({ ...ruleForm, discount_type: String(value) })}
            options={getDiscountTypeOptions(t)}
            size="large" />
            </div>

            <div>
              <label className="block text-sm font-medium text-[var(--mac-text-secondary)] mb-2">
                {t('admin2.dp_label_discount_value')}
              </label>
              <Input
            type="number"
            value={ruleForm.discount_value}
            onChange={(e) => setRuleForm({ ...ruleForm, discount_value: parseFloat(e.target.value) })}
            placeholder="10" />
          
            </div>

            <div>
              <label className="block text-sm font-medium text-[var(--mac-text-secondary)] mb-2">
                {t('admin2.dp_label_start_time')}
              </label>
              <Input
            type="time"
            value={ruleForm.start_time}
            onChange={(e) => setRuleForm({ ...ruleForm, start_time: e.target.value + ':00' })} />
          
            </div>

            <div>
              <label className="block text-sm font-medium text-[var(--mac-text-secondary)] mb-2">
                {t('admin2.dp_label_end_time')}
              </label>
              <Input
            type="time"
            value={ruleForm.end_time}
            onChange={(e) => setRuleForm({ ...ruleForm, end_time: e.target.value + ':00' })} />
          
            </div>

            <div>
              <label className="block text-sm font-medium text-[var(--mac-text-secondary)] mb-2">
                {t('admin2.dp_label_min_quantity')}
              </label>
              <Input
            type="number"
            value={ruleForm.min_quantity}
            onChange={(e) => setRuleForm({ ...ruleForm, min_quantity: parseInt(e.target.value) })}
            placeholder="1" />
          
            </div>

            <div>
              <label className="block text-sm font-medium text-[var(--mac-text-secondary)] mb-2">
                {t('admin2.dp_label_priority')}
              </label>
              <Input
            type="number"
            value={ruleForm.priority}
            onChange={(e) => setRuleForm({ ...ruleForm, priority: parseInt(e.target.value) })}
            placeholder="0" />
          
            </div>

            <div className="admin-grid-span-2">
              <label className="block text-sm font-medium text-[var(--mac-text-secondary)] mb-2">
                {t('admin2.dp_label_description')}
              </label>
              <Textarea
            value={ruleForm.description}
            onChange={(e) => setRuleForm({ ...ruleForm, description: e.target.value })}
            placeholder={t('admin2.dp_rule_description_ph')} />
          
            </div>

            <div className="admin-grid-span-2">
              <label className="block text-sm font-medium text-[var(--mac-text-secondary)] mb-2">
                {t('admin2.dp_label_services')}
              </label>
              <ServiceChecklist
            services={services}
            value={ruleForm.service_ids}
            onChange={(serviceIds) => setRuleForm({ ...ruleForm, service_ids: serviceIds })}
          ></ServiceChecklist>
            </div>
          </div>

          <div className="admin-form-actions-end-8">
            <Button variant="outline" onClick={() => setShowCreateRule(false)}>
              {t('admin2.dp_cancel_btn')}
            </Button>
            <Button onClick={handleCreateRule}>
              <Save size={16} className="mr-2" />
              {t('admin2.dp_create_btn')}
            </Button>
          </div>
        </MacOSCard>
    }
    </div>;


  const renderPackagesTab = () =>
  <div className="flex flex-col gap-6">
      {/* Заголовок и кнопки */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="admin-section-h3">
            {t('admin2.dp_packages_title')}
          </h3>
          <p className="admin-section-desc">
            {t('admin2.dp_packages_desc')}
          </p>
        </div>
        <Button
        onClick={() => setShowCreatePackage(true)}
        className="flex items-center justify-center gap-2">
        
          <Plus size={16} />
          {t('admin2.dp_create_package_btn')}
        </Button>
      </div>

      {/* Список пакетов */}
      <div className="admin-grid-gap-16">
        {servicePackages.length === 0 ?
      <MacOSEmptyState
        type="package"
        title={t('admin2.dp_packages_empty_title')}
        description={t('admin2.dp_packages_empty_desc')}
        action={
        <Button onClick={() => setShowCreatePackage(true)}>
                <Plus size={16} className="mr-2" />
                {t('admin2.dp_create_first_package_btn')}
              </Button>
        } /> :


      servicePackages.map((pkg) =>
      <MacOSCard key={pkg.id} className="p-0">
              <div className="admin-card-header-flex-start">
                <div className="admin-flex-1">
                  <div className="admin-card-title-badges">
                    <h4 className="admin-rule-header">
                      {(pkg as { name?: string })?.name}
                    </h4>
                    <Badge variant={pkg.is_active ? 'success' : 'secondary'}>
                      {pkg.is_active ? t('admin2.dp_package_active') : t('admin2.dp_package_inactive')}
                    </Badge>
                  </div>

                  <p className="admin-rule-desc">
                    {pkg.description}
                  </p>

                  <div className="admin-flex-center-16-sm">
                    <span className="admin-price-savings">
                      <DollarSign size={12} />
                      {t('admin2.dp_value_currency', { value: pkg.package_price, currency: t('admin2.dp_currency') })}
                    </span>
                    {pkg.original_price &&
              <span className="admin-price-strike">
                        {t('admin2.dp_value_currency', { value: pkg.original_price, currency: t('admin2.dp_currency') })}
                      </span>
              }
                    {pkg.savings_percentage &&
              <Badge variant="success">
                        {t('admin2.dp_savings_badge', { percent: pkg.savings_percentage.toFixed(0) })}
                      </Badge>
              }
                    <span className="text-[var(--mac-text-secondary)]">
                      {t('admin2.dp_purchases_count', { count: pkg.current_purchases || 0 })}
                      {pkg.max_purchases && ` / ${pkg.max_purchases}`}
                    </span>
                  </div>

                  {(pkg.valid_from || pkg.valid_to) &&
            <div className="admin-time-info">
                      <Calendar size={12} />
                      {pkg.valid_from && new Date(pkg.valid_from).toLocaleDateString()} -
                      {pkg.valid_to && new Date(pkg.valid_to).toLocaleDateString()}
                    </div>
            }
                </div>

                <div className="admin-flex-gap-8">
                  <Button
              variant="outline"
              onClick={() => setEditingPackage(pkg)}
              className="admin-icon-btn-32"
              title={t('admin2.dp_edit_package_title')}
              type="button"
              aria-label={t('admin2.dp_edit_package_aria', { name: (pkg as { name?: string })?.name || pkg.id })}>

                    <Edit aria-hidden="true" size={16} />
                  </Button>
                  <Button
              variant="outline"
              onClick={() => handleDeletePackage(pkg.id)}
              className="admin-icon-btn-32"
              title={t('admin2.dp_delete_package_title_btn')}
              type="button"
              aria-label={t('admin2.dp_delete_package_aria', { name: (pkg as { name?: string })?.name || pkg.id })}>

                    <Trash2 aria-hidden="true" size={16} />
                  </Button>
                </div>
              </div>
            </MacOSCard>
      )
      }
      </div>

      {/* Форма создания пакета */}
      {showCreatePackage &&
    <MacOSCard className="p-6">
          <div className="admin-card-header-between">
            <h4 className="admin-section-h3-m0">
              {t('admin2.dp_create_package_form_title')}
            </h4>
            <Button
              variant="outline"
              onClick={() => setShowCreatePackage(false)}
              type="button"
              title={t('admin2.dp_close_package_form')}
              aria-label={t('admin2.dp_close_package_form')}>
              <X aria-hidden="true" size={16} />
            </Button>
          </div>

          <div className="admin-grid-form-2col">
            <div>
              <label className="block text-sm font-medium text-[var(--mac-text-secondary)] mb-2">
                {t('admin2.dp_label_name')}
              </label>
              <Input
            value={packageForm.name}
            onChange={(e) => setPackageForm({ ...packageForm, name: e.target.value })}
            placeholder={t('admin2.dp_package_name_ph')} />
          
            </div>

            <div>
              <label className="block text-sm font-medium text-[var(--mac-text-secondary)] mb-2">
                {t('admin2.dp_label_package_price')}
              </label>
              <Input
            type="number"
            value={packageForm.package_price}
            onChange={(e) => setPackageForm({ ...packageForm, package_price: parseFloat(e.target.value) })}
            placeholder="0" />
          
            </div>

            <div>
              <label className="block text-sm font-medium text-[var(--mac-text-secondary)] mb-2">
                {t('admin2.dp_label_valid_from')}
              </label>
              <Input
            type="datetime-local"
            value={packageForm.valid_from}
            onChange={(e) => setPackageForm({ ...packageForm, valid_from: e.target.value })} />
          
            </div>

            <div>
              <label className="block text-sm font-medium text-[var(--mac-text-secondary)] mb-2">
                {t('admin2.dp_label_valid_to')}
              </label>
              <Input
            type="datetime-local"
            value={packageForm.valid_to}
            onChange={(e) => setPackageForm({ ...packageForm, valid_to: e.target.value })} />
          
            </div>

            <div className="admin-grid-span-2">
              <label className="block text-sm font-medium text-[var(--mac-text-secondary)] mb-2">
                {t('admin2.dp_label_description')}
              </label>
              <Textarea
            value={packageForm.description}
            onChange={(e) => setPackageForm({ ...packageForm, description: e.target.value })}
            placeholder={t('admin2.dp_package_description_ph')} />
          
            </div>

            <div className="admin-grid-span-2">
              <label className="block text-sm font-medium text-[var(--mac-text-secondary)] mb-2">
                {t('admin2.dp_label_package_services')}
              </label>
              <ServiceChecklist
            services={services}
            value={packageForm.service_ids}
            onChange={(serviceIds) => setPackageForm({ ...packageForm, service_ids: serviceIds })}
          ></ServiceChecklist>
            </div>
          </div>

          <div className="admin-form-actions-end-8">
            <Button variant="outline" onClick={() => setShowCreatePackage(false)}>
              {t('admin2.dp_cancel_btn')}
            </Button>
            <Button onClick={handleCreatePackage}>
              <Save size={16} className="mr-2" />
              {t('admin2.dp_create_btn')}
            </Button>
          </div>
        </MacOSCard>
    }
    </div>;


  const renderAnalyticsTab = () =>
  <div className="flex flex-col gap-6">
      <div>
        <h3 className="admin-section-h3">
          {t('admin2.dp_analytics_title')}
        </h3>
        <p className="admin-section-desc">
          {t('admin2.dp_analytics_desc')}
        </p>
      </div>

      {analytics ?
    <div className="admin-grid-auto-300">
          <MacOSCard className="p-0">
            <div className="admin-card-title-badges">
              <TrendingUp size={20} color="var(--mac-accent)" />
              <h4 className="admin-rule-header">
                {t('admin2.dp_analytics_total_savings')}
              </h4>
            </div>
            <div className="admin-stats-value-success">
              {t('admin2.dp_value_currency', { value: (analytics.summary as { total_savings?: number })?.total_savings?.toLocaleString() || 0, currency: t('admin2.dp_currency') })}
            </div>
            <p className="admin-stats-label">
              {t('admin2.dp_analytics_period', {
                start: (analytics.period as { start_date?: string })?.start_date ? new Date((analytics.period as { start_date?: string })?.start_date).toLocaleDateString() : '',
                end: (analytics.period as { end_date?: string })?.end_date ? new Date((analytics.period as { end_date?: string })?.end_date).toLocaleDateString() : ''
              })}
            </p>
          </MacOSCard>

          <MacOSCard className="p-0">
            <div className="admin-card-title-badges">
              <Settings size={20} color="var(--mac-purple)" />
              <h4 className="admin-rule-header">
                {t('admin2.dp_analytics_active_rules')}
              </h4>
            </div>
            <div className="admin-stats-value-primary">
              {Number((analytics.summary as { active_rules_count?: number })?.active_rules_count ?? 0)}
            </div>
            <p className="admin-stats-label">
              {t('admin2.dp_analytics_active_rules_sub')}
            </p>
          </MacOSCard>

          <MacOSCard className="p-0">
            <div className="admin-card-title-badges">
              <Package size={20} color="var(--mac-orange)" />
              <h4 className="admin-rule-header">
                {t('admin2.dp_analytics_active_packages')}
              </h4>
            </div>
            <div className="admin-stats-value-primary">
              {Number((analytics.summary as { active_packages_count?: number })?.active_packages_count ?? 0)}
            </div>
            <p className="admin-stats-label">
              {t('admin2.dp_analytics_active_packages_sub')}
            </p>
          </MacOSCard>
        </div> :

    <MacOSEmptyState
      type="analytics"
      title={t('admin2.dp_analytics_empty_title')}
      description={t('admin2.dp_analytics_empty_desc')} />

    }

      {analytics?.rules_statistics &&
    <MacOSCard className="p-4">
          <h4 className="admin-rule-header mb-4">
            {t('admin2.dp_analytics_rules_stats')}
          </h4>
          <div className="flex flex-col gap-2">
            {(analytics.rules_statistics as unknown[] ?? []).map((rule, index) =>
        <div key={index} className="admin-stat-list-row">
                <span className="admin-text-med-primary">
                  {(rule as { name?: string })?.name}
                </span>
                <div className="admin-flex-center-16-sm">
                  <span className="text-[var(--mac-text-secondary)]">
                    {t('admin2.dp_uses_count', { count: (rule as { uses?: number })?.uses })}
                  </span>
                  <span className="text-[var(--mac-success)]">
                    {t('admin2.dp_savings_value', { value: (rule as { total_savings?: number })?.total_savings?.toLocaleString() || 0, currency: t('admin2.dp_currency') })}
                  </span>
                </div>
              </div>
        )}
          </div>
        </MacOSCard>
    }

      {analytics?.packages_statistics &&
    <MacOSCard className="p-4">
          <h4 className="admin-rule-header mb-4">
            {t('admin2.dp_analytics_packages_stats')}
          </h4>
          <div className="flex flex-col gap-2">
            {(analytics.packages_statistics as unknown[] ?? []).map((pkg, index) =>
        <div key={index} className="admin-stat-list-row">
                <span className="admin-text-med-primary">
                  {(pkg as { name?: string })?.name}
                </span>
                <div className="admin-flex-center-16-sm">
                  <span className="text-[var(--mac-text-secondary)]">
                    {t('admin2.dp_purchases_count', { count: (pkg as { purchases?: number })?.purchases })}
                  </span>
                  <span className="text-[var(--mac-success)]">
                    {t('admin2.dp_savings_value', { value: (pkg as { total_savings?: number })?.total_savings?.toLocaleString() || 0, currency: t('admin2.dp_currency') })}
                  </span>
                </div>
              </div>
        )}
          </div>
        </MacOSCard>
    }
    </div>;


  const tabs = [
  { id: 'rules', label: t('admin2.dp_tab_rules'), icon: Settings },
  { id: 'packages', label: t('admin2.dp_tab_packages'), icon: Package },
  { id: 'analytics', label: t('admin2.dp_tab_analytics'), icon: BarChart3 }];


  return (
    <div className="admin-p-0-max-1400">
      <div className="admin-flex-center-16 mb-6">
        <Package size={24} color="var(--mac-accent)" />
        <div>
          <h2 className="admin-page-title">
            {t('admin2.dp_page_title')}
          </h2>
          <p className="admin-page-subtitle">
            {t('admin2.dp_page_subtitle')}
          </p>
        </div>
      </div>

      {/* Табы */}
      <div className="admin-tab-bar">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className="admin-dp-tab-btn"
              style={{
                '--admin-tab-border': isActive ? '2px solid var(--mac-accent)' : '2px solid transparent',
                '--admin-tab-color': isActive ? 'var(--mac-accent)' : 'var(--mac-text-secondary)',
                '--admin-tab-weight': isActive ? 'var(--mac-font-weight-semibold)' : 'var(--mac-font-weight-normal)'
              } as CSSProperties}>
              
              <Icon size={16} />
              {tab.label}
            </button>);

        })}
      </div>

      {/* Контент */}
      {loading ?
      <Skeleton type="card" count={3} /> :

      <>
          {activeTab === 'rules' && renderRulesTab()}
          {activeTab === 'packages' && renderPackagesTab()}
          {activeTab === 'analytics' && renderAnalyticsTab()}
        </>
      }
      {/* P-013 fix: portal-mounted ConfirmDialog rendered once per panel */}
      {confirmDialog as unknown as React.ReactNode}
    </div>);

};

export default DynamicPricingManager;
