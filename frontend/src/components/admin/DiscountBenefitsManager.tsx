/**
 * Компонент для управления системой скидок и льгот
 */
import { useState, useEffect } from 'react';
import type { CSSProperties } from "react";
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
import { useTranslation } from '../../i18n/useTranslation';

// === Domain types ===
// Shape produced by loadAnalytics(): three optional analytics sections, each
// returned by a separate backend endpoint. Fields are optional because the
// backend may omit them when there is no data yet.

interface DiscountAnalyticsSection {
  total_applications?: number;
  total_discount_amount?: number;
  average_discount_percentage?: number;
  [key: string]: unknown;
}

interface BenefitAnalyticsSection {
  total_applications?: number;
  total_benefit_amount?: number;
  average_benefit_percentage?: number;
  [key: string]: unknown;
}

interface LoyaltyAnalyticsSection {
  total_patients?: number;
  active_patients?: number;
  total_points_earned?: number;
  redemption_rate?: number;
  [key: string]: unknown;
}

interface DiscountAnalytics {
  discounts?: DiscountAnalyticsSection | null;
  benefits?: BenefitAnalyticsSection | null;
  loyalty?: LoyaltyAnalyticsSection | null;
  [key: string]: unknown;
}

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
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [activeTab, setActiveTab] = useState('discounts');
  const [discounts, setDiscounts] = useState([]);
  const [benefits, setBenefits] = useState([]);
  const [loyaltyPrograms, setLoyaltyPrograms] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [analytics, setAnalytics] = useState<DiscountAnalytics | null>(null);

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
      toast.error(t('admin2.disc_load_failed'));
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

      const analytics: DiscountAnalytics = {
        discounts: (discountAnalytics.status === 'fulfilled'
          ? (discountAnalytics.value.data as { analytics?: DiscountAnalyticsSection })?.analytics
          : null) ?? null,
        benefits: (benefitAnalytics.status === 'fulfilled'
          ? (benefitAnalytics.value.data as { analytics?: BenefitAnalyticsSection })?.analytics
          : null) ?? null,
        loyalty: (loyaltyAnalytics.status === 'fulfilled'
          ? (loyaltyAnalytics.value.data as { analytics?: LoyaltyAnalyticsSection })?.analytics
          : null) ?? null,
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
      toast.success(t('admin2.disc_create_success'));
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
      toast.error(error.response?.data?.detail || t('admin2.disc_create_error'));
    }
  };

  // Создание льготы
  const createBenefit = async () => {
    try {
      await api.post('/discount-benefits/benefits', sanitizePayload(benefitForm));
      toast.success(t('admin2.disc_benefit_create_success'));
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
      toast.error(error.response?.data?.detail || t('admin2.disc_benefit_create_error'));
    }
  };

  // Создание программы лояльности
  const createLoyaltyProgram = async () => {
    try {
      await api.post('/discount-benefits/loyalty-programs', sanitizePayload(loyaltyForm));
      toast.success(t('admin2.disc_loyalty_create_success'));
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
      toast.error(error.response?.data?.detail || t('admin2.disc_loyalty_create_error'));
    }
  };

  // Типы скидок
  const discountTypes = {
    percentage: t('admin2.disc_type_percentage'),
    fixed_amount: t('admin2.disc_type_fixed_amount'),
    buy_x_get_y: t('admin2.disc_type_buy_x_get_y'),
    loyalty_points: t('admin2.disc_type_loyalty_points'),
    seasonal: t('admin2.disc_type_seasonal'),
    referral: t('admin2.disc_type_referral')
  };

  // Типы льгот
  const benefitTypes = {
    veteran: t('admin2.disc_btype_veteran'),
    disabled: t('admin2.disc_btype_disabled'),
    pensioner: t('admin2.disc_btype_pensioner'),
    student: t('admin2.disc_btype_student'),
    child: t('admin2.disc_btype_child'),
    large_family: t('admin2.disc_btype_large_family'),
    low_income: t('admin2.disc_btype_low_income'),
    employee: t('admin2.disc_btype_employee')
  };

  // Рендер формы создания скидки
  const renderDiscountForm = () =>
  <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{t('admin2.disc_f_name_label')}</label>
          <Input
          value={discountForm.name}
          onChange={(e) => setDiscountForm({ ...discountForm, name: e.target.value })}
          placeholder={t('admin2.disc_f_name_ph')} />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{t('admin2.disc_f_type_label')}</label>
          <Select
          value={discountForm.discount_type}
          onChange={(value: unknown) => setDiscountForm({ ...discountForm, discount_type: String(value) })}
          options={Object.entries(discountTypes).map(([key, value]) => ({ value: key, label: value }))}
          size="large" />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{t('admin2.disc_f_value_label')}</label>
          <Input
          type="number"
          value={discountForm.value}
          onChange={(e) => setDiscountForm({ ...discountForm, value: e.target.value })}
          placeholder={t('admin2.disc_f_value_ph')} />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{t('admin2.disc_f_min_amount_label')}</label>
          <Input
          type="number"
          value={discountForm.min_amount}
          onChange={(e) => setDiscountForm({ ...discountForm, min_amount: e.target.value })}
          placeholder="0" />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{t('admin2.disc_f_max_discount_label')}</label>
          <Input
          type="number"
          value={discountForm.max_discount}
          onChange={(e) => setDiscountForm({ ...discountForm, max_discount: e.target.value })}
          placeholder={t('admin2.disc_not_limited_ph')} />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{t('admin2.disc_f_usage_limit_label')}</label>
          <Input
          type="number"
          value={discountForm.usage_limit}
          onChange={(e) => setDiscountForm({ ...discountForm, usage_limit: e.target.value })}
          placeholder={t('admin2.disc_not_limited_ph')} />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{t('admin2.disc_f_start_date_label')}</label>
          <Input
          type="datetime-local"
          value={discountForm.start_date}
          onChange={(e) => setDiscountForm({ ...discountForm, start_date: e.target.value })} />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{t('admin2.disc_f_end_date_label')}</label>
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
        placeholder={t('admin2.disc_f_desc_ph')}
        rows={3} />
      
      </div>
      <div className="flex flex-wrap gap-4">
          <label className="flex items-center">
            <Checkbox aria-label="Discount applies to services" checked={discountForm.applies_to_services} onChange={(checked: boolean) => setDiscountForm({ ...discountForm, applies_to_services: checked })}
              className="mr-2" />
        
          {t('admin2.disc_applies_to_services')}
        </label>
          <label className="flex items-center">
            <Checkbox aria-label="Discount applies to appointments" checked={discountForm.applies_to_appointments} onChange={(checked: boolean) => setDiscountForm({ ...discountForm, applies_to_appointments: checked })}
              className="mr-2" />
        
          {t('admin2.disc_applies_to_appointments')}
        </label>
          <label className="flex items-center">
            <Checkbox aria-label="Discount can combine with other discounts" checked={discountForm.can_combine_with_others} onChange={(checked: boolean) => setDiscountForm({ ...discountForm, can_combine_with_others: checked })}
              className="mr-2" />
        
          {t('admin2.disc_can_combine')}
        </label>
      </div>
      <div className="flex gap-2">
        <Button onClick={createDiscount} className="bg-blue-500 text-white">
          {t('admin2.disc_create_btn')}
        </Button>
        <Button onClick={() => setShowCreateForm(false)} className="bg-gray-500 text-white">
          {t('admin2.disc_cancel_btn')}
        </Button>
      </div>
    </div>;


  // Рендер формы создания льготы
  const renderBenefitForm = () =>
  <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{t('admin2.disc_bf_name_label')}</label>
          <Input
          value={benefitForm.name}
          onChange={(e) => setBenefitForm({ ...benefitForm, name: e.target.value })}
          placeholder={t('admin2.disc_bf_name_ph')} />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{t('admin2.disc_bf_type_label')}</label>
          <Select
          value={benefitForm.benefit_type}
          onChange={(value: unknown) => setBenefitForm({ ...benefitForm, benefit_type: String(value) })}
          options={Object.entries(benefitTypes).map(([key, value]) => ({ value: key, label: value }))}
          size="large" />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{t('admin2.disc_bf_percent_label')}</label>
          <Input
          type="number"
          value={benefitForm.discount_percentage}
          onChange={(e) => setBenefitForm({ ...benefitForm, discount_percentage: e.target.value })}
          placeholder={t('admin2.disc_bf_percent_ph')}
          max="100" />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{t('admin2.disc_bf_max_amount_label')}</label>
          <Input
          type="number"
          value={benefitForm.max_discount_amount}
          onChange={(e) => setBenefitForm({ ...benefitForm, max_discount_amount: e.target.value })}
          placeholder={t('admin2.disc_not_limited_ph')} />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{t('admin2.disc_bf_age_min_label')}</label>
          <Input
          type="number"
          value={benefitForm.age_min}
          onChange={(e) => setBenefitForm({ ...benefitForm, age_min: e.target.value })}
          placeholder={t('admin2.disc_not_limited_ph')} />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{t('admin2.disc_bf_age_max_label')}</label>
          <Input
          type="number"
          value={benefitForm.age_max}
          onChange={(e) => setBenefitForm({ ...benefitForm, age_max: e.target.value })}
          placeholder={t('admin2.disc_not_limited_ph')} />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{t('admin2.disc_bf_monthly_limit_label')}</label>
          <Input
          type="number"
          value={benefitForm.monthly_limit}
          onChange={(e) => setBenefitForm({ ...benefitForm, monthly_limit: e.target.value })}
          placeholder={t('admin2.disc_not_limited_ph')} />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{t('admin2.disc_bf_yearly_limit_label')}</label>
          <Input
          type="number"
          value={benefitForm.yearly_limit}
          onChange={(e) => setBenefitForm({ ...benefitForm, yearly_limit: e.target.value })}
          placeholder={t('admin2.disc_not_limited_ph')} />
        
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{t('common.description')}</label>
        <Textarea
        value={benefitForm.description}
        onChange={(e) => setBenefitForm({ ...benefitForm, description: e.target.value })}
        placeholder={t('admin2.disc_bf_desc_ph')}
        rows={3} />
      
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{t('admin2.disc_bf_doc_types_label')}</label>
        <Input
        value={benefitForm.document_types}
        onChange={(e) => setBenefitForm({ ...benefitForm, document_types: e.target.value })}
        placeholder='["passport", "certificate"]' />
      
      </div>
      <div className="flex flex-wrap gap-4">
          <label className="flex items-center">
            <Checkbox aria-label="Benefit requires documents" checked={benefitForm.requires_document} onChange={(checked: boolean) => setBenefitForm({ ...benefitForm, requires_document: checked })}
              className="mr-2" />
        
          {t('admin2.disc_requires_documents')}
        </label>
          <label className="flex items-center">
            <Checkbox aria-label="Benefit applies to services" checked={benefitForm.applies_to_services} onChange={(checked: boolean) => setBenefitForm({ ...benefitForm, applies_to_services: checked })}
              className="mr-2" />
        
          {t('admin2.disc_applies_to_services')}
        </label>
          <label className="flex items-center">
            <Checkbox aria-label="Benefit applies to appointments" checked={benefitForm.applies_to_appointments} onChange={(checked: boolean) => setBenefitForm({ ...benefitForm, applies_to_appointments: checked })}
              className="mr-2" />
        
          {t('admin2.disc_applies_to_appointments')}
        </label>
      </div>
      <div className="flex gap-2">
        <Button onClick={createBenefit} className="bg-blue-500 text-white">
          {t('admin2.disc_create_benefit_btn')}
        </Button>
        <Button onClick={() => setShowCreateForm(false)} className="bg-gray-500 text-white">
          {t('admin2.disc_cancel_btn')}
        </Button>
      </div>
    </div>;


  // Рендер формы создания программы лояльности
  const renderLoyaltyForm = () =>
  <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{t('admin2.disc_lf_name_label')}</label>
          <Input
          value={loyaltyForm.name}
          onChange={(e) => setLoyaltyForm({ ...loyaltyForm, name: e.target.value })}
          placeholder={t('admin2.disc_lf_name_ph')} />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{t('admin2.disc_lf_points_per_ruble_label')}</label>
          <Input
          type="number"
          step="0.1"
          value={loyaltyForm.points_per_ruble}
          onChange={(e) => setLoyaltyForm({ ...loyaltyForm, points_per_ruble: e.target.value })}
          placeholder="1.0" />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{t('admin2.disc_lf_ruble_per_point_label')}</label>
          <Input
          type="number"
          step="0.1"
          value={loyaltyForm.ruble_per_point}
          onChange={(e) => setLoyaltyForm({ ...loyaltyForm, ruble_per_point: e.target.value })}
          placeholder="1.0" />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{t('admin2.disc_lf_min_points_label')}</label>
          <Input
          type="number"
          value={loyaltyForm.min_points_to_redeem}
          onChange={(e) => setLoyaltyForm({ ...loyaltyForm, min_points_to_redeem: e.target.value })}
          placeholder="100" />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{t('admin2.disc_lf_min_purchase_label')}</label>
          <Input
          type="number"
          value={loyaltyForm.min_purchase_for_points}
          onChange={(e) => setLoyaltyForm({ ...loyaltyForm, min_purchase_for_points: e.target.value })}
          placeholder="0" />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{t('admin2.disc_lf_max_points_label')}</label>
          <Input
          type="number"
          value={loyaltyForm.max_points_per_purchase}
          onChange={(e) => setLoyaltyForm({ ...loyaltyForm, max_points_per_purchase: e.target.value })}
          placeholder={t('admin2.disc_not_limited_ph')} />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{t('admin2.disc_f_start_date_label')}</label>
          <Input
          type="datetime-local"
          value={loyaltyForm.start_date}
          onChange={(e) => setLoyaltyForm({ ...loyaltyForm, start_date: e.target.value })} />
        
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{t('admin2.disc_f_end_date_label')}</label>
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
        placeholder={t('admin2.disc_lf_desc_ph')}
        rows={3} />
      
      </div>
      <div className="flex gap-2">
        <Button onClick={createLoyaltyProgram} className="bg-blue-500 text-white">
          {t('admin2.disc_create_program_btn')}
        </Button>
        <Button onClick={() => setShowCreateForm(false)} className="bg-gray-500 text-white">
          {t('admin2.disc_cancel_btn')}
        </Button>
      </div>
    </div>;


  // Рендер списка скидок
  const renderDiscountsList = () =>
  <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h3 className="admin-section-h3-m0">
          {t('admin2.disc_list_title')}
        </h3>
        <Button
        onClick={() => setShowCreateForm(true)}
        className="flex items-center justify-center gap-2">
        
          <Plus size={16} />
          {t('admin2.disc_create_btn')}
        </Button>
      </div>

      {showCreateForm &&
    <MacOSCard className="p-0">
          <h4 className="admin-h4-md-semi-primary-mb-16">
            {t('admin2.disc_create_form_title')}
          </h4>
          {renderDiscountForm()}
        </MacOSCard>
    }

      <div className="admin-grid-gap-16">
        {discounts.length === 0 ?
      <MacOSEmptyState
        type="discount"
        title={t('admin2.disc_empty_title')}
        description={t('admin2.disc_empty_desc')}
        action={
        <Button onClick={() => setShowCreateForm(true)}>
                <Plus size={16} className="mr-2" />
                {t('admin2.disc_create_first_btn')}
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
                      {discount.is_active ? t('admin2.disc_status_active') : t('admin2.disc_status_inactive')}
                    </Badge>
                    <Badge variant="info">
                      {discountTypes[discount.discount_type]}
                    </Badge>
                    <Badge variant="warning">
                      {discount.discount_type === 'percentage' ? `${discount.value}%` : `${discount.value} ${t('admin2.disc_currency')}`}
                    </Badge>
                  </div>
                </div>
                <div className="admin-text-right text-sm text-[var(--mac-text-secondary)]">
                  <div>{t('admin2.disc_field_usage_count', { count: discount.usage_count, limit: discount.usage_limit || '∞' })}</div>
                  <div>{t('admin2.disc_field_priority', { value: discount.priority })}</div>
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
          {t('admin2.disc_benefits_list_title')}
        </h3>
        <Button
        onClick={() => setShowCreateForm(true)}
        className="flex items-center justify-center gap-2">
        
          <Plus size={16} />
          {t('admin2.disc_create_benefit_btn')}
        </Button>
      </div>

      {showCreateForm &&
    <MacOSCard className="p-0">
          <h4 className="admin-h4-md-semi-primary-mb-16">
            {t('admin2.disc_create_benefit_form_title')}
          </h4>
          {renderBenefitForm()}
        </MacOSCard>
    }

      <div className="admin-grid-gap-16">
        {benefits.length === 0 ?
      <MacOSEmptyState
        type="benefit"
        title={t('admin2.disc_benefits_empty_title')}
        description={t('admin2.disc_benefits_empty_desc')}
        action={
        <Button onClick={() => setShowCreateForm(true)}>
                <Plus size={16} className="mr-2" />
                {t('admin2.disc_create_first_benefit_btn')}
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
                      {benefit.is_active ? t('admin2.disc_status_active') : t('admin2.disc_status_inactive')}
                    </Badge>
                    <Badge variant="info">
                      {benefitTypes[benefit.benefit_type]}
                    </Badge>
                    <Badge variant="warning">
                      {benefit.discount_percentage}%
                    </Badge>
                    {benefit.requires_document &&
              <Badge variant="secondary">
                        {t('admin2.disc_requires_documents')}
                      </Badge>
              }
                  </div>
                </div>
                <div className="admin-text-right text-sm text-[var(--mac-text-secondary)]">
                  {benefit.monthly_limit && <div>{t('admin2.disc_field_monthly_limit', { value: benefit.monthly_limit, currency: t('admin2.disc_currency') })}</div>}
                  {benefit.yearly_limit && <div>{t('admin2.disc_field_yearly_limit', { value: benefit.yearly_limit, currency: t('admin2.disc_currency') })}</div>}
                  {benefit.max_discount_amount && <div>{t('admin2.disc_field_max_discount', { value: benefit.max_discount_amount, currency: t('admin2.disc_currency') })}</div>}
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
          {t('admin2.disc_loyalty_list_title')}
        </h3>
        <Button
        onClick={() => setShowCreateForm(true)}
        className="flex items-center justify-center gap-2">
        
          <Plus size={16} />
          {t('admin2.disc_create_program_btn')}
        </Button>
      </div>

      {showCreateForm &&
    <MacOSCard className="p-0">
          <h4 className="admin-h4-md-semi-primary-mb-16">
            {t('admin2.disc_create_loyalty_form_title')}
          </h4>
          {renderLoyaltyForm()}
        </MacOSCard>
    }

      <div className="admin-grid-gap-16">
        {loyaltyPrograms.length === 0 ?
      <MacOSEmptyState
        type="loyalty"
        title={t('admin2.disc_loyalty_empty_title')}
        description={t('admin2.disc_loyalty_empty_desc')}
        action={
        <Button onClick={() => setShowCreateForm(true)}>
                <Plus size={16} className="mr-2" />
                {t('admin2.disc_create_first_loyalty_btn')}
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
                      {program.is_active ? t('admin2.disc_status_active') : t('admin2.disc_status_inactive')}
                    </Badge>
                    <Badge variant="info">
                      {program.points_per_ruble} {t('admin2.disc_loyalty_points_unit')}
                    </Badge>
                    <Badge variant="warning">
                      {program.ruble_per_point} {t('admin2.disc_loyalty_ruble_unit')}
                    </Badge>
                  </div>
                </div>
                <div className="admin-text-right text-sm text-[var(--mac-text-secondary)]">
                  <div>{t('admin2.disc_field_min_redeem', { value: program.min_points_to_redeem })}</div>
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
        {t('admin2.disc_analytics_title')}
      </h3>

      {analytics ?
    <div className="admin-grid-auto-300">
          {/* Аналитика скидок */}
          {analytics.discounts &&
      <MacOSCard className="p-0">
              <h4 className="admin-h4-md-semi-primary-mb-12-flex">
                <TrendingUp size={16} />
                {t('admin2.disc_analytics_discounts_title')}
              </h4>
              <div className="flex flex-col gap-2">
                <div className="text-sm text-[var(--mac-text-secondary)]">
                  {t('admin2.disc_analytics_total_applications')} <span className="admin-text-med-primary">{analytics.discounts.total_applications}</span>
                </div>
                <div className="text-sm text-[var(--mac-text-secondary)]">
                  {t('admin2.disc_analytics_total_discount_amount')} <span className="admin-text-med-primary">{analytics.discounts.total_discount_amount?.toFixed(2)} {t('admin2.disc_currency')}</span>
                </div>
                <div className="text-sm text-[var(--mac-text-secondary)]">
                  {t('admin2.disc_analytics_avg_discount_percent')} <span className="admin-text-med-primary">{analytics.discounts.average_discount_percentage?.toFixed(1)}%</span>
                </div>
              </div>
            </MacOSCard>
      }

          {/* Аналитика льгот */}
          {analytics.benefits &&
      <MacOSCard className="p-0">
              <h4 className="admin-h4-md-semi-primary-mb-12-flex">
                <Users size={16} />
                {t('admin2.disc_analytics_benefits_title')}
              </h4>
              <div className="flex flex-col gap-2">
                <div className="text-sm text-[var(--mac-text-secondary)]">
                  {t('admin2.disc_analytics_total_applications')} <span className="admin-text-med-primary">{analytics.benefits.total_applications}</span>
                </div>
                <div className="text-sm text-[var(--mac-text-secondary)]">
                  {t('admin2.disc_analytics_total_benefit_amount')} <span className="admin-text-med-primary">{analytics.benefits.total_benefit_amount?.toFixed(2)} {t('admin2.disc_currency')}</span>
                </div>
                <div className="text-sm text-[var(--mac-text-secondary)]">
                  {t('admin2.disc_analytics_avg_benefit_percent')} <span className="admin-text-med-primary">{analytics.benefits.average_benefit_percentage?.toFixed(1)}%</span>
                </div>
              </div>
            </MacOSCard>
      }

          {/* Аналитика лояльности */}
          {analytics.loyalty &&
      <MacOSCard className="p-0">
              <h4 className="admin-h4-md-semi-primary-mb-12-flex">
                <DollarSign size={16} />
                {t('admin2.disc_analytics_loyalty_title')}
              </h4>
              <div className="flex flex-col gap-2">
                <div className="text-sm text-[var(--mac-text-secondary)]">
                  {t('admin2.disc_analytics_total_participants')} <span className="admin-text-med-primary">{analytics.loyalty.total_patients}</span>
                </div>
                <div className="text-sm text-[var(--mac-text-secondary)]">
                  {t('admin2.disc_analytics_active_participants')} <span className="admin-text-med-primary">{analytics.loyalty.active_patients}</span>
                </div>
                <div className="text-sm text-[var(--mac-text-secondary)]">
                  {t('admin2.disc_analytics_total_points_earned')} <span className="admin-text-med-primary">{analytics.loyalty.total_points_earned}</span>
                </div>
                <div className="text-sm text-[var(--mac-text-secondary)]">
                  {t('admin2.disc_analytics_redemption_rate')} <span className="admin-text-med-primary">{analytics.loyalty.redemption_rate?.toFixed(1)}%</span>
                </div>
              </div>
            </MacOSCard>
      }
        </div> :

    <MacOSEmptyState
      type="analytics"
      title={t('admin2.disc_analytics_empty_title')}
      description={t('admin2.disc_analytics_empty_desc')} />

    }
    </div>;


  const tabs = [
  { id: 'discounts', label: t('admin2.disc_tab_discounts'), count: discounts.length },
  { id: 'benefits', label: t('admin2.disc_tab_benefits'), count: benefits.length },
  { id: 'loyalty', label: t('admin2.disc_tab_loyalty'), count: loyaltyPrograms.length },
  { id: 'analytics', label: t('admin2.disc_tab_analytics') }];


  return (
    <div className="p-0">
      <div className="admin-flex-center-16 mb-6">
        <Percent size={24} color="var(--mac-accent)" />
        <div>
          <h2 className="admin-h2-xl-bold-primary-m0">
            {t('admin2.disc_page_title')}
          </h2>
          <p className="admin-p-sm-secondary-mt-4">
            {t('admin2.disc_page_subtitle')}
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
          } as CSSProperties}>
          
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
