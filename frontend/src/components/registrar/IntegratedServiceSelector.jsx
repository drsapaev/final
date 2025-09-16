import React, { useState, useEffect } from 'react';
import { 
  Heart, 
  Stethoscope, 
  Scissors, 
  TestTube,
  Activity,
  User,
  Package,
  CheckCircle,
  Circle,
  RefreshCw,
  AlertCircle
} from 'lucide-react';
import { Card, Badge } from '../../design-system/components';

/**
 * Интегрированный селектор услуг для регистратуры
 * Использует справочник из админ панели согласно detail.md стр. 112
 */
const IntegratedServiceSelector = ({ 
  selectedServices = [], 
  onServicesChange,
  specialty = null,
  className = ''
}) => {
  const [loading, setLoading] = useState(true);
  const [services, setServices] = useState({});
  const [categories, setCategories] = useState([]);
  const [error, setError] = useState('');
  const [retryCount, setRetryCount] = useState(0);

  // Демо-данные для услуг (fallback)
  const DEMO_SERVICES = {
    consultation: [
      { id: 1, name: 'Консультация кардиолога', price: 50000, specialty: 'cardiology', group: 'consultation' },
      { id: 2, name: 'Консультация дерматолога', price: 40000, specialty: 'dermatology', group: 'consultation' },
      { id: 3, name: 'Консультация стоматолога', price: 30000, specialty: 'stomatology', group: 'consultation' },
      { id: 4, name: 'Консультация терапевта', price: 25000, specialty: 'general', group: 'consultation' }
    ],
    procedure: [
      { id: 5, name: 'ЭКГ', price: 15000, specialty: 'cardiology', group: 'procedure' },
      { id: 6, name: 'Эхокардиография', price: 80000, specialty: 'cardiology', group: 'procedure' },
      { id: 7, name: 'УЗИ кожи', price: 20000, specialty: 'dermatology', group: 'procedure' },
      { id: 8, name: 'Чистка зубов', price: 35000, specialty: 'stomatology', group: 'procedure' }
    ],
    diagnostics: [
      { id: 9, name: 'Рентген грудной клетки', price: 25000, specialty: 'cardiology', group: 'diagnostics' },
      { id: 10, name: 'МРТ сердца', price: 150000, specialty: 'cardiology', group: 'diagnostics' },
      { id: 11, name: 'Дерматоскопия', price: 30000, specialty: 'dermatology', group: 'diagnostics' },
      { id: 12, name: 'Панорамный снимок', price: 40000, specialty: 'stomatology', group: 'diagnostics' }
    ],
    laboratory: [
      { id: 13, name: 'Общий анализ крови', price: 20000, specialty: 'laboratory', group: 'laboratory' },
      { id: 14, name: 'Биохимия крови', price: 35000, specialty: 'laboratory', group: 'laboratory' },
      { id: 15, name: 'Липидный профиль', price: 45000, specialty: 'laboratory', group: 'laboratory' },
      { id: 16, name: 'Коагулограмма', price: 30000, specialty: 'laboratory', group: 'laboratory' }
    ]
  };

  const DEMO_CATEGORIES = [
    { id: 1, name_ru: 'Кардиология', code: 'cardiology', specialty: 'cardiology' },
    { id: 2, name_ru: 'Дерматология', code: 'dermatology', specialty: 'dermatology' },
    { id: 3, name_ru: 'Стоматология', code: 'stomatology', specialty: 'stomatology' },
    { id: 4, name_ru: 'Лаборатория', code: 'laboratory', specialty: 'laboratory' }
  ];

  // Иконки по специальностям из документации
  const specialtyIcons = {
    cardiology: Heart,
    dermatology: Stethoscope,
    stomatology: Scissors,
    laboratory: TestTube,
    general: User
  };

  const specialtyColors = {
    cardiology: 'text-red-600',
    dermatology: 'text-orange-600', 
    stomatology: 'text-blue-600',
    laboratory: 'text-green-600',
    general: 'text-gray-600'
  };

  // Названия групп услуг из detail.md
  const groupNames = {
    consultation: 'Консультации',
    procedure: 'Процедуры',
    diagnostics: 'Диагностика',
    laboratory: 'Лабораторные'
  };

  useEffect(() => {
    loadServices();
  }, [specialty]);

  const loadServices = async () => {
    try {
      setLoading(true);
      setError('');

      // Проверяем наличие токена
      const token = localStorage.getItem('token');
      if (!token) {
        console.warn('Токен не найден, используем демо-данные');
        setServices(DEMO_SERVICES);
        setCategories(DEMO_CATEGORIES);
        setLoading(false);
        return;
      }

      const params = new URLSearchParams();
      if (specialty) params.set('specialty', specialty);
      
      const response = await fetch(`/api/v1/registrar/services?${params}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setServices(data.services_by_group || DEMO_SERVICES);
        setCategories(data.categories || DEMO_CATEGORIES);
        setRetryCount(0); // Сброс счетчика при успехе
      } else if (response.status === 401) {
        // Не авторизован - используем демо-данные
        console.warn('Не авторизован, используем демо-данные');
        setServices(DEMO_SERVICES);
        setCategories(DEMO_CATEGORIES);
      } else {
        throw new Error(`Ошибка сервера: ${response.status}`);
      }
    } catch (err) {
      console.error('Ошибка загрузки услуг:', err);
      
      // Используем демо-данные при ошибке
      setServices(DEMO_SERVICES);
      setCategories(DEMO_CATEGORIES);
      
      // Показываем ошибку только если это не первая попытка
      if (retryCount > 0) {
        setError(`Ошибка загрузки справочника услуг: ${err.message}`);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleRetry = () => {
    setRetryCount(prev => prev + 1);
    loadServices();
  };

  const handleServiceToggle = (serviceId, serviceData) => {
    const isSelected = selectedServices.some(s => s.id === serviceId);
    
    if (isSelected) {
      // Убираем услугу
      const newServices = selectedServices.filter(s => s.id !== serviceId);
      onServicesChange(newServices);
    } else {
      // Добавляем услугу
      const newServices = [...selectedServices, {
        id: serviceId,
        name: serviceData.name,
        price: serviceData.price,
        specialty: serviceData.specialty,
        group: serviceData.group
      }];
      onServicesChange(newServices);
    }
  };

  const getTotalPrice = () => {
    return selectedServices.reduce((sum, service) => sum + (service.price || 0), 0);
  };

  const getServicesByGroup = () => {
    const filteredServices = {};
    
    Object.keys(services).forEach(group => {
      const groupServices = services[group] || [];
      filteredServices[group] = specialty 
        ? groupServices.filter(service => service.specialty === specialty)
        : groupServices;
    });
    
    return filteredServices;
  };

  const filteredServices = getServicesByGroup();

  if (loading) {
    return (
      <div className={`service-selector ${className}`}>
        <div className="flex items-center justify-center p-8">
          <RefreshCw className="w-6 h-6 animate-spin text-blue-600 mr-2" />
          <span className="text-gray-600">Загрузка справочника услуг...</span>
        </div>
      </div>
    );
  }

  return (
    <div className={`service-selector ${className}`}>
      {/* Заголовок с информацией о данных */}
      <div className="mb-4 p-3 bg-blue-50 rounded-lg border border-blue-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center">
            <Package className="w-5 h-5 text-blue-600 mr-2" />
            <span className="font-medium text-blue-900">Справочник услуг</span>
          </div>
          <div className="flex items-center space-x-2">
            {error && (
              <div className="flex items-center text-red-600 text-sm">
                <AlertCircle className="w-4 h-4 mr-1" />
                <span>Демо-данные</span>
              </div>
            )}
            <button
              onClick={handleRetry}
              className="text-blue-600 hover:text-blue-800 text-sm flex items-center"
              title="Обновить данные"
            >
              <RefreshCw className="w-4 h-4 mr-1" />
              Обновить
            </button>
          </div>
        </div>
      </div>

      {/* Фильтр по специальности */}
      {!specialty && (
        <div className="mb-4">
          <div className="flex flex-wrap gap-2">
            {categories.map(category => {
              const Icon = specialtyIcons[category.specialty] || User;
              const colorClass = specialtyColors[category.specialty] || 'text-gray-600';
              
              return (
                <button
                  key={category.id}
                  className={`flex items-center px-3 py-2 rounded-lg border transition-colors ${
                    selectedServices.some(s => s.specialty === category.specialty)
                      ? 'bg-blue-100 border-blue-300 text-blue-700'
                      : 'bg-white border-gray-200 text-gray-700 hover:bg-gray-50'
                  }`}
                  onClick={() => {
                    // Фильтрация по специальности
                    const specialtyServices = Object.values(services)
                      .flat()
                      .filter(service => service.specialty === category.specialty);
                    
                    const newServices = selectedServices.filter(s => 
                      !specialtyServices.some(ss => ss.id === s.id)
                    );
                    
                    onServicesChange(newServices);
                  }}
                >
                  <Icon className={`w-4 h-4 mr-2 ${colorClass}`} />
                  <span className="text-sm">{category.name_ru}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Группы услуг */}
      <div className="space-y-4">
        {Object.keys(filteredServices).map(group => {
          const groupServices = filteredServices[group];
          if (groupServices.length === 0) return null;

          return (
            <Card key={group} className="p-4">
              <h3 className="text-lg font-semibold text-gray-900 mb-3">
                {groupNames[group] || group}
              </h3>
              
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {groupServices.map(service => {
                  const isSelected = selectedServices.some(s => s.id === service.id);
                  const Icon = specialtyIcons[service.specialty] || User;
                  const colorClass = specialtyColors[service.specialty] || 'text-gray-600';
                  
                  return (
                    <div
                      key={service.id}
                      className={`p-3 rounded-lg border cursor-pointer transition-all ${
                        isSelected
                          ? 'bg-blue-50 border-blue-300 ring-2 ring-blue-200'
                          : 'bg-white border-gray-200 hover:bg-gray-50 hover:border-gray-300'
                      }`}
                      onClick={() => handleServiceToggle(service.id, service)}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex items-start space-x-2 flex-1">
                          <div className="flex-shrink-0 mt-1">
                            {isSelected ? (
                              <CheckCircle className="w-5 h-5 text-blue-600" />
                            ) : (
                              <Circle className="w-5 h-5 text-gray-400" />
                            )}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center space-x-2 mb-1">
                              <Icon className={`w-4 h-4 ${colorClass}`} />
                              <span className="text-sm font-medium text-gray-900 truncate">
                                {service.name}
                              </span>
                            </div>
                            <div className="text-xs text-gray-500">
                              {service.specialty && (
                                <Badge variant="secondary" className="mr-1">
                                  {categories.find(c => c.specialty === service.specialty)?.name_ru || service.specialty}
                                </Badge>
                              )}
                            </div>
                          </div>
                        </div>
                        <div className="text-right flex-shrink-0 ml-2">
                          <div className="text-sm font-semibold text-gray-900">
                            {service.price?.toLocaleString('ru-RU')} сум
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>
          );
        })}
      </div>

      {/* Итого */}
      {selectedServices.length > 0 && (
        <Card className="mt-4 p-4 bg-green-50 border-green-200">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <CheckCircle className="w-5 h-5 text-green-600 mr-2" />
              <span className="font-medium text-green-900">
                Выбрано услуг: {selectedServices.length}
              </span>
            </div>
            <div className="text-lg font-bold text-green-900">
              {getTotalPrice().toLocaleString('ru-RU')} сум
            </div>
          </div>
        </Card>
      )}

      {/* Ошибка */}
      {error && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-center">
            <AlertCircle className="w-5 h-5 text-red-600 mr-2" />
            <span className="text-red-800 text-sm">{error}</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default IntegratedServiceSelector;