import React, { useState, useEffect } from 'react';
import { 
  DollarSign, 
  Save, 
  AlertCircle, 
  CheckCircle, 
  Clock, 
  X,
  FileText,
  Stethoscope,
  CheckSquare
} from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import { toast } from 'react-toastify';

import logger from '../../utils/logger';
const API_BASE = (import.meta?.env?.VITE_API_BASE || 'http://localhost:8000/api/v1');

/**
 * Компонент для указания цены стоматологом после лечения
 */
const DentalPriceManager = ({ 
  visitId, 
  serviceId, 
  serviceName, 
  originalPrice, 
  onPriceSet,
  isOpen,
  onClose 
}) => {
  const { theme, getColor } = useTheme();
  const [finalPrice, setFinalPrice] = useState('');
  const [reason, setReason] = useState('');
  const [details, setDetails] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [priceOverrides, setPriceOverrides] = useState([]);
  const [loadingOverrides, setLoadingOverrides] = useState(false);

  // Предустановленные причины для стоматологических процедур
  const dentalReasons = [
    'Дополнительные манипуляции',
    'Сложность случая',
    'Использование премиум материалов',
    'Увеличенное время лечения',
    'Комплексное лечение',
    'Экстренное вмешательство',
    'Дополнительная анестезия',
    'Повторное лечение'
  ];

  useEffect(() => {
    if (isOpen && visitId) {
      loadPriceOverrides();
    }
  }, [isOpen, visitId]);

  const loadPriceOverrides = async () => {
    setLoadingOverrides(true);
    try {
      const response = await fetch(`${API_BASE}/dental/price-overrides?visit_id=${visitId}`);
      if (response.ok) {
        const data = await response.json();
        setPriceOverrides(data);
      }
    } catch (error) {
      logger.error('Error loading price overrides:', error);
    } finally {
      setLoadingOverrides(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!finalPrice || !reason) {
      toast.error('Заполните цену и причину');
      return;
    }

    const priceNum = Number(finalPrice.replace(/[^0-9.-]/g, ''));
    if (isNaN(priceNum) || priceNum <= 0) {
      toast.error('Введите корректную цену');
      return;
    }

    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE}/dental/price-override`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          visit_id: visitId,
          service_id: serviceId,
          new_price: priceNum,
          reason: reason,
          details: details || null,
          treatment_completed: true
        })
      });

      if (response.ok) {
        const result = await response.json();
        toast.success('Цена отправлена в регистратуру для подтверждения');
        
        // Обновляем список изменений
        loadPriceOverrides();
        
        // Очищаем форму
        setFinalPrice('');
        setReason('');
        setDetails('');
        
        // Уведомляем родительский компонент
        onPriceSet?.(result);
      } else {
        const errorData = await response.json();
        toast.error(errorData.detail || 'Ошибка указания цены');
      }
    } catch (error) {
      logger.error('Error setting price:', error);
      toast.error('Ошибка указания цены');
    } finally {
      setIsLoading(false);
    }
  };

  const formatPrice = (price) => {
    return Number(price).toLocaleString('ru-RU') + ' UZS';
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'pending': return 'text-yellow-600 bg-yellow-100';
      case 'approved': return 'text-green-600 bg-green-100';
      case 'rejected': return 'text-red-600 bg-red-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'pending': return <Clock size={16} />;
      case 'approved': return <CheckCircle size={16} />;
      case 'rejected': return <X size={16} />;
      default: return <AlertCircle size={16} />;
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'pending': return 'Ожидает подтверждения';
      case 'approved': return 'Подтверждено';
      case 'rejected': return 'Отклонено';
      default: return status;
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
          <div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center">
              <Stethoscope size={20} className="mr-2 text-blue-600" />
              Указание цены после лечения
            </h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
              {serviceName} • Плановая цена: {formatPrice(originalPrice)}
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
          >
            <X size={24} />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Форма указания цены */}
          <div className="bg-blue-50 dark:bg-blue-900/20 p-4 rounded-lg">
            <div className="flex items-center mb-2">
              <CheckSquare size={16} className="text-blue-600 mr-2" />
              <span className="text-sm font-medium text-blue-900 dark:text-blue-100">
                Лечение завершено
              </span>
            </div>
            <p className="text-sm text-blue-800 dark:text-blue-200">
              Укажите итоговую стоимость лечения с учетом проведенных процедур
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Итоговая стоимость (UZS)
              </label>
              <div className="relative">
                <DollarSign size={16} className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  value={finalPrice}
                  onChange={(e) => setFinalPrice(e.target.value)}
                  className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                  placeholder="Например: 150000"
                  inputMode="numeric"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Обоснование цены
              </label>
              <select
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white mb-2"
              >
                <option value="">Выберите причину</option>
                {dentalReasons.map((reasonText, index) => (
                  <option key={index} value={reasonText}>{reasonText}</option>
                ))}
                <option value="custom">Другая причина</option>
              </select>
              
              {reason === 'custom' && (
                <input
                  type="text"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                  placeholder="Введите причину"
                />
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Детали лечения (необязательно)
              </label>
              <textarea
                value={details}
                onChange={(e) => setDetails(e.target.value)}
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                placeholder="Подробности о проведенном лечении..."
              />
            </div>

            <button
              type="submit"
              disabled={isLoading || !finalPrice || !reason}
              className="w-full flex items-center justify-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2" />
              ) : (
                <Save size={16} className="mr-2" />
              )}
              {isLoading ? 'Отправка...' : 'Отправить в регистратуру'}
            </button>
          </form>

          {/* История указанных цен */}
          <div>
            <h4 className="text-md font-medium text-gray-900 dark:text-white mb-3 flex items-center">
              <FileText size={16} className="mr-2" />
              История указанных цен
            </h4>
            
            {loadingOverrides ? (
              <div className="text-center py-4">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600 mx-auto" />
              </div>
            ) : priceOverrides.length === 0 ? (
              <p className="text-gray-500 dark:text-gray-400 text-sm">
                Цены пока не указывались
              </p>
            ) : (
              <div className="space-y-3">
                {priceOverrides.map((override) => (
                  <div
                    key={override.id}
                    className="border border-gray-200 dark:border-gray-700 rounded-lg p-4"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center">
                        <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(override.status)}`}>
                          {getStatusIcon(override.status)}
                          <span className="ml-1">{getStatusText(override.status)}</span>
                        </span>
                      </div>
                      <span className="text-sm text-gray-500 dark:text-gray-400">
                        {new Date(override.created_at).toLocaleDateString('ru-RU')}
                      </span>
                    </div>
                    
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <span className="text-gray-600 dark:text-gray-400">Плановая:</span>
                        <span className="ml-2 font-medium">{formatPrice(override.original_price)}</span>
                      </div>
                      <div>
                        <span className="text-gray-600 dark:text-gray-400">Итоговая:</span>
                        <span className="ml-2 font-medium text-blue-600">{formatPrice(override.new_price)}</span>
                      </div>
                    </div>
                    
                    <div className="mt-2">
                      <span className="text-gray-600 dark:text-gray-400 text-sm">Обоснование:</span>
                      <span className="ml-2 text-sm">{override.reason}</span>
                    </div>
                    
                    {override.details && (
                      <div className="mt-1">
                        <span className="text-gray-600 dark:text-gray-400 text-sm">Детали:</span>
                        <span className="ml-2 text-sm">{override.details}</span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default DentalPriceManager;

