/**
 * Компонент для управления системой скидок и льгот
 */
import { useState, useEffect } from 'react';
import {
  MacOSCard,
  Button,
  Badge,
  Input,
  Textarea,
  Skeleton,
  MacOSEmptyState,
  Select,
  Checkbox } from '../ui/macos';
import {
  Percent,
  Plus,




  TrendingUp,
  Users,

  DollarSign } from
'lucide-react';
import { toast } from 'react-toastify';

import { api } from '../../api/client';
import logger from '../../utils/logger';
import { useTranslation } from '../../i18n/adapter';

const sanitizePayload = (form) =>
  Object.fromEntries(
    Object.entries(form).filter(([, value]) => {
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

const DiscountBenefitsManager = () => {
  const [activeTab, setActiveTab] = useState('discounts');
  const [discounts, setDiscounts] = useState([]);
  const [benefits, setBenefits] = useState([]);
  const [loyaltyPrograms, setLoyaltyPrograms] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [analytics, setAnalytics] = useState(null);

  // Формы для создания/редактирования
  const [discountForm, setDiscountForm] = useState({
    name: '',
    description: '',
    discount_type: 'percentage',
    value: '',
    min_amount: '0',
    max_discount: '',
    start_date: '',
    end_date: '',
    usage_limit: '',
    applies_to_services: true,
    applies_to_appointments: true,
    applies_to_packages: true,
    can_combine_with_others: false,
    priority: '0'
  });

  const [benefitForm, setBenefitForm] = useState({
    name: '',
    description: '',
    benefit_type: 'veteran',
    discount_percentage: '',
    max_discount_amount: '',
    requires_document: true,
    document_types: '',
    age_min: '',
    age_max: '',
    applies_to_services: true,
    applies_to_appointments: true,
    monthly_limit: '',
    yearly_limit: ''
  });

  const [loyaltyForm, setLoyaltyForm] = useState({
    name: '',
    description: '',
    points_per_ruble: '1.0',
    min_purchase_for_points: '0',
    ruble_per_point: '1.0',
    min_points_to_redeem: '100',
    max_points_per_purchase: '',
    start_date: '',
    end_date: ''
  });

  // Загрузка данных
  const loadData = async () => {
    setLoading(true);
    try {
      const [discountsResponse, benefitsResponse, loyaltyResponse] = await Promise.allSettled([
      api.get('/discount-benefits/discounts'),
      api.get('/discount-benefits/benefits'),
      api.get('/discount-benefits/loyalty-programs')]
      );

      if (discountsResponse.status === 'fulfilled') {
        setDiscounts(discountsResponse.value.data?.discounts || discountsResponse.value.data || []);
      }

      if (benefitsResponse.status === 'fulfilled') {
        setBenefits(benefitsResponse.value.data?.benefits || benefitsResponse.value.data || []);
      }

      if (loyaltyResponse.status === 'fulfilled') {
        setLoyaltyPrograms(loyaltyResponse.value.data?.programs || loyaltyResponse.value.data || []);
      }

    } catch (error) {
      logger.error('Ошибка загрузки данных:', error);
      toast.error('Ошибка загрузки данных');
    } finally {
      setLoading(false);
    }
  };

  // Загрузка аналитики
  const loadAnalytics = async () => {
    try {
      const [discountAnalytics, benefitAnalytics, loyaltyAnalytics] = await Promise.allSettled([
      api.get('/discount-benefits/analytics/discounts'),
      api.get('/discount-benefits/analytics/benefits'),
      api.get('/discount-benefits/analytics/loyalty')]
      );

      const analytics = {
        discounts: discountAnalytics.status === 'fulfilled' ? discountAnalytics.value.data?.analytics : null,
        benefits: benefitAnalytics.status === 'fulfilled' ? benefitAnalytics.value.data?.analytics : null,
        loyalty: loyaltyAnalytics.status === 'fulfilled' ? loyaltyAnalytics.value.data?.analytics : null
      };

      setAnalytics(analytics);
    } catch (error) {
      logger.error('Ошибка загрузки аналитики:', error);
    }
  };

  useEffect(() => {
    loadData();
    loadAnalytics();
  }, []);

  // Создание скидки
  const createDiscount = async () => {
    try {
      await api.post('/discount-benefits/discounts', sanitizePayload(discountForm));
      toast.success('Скидка создана успешно');
      setShowCreateForm(false);
      setDiscountForm({
        name: '',
        description: '',
        discount_type: 'percentage',
        value: '',
        min_amount: '0',
        max_discount: '',
        start_date: '',
        end_date: '',
        usage_limit: '',
        applies_to_services: true,
        applies_to_appointments: true,
        applies_to_packages: true,
        can_combine_with_others: false,
        priority: '0'
      });
      loadData();
    } catch (error) {
      logger.error('Ошибка создания скидки:', error);
      toast.error(error.response?.data?.detail || 'Ошибка создания скидки');
    }
  };

  // Создание льготы
  const createBenefit = async () => {
    try {
      await api.post('/discount-benefits/benefits', sanitizePayload(benefitForm));
      toast.success('Льгота создана успешно');
      setShowCreateForm(false);
      setBenefitForm({
        name: '',
        description: '',
        benefit_type: 'veteran',
        discount_percentage: '',
        max_discount_amount: '',
        requires_document: true,
        document_types: '',
        age_min: '',
        age_max: '',
        applies_to_services: true,
        applies_to_appointments: true,
        monthly_limit: '',
        yearly_limit: ''
      });
      loadData();
    } catch (error) {
      logger.error('Ошибка создания льготы:', error);
      toast.error(error.response?.data?.detail || 'Ошибка создания льготы');
    }
  };

  // Создание программы лояльности
  const createLoyaltyProgram = async () => {
    try {
      await api.post('/discount-benefits/loyalty-programs', sanitizePayload(loyaltyForm));
      toast.success('Программа лояльности создана успешно');
      setShowCreateForm(false);
      setLoyaltyForm({
        name: '',
        description: '',
        points_per_ruble: '1.0',
        min_purchase_for_points: '0',
        ruble_per_point: '1.0',
        min_points_to_redeem: '100',
        max_points_per_purchase: '',
        start_date: '',
        end_date: ''
      });
      loadData();
    } catch (error) {
      logger.error('Ошибка создания программы лояльности:', error);
      toast.error(error.response?.data?.detail || 'Ошибка создания программы лояльности');
    }
  };

  // Типы скидок
  const discountTypes = {
    percentage: 'Процентная',
    fixed_amount: 'Фиксированная сумма',
    buy_x_get_y: 'Купи X получи Y',
    loyalty_points: 'Бонусные баллы',
    seasonal: 'Сезонная',
    referral: 'Реферальная'
  };

  // Типы льгот
  const benefitTypes = {
    veteran: 'Ветеран',
    disabled: 'Инвалид',
    pensioner: 'Пенсионер',
    student: 'Студент',
    child: 'Ребенок',
    large_family: 'Многодетная семья',
    low_income: 'Малообеспеченная семья',
    employee: 'Сотрудник клиники'
  };

  // Рендер формы создания скидки
  const renderDiscountForm = () =>
  <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Название скидки</label>
          <Input
          value={discountForm.name}
          onChange={(e) => setDiscountForm({ ...discountForm, name: e.target.value })}
          placeholder="Введите название скидки" />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Тип скидки</label>
          <Select
          value={discountForm.discount_type}
          onChange={(value) => setDiscountForm({ ...discountForm, discount_type: value })}
          options={Object.entries(discountTypes).map(([key, value]) => ({ value: key, label: value }))}
          size="large" />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Значение скидки</label>
          <Input
          type="number"
          value={discountForm.value}
          onChange={(e) => setDiscountForm({ ...discountForm, value: e.target.value })}
          placeholder="Введите значение" />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Минимальная сумма</label>
          <Input
          type="number"
          value={discountForm.min_amount}
          onChange={(e) => setDiscountForm({ ...discountForm, min_amount: e.target.value })}
          placeholder="0" />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Максимальная скидка</label>
          <Input
          type="number"
          value={discountForm.max_discount}
          onChange={(e) => setDiscountForm({ ...discountForm, max_discount: e.target.value })}
          placeholder="Не ограничено" />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Лимит использований</label>
          <Input
          type="number"
          value={discountForm.usage_limit}
          onChange={(e) => setDiscountForm({ ...discountForm, usage_limit: e.target.value })}
          placeholder="Не ограничено" />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Дата начала</label>
          <Input
          type="datetime-local"
          value={discountForm.start_date}
          onChange={(e) => setDiscountForm({ ...discountForm, start_date: e.target.value })} />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Дата окончания</label>
          <Input
          type="datetime-local"
          value={discountForm.end_date}
          onChange={(e) => setDiscountForm({ ...discountForm, end_date: e.target.value })} />
        
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{t('common.description')}</label>
        <Textarea
        value={discountForm.description}
        onChange={(e) => setDiscountForm({ ...discountForm, description: e.target.value })}
        placeholder="Введите описание скидки"
        rows={3} />
      
      </div>
      <div className="flex flex-wrap gap-4">
          <label className="flex items-center">
            <Checkbox aria-label="Discount applies to services" checked={discountForm.applies_to_services} onChange={(e) => setDiscountForm({ ...discountForm, applies_to_services: e.target.checked })}
              className="mr-2" />
        
          Применяется к услугам
        </label>
          <label className="flex items-center">
            <Checkbox aria-label="Discount applies to appointments" checked={discountForm.applies_to_appointments} onChange={(e) => setDiscountForm({ ...discountForm, applies_to_appointments: e.target.checked })}
              className="mr-2" />
        
          Применяется к записям
        </label>
          <label className="flex items-center">
            <Checkbox aria-label="Discount can combine with other discounts" checked={discountForm.can_combine_with_others} onChange={(e) => setDiscountForm({ ...discountForm, can_combine_with_others: e.target.checked })}
              className="mr-2" />
        
          Можно комбинировать с другими
        </label>
      </div>
      <div className="flex gap-2">
        <Button onClick={createDiscount} className="bg-blue-500 text-white">
          Создать скидку
        </Button>
        <Button onClick={() => setShowCreateForm(false)} className="bg-gray-500 text-white">
          Отмена
        </Button>
      </div>
    </div>;


  // Рендер формы создания льготы
  const renderBenefitForm = () =>
  <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Название льготы</label>
          <Input
          value={benefitForm.name}
          onChange={(e) => setBenefitForm({ ...benefitForm, name: e.target.value })}
          placeholder="Введите название льготы" />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Тип льготы</label>
          <Select
          value={benefitForm.benefit_type}
          onChange={(value) => setBenefitForm({ ...benefitForm, benefit_type: value })}
          options={Object.entries(benefitTypes).map(([key, value]) => ({ value: key, label: value }))}
          size="large" />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Процент скидки</label>
          <Input
          type="number"
          value={benefitForm.discount_percentage}
          onChange={(e) => setBenefitForm({ ...benefitForm, discount_percentage: e.target.value })}
          placeholder="Введите процент"
          max="100" />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Максимальная сумма льготы</label>
          <Input
          type="number"
          value={benefitForm.max_discount_amount}
          onChange={(e) => setBenefitForm({ ...benefitForm, max_discount_amount: e.target.value })}
          placeholder="Не ограничено" />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Минимальный возраст</label>
          <Input
          type="number"
          value={benefitForm.age_min}
          onChange={(e) => setBenefitForm({ ...benefitForm, age_min: e.target.value })}
          placeholder="Не ограничено" />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Максимальный возраст</label>
          <Input
          type="number"
          value={benefitForm.age_max}
          onChange={(e) => setBenefitForm({ ...benefitForm, age_max: e.target.value })}
          placeholder="Не ограничено" />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Месячный лимит</label>
          <Input
          type="number"
          value={benefitForm.monthly_limit}
          onChange={(e) => setBenefitForm({ ...benefitForm, monthly_limit: e.target.value })}
          placeholder="Не ограничено" />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Годовой лимит</label>
          <Input
          type="number"
          value={benefitForm.yearly_limit}
          onChange={(e) => setBenefitForm({ ...benefitForm, yearly_limit: e.target.value })}
          placeholder="Не ограничено" />
        
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{t('common.description')}</label>
        <Textarea
        value={benefitForm.description}
        onChange={(e) => setBenefitForm({ ...benefitForm, description: e.target.value })}
        placeholder="Введите описание льготы"
        rows={3} />
      
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Типы документов (JSON)</label>
        <Input
        value={benefitForm.document_types}
        onChange={(e) => setBenefitForm({ ...benefitForm, document_types: e.target.value })}
        placeholder='["passport", "certificate"]' />
      
      </div>
      <div className="flex flex-wrap gap-4">
          <label className="flex items-center">
            <Checkbox aria-label="Benefit requires documents" checked={benefitForm.requires_document} onChange={(e) => setBenefitForm({ ...benefitForm, requires_document: e.target.checked })}
              className="mr-2" />
        
          Требует документы
        </label>
          <label className="flex items-center">
            <Checkbox aria-label="Benefit applies to services" checked={benefitForm.applies_to_services} onChange={(e) => setBenefitForm({ ...benefitForm, applies_to_services: e.target.checked })}
              className="mr-2" />
        
          Применяется к услугам
        </label>
          <label className="flex items-center">
            <Checkbox aria-label="Benefit applies to appointments" checked={benefitForm.applies_to_appointments} onChange={(e) => setBenefitForm({ ...benefitForm, applies_to_appointments: e.target.checked })}
              className="mr-2" />
        
          Применяется к записям
        </label>
      </div>
      <div className="flex gap-2">
        <Button onClick={createBenefit} className="bg-blue-500 text-white">
          Создать льготу
        </Button>
        <Button onClick={() => setShowCreateForm(false)} className="bg-gray-500 text-white">
          Отмена
        </Button>
      </div>
    </div>;


  // Рендер формы создания программы лояльности
  const renderLoyaltyForm = () =>
  <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Название программы</label>
          <Input
          value={loyaltyForm.name}
          onChange={(e) => setLoyaltyForm({ ...loyaltyForm, name: e.target.value })}
          placeholder="Введите название программы" />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Баллов за рубль</label>
          <Input
          type="number"
          step="0.1"
          value={loyaltyForm.points_per_ruble}
          onChange={(e) => setLoyaltyForm({ ...loyaltyForm, points_per_ruble: e.target.value })}
          placeholder="1.0" />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Рублей за балл</label>
          <Input
          type="number"
          step="0.1"
          value={loyaltyForm.ruble_per_point}
          onChange={(e) => setLoyaltyForm({ ...loyaltyForm, ruble_per_point: e.target.value })}
          placeholder="1.0" />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Минимум баллов для списания</label>
          <Input
          type="number"
          value={loyaltyForm.min_points_to_redeem}
          onChange={(e) => setLoyaltyForm({ ...loyaltyForm, min_points_to_redeem: e.target.value })}
          placeholder="100" />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Минимальная покупка для начисления</label>
          <Input
          type="number"
          value={loyaltyForm.min_purchase_for_points}
          onChange={(e) => setLoyaltyForm({ ...loyaltyForm, min_purchase_for_points: e.target.value })}
          placeholder="0" />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Максимум баллов за покупку</label>
          <Input
          type="number"
          value={loyaltyForm.max_points_per_purchase}
          onChange={(e) => setLoyaltyForm({ ...loyaltyForm, max_points_per_purchase: e.target.value })}
          placeholder="Не ограничено" />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Дата начала</label>
          <Input
          type="datetime-local"
          value={loyaltyForm.start_date}
          onChange={(e) => setLoyaltyForm({ ...loyaltyForm, start_date: e.target.value })} />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Дата окончания</label>
          <Input
          type="datetime-local"
          value={loyaltyForm.end_date}
          onChange={(e) => setLoyaltyForm({ ...loyaltyForm, end_date: e.target.value })} />
        
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{t('common.description')}</label>
        <Textarea
        value={loyaltyForm.description}
        onChange={(e) => setLoyaltyForm({ ...loyaltyForm, description: e.target.value })}
        placeholder="Введите описание программы"
        rows={3} />
      
      </div>
      <div className="flex gap-2">
        <Button onClick={createLoyaltyProgram} className="bg-blue-500 text-white">
          Создать программу
        </Button>
        <Button onClick={() => setShowCreateForm(false)} className="bg-gray-500 text-white">
          Отмена
        </Button>
      </div>
    </div>;


  // Рендер списка скидок
  const renderDiscountsList = () =>
  <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h3 className="admin-section-h3-m0">
          Скидки
        </h3>
        <Button
        onClick={() => setShowCreateForm(true)}
        className="flex items-center justify-center gap-2">
        
          <Plus size={16} />
          Создать скидку
        </Button>
      </div>

      {showCreateForm &&
    <MacOSCard className="p-0">
          <h4 className="admin-h4-md-semi-primary-mb-16">
            Создание новой скидки
          </h4>
          {renderDiscountForm()}
        </MacOSCard>
    }

      <div className="admin-grid-gap-16">
        {discounts.length === 0 ?
      <MacOSEmptyState
        type="discount"
        title="Скидки не найдены"
        description="В системе пока нет созданных скидок"
        action={
        <Button onClick={() => setShowCreateForm(true)}>
                <Plus size={16} className="mr-2" />
                Создать первую скидку
              </Button>
        } /> :


      discounts.map((discount) =>
      <MacOSCard key={discount.id} className="p-0">
              <div className="admin-flex-between-flex-start">
                <div>
                  <h4 className="admin-h4-md-semi-primary-mb-8">
                    {discount.name}
                  </h4>
                  <p className="admin-p-sm-secondary-mb-12">
                    {discount.description}
                  </p>
                  <div className="admin-flex-wrap-8">
                    <Badge variant={discount.is_active ? 'success' : 'error'}>
                      {discount.is_active ? 'Активна' : 'Неактивна'}
                    </Badge>
                    <Badge variant="info">
                      {discountTypes[discount.discount_type]}
                    </Badge>
                    <Badge variant="warning">
                      {discount.discount_type === 'percentage' ? `${discount.value}%` : `${discount.value} сум`}
                    </Badge>
                  </div>
                </div>
                <div className="admin-text-right text-sm text-[var(--mac-text-secondary)]">
                  <div>Использований: {discount.usage_count}/{discount.usage_limit || '∞'}</div>
                  <div>Приоритет: {discount.priority}</div>
                </div>
              </div>
            </MacOSCard>
      )
      }
      </div>
    </div>;


  // Рендер списка льгот
  const renderBenefitsList = () =>
  <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h3 className="admin-section-h3-m0">
          Льготы
        </h3>
        <Button
        onClick={() => setShowCreateForm(true)}
        className="flex items-center justify-center gap-2">
        
          <Plus size={16} />
          Создать льготу
        </Button>
      </div>

      {showCreateForm &&
    <MacOSCard className="p-0">
          <h4 className="admin-h4-md-semi-primary-mb-16">
            Создание новой льготы
          </h4>
          {renderBenefitForm()}
        </MacOSCard>
    }

      <div className="admin-grid-gap-16">
        {benefits.length === 0 ?
      <MacOSEmptyState
        type="benefit"
        title="Льготы не найдены"
        description="В системе пока нет созданных льгот"
        action={
        <Button onClick={() => setShowCreateForm(true)}>
                <Plus size={16} className="mr-2" />
                Создать первую льготу
              </Button>
        } /> :


      benefits.map((benefit) =>
      <MacOSCard key={benefit.id} className="p-0">
              <div className="admin-flex-between-flex-start">
                <div>
                  <h4 className="admin-h4-md-semi-primary-mb-8">
                    {benefit.name}
                  </h4>
                  <p className="admin-p-sm-secondary-mb-12">
                    {benefit.description}
                  </p>
                  <div className="admin-flex-wrap-8">
                    <Badge variant={benefit.is_active ? 'success' : 'error'}>
                      {benefit.is_active ? 'Активна' : 'Неактивна'}
                    </Badge>
                    <Badge variant="info">
                      {benefitTypes[benefit.benefit_type]}
                    </Badge>
                    <Badge variant="warning">
                      {benefit.discount_percentage}%
                    </Badge>
                    {benefit.requires_document &&
              <Badge variant="secondary">
                        Требует документы
                      </Badge>
              }
                  </div>
                </div>
                <div className="admin-text-right text-sm text-[var(--mac-text-secondary)]">
                  {benefit.monthly_limit && <div>Месячный лимит: {benefit.monthly_limit} сум</div>}
                  {benefit.yearly_limit && <div>Годовой лимит: {benefit.yearly_limit} сум</div>}
                  {benefit.max_discount_amount && <div>Макс. скидка: {benefit.max_discount_amount} сум</div>}
                </div>
              </div>
            </MacOSCard>
      )
      }
      </div>
    </div>;


  // Рендер списка программ лояльности
  const renderLoyaltyList = () =>
  <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h3 className="admin-section-h3-m0">
          Программы лояльности
        </h3>
        <Button
        onClick={() => setShowCreateForm(true)}
        className="flex items-center justify-center gap-2">
        
          <Plus size={16} />
          Создать программу
        </Button>
      </div>

      {showCreateForm &&
    <MacOSCard className="p-0">
          <h4 className="admin-h4-md-semi-primary-mb-16">
            Создание новой программы лояльности
          </h4>
          {renderLoyaltyForm()}
        </MacOSCard>
    }

      <div className="admin-grid-gap-16">
        {loyaltyPrograms.length === 0 ?
      <MacOSEmptyState
        type="loyalty"
        title="Программы лояльности не найдены"
        description="В системе пока нет созданных программ лояльности"
        action={
        <Button onClick={() => setShowCreateForm(true)}>
                <Plus size={16} className="mr-2" />
                Создать первую программу
              </Button>
        } /> :


      loyaltyPrograms.map((program) =>
      <MacOSCard key={program.id} className="p-0">
              <div className="admin-flex-between-flex-start">
                <div>
                  <h4 className="admin-h4-md-semi-primary-mb-8">
                    {program.name}
                  </h4>
                  <p className="admin-p-sm-secondary-mb-12">
                    {program.description}
                  </p>
                  <div className="admin-flex-wrap-8">
                    <Badge variant={program.is_active ? 'success' : 'error'}>
                      {program.is_active ? 'Активна' : 'Неактивна'}
                    </Badge>
                    <Badge variant="info">
                      {program.points_per_ruble} балл/сум
                    </Badge>
                    <Badge variant="warning">
                      {program.ruble_per_point} сум/балл
                    </Badge>
                  </div>
                </div>
                <div className="admin-text-right text-sm text-[var(--mac-text-secondary)]">
                  <div>Мин. для списания: {program.min_points_to_redeem} баллов</div>
                </div>
              </div>
            </MacOSCard>
      )
      }
      </div>
    </div>;


  // Рендер аналитики
  const renderAnalytics = () =>
  <div className="flex flex-col gap-6">
      <h3 className="admin-section-h3-m0">
        Аналитика
      </h3>

      {analytics ?
    <div className="admin-grid-auto-300">
          {/* Аналитика скидок */}
          {analytics.discounts &&
      <MacOSCard className="p-0">
              <h4 className="admin-h4-md-semi-primary-mb-12-flex">
                <TrendingUp size={16} />
                Скидки
              </h4>
              <div className="flex flex-col gap-2">
                <div className="text-sm text-[var(--mac-text-secondary)]">
                  Всего применений: <span className="admin-text-med-primary">{analytics.discounts.total_applications}</span>
                </div>
                <div className="text-sm text-[var(--mac-text-secondary)]">
                  Общая сумма скидок: <span className="admin-text-med-primary">{analytics.discounts.total_discount_amount?.toFixed(2)} сум</span>
                </div>
                <div className="text-sm text-[var(--mac-text-secondary)]">
                  Средний процент скидки: <span className="admin-text-med-primary">{analytics.discounts.average_discount_percentage?.toFixed(1)}%</span>
                </div>
              </div>
            </MacOSCard>
      }

          {/* Аналитика льгот */}
          {analytics.benefits &&
      <MacOSCard className="p-0">
              <h4 className="admin-h4-md-semi-primary-mb-12-flex">
                <Users size={16} />
                Льготы
              </h4>
              <div className="flex flex-col gap-2">
                <div className="text-sm text-[var(--mac-text-secondary)]">
                  Всего применений: <span className="admin-text-med-primary">{analytics.benefits.total_applications}</span>
                </div>
                <div className="text-sm text-[var(--mac-text-secondary)]">
                  Общая сумма льгот: <span className="admin-text-med-primary">{analytics.benefits.total_benefit_amount?.toFixed(2)} сум</span>
                </div>
                <div className="text-sm text-[var(--mac-text-secondary)]">
                  Средний процент льготы: <span className="admin-text-med-primary">{analytics.benefits.average_benefit_percentage?.toFixed(1)}%</span>
                </div>
              </div>
            </MacOSCard>
      }

          {/* Аналитика лояльности */}
          {analytics.loyalty &&
      <MacOSCard className="p-0">
              <h4 className="admin-h4-md-semi-primary-mb-12-flex">
                <DollarSign size={16} />
                Лояльность
              </h4>
              <div className="flex flex-col gap-2">
                <div className="text-sm text-[var(--mac-text-secondary)]">
                  Всего участников: <span className="admin-text-med-primary">{analytics.loyalty.total_patients}</span>
                </div>
                <div className="text-sm text-[var(--mac-text-secondary)]">
                  Активных участников: <span className="admin-text-med-primary">{analytics.loyalty.active_patients}</span>
                </div>
                <div className="text-sm text-[var(--mac-text-secondary)]">
                  Всего баллов начислено: <span className="admin-text-med-primary">{analytics.loyalty.total_points_earned}</span>
                </div>
                <div className="text-sm text-[var(--mac-text-secondary)]">
                  Процент погашения: <span className="admin-text-med-primary">{analytics.loyalty.redemption_rate?.toFixed(1)}%</span>
                </div>
              </div>
            </MacOSCard>
      }
        </div> :

    <MacOSEmptyState
      type="analytics"
      title="Аналитика недоступна"
      description="Данные аналитики будут доступны после создания скидок, льгот и программ лояльности" />

    }
    </div>;


  const tabs = [
  { id: 'discounts', label: 'Скидки', count: discounts.length },
  { id: 'benefits', label: 'Льготы', count: benefits.length },
  { id: 'loyalty', label: 'Лояльность', count: loyaltyPrograms.length },
  { id: 'analytics', label: 'Аналитика' }];


  return (
    <div className="p-0">
      <div className="admin-flex-center-16 mb-6">
        <Percent size={24} color="var(--mac-accent)" />
        <div>
          <h2 className="admin-h2-xl-bold-primary-m0">
            Система скидок и льгот
          </h2>
          <p className="admin-p-sm-secondary-mt-4">
            Управление скидками, льготами и программами лояльности
          </p>
        </div>
      </div>

      {/* Навигация по вкладкам */}
      <div className="admin-tab-bar">
        {tabs.map((tab) =>
        <button
          key={tab.id}
          onClick={() => {
            setActiveTab(tab.id);
            setShowCreateForm(false);
          }}
          data-active={activeTab === tab.id ? 'true' : 'false'}
          className="admin-dp-tab-btn"
          style={{
            '--admin-tab-border': activeTab === tab.id ? '2px solid var(--mac-accent)' : '2px solid transparent',
            '--admin-tab-color': activeTab === tab.id ? 'var(--mac-accent)' : 'var(--mac-text-secondary)',
            '--admin-tab-weight': activeTab === tab.id ? 'var(--mac-font-weight-semibold)' : 'var(--mac-font-weight-normal)'
          }}>
          
            {tab.label}
            {tab.count !== undefined &&
          <Badge variant="secondary" className="admin-ml-8">
                {tab.count}
              </Badge>
          }
          </button>
        )}
      </div>

      {/* Содержимое вкладок */}
      {loading ?
      <Skeleton type="card" count={3} /> :

      <div>
          {activeTab === 'discounts' && renderDiscountsList()}
          {activeTab === 'benefits' && renderBenefitsList()}
          {activeTab === 'loyalty' && renderLoyaltyList()}
          {activeTab === 'analytics' && renderAnalytics()}
        </div>
      }
    </div>);

};

export default DiscountBenefitsManager;
