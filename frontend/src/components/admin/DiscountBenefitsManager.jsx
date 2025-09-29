/**
 * Компонент для управления системой скидок и льгот
 */
import React, { useState, useEffect } from 'react';
import { Card, Button, Badge, Input, Select, Label, Textarea } from '../ui/native';
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
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-semibold">Скидки</h3>
        <Button 
          onClick={() => setShowCreateForm(true)} 
          className="bg-green-500 text-white"
        >
          Создать скидку
        </Button>
      </div>
      
      {showCreateForm && (
        <Card className="p-4">
          <h4 className="text-md font-semibold mb-4">Создание новой скидки</h4>
          {renderDiscountForm()}
        </Card>
      )}

      <div className="grid gap-4">
        {discounts.map((discount) => (
          <Card key={discount.id} className="p-4">
            <div className="flex justify-between items-start">
              <div>
                <h4 className="font-semibold">{discount.name}</h4>
                <p className="text-gray-600 text-sm">{discount.description}</p>
                <div className="flex gap-2 mt-2">
                  <Badge className={discount.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}>
                    {discount.is_active ? 'Активна' : 'Неактивна'}
                  </Badge>
                  <Badge className="bg-blue-100 text-blue-800">
                    {discountTypes[discount.discount_type]}
                  </Badge>
                  <Badge className="bg-purple-100 text-purple-800">
                    {discount.discount_type === 'percentage' ? `${discount.value}%` : `${discount.value} руб.`}
                  </Badge>
                </div>
              </div>
              <div className="text-right text-sm text-gray-500">
                <div>Использований: {discount.usage_count}/{discount.usage_limit || '∞'}</div>
                <div>Приоритет: {discount.priority}</div>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );

  // Рендер списка льгот
  const renderBenefitsList = () => (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-semibold">Льготы</h3>
        <Button 
          onClick={() => setShowCreateForm(true)} 
          className="bg-green-500 text-white"
        >
          Создать льготу
        </Button>
      </div>
      
      {showCreateForm && (
        <Card className="p-4">
          <h4 className="text-md font-semibold mb-4">Создание новой льготы</h4>
          {renderBenefitForm()}
        </Card>
      )}

      <div className="grid gap-4">
        {benefits.map((benefit) => (
          <Card key={benefit.id} className="p-4">
            <div className="flex justify-between items-start">
              <div>
                <h4 className="font-semibold">{benefit.name}</h4>
                <p className="text-gray-600 text-sm">{benefit.description}</p>
                <div className="flex gap-2 mt-2">
                  <Badge className={benefit.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}>
                    {benefit.is_active ? 'Активна' : 'Неактивна'}
                  </Badge>
                  <Badge className="bg-blue-100 text-blue-800">
                    {benefitTypes[benefit.benefit_type]}
                  </Badge>
                  <Badge className="bg-purple-100 text-purple-800">
                    {benefit.discount_percentage}%
                  </Badge>
                  {benefit.requires_document && (
                    <Badge className="bg-orange-100 text-orange-800">
                      Требует документы
                    </Badge>
                  )}
                </div>
              </div>
              <div className="text-right text-sm text-gray-500">
                {benefit.monthly_limit && <div>Месячный лимит: {benefit.monthly_limit} руб.</div>}
                {benefit.yearly_limit && <div>Годовой лимит: {benefit.yearly_limit} руб.</div>}
                {benefit.max_discount_amount && <div>Макс. скидка: {benefit.max_discount_amount} руб.</div>}
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );

  // Рендер списка программ лояльности
  const renderLoyaltyList = () => (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-semibold">Программы лояльности</h3>
        <Button 
          onClick={() => setShowCreateForm(true)} 
          className="bg-green-500 text-white"
        >
          Создать программу
        </Button>
      </div>
      
      {showCreateForm && (
        <Card className="p-4">
          <h4 className="text-md font-semibold mb-4">Создание новой программы лояльности</h4>
          {renderLoyaltyForm()}
        </Card>
      )}

      <div className="grid gap-4">
        {loyaltyPrograms.map((program) => (
          <Card key={program.id} className="p-4">
            <div className="flex justify-between items-start">
              <div>
                <h4 className="font-semibold">{program.name}</h4>
                <p className="text-gray-600 text-sm">{program.description}</p>
                <div className="flex gap-2 mt-2">
                  <Badge className={program.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}>
                    {program.is_active ? 'Активна' : 'Неактивна'}
                  </Badge>
                  <Badge className="bg-blue-100 text-blue-800">
                    {program.points_per_ruble} балл/руб.
                  </Badge>
                  <Badge className="bg-purple-100 text-purple-800">
                    {program.ruble_per_point} руб./балл
                  </Badge>
                </div>
              </div>
              <div className="text-right text-sm text-gray-500">
                <div>Мин. для списания: {program.min_points_to_redeem} баллов</div>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );

  // Рендер аналитики
  const renderAnalytics = () => (
    <div className="space-y-6">
      <h3 className="text-lg font-semibold">Аналитика</h3>
      
      {analytics && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Аналитика скидок */}
          {analytics.discounts && (
            <Card className="p-4">
              <h4 className="font-semibold mb-2">Скидки</h4>
              <div className="space-y-2 text-sm">
                <div>Всего применений: {analytics.discounts.total_applications}</div>
                <div>Общая сумма скидок: {analytics.discounts.total_discount_amount?.toFixed(2)} руб.</div>
                <div>Средний процент скидки: {analytics.discounts.average_discount_percentage?.toFixed(1)}%</div>
              </div>
            </Card>
          )}

          {/* Аналитика льгот */}
          {analytics.benefits && (
            <Card className="p-4">
              <h4 className="font-semibold mb-2">Льготы</h4>
              <div className="space-y-2 text-sm">
                <div>Всего применений: {analytics.benefits.total_applications}</div>
                <div>Общая сумма льгот: {analytics.benefits.total_benefit_amount?.toFixed(2)} руб.</div>
                <div>Средний процент льготы: {analytics.benefits.average_benefit_percentage?.toFixed(1)}%</div>
              </div>
            </Card>
          )}

          {/* Аналитика лояльности */}
          {analytics.loyalty && (
            <Card className="p-4">
              <h4 className="font-semibold mb-2">Лояльность</h4>
              <div className="space-y-2 text-sm">
                <div>Всего участников: {analytics.loyalty.total_patients}</div>
                <div>Активных участников: {analytics.loyalty.active_patients}</div>
                <div>Всего баллов начислено: {analytics.loyalty.total_points_earned}</div>
                <div>Процент погашения: {analytics.loyalty.redemption_rate?.toFixed(1)}%</div>
              </div>
            </Card>
          )}
        </div>
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
    <div className="p-6">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900">Система скидок и льгот</h2>
        <p className="text-gray-600">Управление скидками, льготами и программами лояльности</p>
      </div>

      {/* Навигация по вкладкам */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="-mb-px flex space-x-8">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => {
                setActiveTab(tab.id);
                setShowCreateForm(false);
              }}
              className={`py-2 px-1 border-b-2 font-medium text-sm ${
                activeTab === tab.id
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              {tab.label}
              {tab.count !== undefined && (
                <Badge className="ml-2 bg-gray-100 text-gray-800">
                  {tab.count}
                </Badge>
              )}
            </button>
          ))}
        </nav>
      </div>

      {/* Содержимое вкладок */}
      {loading ? (
        <div className="flex justify-center items-center h-64">
          <div className="text-gray-500">Загрузка...</div>
        </div>
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

