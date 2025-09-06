import React, { useState, useEffect } from 'react';
import { 
  Package, 
  Heart, 
  Activity,
  Stethoscope,
  TestTube,
  Plus,
  Minus,
  Edit,
  DollarSign,
  Clock,
  CheckCircle,
  Circle,
  RefreshCw,
  AlertCircle
} from 'lucide-react';
import { Card, Button, Badge } from '../../design-system/components';

/**
 * Селектор услуг для панели врача
 * Использует справочник из админ панели согласно passport.md стр. 1254
 */
const DoctorServiceSelector = ({ 
  specialty = 'cardiology',
  selectedServices = [],
  onServicesChange,
  canEditPrices = true,
  className = ''
}) => {
  const [loading, setLoading] = useState(true);
  const [services, setServices] = useState({});
  const [error, setError] = useState('');

  // Иконки для категорий услуг
  const categoryIcons = {
    'consultation.cardiology': Heart,
    'consultation.dermatology': Stethoscope,
    'consultation.stomatology': TestTube,
    'diagnostics.ecg': Activity,
    'diagnostics.echo': Heart,
    'procedure.cosmetology': Stethoscope,
    'laboratory.blood': TestTube
  };

  // Названия категорий
  const categoryNames = {
    'consultation.cardiology': 'Консультация кардиолога',
    'consultation.dermatology': 'Консультация дерматолога', 
    'consultation.stomatology': 'Консультация стоматолога',
    'diagnostics.ecg': 'ЭКГ',
    'diagnostics.echo': 'ЭхоКГ',
    'procedure.cosmetology': 'Косметологические процедуры',
    'laboratory.blood': 'Анализы крови'
  };

  useEffect(() => {
    loadServices();
  }, [specialty]);

  const loadServices = async () => {
    try {
      setLoading(true);
      setError('');

      const response = await fetch(`/api/v1/doctor/${specialty}/services`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });

      if (response.ok) {
        const data = await response.json();
        setServices(data.services_by_category);
      } else {
        const error = await response.json();
        throw new Error(error.detail);
      }
    } catch (err) {
      console.error('Ошибка загрузки услуг врача:', err);
      setError('Ошибка загрузки услуг');
    } finally {
      setLoading(false);
    }
  };

  const handleServiceToggle = (service) => {
    const existingIndex = selectedServices.findIndex(s => s.id === service.id);
    
    if (existingIndex >= 0) {
      // Убираем услугу
      const newServices = selectedServices.filter((_, index) => index !== existingIndex);
      onServicesChange(newServices);
    } else {
      // Добавляем услугу
      const newService = {
        id: service.id,
        name: service.name,
        code: service.code,
        price: service.price,
        currency: service.currency,
        duration_minutes: service.duration_minutes,
        quantity: 1,
        total: service.price
      };
      
      onServicesChange([...selectedServices, newService]);
    }
  };

  const handleQuantityChange = (serviceId, quantity) => {
    const newServices = selectedServices.map(service => {
      if (service.id === serviceId) {
        return {
          ...service,
          quantity: Math.max(1, quantity),
          total: service.price * Math.max(1, quantity)
        };
      }
      return service;
    });
    
    onServicesChange(newServices);
  };

  const handlePriceChange = (serviceId, newPrice) => {
    if (!canEditPrices) return;
    
    const newServices = selectedServices.map(service => {
      if (service.id === serviceId) {
        return {
          ...service,
          price: newPrice,
          total: newPrice * service.quantity
        };
      }
      return service;
    });
    
    onServicesChange(newServices);
  };

  const isServiceSelected = (serviceId) => {
    return selectedServices.some(s => s.id === serviceId);
  };

  const getTotalCost = () => {
    return selectedServices.reduce((total, service) => total + (service.total || service.price * service.quantity), 0);
  };

  const getTotalDuration = () => {
    return selectedServices.reduce((total, service) => total + (service.duration_minutes * service.quantity), 0);
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
      {/* Итоговая информация */}
      {selectedServices.length > 0 && (
        <Card className="p-4 bg-green-50 border-green-200 dark:bg-green-900/20">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-center">
            <div>
              <div className="text-2xl font-bold text-green-600">{selectedServices.length}</div>
              <div className="text-sm text-gray-600">Услуг</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-blue-600">{getTotalDuration()}</div>
              <div className="text-sm text-gray-600">Минут</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-purple-600">
                {getTotalCost().toLocaleString()} UZS
              </div>
              <div className="text-sm text-gray-600">Стоимость</div>
            </div>
          </div>
        </Card>
      )}

      {/* Выбранные услуги */}
      {selectedServices.length > 0 && (
        <Card className="p-4">
          <h3 className="text-lg font-medium mb-3">Выбранные услуги:</h3>
          <div className="space-y-2">
            {selectedServices.map((service, index) => (
              <div key={service.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg dark:bg-gray-800">
                <div className="flex items-center">
                  <CheckCircle size={16} className="mr-3 text-green-600" />
                  <div>
                    <div className="font-medium">{service.name}</div>
                    <div className="text-sm text-gray-500">
                      {service.duration_minutes} мин
                    </div>
                  </div>
                </div>
                
                <div className="flex items-center space-x-3">
                  {/* Количество */}
                  <div className="flex items-center space-x-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleQuantityChange(service.id, service.quantity - 1)}
                      disabled={service.quantity <= 1}
                    >
                      <Minus size={14} />
                    </Button>
                    <span className="w-8 text-center">{service.quantity}</span>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleQuantityChange(service.id, service.quantity + 1)}
                    >
                      <Plus size={14} />
                    </Button>
                  </div>
                  
                  {/* Цена */}
                  {canEditPrices ? (
                    <input
                      type="number"
                      value={service.price}
                      onChange={(e) => handlePriceChange(service.id, parseFloat(e.target.value) || 0)}
                      className="w-24 px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                      min="0"
                    />
                  ) : (
                    <span className="font-medium">{service.price.toLocaleString()}</span>
                  )}
                  
                  <span className="text-sm text-gray-500">{service.currency}</span>
                  
                  {/* Убрать услугу */}
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleServiceToggle(service)}
                  >
                    <Minus size={14} />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Доступные услуги */}
      <div className="space-y-4">
        {Object.entries(services).map(([categoryCode, categoryData]) => {
          const CategoryIcon = categoryIcons[categoryCode] || Package;
          const categoryName = categoryNames[categoryCode] || categoryData.category.name_ru;
          
          return (
            <Card key={categoryCode} className="p-4">
              <h3 className="text-lg font-medium mb-3 flex items-center">
                <CategoryIcon size={20} className="mr-2 text-blue-600" />
                {categoryName}
              </h3>
              
              <div className="grid grid-cols-1 gap-2">
                {categoryData.services.map(service => {
                  const isSelected = isServiceSelected(service.id);
                  
                  return (
                    <div
                      key={service.id}
                      className={`flex items-center justify-between p-3 rounded-lg border cursor-pointer transition-all ${
                        isSelected
                          ? 'bg-blue-50 border-blue-300 dark:bg-blue-900/20 dark:border-blue-600'
                          : 'bg-gray-50 border-gray-200 hover:bg-gray-100 dark:bg-gray-800 dark:border-gray-700 dark:hover:bg-gray-700'
                      }`}
                      onClick={() => handleServiceToggle(service)}
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
                        </div>
                      </div>
                      
                      <div className="text-right">
                        <div className="font-bold text-gray-900 dark:text-white">
                          {service.price.toLocaleString()} {service.currency}
                        </div>
                        <div className="text-sm text-gray-500 flex items-center">
                          <Clock size={12} className="mr-1" />
                          {service.duration_minutes} мин
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

      {Object.keys(services).length === 0 && (
        <Card className="p-8 text-center">
          <Package size={48} className="mx-auto text-gray-400 mb-4" />
          <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
            Услуги не найдены
          </h3>
          <p className="text-gray-500">
            Добавьте услуги для специальности "{specialty}" в админ панели
          </p>
        </Card>
      )}
    </div>
  );
};

export default DoctorServiceSelector;
