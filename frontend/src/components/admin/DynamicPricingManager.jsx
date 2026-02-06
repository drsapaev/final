import React, { useState, useEffect } from 'react';
import {
  MacOSCard,
  MacOSButton,
  MacOSBadge,
  MacOSInput,
  MacOSSelect,
  MacOSTextarea,
  MacOSLoadingSkeleton,
  MacOSEmptyState,
  MacOSAlert
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
  Eye,
  Play,
  Pause
} from 'lucide-react';
import { toast } from 'react-toastify';

import { api } from '../../api/client';
import logger from '../../utils/logger';

// API base URL with fallback for development
const API_BASE = import.meta.env.VITE_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';

const DynamicPricingManager = () => {
  const [activeTab, setActiveTab] = useState('rules');
  const [pricingRules, setPricingRules] = useState([]);
  const [servicePackages, setServicePackages] = useState([]);
  const [services, setServices] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showCreateRule, setShowCreateRule] = useState(false);
  const [showCreatePackage, setShowCreatePackage] = useState(false);
  const [editingRule, setEditingRule] = useState(null);
  const [editingPackage, setEditingPackage] = useState(null);

  // Форма для правила ценообразования
  const [ruleForm, setRuleForm] = useState({
    name: '',
    description: '',
    rule_type: 'TIME_BASED',
    discount_type: 'PERCENTAGE',
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

  useEffect(() => {
    loadData();
  }, [activeTab]);

  const loadData = async () => {
    setLoading(true);
    try {
      // Загружаем услуги
      try {
        const response = await api.get('/services');
        setServices(Array.isArray(response.data) ? response.data : []);
      } catch (e) {
        logger.error('Failed to load services:', e);
        setServices([]);
      }

      if (activeTab === 'rules') {
        // Загружаем правила ценообразования
        try {
          const response = await api.get('/dynamic-pricing/pricing-rules');
          setPricingRules(Array.isArray(response.data) ? response.data : []);
        } catch (e) {
          logger.error('Failed to load pricing rules:', e);
          setPricingRules([]);
        }
      } else if (activeTab === 'packages') {
        // Загружаем пакеты услуг
        try {
          const response = await api.get('/dynamic-pricing/service-packages');
          setServicePackages(Array.isArray(response.data) ? response.data : []);
        } catch (e) {
          logger.error('Failed to load packages:', e);
          setServicePackages([]);
        }
      } else if (activeTab === 'analytics') {
        // Загружаем аналитику
        try {
          const response = await api.get('/dynamic-pricing/pricing-analytics');
          setAnalytics(response.data);
        } catch (e) {
          logger.error('Failed to load analytics:', e);
          setAnalytics(null);
        }
      }
    } catch (error) {
      logger.error('Ошибка загрузки данных:', error);
      toast.error('Ошибка загрузки данных');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateRule = async () => {
    try {
      await api.post('/dynamic-pricing/pricing-rules', ruleForm);
      toast.success('Правило создано успешно');
      setShowCreateRule(false);
      setRuleForm({
        name: '',
        description: '',
        rule_type: 'TIME_BASED',
        discount_type: 'PERCENTAGE',
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
      toast.error(error.response?.data?.detail || 'Ошибка создания правила');
    }
  };

  const handleCreatePackage = async () => {
    try {
      await api.post('/dynamic-pricing/service-packages', packageForm);
      toast.success('Пакет создан успешно');
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
      toast.error(error.response?.data?.detail || 'Ошибка создания пакета');
    }
  };

  const handleToggleRule = async (ruleId, isActive) => {
    try {
      await api.put(`/dynamic-pricing/pricing-rules/${ruleId}`, { is_active: !isActive });
      toast.success(isActive ? 'Правило деактивировано' : 'Правило активировано');
      loadData();
    } catch (error) {
      logger.error('Ошибка изменения статуса правила:', error);
      toast.error('Ошибка изменения статуса правила');
    }
  };

  const handleDeleteRule = async (ruleId) => {
    if (!confirm('Вы уверены, что хотите удалить это правило?')) return;

    try {
      await api.delete(`/dynamic-pricing/pricing-rules/${ruleId}`);
      toast.success('Правило удалено');
      loadData();
    } catch (error) {
      logger.error('Ошибка удаления правила:', error);
      toast.error('Ошибка удаления правила');
    }
  };

  const handleDeletePackage = async (packageId) => {
    if (!confirm('Вы уверены, что хотите удалить этот пакет?')) return;

    try {
      await api.delete(`/dynamic-pricing/service-packages/${packageId}`);
      toast.success('Пакет удален');
      loadData();
    } catch (error) {
      logger.error('Ошибка удаления пакета:', error);
      toast.error('Ошибка удаления пакета');
    }
  };

  const handleUpdateDynamicPrices = async () => {
    try {
      const response = await api.post('/dynamic-pricing/update-dynamic-prices');
      toast.success(`Обновлено цен: ${response.data.updated_count} из ${response.data.total_services}`);
    } catch (error) {
      logger.error('Ошибка обновления цен:', error);
      toast.error('Ошибка обновления цен');
    }
  };

  const renderRulesTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Заголовок и кнопки */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <div>
          <h3 style={{
            margin: '0 0 4px 0',
            color: 'var(--mac-text-primary)',
            fontSize: 'var(--mac-font-size-lg)',
            fontWeight: 'var(--mac-font-weight-semibold)'
          }}>
            Правила ценообразования
          </h3>
          <p style={{
            margin: 0,
            color: 'var(--mac-text-secondary)',
            fontSize: 'var(--mac-font-size-sm)'
          }}>
            Управление автоматическими скидками и правилами
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <MacOSButton
            onClick={handleUpdateDynamicPrices}
            variant="outline"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}
          >
            <TrendingUp size={16} />
            Обновить цены
          </MacOSButton>
          <MacOSButton
            onClick={() => setShowCreateRule(true)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}
          >
            <Plus size={16} />
            Создать правило
          </MacOSButton>
        </div>
      </div>

      {/* Список правил */}
      <div style={{ display: 'grid', gap: '16px' }}>
        {pricingRules.length === 0 ? (
          <MacOSEmptyState
            type="rule"
            title="Правила не найдены"
            description="В системе пока нет созданных правил ценообразования"
            action={
              <MacOSButton onClick={() => setShowCreateRule(true)}>
                <Plus size={16} style={{ marginRight: '8px' }} />
                Создать первое правило
              </MacOSButton>
            }
          />
        ) : (
          pricingRules.map(rule => (
            <MacOSCard key={rule.id} style={{ padding: 0 }}>
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'flex-start'
              }}>
                <div style={{ flex: 1 }}>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    marginBottom: '12px'
                  }}>
                    <h4 style={{
                      margin: 0,
                      color: 'var(--mac-text-primary)',
                      fontSize: 'var(--mac-font-size-md)',
                      fontWeight: 'var(--mac-font-weight-semibold)'
                    }}>
                      {rule.name}
                    </h4>
                    <MacOSBadge variant={rule.is_active ? 'success' : 'secondary'}>
                      {rule.is_active ? 'Активно' : 'Неактивно'}
                    </MacOSBadge>
                    <MacOSBadge variant="outline">
                      {rule.rule_type === 'TIME_BASED' && 'По времени'}
                      {rule.rule_type === 'VOLUME_BASED' && 'По объему'}
                      {rule.rule_type === 'SEASONAL' && 'Сезонное'}
                      {rule.rule_type === 'LOYALTY' && 'Лояльность'}
                      {rule.rule_type === 'PACKAGE' && 'Пакетное'}
                      {rule.rule_type === 'DYNAMIC' && 'Динамическое'}
                    </MacOSBadge>
                  </div>

                  <p style={{
                    margin: '0 0 12px 0',
                    color: 'var(--mac-text-secondary)',
                    fontSize: 'var(--mac-font-size-sm)'
                  }}>
                    {rule.description}
                  </p>

                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '16px',
                    fontSize: 'var(--mac-font-size-sm)',
                    color: 'var(--mac-text-secondary)'
                  }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Percent size={12} />
                      {rule.discount_type === 'PERCENTAGE' ? `${rule.discount_value}%` : `${rule.discount_value} ₽`}
                    </span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Users size={12} />
                      Использований: {rule.current_uses || 0}
                      {rule.max_uses && ` / ${rule.max_uses}`}
                    </span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <BarChart3 size={12} />
                      Приоритет: {rule.priority}
                    </span>
                  </div>

                  {(rule.start_time || rule.end_time) && (
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                      fontSize: 'var(--mac-font-size-sm)',
                      color: 'var(--mac-text-secondary)',
                      marginTop: '8px'
                    }}>
                      <Clock size={12} />
                      {rule.start_time} - {rule.end_time}
                    </div>
                  )}
                </div>

                <div style={{ display: 'flex', gap: '8px' }}>
                  <MacOSButton
                    variant="outline"
                    onClick={() => handleToggleRule(rule.id, rule.is_active)}
                    style={{
                      padding: '6px',
                      minWidth: 'auto',
                      width: '32px',
                      height: '32px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center'
                    }}
                    title={rule.is_active ? 'Приостановить' : 'Активировать'}
                  >
                    {rule.is_active ? <Pause size={16} /> : <Play size={16} />}
                  </MacOSButton>
                  <MacOSButton
                    variant="outline"
                    onClick={() => setEditingRule(rule)}
                    style={{
                      padding: '6px',
                      minWidth: 'auto',
                      width: '32px',
                      height: '32px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center'
                    }}
                    title="Редактировать"
                  >
                    <Edit size={16} />
                  </MacOSButton>
                  <MacOSButton
                    variant="outline"
                    onClick={() => handleDeleteRule(rule.id)}
                    style={{
                      padding: '6px',
                      minWidth: 'auto',
                      width: '32px',
                      height: '32px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center'
                    }}
                    title="Удалить"
                  >
                    <Trash2 size={16} />
                  </MacOSButton>
                </div>
              </div>
            </MacOSCard>
          ))
        )}
      </div>

      {/* Форма создания правила */}
      {showCreateRule && (
        <MacOSCard style={{ padding: '24px' }}>
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '16px'
          }}>
            <h4 style={{
              margin: 0,
              color: 'var(--mac-text-primary)',
              fontSize: 'var(--mac-font-size-lg)',
              fontWeight: 'var(--mac-font-weight-semibold)'
            }}>
              Создать правило ценообразования
            </h4>
            <MacOSButton variant="outline" onClick={() => setShowCreateRule(false)}>
              <X size={16} />
            </MacOSButton>
          </div>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(2, 1fr)',
            gap: '16px'
          }}>
            <div>
              <label style={{
                display: 'block',
                marginBottom: '8px',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)'
              }}>
                Название
              </label>
              <MacOSInput
                value={ruleForm.name}
                onChange={(e) => setRuleForm({ ...ruleForm, name: e.target.value })}
                placeholder="Название правила"
              />
            </div>

            <div>
              <label style={{
                display: 'block',
                marginBottom: '8px',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)'
              }}>
                Тип правила
              </label>
              <MacOSSelect
                value={ruleForm.rule_type}
                onChange={(e) => setRuleForm({ ...ruleForm, rule_type: e.target.value })}
              >
                <option value="TIME_BASED">По времени</option>
                <option value="VOLUME_BASED">По объему</option>
                <option value="SEASONAL">Сезонное</option>
                <option value="LOYALTY">Лояльность</option>
                <option value="PACKAGE">Пакетное</option>
                <option value="DYNAMIC">Динамическое</option>
              </MacOSSelect>
            </div>

            <div>
              <label style={{
                display: 'block',
                marginBottom: '8px',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)'
              }}>
                Тип скидки
              </label>
              <MacOSSelect
                value={ruleForm.discount_type}
                onChange={(e) => setRuleForm({ ...ruleForm, discount_type: e.target.value })}
              >
                <option value="PERCENTAGE">Процентная</option>
                <option value="FIXED_AMOUNT">Фиксированная сумма</option>
                <option value="BUY_X_GET_Y">Купи X получи Y</option>
                <option value="TIERED">Ступенчатая</option>
              </MacOSSelect>
            </div>

            <div>
              <label style={{
                display: 'block',
                marginBottom: '8px',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)'
              }}>
                Размер скидки
              </label>
              <MacOSInput
                type="number"
                value={ruleForm.discount_value}
                onChange={(e) => setRuleForm({ ...ruleForm, discount_value: parseFloat(e.target.value) })}
                placeholder="10"
              />
            </div>

            <div>
              <label style={{
                display: 'block',
                marginBottom: '8px',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)'
              }}>
                Время начала
              </label>
              <MacOSInput
                type="time"
                value={ruleForm.start_time}
                onChange={(e) => setRuleForm({ ...ruleForm, start_time: e.target.value + ':00' })}
              />
            </div>

            <div>
              <label style={{
                display: 'block',
                marginBottom: '8px',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)'
              }}>
                Время окончания
              </label>
              <MacOSInput
                type="time"
                value={ruleForm.end_time}
                onChange={(e) => setRuleForm({ ...ruleForm, end_time: e.target.value + ':00' })}
              />
            </div>

            <div>
              <label style={{
                display: 'block',
                marginBottom: '8px',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)'
              }}>
                Минимальное количество
              </label>
              <MacOSInput
                type="number"
                value={ruleForm.min_quantity}
                onChange={(e) => setRuleForm({ ...ruleForm, min_quantity: parseInt(e.target.value) })}
                placeholder="1"
              />
            </div>

            <div>
              <label style={{
                display: 'block',
                marginBottom: '8px',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)'
              }}>
                Приоритет
              </label>
              <MacOSInput
                type="number"
                value={ruleForm.priority}
                onChange={(e) => setRuleForm({ ...ruleForm, priority: parseInt(e.target.value) })}
                placeholder="0"
              />
            </div>

            <div style={{ gridColumn: 'span 2' }}>
              <label style={{
                display: 'block',
                marginBottom: '8px',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)'
              }}>
                Описание
              </label>
              <MacOSTextarea
                value={ruleForm.description}
                onChange={(e) => setRuleForm({ ...ruleForm, description: e.target.value })}
                placeholder="Описание правила"
              />
            </div>

            <div style={{ gridColumn: 'span 2' }}>
              <label style={{
                display: 'block',
                marginBottom: '8px',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)'
              }}>
                Услуги
              </label>
              <MacOSSelect
                multiple
                value={ruleForm.service_ids}
                onChange={(e) => {
                  const values = Array.from(e.target.selectedOptions, option => parseInt(option.value));
                  setRuleForm({ ...ruleForm, service_ids: values });
                }}
              >
                {services.map(service => (
                  <option key={service.id} value={service.id}>
                    {service.name} - {service.price} ₽
                  </option>
                ))}
              </MacOSSelect>
            </div>
          </div>

          <div style={{
            display: 'flex',
            justifyContent: 'flex-end',
            gap: '8px',
            marginTop: '16px'
          }}>
            <MacOSButton variant="outline" onClick={() => setShowCreateRule(false)}>
              Отмена
            </MacOSButton>
            <MacOSButton onClick={handleCreateRule}>
              <Save size={16} style={{ marginRight: '8px' }} />
              Создать
            </MacOSButton>
          </div>
        </MacOSCard>
      )}
    </div>
  );

  const renderPackagesTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Заголовок и кнопки */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <div>
          <h3 style={{
            margin: '0 0 4px 0',
            color: 'var(--mac-text-primary)',
            fontSize: 'var(--mac-font-size-lg)',
            fontWeight: 'var(--mac-font-weight-semibold)'
          }}>
            Пакеты услуг
          </h3>
          <p style={{
            margin: 0,
            color: 'var(--mac-text-secondary)',
            fontSize: 'var(--mac-font-size-sm)'
          }}>
            Управление комплексными предложениями
          </p>
        </div>
        <MacOSButton
          onClick={() => setShowCreatePackage(true)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}
        >
          <Plus size={16} />
          Создать пакет
        </MacOSButton>
      </div>

      {/* Список пакетов */}
      <div style={{ display: 'grid', gap: '16px' }}>
        {servicePackages.length === 0 ? (
          <MacOSEmptyState
            type="package"
            title="Пакеты не найдены"
            description="В системе пока нет созданных пакетов услуг"
            action={
              <MacOSButton onClick={() => setShowCreatePackage(true)}>
                <Plus size={16} style={{ marginRight: '8px' }} />
                Создать первый пакет
              </MacOSButton>
            }
          />
        ) : (
          servicePackages.map(pkg => (
            <MacOSCard key={pkg.id} style={{ padding: 0 }}>
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'flex-start'
              }}>
                <div style={{ flex: 1 }}>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    marginBottom: '12px'
                  }}>
                    <h4 style={{
                      margin: 0,
                      color: 'var(--mac-text-primary)',
                      fontSize: 'var(--mac-font-size-md)',
                      fontWeight: 'var(--mac-font-weight-semibold)'
                    }}>
                      {pkg.name}
                    </h4>
                    <MacOSBadge variant={pkg.is_active ? 'success' : 'secondary'}>
                      {pkg.is_active ? 'Активен' : 'Неактивен'}
                    </MacOSBadge>
                  </div>

                  <p style={{
                    margin: '0 0 12px 0',
                    color: 'var(--mac-text-secondary)',
                    fontSize: 'var(--mac-font-size-sm)'
                  }}>
                    {pkg.description}
                  </p>

                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '16px',
                    fontSize: 'var(--mac-font-size-sm)'
                  }}>
                    <span style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                      color: 'var(--mac-success)',
                      fontWeight: 'var(--mac-font-weight-semibold)'
                    }}>
                      <DollarSign size={12} />
                      {pkg.package_price} ₽
                    </span>
                    {pkg.original_price && (
                      <span style={{
                        color: 'var(--mac-text-tertiary)',
                        textDecoration: 'line-through'
                      }}>
                        {pkg.original_price} ₽
                      </span>
                    )}
                    {pkg.savings_percentage && (
                      <MacOSBadge variant="success">
                        Экономия {pkg.savings_percentage.toFixed(0)}%
                      </MacOSBadge>
                    )}
                    <span style={{ color: 'var(--mac-text-secondary)' }}>
                      Покупок: {pkg.current_purchases || 0}
                      {pkg.max_purchases && ` / ${pkg.max_purchases}`}
                    </span>
                  </div>

                  {(pkg.valid_from || pkg.valid_to) && (
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                      fontSize: 'var(--mac-font-size-sm)',
                      color: 'var(--mac-text-secondary)',
                      marginTop: '8px'
                    }}>
                      <Calendar size={12} />
                      {pkg.valid_from && new Date(pkg.valid_from).toLocaleDateString()} -
                      {pkg.valid_to && new Date(pkg.valid_to).toLocaleDateString()}
                    </div>
                  )}
                </div>

                <div style={{ display: 'flex', gap: '8px' }}>
                  <MacOSButton
                    variant="outline"
                    onClick={() => setEditingPackage(pkg)}
                    style={{
                      padding: '6px',
                      minWidth: 'auto',
                      width: '32px',
                      height: '32px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center'
                    }}
                    title="Редактировать"
                  >
                    <Edit size={16} />
                  </MacOSButton>
                  <MacOSButton
                    variant="outline"
                    onClick={() => handleDeletePackage(pkg.id)}
                    style={{
                      padding: '6px',
                      minWidth: 'auto',
                      width: '32px',
                      height: '32px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center'
                    }}
                    title="Удалить"
                  >
                    <Trash2 size={16} />
                  </MacOSButton>
                </div>
              </div>
            </MacOSCard>
          ))
        )}
      </div>

      {/* Форма создания пакета */}
      {showCreatePackage && (
        <MacOSCard style={{ padding: '24px' }}>
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '16px'
          }}>
            <h4 style={{
              margin: 0,
              color: 'var(--mac-text-primary)',
              fontSize: 'var(--mac-font-size-lg)',
              fontWeight: 'var(--mac-font-weight-semibold)'
            }}>
              Создать пакет услуг
            </h4>
            <MacOSButton variant="outline" onClick={() => setShowCreatePackage(false)}>
              <X size={16} />
            </MacOSButton>
          </div>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(2, 1fr)',
            gap: '16px'
          }}>
            <div>
              <label style={{
                display: 'block',
                marginBottom: '8px',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)'
              }}>
                Название
              </label>
              <MacOSInput
                value={packageForm.name}
                onChange={(e) => setPackageForm({ ...packageForm, name: e.target.value })}
                placeholder="Название пакета"
              />
            </div>

            <div>
              <label style={{
                display: 'block',
                marginBottom: '8px',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)'
              }}>
                Цена пакета
              </label>
              <MacOSInput
                type="number"
                value={packageForm.package_price}
                onChange={(e) => setPackageForm({ ...packageForm, package_price: parseFloat(e.target.value) })}
                placeholder="0"
              />
            </div>

            <div>
              <label style={{
                display: 'block',
                marginBottom: '8px',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)'
              }}>
                Действует с
              </label>
              <MacOSInput
                type="datetime-local"
                value={packageForm.valid_from}
                onChange={(e) => setPackageForm({ ...packageForm, valid_from: e.target.value })}
              />
            </div>

            <div>
              <label style={{
                display: 'block',
                marginBottom: '8px',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)'
              }}>
                Действует до
              </label>
              <MacOSInput
                type="datetime-local"
                value={packageForm.valid_to}
                onChange={(e) => setPackageForm({ ...packageForm, valid_to: e.target.value })}
              />
            </div>

            <div style={{ gridColumn: 'span 2' }}>
              <label style={{
                display: 'block',
                marginBottom: '8px',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)'
              }}>
                Описание
              </label>
              <MacOSTextarea
                value={packageForm.description}
                onChange={(e) => setPackageForm({ ...packageForm, description: e.target.value })}
                placeholder="Описание пакета"
              />
            </div>

            <div style={{ gridColumn: 'span 2' }}>
              <label style={{
                display: 'block',
                marginBottom: '8px',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)'
              }}>
                Услуги в пакете
              </label>
              <MacOSSelect
                multiple
                value={packageForm.service_ids}
                onChange={(e) => {
                  const values = Array.from(e.target.selectedOptions, option => parseInt(option.value));
                  setPackageForm({ ...packageForm, service_ids: values });
                }}
              >
                {services.map(service => (
                  <option key={service.id} value={service.id}>
                    {service.name} - {service.price} ₽
                  </option>
                ))}
              </MacOSSelect>
            </div>
          </div>

          <div style={{
            display: 'flex',
            justifyContent: 'flex-end',
            gap: '8px',
            marginTop: '16px'
          }}>
            <MacOSButton variant="outline" onClick={() => setShowCreatePackage(false)}>
              Отмена
            </MacOSButton>
            <MacOSButton onClick={handleCreatePackage}>
              <Save size={16} style={{ marginRight: '8px' }} />
              Создать
            </MacOSButton>
          </div>
        </MacOSCard>
      )}
    </div>
  );

  const renderAnalyticsTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div>
        <h3 style={{
          margin: '0 0 4px 0',
          color: 'var(--mac-text-primary)',
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-semibold)'
        }}>
          Аналитика ценообразования
        </h3>
        <p style={{
          margin: 0,
          color: 'var(--mac-text-secondary)',
          fontSize: 'var(--mac-font-size-sm)'
        }}>
          Статистика применения правил и пакетов
        </p>
      </div>

      {analytics ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '16px' }}>
          <MacOSCard style={{ padding: 0 }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              marginBottom: '12px'
            }}>
              <TrendingUp size={20} color="var(--mac-accent)" />
              <h4 style={{
                margin: 0,
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-md)',
                fontWeight: 'var(--mac-font-weight-semibold)'
              }}>
                Общая экономия
              </h4>
            </div>
            <div style={{
              fontSize: 'var(--mac-font-size-2xl)',
              fontWeight: 'var(--mac-font-weight-bold)',
              color: 'var(--mac-success)',
              marginBottom: '8px'
            }}>
              {analytics.summary?.total_savings?.toLocaleString() || 0} ₽
            </div>
            <p style={{
              margin: 0,
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-secondary)'
            }}>
              За период {analytics.period?.start_date && new Date(analytics.period.start_date).toLocaleDateString()} -
              {analytics.period?.end_date && new Date(analytics.period.end_date).toLocaleDateString()}
            </p>
          </MacOSCard>

          <MacOSCard style={{ padding: 0 }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              marginBottom: '12px'
            }}>
              <Settings size={20} color="var(--mac-purple)" />
              <h4 style={{
                margin: 0,
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-md)',
                fontWeight: 'var(--mac-font-weight-semibold)'
              }}>
                Активные правила
              </h4>
            </div>
            <div style={{
              fontSize: 'var(--mac-font-size-2xl)',
              fontWeight: 'var(--mac-font-weight-bold)',
              color: 'var(--mac-text-primary)',
              marginBottom: '8px'
            }}>
              {analytics.summary?.active_rules_count || 0}
            </div>
            <p style={{
              margin: 0,
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-secondary)'
            }}>
              Правил ценообразования
            </p>
          </MacOSCard>

          <MacOSCard style={{ padding: 0 }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              marginBottom: '12px'
            }}>
              <Package size={20} color="var(--mac-orange)" />
              <h4 style={{
                margin: 0,
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-md)',
                fontWeight: 'var(--mac-font-weight-semibold)'
              }}>
                Активные пакеты
              </h4>
            </div>
            <div style={{
              fontSize: 'var(--mac-font-size-2xl)',
              fontWeight: 'var(--mac-font-weight-bold)',
              color: 'var(--mac-text-primary)',
              marginBottom: '8px'
            }}>
              {analytics.summary?.active_packages_count || 0}
            </div>
            <p style={{
              margin: 0,
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-secondary)'
            }}>
              Пакетов услуг
            </p>
          </MacOSCard>
        </div>
      ) : (
        <MacOSEmptyState
          type="analytics"
          title="Аналитика недоступна"
          description="Данные аналитики еще не загружены или отсутствуют"
        />
      )}

      {analytics?.rules_statistics && (
        <MacOSCard style={{ padding: '16px' }}>
          <h4 style={{
            margin: '0 0 16px 0',
            color: 'var(--mac-text-primary)',
            fontSize: 'var(--mac-font-size-md)',
            fontWeight: 'var(--mac-font-weight-semibold)'
          }}>
            Статистика правил
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {analytics.rules_statistics.map((rule, index) => (
              <div key={index} style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '8px',
                backgroundColor: 'var(--mac-bg-secondary)',
                borderRadius: 'var(--mac-radius-md)'
              }}>
                <span style={{
                  fontWeight: 'var(--mac-font-weight-medium)',
                  color: 'var(--mac-text-primary)'
                }}>
                  {rule.name}
                </span>
                <div style={{ display: 'flex', gap: '16px', fontSize: 'var(--mac-font-size-sm)' }}>
                  <span style={{ color: 'var(--mac-text-secondary)' }}>
                    Использований: {rule.uses}
                  </span>
                  <span style={{ color: 'var(--mac-success)' }}>
                    Экономия: {rule.total_savings?.toLocaleString() || 0} ₽
                  </span>
                </div>
              </div>
            ))}
          </div>
        </MacOSCard>
      )}

      {analytics?.packages_statistics && (
        <MacOSCard style={{ padding: '16px' }}>
          <h4 style={{
            margin: '0 0 16px 0',
            color: 'var(--mac-text-primary)',
            fontSize: 'var(--mac-font-size-md)',
            fontWeight: 'var(--mac-font-weight-semibold)'
          }}>
            Статистика пакетов
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {analytics.packages_statistics.map((pkg, index) => (
              <div key={index} style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '8px',
                backgroundColor: 'var(--mac-bg-secondary)',
                borderRadius: 'var(--mac-radius-md)'
              }}>
                <span style={{
                  fontWeight: 'var(--mac-font-weight-medium)',
                  color: 'var(--mac-text-primary)'
                }}>
                  {pkg.name}
                </span>
                <div style={{ display: 'flex', gap: '16px', fontSize: 'var(--mac-font-size-sm)' }}>
                  <span style={{ color: 'var(--mac-text-secondary)' }}>
                    Покупок: {pkg.purchases}
                  </span>
                  <span style={{ color: 'var(--mac-success)' }}>
                    Экономия: {pkg.total_savings?.toLocaleString() || 0} ₽
                  </span>
                </div>
              </div>
            ))}
          </div>
        </MacOSCard>
      )}
    </div>
  );

  const tabs = [
    { id: 'rules', label: 'Правила', icon: Settings },
    { id: 'packages', label: 'Пакеты', icon: Package },
    { id: 'analytics', label: 'Аналитика', icon: BarChart3 }
  ];

  return (
    <div style={{ padding: 0, maxWidth: '1400px', margin: '0 auto' }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '16px',
        marginBottom: '24px'
      }}>
        <Package size={24} color="var(--mac-accent)" />
        <div>
          <h2 style={{
            margin: 0,
            color: 'var(--mac-text-primary)',
            fontSize: 'var(--mac-font-size-xl)',
            fontWeight: 'var(--mac-font-weight-bold)'
          }}>
            Динамическое ценообразование
          </h2>
          <p style={{
            margin: '4px 0 0 0',
            color: 'var(--mac-text-secondary)',
            fontSize: 'var(--mac-font-size-sm)'
          }}>
            Управление правилами ценообразования, пакетами услуг и динамическими ценами
          </p>
        </div>
      </div>

      {/* Табы */}
      <div style={{
        display: 'flex',
        borderBottom: '1px solid var(--mac-border)',
        marginBottom: '24px'
      }}>
        {tabs.map(tab => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                padding: '16px 24px',
                border: 'none',
                background: 'none',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                borderBottom: activeTab === tab.id ? '2px solid var(--mac-accent)' : '2px solid transparent',
                color: activeTab === tab.id ? 'var(--mac-accent)' : 'var(--mac-text-secondary)',
                fontWeight: activeTab === tab.id ? 'var(--mac-font-weight-semibold)' : 'var(--mac-font-weight-normal)',
                fontSize: 'var(--mac-font-size-sm)',
                transition: 'all var(--mac-duration-normal) var(--mac-ease)'
              }}
            >
              <Icon size={16} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Контент */}
      {loading ? (
        <MacOSLoadingSkeleton type="card" count={3} />
      ) : (
        <>
          {activeTab === 'rules' && renderRulesTab()}
          {activeTab === 'packages' && renderPackagesTab()}
          {activeTab === 'analytics' && renderAnalyticsTab()}
        </>
      )}
    </div>
  );
};

export default DynamicPricingManager;

