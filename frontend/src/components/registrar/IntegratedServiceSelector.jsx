import React, { useState, useEffect, useRef } from 'react';
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
import { Card, Badge } from '../ui/native';

import logger from '../../utils/logger';
/**
 * Интегрированный селектор услуг для регистратуры
 * Использует справочник из админ панели согласно detail.md стр. 112
 */
const IntegratedServiceSelector = ({ 
  selectedServices = [], 
  onServicesChange,
  className = '',
  simple = false,
  onNext
}) => {
  const [loading, setLoading] = useState(true);
  const [services, setServices] = useState({});
  const [categories, setCategories] = useState([]);
  const [error, setError] = useState('');
  const [retryCount, setRetryCount] = useState(0);

  // Базовый справочник услуг согласно утвержденному плану
  const DEMO_SERVICES = {
    cardiology: [
      { id: 1, code: 'consultation.cardiology', name: 'Консультация кардиолога', price: 50000, specialty: 'cardiology', group: 'cardiology' },
      { id: 2, code: 'echo.cardiography', name: 'ЭхоКГ', price: 80000, specialty: 'cardiology', group: 'cardiology' },
      { id: 3, code: 'ecg', name: 'ЭКГ', price: 25000, specialty: 'cardiology', group: 'cardiology' }
    ],
    dermatology: [
      { id: 4, code: 'consultation.dermatology', name: 'Консультация дерматолога', price: 40000, specialty: 'dermatology', group: 'dermatology' },
      { id: 5, code: 'derm.skin_diagnostics', name: 'Дерматоскопия', price: 30000, specialty: 'dermatology', group: 'dermatology' }
    ],
    cosmetology: [
      { id: 6, code: 'cosmetology.botox', name: 'Ботулотоксин', price: 150000, specialty: 'cosmetology', group: 'cosmetology' },
      { id: 7, code: 'cosmetology.mesotherapy', name: 'Мезотерапия', price: 120000, specialty: 'cosmetology', group: 'cosmetology' },
      { id: 8, code: 'cosmetology.peel', name: 'Пилинг', price: 40000, specialty: 'cosmetology', group: 'cosmetology' },
      { id: 9, code: 'cosmetology.laser', name: 'Лазерные процедуры', price: 80000, specialty: 'cosmetology', group: 'cosmetology' }
    ],
    dentistry: [
      { id: 10, code: 'consultation.dentistry', name: 'Консультация стоматолога', price: 35000, specialty: 'dentistry', group: 'dentistry' }
    ],
    laboratory: [
      { id: 11, code: 'lab.cbc', name: 'Общий анализ крови', price: 15000, specialty: 'laboratory', group: 'laboratory' },
      { id: 12, code: 'lab.biochem', name: 'Биохимический анализ крови', price: 25000, specialty: 'laboratory', group: 'laboratory' },
      { id: 13, code: 'lab.urine', name: 'Общий анализ мочи', price: 10000, specialty: 'laboratory', group: 'laboratory' },
      { id: 14, code: 'lab.coag', name: 'Коагулограмма', price: 20000, specialty: 'laboratory', group: 'laboratory' },
      { id: 15, code: 'lab.hormones', name: 'Гормоны', price: 30000, specialty: 'laboratory', group: 'laboratory' },
      { id: 16, code: 'lab.infection', name: 'Инфекции/серология', price: 25000, specialty: 'laboratory', group: 'laboratory' }
    ],
    other: [
      { id: 17, code: 'other.general', name: 'Прочие процедуры', price: 20000, specialty: 'other', group: 'other' }
    ]
  };

  const DEMO_CATEGORIES = [
    { id: 1, name_ru: 'Кардиология', code: 'cardiology', specialty: 'cardiology' },
    { id: 2, name_ru: 'Дерматология', code: 'dermatology', specialty: 'dermatology' },
    { id: 3, name_ru: 'Косметология', code: 'cosmetology', specialty: 'cosmetology' },
    { id: 4, name_ru: 'Стоматология', code: 'dentistry', specialty: 'dentistry' },
    { id: 5, name_ru: 'Лаборатория', code: 'laboratory', specialty: 'laboratory' },
    { id: 6, name_ru: 'Прочее', code: 'other', specialty: 'other' }
  ];

  // Иконки по специальностям из документации
  const specialtyIcons = {
    cardiology: Heart,
    dermatology: Stethoscope,
    cosmetology: Activity,
    dentistry: Scissors,
    laboratory: TestTube,
    other: User
  };

  const specialtyColors = {
    cardiology: 'text-red-600',
    dermatology: 'text-orange-600', 
    cosmetology: 'text-pink-600',
    dentistry: 'text-blue-600',
    laboratory: 'text-green-600',
    other: 'text-gray-600'
  };

  // Названия групп услуг из detail.md
  const groupNames = {
    cardiology: 'Кардиология',
    dermatology: 'Дерматология',
    cosmetology: 'Косметология',
    dentistry: 'Стоматология',
    laboratory: 'Лаборатория',
    other: 'Прочие услуги'
  };

  const hasLoadedRef = useRef(false);
  useEffect(() => {
    if (hasLoadedRef.current) return;
    hasLoadedRef.current = true;
    loadServices();
  }, []);

  const loadServices = async () => {
    try {
      // не включаем индикатор загрузки, чтобы избежать мерцаний
      setError('');

      // Сначала устанавливаем fallback данные
      logger.log('IntegratedServiceSelector: Setting fallback data');
      setServices(DEMO_SERVICES);
      setCategories(DEMO_CATEGORIES);
      setLoading(false);

      // Проверяем наличие токена
      const token = localStorage.getItem('auth_token');
      if (!token) {
        logger.warn('Токен не найден, используем демо-данные');
        return;
      }

      // Пытаемся загрузить с API, но не заменяем fallback данные если API пустой
      try {
      const params = new URLSearchParams();
      // Исключаем фильтрацию по specialty, чтобы не терять группы
      const API_BASE = (import.meta?.env?.VITE_API_BASE_URL) || 'http://localhost:8000';
        const response = await fetch(`${API_BASE}/api/v1/registrar/services?${params}`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        });

        if (response.ok) {
          const data = await response.json();
          logger.log('IntegratedServiceSelector: API response:', data);
          
          // Проверяем структуру ответа более детально
          if (data.services_by_group) {
            const groupKeys = Object.keys(data.services_by_group);
            logger.log('IntegratedServiceSelector: Groups in API response:', groupKeys);
            
            // Проверяем, есть ли реальные услуги в группах
            let hasServices = false;
            for (const group of groupKeys) {
              const groupServices = data.services_by_group[group];
              if (Array.isArray(groupServices) && groupServices.length > 0) {
                hasServices = true;
                logger.log(`IntegratedServiceSelector: Group ${group} has ${groupServices.length} services`);
              }
            }
            
            if (hasServices) {
              setServices(data.services_by_group);
              setCategories(data.categories || DEMO_CATEGORIES);
              logger.log('IntegratedServiceSelector: Loaded data from API with services');
            } else {
              logger.log('IntegratedServiceSelector: API groups are empty, keeping fallback');
              // Не перезаписываем fallback пустыми данными
            }
          } else {
            logger.log('IntegratedServiceSelector: No services_by_group in API response, keeping fallback');
          }
          setRetryCount(0);
        } else {
          logger.warn('IntegratedServiceSelector: API request failed, keeping fallback data');
        }
      } catch (apiError) {
        logger.warn('IntegratedServiceSelector: API error, keeping fallback data:', apiError);
      }
    } catch (err) {
      logger.error('IntegratedServiceSelector: Critical error:', err);
      // Fallback данные уже установлены выше, просто показываем ошибку
      if (retryCount > 0) {
        setError(`Ошибка загрузки справочника услуг: ${err.message}`);
      }
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
      onServicesChange?.(newServices);
    } else {
      // Добавляем услугу
      const newServices = [...selectedServices, {
        id: serviceId,
        code: serviceData.code,
        name: serviceData.name,
        price: serviceData.price,
        specialty: serviceData.specialty,
        group: serviceData.group
      }];
      onServicesChange?.(newServices);
    }
  };

  const getTotalPrice = () => {
    return selectedServices.reduce((sum, service) => sum + (service.price || 0), 0);
  };

  const getServicesByGroup = () => {
    // Если services пустой, используем DEMO_SERVICES
    const sourceServices = Object.keys(services).length > 0 ? services : DEMO_SERVICES;
    const filteredServices = {};
    
    Object.keys(sourceServices).forEach(group => {
      const groupServices = sourceServices[group] || [];
      // Убеждаемся, что groupServices - это массив
      const servicesArray = Array.isArray(groupServices) ? groupServices : [];
      // Не фильтруем услуги по специальности, показываем все доступные
      filteredServices[group] = servicesArray;
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

  const content = (
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

      {/* Фильтр по специальности отключен в мастере регистратуры */}
      {false && (
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

      {/* Быстрые тумблеры для кардиологии */}
      <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg">
        <h3 className="text-sm font-semibold text-red-900 mb-3 flex items-center">
          <Heart className="w-4 h-4 mr-2" />
          Быстрый выбор кардиологии
        </h3>
        <div className="flex flex-wrap gap-2">
          {/* ЭКГ тумблер */}
          {(() => {
            const ecgService = filteredServices.cardiology?.find(s => s.code === 'ecg');
            const isEcgSelected = selectedServices.some(s => s.code === 'ecg');
            
            if (!ecgService) return null;
            
            return (
              <button
                onClick={() => handleServiceToggle(ecgService.id, ecgService)}
                className={`flex items-center px-3 py-2 rounded-lg border transition-colors ${
                  isEcgSelected
                    ? 'bg-red-100 border-red-300 text-red-700'
                    : 'bg-white border-red-200 text-red-700 hover:bg-red-50'
                }`}
              >
                <Activity className="w-4 h-4 mr-2" />
                <span className="text-sm font-medium">ЭКГ</span>
                {isEcgSelected && <CheckCircle className="w-4 h-4 ml-2" />}
              </button>
            );
          })()}
          
          {/* ЭхоКГ тумблер */}
          {(() => {
            const echoService = filteredServices.cardiology?.find(s => s.code === 'echo.cardiography');
            const isEchoSelected = selectedServices.some(s => s.code === 'echo.cardiography');
            
            if (!echoService) return null;
            
            return (
              <button
                onClick={() => handleServiceToggle(echoService.id, echoService)}
                className={`flex items-center px-3 py-2 rounded-lg border transition-colors ${
                  isEchoSelected
                    ? 'bg-red-100 border-red-300 text-red-700'
                    : 'bg-white border-red-200 text-red-700 hover:bg-red-50'
                }`}
              >
                <Heart className="w-4 h-4 mr-2" />
                <span className="text-sm font-medium">ЭхоКГ</span>
                {isEchoSelected && <CheckCircle className="w-4 h-4 ml-2" />}
              </button>
            );
          })()}
        </div>
      </div>

      {/* Группы услуг */}
      <div className="space-y-4">
        {Object.keys(filteredServices).map(group => {
          const groupServices = filteredServices[group];
          if (!Array.isArray(groupServices) || groupServices.length === 0) {
            return null;
          }

          return (
            <Card key={group} className="p-4">
              <h3 className="text-lg font-semibold text-gray-900 mb-3">
                {groupNames[group] || group}
              </h3>
              
              <div className="space-y-3">
                <select
                  className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white"
                  onChange={(e) => {
                    const serviceId = parseInt(e.target.value);
                    if (serviceId) {
                      const service = groupServices.find(s => s.id === serviceId);
                      if (service) {
                        handleServiceToggle(service.id, service);
                        e.target.value = ''; // Сброс выбора
                      }
                    }
                  }}
                >
                  <option value="">Выберите услугу из {groupNames[group] || group}</option>
                  {groupServices.map(service => (
                    <option key={service.id} value={service.id}>
                      {service.name} - {service.price?.toLocaleString('ru-RU')} сум
                    </option>
                  ))}
                </select>
                
                {/* Выбранные услуги из этой группы */}
                {selectedServices.filter(s => s.group === group).map(service => (
                  <div key={service.id} className="flex items-center justify-between p-3 bg-blue-50 border border-blue-200 rounded-lg">
                    <div className="flex items-center space-x-2">
                      <CheckCircle className="w-5 h-5 text-blue-600" />
                      <span className="font-medium text-gray-900">{service.name}</span>
                      <span className="text-sm text-gray-600">({service.price?.toLocaleString('ru-RU')} сум)</span>
                    </div>
                    <button
                      onClick={() => handleServiceToggle(service.id, service)}
                      className="text-red-600 hover:text-red-800 p-1"
                      title="Удалить услугу"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            </Card>
          );
        })}
      </div>

      {/* Итого + Далее (в простом режиме) */}
      {(selectedServices.length > 0) && (
        <Card className="mt-4 p-4 bg-green-50 border-green-200">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <CheckCircle className="w-5 h-5 text-green-600 mr-2" />
              <span className="font-medium text-green-900">
                Выбрано услуг: {selectedServices.length}
              </span>
            </div>
            <div className="flex items-center gap-3">
              <div className="text-lg font-bold text-green-900">
                {getTotalPrice().toLocaleString('ru-RU')} сум
              </div>
              {simple && (
                <button className="px-4 py-2 rounded bg-blue-600 text-white" onClick={() => onNext?.()}>
                  Далее →
                </button>
              )}
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

  // Простой режим возвращает компактный контент без лишних вспомогательных блоков
  return content;
};

export default IntegratedServiceSelector;

