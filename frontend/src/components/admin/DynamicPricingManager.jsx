import React, { useState, useEffect } from 'react';
import { 
  Card, 
  Button, 
  Badge, 
  Input, 
  Select, 
  Label, 
  Textarea 
} from '../ui/native';
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
      const token = localStorage.getItem('access_token');
      const headers = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      };

      // Загружаем услуги
      const servicesResponse = await fetch(`${import.meta.env.VITE_API_URL}/api/v1/services`, {
        headers
      });
      if (servicesResponse.ok) {
        const servicesData = await servicesResponse.json();
        setServices(servicesData);
      }

      if (activeTab === 'rules') {
        // Загружаем правила ценообразования
        const rulesResponse = await fetch(`${import.meta.env.VITE_API_URL}/api/v1/dynamic-pricing/pricing-rules`, {
          headers
        });
        if (rulesResponse.ok) {
          const rulesData = await rulesResponse.json();
          setPricingRules(rulesData);
        }
      } else if (activeTab === 'packages') {
        // Загружаем пакеты услуг
        const packagesResponse = await fetch(`${import.meta.env.VITE_API_URL}/api/v1/dynamic-pricing/service-packages`, {
          headers
        });
        if (packagesResponse.ok) {
          const packagesData = await packagesResponse.json();
          setServicePackages(packagesData);
        }
      } else if (activeTab === 'analytics') {
        // Загружаем аналитику
        const analyticsResponse = await fetch(`${import.meta.env.VITE_API_URL}/api/v1/dynamic-pricing/pricing-analytics`, {
          headers
        });
        if (analyticsResponse.ok) {
          const analyticsData = await analyticsResponse.json();
          setAnalytics(analyticsData);
        }
      }
    } catch (error) {
      console.error('Ошибка загрузки данных:', error);
      toast.error('Ошибка загрузки данных');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateRule = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/v1/dynamic-pricing/pricing-rules`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(ruleForm)
      });

      if (response.ok) {
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
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Ошибка создания правила');
      }
    } catch (error) {
      console.error('Ошибка создания правила:', error);
      toast.error('Ошибка создания правила');
    }
  };

  const handleCreatePackage = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/v1/dynamic-pricing/service-packages`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(packageForm)
      });

      if (response.ok) {
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
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Ошибка создания пакета');
      }
    } catch (error) {
      console.error('Ошибка создания пакета:', error);
      toast.error('Ошибка создания пакета');
    }
  };

  const handleToggleRule = async (ruleId, isActive) => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/v1/dynamic-pricing/pricing-rules/${ruleId}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ is_active: !isActive })
      });

      if (response.ok) {
        toast.success(isActive ? 'Правило деактивировано' : 'Правило активировано');
        loadData();
      } else {
        toast.error('Ошибка изменения статуса правила');
      }
    } catch (error) {
      console.error('Ошибка изменения статуса правила:', error);
      toast.error('Ошибка изменения статуса правила');
    }
  };

  const handleDeleteRule = async (ruleId) => {
    if (!confirm('Вы уверены, что хотите удалить это правило?')) return;

    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/v1/dynamic-pricing/pricing-rules/${ruleId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        toast.success('Правило удалено');
        loadData();
      } else {
        toast.error('Ошибка удаления правила');
      }
    } catch (error) {
      console.error('Ошибка удаления правила:', error);
      toast.error('Ошибка удаления правила');
    }
  };

  const handleUpdateDynamicPrices = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/v1/dynamic-pricing/update-dynamic-prices`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        const result = await response.json();
        toast.success(`Обновлено цен: ${result.updated_count} из ${result.total_services}`);
      } else {
        toast.error('Ошибка обновления цен');
      }
    } catch (error) {
      console.error('Ошибка обновления цен:', error);
      toast.error('Ошибка обновления цен');
    }
  };

  const renderRulesTab = () => (
    <div className="space-y-6">
      {/* Заголовок и кнопки */}
      <div className="flex justify-between items-center">
        <div>
          <h3 className="text-lg font-semibold">Правила ценообразования</h3>
          <p className="text-gray-600">Управление автоматическими скидками и правилами</p>
        </div>
        <div className="flex gap-2">
          <Button onClick={handleUpdateDynamicPrices} variant="outline">
            <TrendingUp className="w-4 h-4 mr-2" />
            Обновить цены
          </Button>
          <Button onClick={() => setShowCreateRule(true)}>
            <Plus className="w-4 h-4 mr-2" />
            Создать правило
          </Button>
        </div>
      </div>

      {/* Список правил */}
      <div className="grid gap-4">
        {pricingRules.map(rule => (
          <Card key={rule.id} className="p-4">
            <div className="flex justify-between items-start">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <h4 className="font-medium">{rule.name}</h4>
                  <Badge variant={rule.is_active ? 'success' : 'secondary'}>
                    {rule.is_active ? 'Активно' : 'Неактивно'}
                  </Badge>
                  <Badge variant="outline">
                    {rule.rule_type === 'TIME_BASED' && 'По времени'}
                    {rule.rule_type === 'VOLUME_BASED' && 'По объему'}
                    {rule.rule_type === 'SEASONAL' && 'Сезонное'}
                    {rule.rule_type === 'LOYALTY' && 'Лояльность'}
                    {rule.rule_type === 'PACKAGE' && 'Пакетное'}
                    {rule.rule_type === 'DYNAMIC' && 'Динамическое'}
                  </Badge>
                </div>
                
                <p className="text-gray-600 text-sm mb-2">{rule.description}</p>
                
                <div className="flex items-center gap-4 text-sm text-gray-500">
                  <span className="flex items-center gap-1">
                    <Percent className="w-3 h-3" />
                    {rule.discount_type === 'PERCENTAGE' ? `${rule.discount_value}%` : `${rule.discount_value} ₽`}
                  </span>
                  <span className="flex items-center gap-1">
                    <Users className="w-3 h-3" />
                    Использований: {rule.current_uses || 0}
                    {rule.max_uses && ` / ${rule.max_uses}`}
                  </span>
                  <span className="flex items-center gap-1">
                    <BarChart3 className="w-3 h-3" />
                    Приоритет: {rule.priority}
                  </span>
                </div>

                {(rule.start_time || rule.end_time) && (
                  <div className="flex items-center gap-1 text-sm text-gray-500 mt-1">
                    <Clock className="w-3 h-3" />
                    {rule.start_time} - {rule.end_time}
                  </div>
                )}
              </div>
              
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleToggleRule(rule.id, rule.is_active)}
                >
                  {rule.is_active ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setEditingRule(rule)}
                >
                  <Edit className="w-4 h-4" />
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleDeleteRule(rule.id)}
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            </div>
          </Card>
        ))}
      </div>

      {/* Форма создания правила */}
      {showCreateRule && (
        <Card className="p-6">
          <div className="flex justify-between items-center mb-4">
            <h4 className="text-lg font-medium">Создать правило ценообразования</h4>
            <Button variant="outline" onClick={() => setShowCreateRule(false)}>
              <X className="w-4 h-4" />
            </Button>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Название</Label>
              <Input
                value={ruleForm.name}
                onChange={(e) => setRuleForm({...ruleForm, name: e.target.value})}
                placeholder="Название правила"
              />
            </div>

            <div>
              <Label>Тип правила</Label>
              <Select
                value={ruleForm.rule_type}
                onChange={(e) => setRuleForm({...ruleForm, rule_type: e.target.value})}
              >
                <option value="TIME_BASED">По времени</option>
                <option value="VOLUME_BASED">По объему</option>
                <option value="SEASONAL">Сезонное</option>
                <option value="LOYALTY">Лояльность</option>
                <option value="PACKAGE">Пакетное</option>
                <option value="DYNAMIC">Динамическое</option>
              </Select>
            </div>

            <div>
              <Label>Тип скидки</Label>
              <Select
                value={ruleForm.discount_type}
                onChange={(e) => setRuleForm({...ruleForm, discount_type: e.target.value})}
              >
                <option value="PERCENTAGE">Процентная</option>
                <option value="FIXED_AMOUNT">Фиксированная сумма</option>
                <option value="BUY_X_GET_Y">Купи X получи Y</option>
                <option value="TIERED">Ступенчатая</option>
              </Select>
            </div>

            <div>
              <Label>Размер скидки</Label>
              <Input
                type="number"
                value={ruleForm.discount_value}
                onChange={(e) => setRuleForm({...ruleForm, discount_value: parseFloat(e.target.value)})}
                placeholder="10"
              />
            </div>

            <div>
              <Label>Время начала</Label>
              <Input
                type="time"
                value={ruleForm.start_time}
                onChange={(e) => setRuleForm({...ruleForm, start_time: e.target.value + ':00'})}
              />
            </div>

            <div>
              <Label>Время окончания</Label>
              <Input
                type="time"
                value={ruleForm.end_time}
                onChange={(e) => setRuleForm({...ruleForm, end_time: e.target.value + ':00'})}
              />
            </div>

            <div>
              <Label>Минимальное количество</Label>
              <Input
                type="number"
                value={ruleForm.min_quantity}
                onChange={(e) => setRuleForm({...ruleForm, min_quantity: parseInt(e.target.value)})}
                placeholder="1"
              />
            </div>

            <div>
              <Label>Приоритет</Label>
              <Input
                type="number"
                value={ruleForm.priority}
                onChange={(e) => setRuleForm({...ruleForm, priority: parseInt(e.target.value)})}
                placeholder="0"
              />
            </div>

            <div className="col-span-2">
              <Label>Описание</Label>
              <Textarea
                value={ruleForm.description}
                onChange={(e) => setRuleForm({...ruleForm, description: e.target.value})}
                placeholder="Описание правила"
              />
            </div>

            <div className="col-span-2">
              <Label>Услуги</Label>
              <Select
                multiple
                value={ruleForm.service_ids}
                onChange={(e) => {
                  const values = Array.from(e.target.selectedOptions, option => parseInt(option.value));
                  setRuleForm({...ruleForm, service_ids: values});
                }}
              >
                {services.map(service => (
                  <option key={service.id} value={service.id}>
                    {service.name} - {service.price} ₽
                  </option>
                ))}
              </Select>
            </div>
          </div>

          <div className="flex justify-end gap-2 mt-4">
            <Button variant="outline" onClick={() => setShowCreateRule(false)}>
              Отмена
            </Button>
            <Button onClick={handleCreateRule}>
              <Save className="w-4 h-4 mr-2" />
              Создать
            </Button>
          </div>
        </Card>
      )}
    </div>
  );

  const renderPackagesTab = () => (
    <div className="space-y-6">
      {/* Заголовок и кнопки */}
      <div className="flex justify-between items-center">
        <div>
          <h3 className="text-lg font-semibold">Пакеты услуг</h3>
          <p className="text-gray-600">Управление комплексными предложениями</p>
        </div>
        <Button onClick={() => setShowCreatePackage(true)}>
          <Plus className="w-4 h-4 mr-2" />
          Создать пакет
        </Button>
      </div>

      {/* Список пакетов */}
      <div className="grid gap-4">
        {servicePackages.map(pkg => (
          <Card key={pkg.id} className="p-4">
            <div className="flex justify-between items-start">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <h4 className="font-medium">{pkg.name}</h4>
                  <Badge variant={pkg.is_active ? 'success' : 'secondary'}>
                    {pkg.is_active ? 'Активен' : 'Неактивен'}
                  </Badge>
                </div>
                
                <p className="text-gray-600 text-sm mb-2">{pkg.description}</p>
                
                <div className="flex items-center gap-4 text-sm">
                  <span className="flex items-center gap-1 text-green-600 font-medium">
                    <DollarSign className="w-3 h-3" />
                    {pkg.package_price} ₽
                  </span>
                  {pkg.original_price && (
                    <span className="text-gray-400 line-through">
                      {pkg.original_price} ₽
                    </span>
                  )}
                  {pkg.savings_percentage && (
                    <Badge variant="success">
                      Экономия {pkg.savings_percentage.toFixed(0)}%
                    </Badge>
                  )}
                  <span className="text-gray-500">
                    Покупок: {pkg.current_purchases || 0}
                    {pkg.max_purchases && ` / ${pkg.max_purchases}`}
                  </span>
                </div>

                {(pkg.valid_from || pkg.valid_to) && (
                  <div className="flex items-center gap-1 text-sm text-gray-500 mt-1">
                    <Calendar className="w-3 h-3" />
                    {pkg.valid_from && new Date(pkg.valid_from).toLocaleDateString()} - 
                    {pkg.valid_to && new Date(pkg.valid_to).toLocaleDateString()}
                  </div>
                )}
              </div>
              
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setEditingPackage(pkg)}
                >
                  <Edit className="w-4 h-4" />
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleDeletePackage(pkg.id)}
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            </div>
          </Card>
        ))}
      </div>

      {/* Форма создания пакета */}
      {showCreatePackage && (
        <Card className="p-6">
          <div className="flex justify-between items-center mb-4">
            <h4 className="text-lg font-medium">Создать пакет услуг</h4>
            <Button variant="outline" onClick={() => setShowCreatePackage(false)}>
              <X className="w-4 h-4" />
            </Button>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Название</Label>
              <Input
                value={packageForm.name}
                onChange={(e) => setPackageForm({...packageForm, name: e.target.value})}
                placeholder="Название пакета"
              />
            </div>

            <div>
              <Label>Цена пакета</Label>
              <Input
                type="number"
                value={packageForm.package_price}
                onChange={(e) => setPackageForm({...packageForm, package_price: parseFloat(e.target.value)})}
                placeholder="0"
              />
            </div>

            <div>
              <Label>Действует с</Label>
              <Input
                type="datetime-local"
                value={packageForm.valid_from}
                onChange={(e) => setPackageForm({...packageForm, valid_from: e.target.value})}
              />
            </div>

            <div>
              <Label>Действует до</Label>
              <Input
                type="datetime-local"
                value={packageForm.valid_to}
                onChange={(e) => setPackageForm({...packageForm, valid_to: e.target.value})}
              />
            </div>

            <div className="col-span-2">
              <Label>Описание</Label>
              <Textarea
                value={packageForm.description}
                onChange={(e) => setPackageForm({...packageForm, description: e.target.value})}
                placeholder="Описание пакета"
              />
            </div>

            <div className="col-span-2">
              <Label>Услуги в пакете</Label>
              <Select
                multiple
                value={packageForm.service_ids}
                onChange={(e) => {
                  const values = Array.from(e.target.selectedOptions, option => parseInt(option.value));
                  setPackageForm({...packageForm, service_ids: values});
                }}
              >
                {services.map(service => (
                  <option key={service.id} value={service.id}>
                    {service.name} - {service.price} ₽
                  </option>
                ))}
              </Select>
            </div>
          </div>

          <div className="flex justify-end gap-2 mt-4">
            <Button variant="outline" onClick={() => setShowCreatePackage(false)}>
              Отмена
            </Button>
            <Button onClick={handleCreatePackage}>
              <Save className="w-4 h-4 mr-2" />
              Создать
            </Button>
          </div>
        </Card>
      )}
    </div>
  );

  const renderAnalyticsTab = () => (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold">Аналитика ценообразования</h3>
        <p className="text-gray-600">Статистика применения правил и пакетов</p>
      </div>

      {analytics && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card className="p-4">
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="w-5 h-5 text-blue-500" />
              <h4 className="font-medium">Общая экономия</h4>
            </div>
            <div className="text-2xl font-bold text-green-600">
              {analytics.summary?.total_savings?.toLocaleString() || 0} ₽
            </div>
            <p className="text-sm text-gray-500">
              За период {analytics.period?.start_date && new Date(analytics.period.start_date).toLocaleDateString()} - 
              {analytics.period?.end_date && new Date(analytics.period.end_date).toLocaleDateString()}
            </p>
          </Card>

          <Card className="p-4">
            <div className="flex items-center gap-2 mb-2">
              <Settings className="w-5 h-5 text-purple-500" />
              <h4 className="font-medium">Активные правила</h4>
            </div>
            <div className="text-2xl font-bold">
              {analytics.summary?.active_rules_count || 0}
            </div>
            <p className="text-sm text-gray-500">Правил ценообразования</p>
          </Card>

          <Card className="p-4">
            <div className="flex items-center gap-2 mb-2">
              <Package className="w-5 h-5 text-orange-500" />
              <h4 className="font-medium">Активные пакеты</h4>
            </div>
            <div className="text-2xl font-bold">
              {analytics.summary?.active_packages_count || 0}
            </div>
            <p className="text-sm text-gray-500">Пакетов услуг</p>
          </Card>
        </div>
      )}

      {analytics?.rules_statistics && (
        <Card className="p-4">
          <h4 className="font-medium mb-4">Статистика правил</h4>
          <div className="space-y-2">
            {analytics.rules_statistics.map((rule, index) => (
              <div key={index} className="flex justify-between items-center p-2 bg-gray-50 rounded">
                <span className="font-medium">{rule.name}</span>
                <div className="flex gap-4 text-sm">
                  <span>Использований: {rule.uses}</span>
                  <span className="text-green-600">Экономия: {rule.total_savings?.toLocaleString() || 0} ₽</span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {analytics?.packages_statistics && (
        <Card className="p-4">
          <h4 className="font-medium mb-4">Статистика пакетов</h4>
          <div className="space-y-2">
            {analytics.packages_statistics.map((pkg, index) => (
              <div key={index} className="flex justify-between items-center p-2 bg-gray-50 rounded">
                <span className="font-medium">{pkg.name}</span>
                <div className="flex gap-4 text-sm">
                  <span>Покупок: {pkg.purchases}</span>
                  <span className="text-green-600">Экономия: {pkg.total_savings?.toLocaleString() || 0} ₽</span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );

  const tabs = [
    { id: 'rules', label: 'Правила', icon: Settings },
    { id: 'packages', label: 'Пакеты', icon: Package },
    { id: 'analytics', label: 'Аналитика', icon: BarChart3 }
  ];

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h2 className="text-2xl font-bold mb-2">Динамическое ценообразование</h2>
        <p className="text-gray-600">
          Управление правилами ценообразования, пакетами услуг и динамическими ценами
        </p>
      </div>

      {/* Табы */}
      <div className="flex space-x-1 mb-6 bg-gray-100 p-1 rounded-lg">
        {tabs.map(tab => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-md transition-colors ${
                activeTab === tab.id
                  ? 'bg-white shadow-sm text-blue-600'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Контент */}
      {loading ? (
        <div className="flex justify-center items-center h-64">
          <div className="text-gray-500">Загрузка...</div>
        </div>
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

