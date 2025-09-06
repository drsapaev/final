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

  // Иконки по специальностям из документации
  const specialtyIcons = {
    cardiology: Heart,
    dermatology: Stethoscope,
    stomatology: Scissors,
    laboratory: TestTube
  };

  const specialtyColors = {
    cardiology: 'text-red-600',
    dermatology: 'text-orange-600', 
    stomatology: 'text-blue-600',
    laboratory: 'text-green-600'
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

      const params = new URLSearchParams();
      if (specialty) params.set('specialty', specialty);
      
      const response = await fetch(`/api/v1/registrar/services?${params}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setServices(data.services_by_group);
        setCategories(data.categories);
      } else {
        throw new Error('Ошибка загрузки услуг');
      }
    } catch (err) {
      console.error('Ошибка загрузки услуг:', err);
      setError('Ошибка загрузки справочника услуг');
    } finally {
      setLoading(false);
    }
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
        currency: serviceData.currency,
        duration_minutes: serviceData.duration_minutes,
        category_id: serviceData.category_id,
        doctor_id: serviceData.doctor_id
      }];
      onServicesChange(newServices);
    }
  };

  const isServiceSelected = (serviceId) => {
    return selectedServices.some(s => s.id === serviceId);
  };

  const getTotalCost = () => {
    return selectedServices.reduce((total, service) => total + (service.price || 0), 0);
  };

  if (loading) {
    return (
      <Card className={`p-4 ${className}`}>
        <div className="flex items-center justify-center">
          <RefreshCw className="animate-spin mr-2" size={20} />
          <span>Загрузка услуг...</span>
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className={`p-4 ${className}`}>
        <div className="flex items-center text-red-600">
          <AlertCircle size={20} className="mr-2" />
          <span>{error}</span>
        </div>
      </Card>
    );
  }

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Итоговая стоимость */}
      {selectedServices.length > 0 && (
        <Card className="p-4 bg-blue-50 border-blue-200 dark:bg-blue-900/20">
          <div className="flex items-center justify-between">
            <span className="font-medium">Выбрано услуг: {selectedServices.length}</span>
            <span className="text-xl font-bold text-blue-600">
              {getTotalCost().toLocaleString()} UZS
            </span>
          </div>
        </Card>
      )}

      {/* Группы услуг */}
      {Object.entries(services).map(([groupKey, groupData]) => {
        // Пропускаем пустые группы
        const hasServices = Object.values(groupData).some(subgroup => subgroup.length > 0);
        if (!hasServices) return null;

        return (
          <Card key={groupKey} className="p-4">
            <h3 className="text-lg font-medium mb-4 flex items-center">
              <Package size={20} className="mr-2 text-gray-600" />
              {groupNames[groupKey]}
            </h3>
            
            {Object.entries(groupData).map(([subgroupKey, servicesList]) => {
              if (servicesList.length === 0) return null;
              
              const SpecialtyIcon = specialtyIcons[subgroupKey] || Package;
              const iconColor = specialtyColors[subgroupKey] || 'text-gray-600';

              return (
                <div key={subgroupKey} className="mb-4 last:mb-0">
                  <h4 className="text-md font-medium mb-3 flex items-center">
                    <SpecialtyIcon size={18} className={`mr-2 ${iconColor}`} />
                    {subgroupKey === 'cardiology' && 'Кардиология'}
                    {subgroupKey === 'dermatology' && 'Дерматология'}
                    {subgroupKey === 'stomatology' && 'Стоматология'}
                    {subgroupKey === 'cosmetology' && 'Косметология'}
                    {subgroupKey === 'ecg' && 'ЭКГ'}
                    {subgroupKey === 'echo' && 'ЭхоКГ'}
                    {subgroupKey === 'lab' && 'Анализы'}
                    {subgroupKey === 'blood' && 'Анализы крови'}
                    {subgroupKey === 'biochemistry' && 'Биохимия'}
                    {subgroupKey === 'hormones' && 'Гормоны'}
                  </h4>
                  
                  <div className="grid grid-cols-1 gap-2">
                    {servicesList.map(service => {
                      const isSelected = isServiceSelected(service.id);
                      
                      return (
                        <div
                          key={service.id}
                          className={`flex items-center justify-between p-3 rounded-lg border cursor-pointer transition-all ${
                            isSelected
                              ? 'bg-blue-50 border-blue-300 dark:bg-blue-900/20 dark:border-blue-600'
                              : 'bg-gray-50 border-gray-200 hover:bg-gray-100 dark:bg-gray-800 dark:border-gray-700 dark:hover:bg-gray-700'
                          }`}
                          onClick={() => handleServiceToggle(service.id, service)}
                        >
                          <div className="flex items-center">
                            {isSelected ? (
                              <CheckCircle size={20} className="mr-3 text-blue-600" />
                            ) : (
                              <Circle size={20} className="mr-3 text-gray-400" />
                            )}
                            <div>
                              <div className="font-medium text-gray-900 dark:text-white">
                                {service.name}
                              </div>
                              {service.code && (
                                <div className="text-sm text-gray-500">
                                  Код: {service.code}
                                </div>
                              )}
                              {service.duration_minutes && (
                                <div className="text-sm text-gray-500">
                                  Длительность: {service.duration_minutes} мин
                                </div>
                              )}
                            </div>
                          </div>
                          
                          <div className="text-right">
                            <div className="font-bold text-gray-900 dark:text-white">
                              {service.price ? `${service.price.toLocaleString()} ${service.currency}` : 'Бесплатно'}
                            </div>
                            {service.doctor_id && (
                              <div className="text-sm text-gray-500">
                                Врач #{service.doctor_id}
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </Card>
        );
      })}

      {Object.keys(services).length === 0 && (
        <Card className="p-8 text-center">
          <Package size={48} className="mx-auto text-gray-400 mb-4" />
          <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
            Услуги не найдены
          </h3>
          <p className="text-gray-500">
            Добавьте услуги в справочник через админ панель
          </p>
        </Card>
      )}
    </div>
  );
};

export default IntegratedServiceSelector;
