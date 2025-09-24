import React, { useState, useEffect } from 'react';
import { 
  CheckCircle, 
  XCircle, 
  Clock, 
  DollarSign, 
  User, 
  Calendar,
  AlertCircle,
  FileText,
  Filter,
  RefreshCw
} from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import { toast } from 'react-hot-toast';

const API_BASE = (import.meta?.env?.VITE_API_BASE || 'http://localhost:8000/api/v1');

/**
 * Компонент для одобрения/отклонения изменений цен врачами
 */
const PriceOverrideApproval = () => {
  const { theme, getColor } = useTheme();
  const [priceOverrides, setPriceOverrides] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('pending');
  const [selectedOverride, setSelectedOverride] = useState(null);
  const [showApprovalModal, setShowApprovalModal] = useState(false);
  const [rejectionReason, setRejectionReason] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);

  useEffect(() => {
    loadPriceOverrides();
  }, [statusFilter]);

  const loadPriceOverrides = async () => {
    setLoading(true);
    try {
      const response = await fetch(
        `${API_BASE}/registrar/price-overrides?status_filter=${statusFilter}&limit=100`
      );
      if (response.ok) {
        const data = await response.json();
        setPriceOverrides(data);
      } else {
        toast.error('Ошибка загрузки изменений цен');
      }
    } catch (error) {
      console.error('Error loading price overrides:', error);
      toast.error('Ошибка загрузки изменений цен');
    } finally {
      setLoading(false);
    }
  };

  const handleApproval = async (overrideId, action, rejectionReason = null) => {
    setIsProcessing(true);
    try {
      const response = await fetch(`${API_BASE}/registrar/price-override/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          override_id: overrideId,
          action: action,
          rejection_reason: rejectionReason
        })
      });

      if (response.ok) {
        const result = await response.json();
        toast.success(result.message);
        
        // Обновляем список
        loadPriceOverrides();
        
        // Закрываем модальное окно
        setShowApprovalModal(false);
        setSelectedOverride(null);
        setRejectionReason('');
      } else {
        const errorData = await response.json();
        toast.error(errorData.detail || 'Ошибка обработки запроса');
      }
    } catch (error) {
      console.error('Error processing approval:', error);
      toast.error('Ошибка обработки запроса');
    } finally {
      setIsProcessing(false);
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
      case 'rejected': return <XCircle size={16} />;
      default: return <AlertCircle size={16} />;
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'pending': return 'Ожидает одобрения';
      case 'approved': return 'Одобрено';
      case 'rejected': return 'Отклонено';
      default: return status;
    }
  };

  const getSpecialtyText = (specialty) => {
    switch (specialty) {
      case 'dermatology': return 'Дерматология';
      case 'cosmetology': return 'Косметология';
      case 'stomatology': return 'Стоматология';
      case 'dental': return 'Стоматология';
      case 'cardiology': return 'Кардиология';
      default: return specialty;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
            Изменения цен врачами
          </h2>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            Одобрение и отклонение изменений цен процедур
          </p>
        </div>
        
        <div className="flex items-center gap-3">
          {/* Фильтр по статусу */}
          <div className="flex items-center gap-2">
            <Filter size={16} className="text-gray-500" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
            >
              <option value="pending">Ожидают одобрения</option>
              <option value="approved">Одобренные</option>
              <option value="rejected">Отклоненные</option>
              <option value="all">Все</option>
            </select>
          </div>
          
          {/* Кнопка обновления */}
          <button
            onClick={loadPriceOverrides}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            Обновить
          </button>
        </div>
      </div>

      {/* Список изменений цен */}
      {loading ? (
        <div className="text-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto" />
          <p className="text-gray-500 mt-2">Загрузка...</p>
        </div>
      ) : priceOverrides.length === 0 ? (
        <div className="text-center py-8">
          <AlertCircle size={48} className="text-gray-400 mx-auto mb-4" />
          <p className="text-gray-500">Изменений цен не найдено</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {priceOverrides.map((override) => (
            <div
              key={override.id}
              className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6 shadow-sm"
            >
              {/* Header карточки */}
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(override.status)}`}>
                    {getStatusIcon(override.status)}
                    <span className="ml-2">{getStatusText(override.status)}</span>
                  </span>
                  
                  <span className="text-sm text-gray-500 dark:text-gray-400">
                    #{override.id}
                  </span>
                </div>
                
                <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                  <Calendar size={14} />
                  {new Date(override.created_at).toLocaleDateString('ru-RU')}
                </div>
              </div>

              {/* Основная информация */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
                <div>
                  <label className="block text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">
                    Пациент
                  </label>
                  <div className="flex items-center gap-2">
                    <User size={16} className="text-gray-400" />
                    <span className="text-sm">{override.patient_name || 'Не указан'}</span>
                  </div>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">
                    Врач
                  </label>
                  <div className="text-sm">
                    <div>{override.doctor_name}</div>
                    <div className="text-gray-500">{getSpecialtyText(override.doctor_specialty)}</div>
                  </div>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">
                    Услуга
                  </label>
                  <div className="text-sm">{override.service_name}</div>
                </div>
              </div>

              {/* Цены */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="block text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">
                    Базовая цена
                  </label>
                  <div className="flex items-center gap-2">
                    <DollarSign size={16} className="text-gray-400" />
                    <span className="text-lg font-medium">{formatPrice(override.original_price)}</span>
                  </div>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">
                    Новая цена
                  </label>
                  <div className="flex items-center gap-2">
                    <DollarSign size={16} className="text-blue-600" />
                    <span className="text-lg font-medium text-blue-600">{formatPrice(override.new_price)}</span>
                    <span className="text-sm text-gray-500">
                      ({override.new_price > override.original_price ? '+' : ''}
                      {formatPrice(override.new_price - override.original_price)})
                    </span>
                  </div>
                </div>
              </div>

              {/* Обоснование */}
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">
                  Обоснование
                </label>
                <div className="text-sm">{override.reason}</div>
                {override.details && (
                  <div className="text-sm text-gray-500 mt-1">{override.details}</div>
                )}
              </div>

              {/* Действия */}
              {override.status === 'pending' && (
                <div className="flex gap-3 pt-4 border-t border-gray-200 dark:border-gray-700">
                  <button
                    onClick={() => handleApproval(override.id, 'approve')}
                    disabled={isProcessing}
                    className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 disabled:opacity-50"
                  >
                    <CheckCircle size={16} />
                    Одобрить
                  </button>
                  
                  <button
                    onClick={() => {
                      setSelectedOverride(override);
                      setShowApprovalModal(true);
                    }}
                    disabled={isProcessing}
                    className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 disabled:opacity-50"
                  >
                    <XCircle size={16} />
                    Отклонить
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Модальное окно для отклонения */}
      {showApprovalModal && selectedOverride && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full">
            <div className="p-6">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                Отклонить изменение цены
              </h3>
              
              <div className="mb-4">
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                  Услуга: {selectedOverride.service_name}
                </p>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Цена: {formatPrice(selectedOverride.original_price)} → {formatPrice(selectedOverride.new_price)}
                </p>
              </div>
              
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Причина отклонения
                </label>
                <textarea
                  value={rejectionReason}
                  onChange={(e) => setRejectionReason(e.target.value)}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-red-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                  placeholder="Укажите причину отклонения..."
                />
              </div>
              
              <div className="flex gap-3">
                <button
                  onClick={() => handleApproval(selectedOverride.id, 'reject', rejectionReason)}
                  disabled={isProcessing || !rejectionReason.trim()}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 disabled:opacity-50"
                >
                  {isProcessing ? (
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
                  ) : (
                    <XCircle size={16} />
                  )}
                  Отклонить
                </button>
                
                <button
                  onClick={() => {
                    setShowApprovalModal(false);
                    setSelectedOverride(null);
                    setRejectionReason('');
                  }}
                  disabled={isProcessing}
                  className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-500 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700"
                >
                  Отмена
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PriceOverrideApproval;
