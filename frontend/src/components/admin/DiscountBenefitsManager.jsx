/**
 * Компонент для управления системой скидок и льгот
 */
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
  Percent, 
  Plus, 
  Edit, 
  Trash2, 
  Save, 
  X, 
  TrendingUp,
  Users,
  Calendar,
  DollarSign
} from 'lucide-react';
import { toast } from 'react-toastify';

const DiscountBenefitsManager = () => {
  const [activeTab, setActiveTab] = useState('discounts');
  const [discounts, setDiscounts] = useState([]);
  const [benefits, setBenefits] = useState([]);
  const [loyaltyPrograms, setLoyaltyPrograms] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingItem, setEditingItem] = useState(null);
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

  const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

  // Получение токена авторизации
  const getAuthToken = () => {
    return localStorage.getItem('access_token');
  };

  // Заголовки для API запросов
  const getHeaders = () => ({
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${getAuthToken()}`
  });

  // Загрузка данных
  const loadData = async () => {
    setLoading(true);
    try {
      const token = getAuthToken();
      if (!token) {
        toast.error('Необходима авторизация');
        return;
      }

      const headers = getHeaders();

      // Загрузка скидок
      const discountsResponse = await fetch(`${API_BASE}/discount-benefits/discounts`, { headers });
      if (discountsResponse.ok) {
        const discountsData = await discountsResponse.json();
        setDiscounts(discountsData.discounts || []);
      }

      // Загрузка льгот
      const benefitsResponse = await fetch(`${API_BASE}/discount-benefits/benefits`, { headers });
      if (benefitsResponse.ok) {
        const benefitsData = await benefitsResponse.json();
        setBenefits(benefitsData.benefits || []);
      }

      // Загрузка программ лояльности
      const loyaltyResponse = await fetch(`${API_BASE}/discount-benefits/loyalty-programs`, { headers });
      if (loyaltyResponse.ok) {
        const loyaltyData = await loyaltyResponse.json();
        setLoyaltyPrograms(loyaltyData.programs || []);
      }

    } catch (error) {
      console.error('Ошибка загрузки данных:', error);
      toast.error('Ошибка загрузки данных');
    } finally {
      setLoading(false);
    }
  };

  // Загрузка аналитики
  const loadAnalytics = async () => {
    try {
      const headers = getHeaders();
      
      const [discountAnalytics, benefitAnalytics, loyaltyAnalytics] = await Promise.all([
        fetch(`${API_BASE}/discount-benefits/analytics/discounts`, { headers }),
        fetch(`${API_BASE}/discount-benefits/analytics/benefits`, { headers }),
        fetch(`${API_BASE}/discount-benefits/analytics/loyalty`, { headers })
      ]);

      const analytics = {
        discounts: discountAnalytics.ok ? (await discountAnalytics.json()).analytics : null,
        benefits: benefitAnalytics.ok ? (await benefitAnalytics.json()).analytics : null,
        loyalty: loyaltyAnalytics.ok ? (await loyaltyAnalytics.json()).analytics : null
      };

      setAnalytics(analytics);
    } catch (error) {
      console.error('Ошибка загрузки аналитики:', error);
    }
  };

  useEffect(() => {
    loadData();
    loadAnalytics();
  }, []);

  // Создание скидки
  const createDiscount = async () => {
    try {
      const response = await fetch(`${API_BASE}/discount-benefits/discounts`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify(discountForm)
      });

      if (response.ok) {
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
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Ошибка создания скидки');
      }
    } catch (error) {
      console.error('Ошибка создания скидки:', error);
      toast.error('Ошибка создания скидки');
    }
  };

  // Создание льготы
  const createBenefit = async () => {
    try {
      const response = await fetch(`${API_BASE}/discount-benefits/benefits`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify(benefitForm)
      });

      if (response.ok) {
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
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Ошибка создания льготы');
      }
    } catch (error) {
      console.error('Ошибка создания льготы:', error);
      toast.error('Ошибка создания льготы');
    }
  };

  // Создание программы лояльности
  const createLoyaltyProgram = async () => {
    try {
      const response = await fetch(`${API_BASE}/discount-benefits/loyalty-programs`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify(loyaltyForm)
      });

      if (response.ok) {
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
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Ошибка создания программы лояльности');
      }
    } catch (error) {
      console.error('Ошибка создания программы лояльности:', error);
      toast.error('Ошибка создания программы лояльности');
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
  const renderDiscountForm = () => (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <Label>Название скидки</Label>
          <Input
            value={discountForm.name}
            onChange={(e) => setDiscountForm({...discountForm, name: e.target.value})}
            placeholder="Введите название скидки"
          />
        </div>
        <div>
          <Label>Тип скидки</Label>
          <Select
            value={discountForm.discount_type}
            onChange={(e) => setDiscountForm({...discountForm, discount_type: e.target.value})}
          >
            {Object.entries(discountTypes).map(([key, value]) => (
              <option key={key} value={key}>{value}</option>
            ))}
          </Select>
        </div>
        <div>
          <Label>Значение скидки</Label>
          <Input
            type="number"
            value={discountForm.value}
            onChange={(e) => setDiscountForm({...discountForm, value: e.target.value})}
            placeholder="Введите значение"
          />
        </div>
        <div>
          <Label>Минимальная сумма</Label>
          <Input
            type="number"
            value={discountForm.min_amount}
            onChange={(e) => setDiscountForm({...discountForm, min_amount: e.target.value})}
            placeholder="0"
          />
        </div>
        <div>
          <Label>Максимальная скидка</Label>
          <Input
            type="number"
            value={discountForm.max_discount}
            onChange={(e) => setDiscountForm({...discountForm, max_discount: e.target.value})}
            placeholder="Не ограничено"
          />
        </div>
        <div>
          <Label>Лимит использований</Label>
          <Input
            type="number"
            value={discountForm.usage_limit}
            onChange={(e) => setDiscountForm({...discountForm, usage_limit: e.target.value})}
            placeholder="Не ограничено"
          />
        </div>
        <div>
          <Label>Дата начала</Label>
          <Input
            type="datetime-local"
            value={discountForm.start_date}
            onChange={(e) => setDiscountForm({...discountForm, start_date: e.target.value})}
          />
        </div>
        <div>
          <Label>Дата окончания</Label>
          <Input
            type="datetime-local"
            value={discountForm.end_date}
            onChange={(e) => setDiscountForm({...discountForm, end_date: e.target.value})}
          />
        </div>
      </div>
      <div>
        <Label>Описание</Label>
        <Textarea
          value={discountForm.description}
          onChange={(e) => setDiscountForm({...discountForm, description: e.target.value})}
          placeholder="Введите описание скидки"
          rows={3}
        />
      </div>
      <div className="flex flex-wrap gap-4">
        <label className="flex items-center">
          <input
            type="checkbox"
            checked={discountForm.applies_to_services}
            onChange={(e) => setDiscountForm({...discountForm, applies_to_services: e.target.checked})}
            className="mr-2"
          />
          Применяется к услугам
        </label>
        <label className="flex items-center">
          <input
            type="checkbox"
            checked={discountForm.applies_to_appointments}
            onChange={(e) => setDiscountForm({...discountForm, applies_to_appointments: e.target.checked})}
            className="mr-2"
          />
          Применяется к записям
        </label>
        <label className="flex items-center">
          <input
            type="checkbox"
            checked={discountForm.can_combine_with_others}
            onChange={(e) => setDiscountForm({...discountForm, can_combine_with_others: e.target.checked})}
            className="mr-2"
          />
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
    </div>
  );

  // Рендер формы создания льготы
  const renderBenefitForm = () => (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <Label>Название льготы</Label>
          <Input
            value={benefitForm.name}
            onChange={(e) => setBenefitForm({...benefitForm, name: e.target.value})}
            placeholder="Введите название льготы"
          />
        </div>
        <div>
          <Label>Тип льготы</Label>
          <Select
            value={benefitForm.benefit_type}
            onChange={(e) => setBenefitForm({...benefitForm, benefit_type: e.target.value})}
          >
            {Object.entries(benefitTypes).map(([key, value]) => (
              <option key={key} value={key}>{value}</option>
            ))}
          </Select>
        </div>
        <div>
          <Label>Процент скидки</Label>
          <Input
            type="number"
            value={benefitForm.discount_percentage}
            onChange={(e) => setBenefitForm({...benefitForm, discount_percentage: e.target.value})}
            placeholder="Введите процент"
            max="100"
          />
        </div>
        <div>
          <Label>Максимальная сумма льготы</Label>
          <Input
            type="number"
            value={benefitForm.max_discount_amount}
            onChange={(e) => setBenefitForm({...benefitForm, max_discount_amount: e.target.value})}
            placeholder="Не ограничено"
          />
        </div>
        <div>
          <Label>Минимальный возраст</Label>
          <Input
            type="number"
            value={benefitForm.age_min}
            onChange={(e) => setBenefitForm({...benefitForm, age_min: e.target.value})}
            placeholder="Не ограничено"
          />
        </div>
        <div>
          <Label>Максимальный возраст</Label>
          <Input
            type="number"
            value={benefitForm.age_max}
            onChange={(e) => setBenefitForm({...benefitForm, age_max: e.target.value})}
            placeholder="Не ограничено"
          />
        </div>
        <div>
          <Label>Месячный лимит</Label>
          <Input
            type="number"
            value={benefitForm.monthly_limit}
            onChange={(e) => setBenefitForm({...benefitForm, monthly_limit: e.target.value})}
            placeholder="Не ограничено"
          />
        </div>
        <div>
          <Label>Годовой лимит</Label>
          <Input
            type="number"
            value={benefitForm.yearly_limit}
            onChange={(e) => setBenefitForm({...benefitForm, yearly_limit: e.target.value})}
            placeholder="Не ограничено"
          />
        </div>
      </div>
      <div>
        <Label>Описание</Label>
        <Textarea
          value={benefitForm.description}
          onChange={(e) => setBenefitForm({...benefitForm, description: e.target.value})}
          placeholder="Введите описание льготы"
          rows={3}
        />
      </div>
      <div>
        <Label>Типы документов (JSON)</Label>
        <Input
          value={benefitForm.document_types}
          onChange={(e) => setBenefitForm({...benefitForm, document_types: e.target.value})}
          placeholder='["passport", "certificate"]'
        />
      </div>
      <div className="flex flex-wrap gap-4">
        <label className="flex items-center">
          <input
            type="checkbox"
            checked={benefitForm.requires_document}
            onChange={(e) => setBenefitForm({...benefitForm, requires_document: e.target.checked})}
            className="mr-2"
          />
          Требует документы
        </label>
        <label className="flex items-center">
          <input
            type="checkbox"
            checked={benefitForm.applies_to_services}
            onChange={(e) => setBenefitForm({...benefitForm, applies_to_services: e.target.checked})}
            className="mr-2"
          />
          Применяется к услугам
        </label>
        <label className="flex items-center">
          <input
            type="checkbox"
            checked={benefitForm.applies_to_appointments}
            onChange={(e) => setBenefitForm({...benefitForm, applies_to_appointments: e.target.checked})}
            className="mr-2"
          />
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
    </div>
  );

  // Рендер формы создания программы лояльности
  const renderLoyaltyForm = () => (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <Label>Название программы</Label>
          <Input
            value={loyaltyForm.name}
            onChange={(e) => setLoyaltyForm({...loyaltyForm, name: e.target.value})}
            placeholder="Введите название программы"
          />
        </div>
        <div>
          <Label>Баллов за рубль</Label>
          <Input
            type="number"
            step="0.1"
            value={loyaltyForm.points_per_ruble}
            onChange={(e) => setLoyaltyForm({...loyaltyForm, points_per_ruble: e.target.value})}
            placeholder="1.0"
          />
        </div>
        <div>
          <Label>Рублей за балл</Label>
          <Input
            type="number"
            step="0.1"
            value={loyaltyForm.ruble_per_point}
            onChange={(e) => setLoyaltyForm({...loyaltyForm, ruble_per_point: e.target.value})}
            placeholder="1.0"
          />
        </div>
        <div>
          <Label>Минимум баллов для списания</Label>
          <Input
            type="number"
            value={loyaltyForm.min_points_to_redeem}
            onChange={(e) => setLoyaltyForm({...loyaltyForm, min_points_to_redeem: e.target.value})}
            placeholder="100"
          />
        </div>
        <div>
          <Label>Минимальная покупка для начисления</Label>
          <Input
            type="number"
            value={loyaltyForm.min_purchase_for_points}
            onChange={(e) => setLoyaltyForm({...loyaltyForm, min_purchase_for_points: e.target.value})}
            placeholder="0"
          />
        </div>
        <div>
          <Label>Максимум баллов за покупку</Label>
          <Input
            type="number"
            value={loyaltyForm.max_points_per_purchase}
            onChange={(e) => setLoyaltyForm({...loyaltyForm, max_points_per_purchase: e.target.value})}
            placeholder="Не ограничено"
          />
        </div>
        <div>
          <Label>Дата начала</Label>
          <Input
            type="datetime-local"
            value={loyaltyForm.start_date}
            onChange={(e) => setLoyaltyForm({...loyaltyForm, start_date: e.target.value})}
          />
        </div>
        <div>
          <Label>Дата окончания</Label>
          <Input
            type="datetime-local"
            value={loyaltyForm.end_date}
            onChange={(e) => setLoyaltyForm({...loyaltyForm, end_date: e.target.value})}
          />
        </div>
      </div>
      <div>
        <Label>Описание</Label>
        <Textarea
          value={loyaltyForm.description}
          onChange={(e) => setLoyaltyForm({...loyaltyForm, description: e.target.value})}
          placeholder="Введите описание программы"
          rows={3}
        />
      </div>
      <div className="flex gap-2">
        <Button onClick={createLoyaltyProgram} className="bg-blue-500 text-white">
          Создать программу
        </Button>
        <Button onClick={() => setShowCreateForm(false)} className="bg-gray-500 text-white">
          Отмена
        </Button>
      </div>
    </div>
  );

  // Рендер списка скидок
  const renderDiscountsList = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center' 
      }}>
        <h3 style={{ 
          margin: 0,
          color: 'var(--mac-text-primary)',
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-semibold)'
        }}>
          Скидки
        </h3>
        <MacOSButton 
          onClick={() => setShowCreateForm(true)}
          style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '8px' 
          }}
        >
          <Plus size={16} />
          Создать скидку
        </MacOSButton>
      </div>
      
      {showCreateForm && (
        <MacOSCard style={{ padding: 0 }}>
          <h4 style={{ 
            margin: '0 0 16px 0',
            color: 'var(--mac-text-primary)',
            fontSize: 'var(--mac-font-size-md)',
            fontWeight: 'var(--mac-font-weight-semibold)'
          }}>
            Создание новой скидки
          </h4>
          {renderDiscountForm()}
        </MacOSCard>
      )}

      <div style={{ display: 'grid', gap: '16px' }}>
        {discounts.length === 0 ? (
          <MacOSEmptyState
            type="discount"
            title="Скидки не найдены"
            description="В системе пока нет созданных скидок"
            action={
              <MacOSButton onClick={() => setShowCreateForm(true)}>
                <Plus size={16} style={{ marginRight: '8px' }} />
                Создать первую скидку
              </MacOSButton>
            }
          />
        ) : (
          discounts.map((discount) => (
            <MacOSCard key={discount.id} style={{ padding: 0 }}>
              <div style={{ 
                display: 'flex', 
                justifyContent: 'space-between', 
                alignItems: 'flex-start' 
              }}>
                <div>
                  <h4 style={{ 
                    margin: '0 0 8px 0',
                    color: 'var(--mac-text-primary)',
                    fontSize: 'var(--mac-font-size-md)',
                    fontWeight: 'var(--mac-font-weight-semibold)'
                  }}>
                    {discount.name}
                  </h4>
                  <p style={{ 
                    margin: '0 0 12px 0',
                    color: 'var(--mac-text-secondary)',
                    fontSize: 'var(--mac-font-size-sm)'
                  }}>
                    {discount.description}
                  </p>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    <MacOSBadge variant={discount.is_active ? 'success' : 'error'}>
                      {discount.is_active ? 'Активна' : 'Неактивна'}
                    </MacOSBadge>
                    <MacOSBadge variant="info">
                      {discountTypes[discount.discount_type]}
                    </MacOSBadge>
                    <MacOSBadge variant="warning">
                      {discount.discount_type === 'percentage' ? `${discount.value}%` : `${discount.value} руб.`}
                    </MacOSBadge>
                  </div>
                </div>
                <div style={{ 
                  textAlign: 'right',
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-text-secondary)'
                }}>
                  <div>Использований: {discount.usage_count}/{discount.usage_limit || '∞'}</div>
                  <div>Приоритет: {discount.priority}</div>
                </div>
              </div>
            </MacOSCard>
          ))
        )}
      </div>
    </div>
  );

  // Рендер списка льгот
  const renderBenefitsList = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center' 
      }}>
        <h3 style={{ 
          margin: 0,
          color: 'var(--mac-text-primary)',
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-semibold)'
        }}>
          Льготы
        </h3>
        <MacOSButton 
          onClick={() => setShowCreateForm(true)}
          style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '8px' 
          }}
        >
          <Plus size={16} />
          Создать льготу
        </MacOSButton>
      </div>
      
      {showCreateForm && (
        <MacOSCard style={{ padding: 0 }}>
          <h4 style={{ 
            margin: '0 0 16px 0',
            color: 'var(--mac-text-primary)',
            fontSize: 'var(--mac-font-size-md)',
            fontWeight: 'var(--mac-font-weight-semibold)'
          }}>
            Создание новой льготы
          </h4>
          {renderBenefitForm()}
        </MacOSCard>
      )}

      <div style={{ display: 'grid', gap: '16px' }}>
        {benefits.length === 0 ? (
          <MacOSEmptyState
            type="benefit"
            title="Льготы не найдены"
            description="В системе пока нет созданных льгот"
            action={
              <MacOSButton onClick={() => setShowCreateForm(true)}>
                <Plus size={16} style={{ marginRight: '8px' }} />
                Создать первую льготу
              </MacOSButton>
            }
          />
        ) : (
          benefits.map((benefit) => (
            <MacOSCard key={benefit.id} style={{ padding: 0 }}>
              <div style={{ 
                display: 'flex', 
                justifyContent: 'space-between', 
                alignItems: 'flex-start' 
              }}>
                <div>
                  <h4 style={{ 
                    margin: '0 0 8px 0',
                    color: 'var(--mac-text-primary)',
                    fontSize: 'var(--mac-font-size-md)',
                    fontWeight: 'var(--mac-font-weight-semibold)'
                  }}>
                    {benefit.name}
                  </h4>
                  <p style={{ 
                    margin: '0 0 12px 0',
                    color: 'var(--mac-text-secondary)',
                    fontSize: 'var(--mac-font-size-sm)'
                  }}>
                    {benefit.description}
                  </p>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    <MacOSBadge variant={benefit.is_active ? 'success' : 'error'}>
                      {benefit.is_active ? 'Активна' : 'Неактивна'}
                    </MacOSBadge>
                    <MacOSBadge variant="info">
                      {benefitTypes[benefit.benefit_type]}
                    </MacOSBadge>
                    <MacOSBadge variant="warning">
                      {benefit.discount_percentage}%
                    </MacOSBadge>
                    {benefit.requires_document && (
                      <MacOSBadge variant="secondary">
                        Требует документы
                      </MacOSBadge>
                    )}
                  </div>
                </div>
                <div style={{ 
                  textAlign: 'right',
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-text-secondary)'
                }}>
                  {benefit.monthly_limit && <div>Месячный лимит: {benefit.monthly_limit} руб.</div>}
                  {benefit.yearly_limit && <div>Годовой лимит: {benefit.yearly_limit} руб.</div>}
                  {benefit.max_discount_amount && <div>Макс. скидка: {benefit.max_discount_amount} руб.</div>}
                </div>
              </div>
            </MacOSCard>
          ))
        )}
      </div>
    </div>
  );

  // Рендер списка программ лояльности
  const renderLoyaltyList = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center' 
      }}>
        <h3 style={{ 
          margin: 0,
          color: 'var(--mac-text-primary)',
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-semibold)'
        }}>
          Программы лояльности
        </h3>
        <MacOSButton 
          onClick={() => setShowCreateForm(true)}
          style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '8px' 
          }}
        >
          <Plus size={16} />
          Создать программу
        </MacOSButton>
      </div>
      
      {showCreateForm && (
        <MacOSCard style={{ padding: 0 }}>
          <h4 style={{ 
            margin: '0 0 16px 0',
            color: 'var(--mac-text-primary)',
            fontSize: 'var(--mac-font-size-md)',
            fontWeight: 'var(--mac-font-weight-semibold)'
          }}>
            Создание новой программы лояльности
          </h4>
          {renderLoyaltyForm()}
        </MacOSCard>
      )}

      <div style={{ display: 'grid', gap: '16px' }}>
        {loyaltyPrograms.length === 0 ? (
          <MacOSEmptyState
            type="loyalty"
            title="Программы лояльности не найдены"
            description="В системе пока нет созданных программ лояльности"
            action={
              <MacOSButton onClick={() => setShowCreateForm(true)}>
                <Plus size={16} style={{ marginRight: '8px' }} />
                Создать первую программу
              </MacOSButton>
            }
          />
        ) : (
          loyaltyPrograms.map((program) => (
            <MacOSCard key={program.id} style={{ padding: 0 }}>
              <div style={{ 
                display: 'flex', 
                justifyContent: 'space-between', 
                alignItems: 'flex-start' 
              }}>
                <div>
                  <h4 style={{ 
                    margin: '0 0 8px 0',
                    color: 'var(--mac-text-primary)',
                    fontSize: 'var(--mac-font-size-md)',
                    fontWeight: 'var(--mac-font-weight-semibold)'
                  }}>
                    {program.name}
                  </h4>
                  <p style={{ 
                    margin: '0 0 12px 0',
                    color: 'var(--mac-text-secondary)',
                    fontSize: 'var(--mac-font-size-sm)'
                  }}>
                    {program.description}
                  </p>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    <MacOSBadge variant={program.is_active ? 'success' : 'error'}>
                      {program.is_active ? 'Активна' : 'Неактивна'}
                    </MacOSBadge>
                    <MacOSBadge variant="info">
                      {program.points_per_ruble} балл/руб.
                    </MacOSBadge>
                    <MacOSBadge variant="warning">
                      {program.ruble_per_point} руб./балл
                    </MacOSBadge>
                  </div>
                </div>
                <div style={{ 
                  textAlign: 'right',
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-text-secondary)'
                }}>
                  <div>Мин. для списания: {program.min_points_to_redeem} баллов</div>
                </div>
              </div>
            </MacOSCard>
          ))
        )}
      </div>
    </div>
  );

  // Рендер аналитики
  const renderAnalytics = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <h3 style={{ 
        margin: 0,
        color: 'var(--mac-text-primary)',
        fontSize: 'var(--mac-font-size-lg)',
        fontWeight: 'var(--mac-font-weight-semibold)'
      }}>
        Аналитика
      </h3>
      
      {analytics ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '16px' }}>
          {/* Аналитика скидок */}
          {analytics.discounts && (
            <MacOSCard style={{ padding: 0 }}>
              <h4 style={{ 
                margin: '0 0 12px 0',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-md)',
                fontWeight: 'var(--mac-font-weight-semibold)',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}>
                <TrendingUp size={16} />
                Скидки
              </h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div style={{ 
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-text-secondary)'
                }}>
                  Всего применений: <span style={{ color: 'var(--mac-text-primary)', fontWeight: 'var(--mac-font-weight-medium)' }}>{analytics.discounts.total_applications}</span>
                </div>
                <div style={{ 
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-text-secondary)'
                }}>
                  Общая сумма скидок: <span style={{ color: 'var(--mac-text-primary)', fontWeight: 'var(--mac-font-weight-medium)' }}>{analytics.discounts.total_discount_amount?.toFixed(2)} руб.</span>
                </div>
                <div style={{ 
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-text-secondary)'
                }}>
                  Средний процент скидки: <span style={{ color: 'var(--mac-text-primary)', fontWeight: 'var(--mac-font-weight-medium)' }}>{analytics.discounts.average_discount_percentage?.toFixed(1)}%</span>
                </div>
              </div>
            </MacOSCard>
          )}

          {/* Аналитика льгот */}
          {analytics.benefits && (
            <MacOSCard style={{ padding: 0 }}>
              <h4 style={{ 
                margin: '0 0 12px 0',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-md)',
                fontWeight: 'var(--mac-font-weight-semibold)',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}>
                <Users size={16} />
                Льготы
              </h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div style={{ 
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-text-secondary)'
                }}>
                  Всего применений: <span style={{ color: 'var(--mac-text-primary)', fontWeight: 'var(--mac-font-weight-medium)' }}>{analytics.benefits.total_applications}</span>
                </div>
                <div style={{ 
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-text-secondary)'
                }}>
                  Общая сумма льгот: <span style={{ color: 'var(--mac-text-primary)', fontWeight: 'var(--mac-font-weight-medium)' }}>{analytics.benefits.total_benefit_amount?.toFixed(2)} руб.</span>
                </div>
                <div style={{ 
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-text-secondary)'
                }}>
                  Средний процент льготы: <span style={{ color: 'var(--mac-text-primary)', fontWeight: 'var(--mac-font-weight-medium)' }}>{analytics.benefits.average_benefit_percentage?.toFixed(1)}%</span>
                </div>
              </div>
            </MacOSCard>
          )}

          {/* Аналитика лояльности */}
          {analytics.loyalty && (
            <MacOSCard style={{ padding: 0 }}>
              <h4 style={{ 
                margin: '0 0 12px 0',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-md)',
                fontWeight: 'var(--mac-font-weight-semibold)',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}>
                <DollarSign size={16} />
                Лояльность
              </h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div style={{ 
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-text-secondary)'
                }}>
                  Всего участников: <span style={{ color: 'var(--mac-text-primary)', fontWeight: 'var(--mac-font-weight-medium)' }}>{analytics.loyalty.total_patients}</span>
                </div>
                <div style={{ 
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-text-secondary)'
                }}>
                  Активных участников: <span style={{ color: 'var(--mac-text-primary)', fontWeight: 'var(--mac-font-weight-medium)' }}>{analytics.loyalty.active_patients}</span>
                </div>
                <div style={{ 
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-text-secondary)'
                }}>
                  Всего баллов начислено: <span style={{ color: 'var(--mac-text-primary)', fontWeight: 'var(--mac-font-weight-medium)' }}>{analytics.loyalty.total_points_earned}</span>
                </div>
                <div style={{ 
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-text-secondary)'
                }}>
                  Процент погашения: <span style={{ color: 'var(--mac-text-primary)', fontWeight: 'var(--mac-font-weight-medium)' }}>{analytics.loyalty.redemption_rate?.toFixed(1)}%</span>
                </div>
              </div>
            </MacOSCard>
          )}
        </div>
      ) : (
        <MacOSEmptyState
          type="analytics"
          title="Аналитика недоступна"
          description="Данные аналитики будут доступны после создания скидок, льгот и программ лояльности"
        />
      )}
    </div>
  );

  const tabs = [
    { id: 'discounts', label: 'Скидки', count: discounts.length },
    { id: 'benefits', label: 'Льготы', count: benefits.length },
    { id: 'loyalty', label: 'Лояльность', count: loyaltyPrograms.length },
    { id: 'analytics', label: 'Аналитика' }
  ];

  return (
    <div style={{ padding: 0 }}>
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        gap: '16px',
        marginBottom: '24px'
      }}>
        <Percent size={24} color="var(--mac-accent)" />
        <div>
          <h2 style={{ 
            margin: 0, 
            color: 'var(--mac-text-primary)',
            fontSize: 'var(--mac-font-size-xl)',
            fontWeight: 'var(--mac-font-weight-bold)'
          }}>
            Система скидок и льгот
          </h2>
          <p style={{ 
            margin: '4px 0 0 0',
            color: 'var(--mac-text-secondary)',
            fontSize: 'var(--mac-font-size-sm)'
          }}>
            Управление скидками, льготами и программами лояльности
          </p>
        </div>
      </div>

      {/* Навигация по вкладкам */}
      <div style={{ 
        display: 'flex', 
        borderBottom: '1px solid var(--mac-border)',
        marginBottom: '24px'
      }}>
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => {
              setActiveTab(tab.id);
              setShowCreateForm(false);
            }}
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
            {tab.label}
            {tab.count !== undefined && (
              <MacOSBadge variant="secondary" style={{ marginLeft: '8px' }}>
                {tab.count}
              </MacOSBadge>
            )}
          </button>
        ))}
      </div>

      {/* Содержимое вкладок */}
      {loading ? (
        <MacOSLoadingSkeleton type="card" count={3} />
      ) : (
        <div>
          {activeTab === 'discounts' && renderDiscountsList()}
          {activeTab === 'benefits' && renderBenefitsList()}
          {activeTab === 'loyalty' && renderLoyaltyList()}
          {activeTab === 'analytics' && renderAnalytics()}
        </div>
      )}
    </div>
  );
};

export default DiscountBenefitsManager;

