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
  RefreshCw,
  Phone,
  Stethoscope,
  Package,
  Bell
} from 'lucide-react';
import { Card, Badge, Button } from '../ui/native';
import { useTheme } from '../../contexts/ThemeContext';
import { toast } from 'react-toastify';

const API_BASE = (import.meta?.env?.VITE_API_BASE || 'http://localhost:8000/api/v1');

/**
 * Компонент для одобрения/отклонения заявок All Free в админке
 */
const AllFreeApproval = () => {
  const { theme, getColor } = useTheme();
  const [allFreeRequests, setAllFreeRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('pending');
  const [selectedRequest, setSelectedRequest] = useState(null);
  const [showApprovalModal, setShowApprovalModal] = useState(false);
  const [rejectionReason, setRejectionReason] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);

  useEffect(() => {
    loadAllFreeRequests();
  }, [statusFilter]);

  const loadAllFreeRequests = async () => {
    setLoading(true);
    try {
      const response = await fetch(
        `${API_BASE}/admin/all-free-requests?status_filter=${statusFilter}&limit=100`,
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
            'Content-Type': 'application/json'
          }
        }
      );
      if (response.ok) {
        const data = await response.json();
        setAllFreeRequests(data);
      } else {
        toast.error('Ошибка загрузки заявок All Free');
      }
    } catch (error) {
      console.error('Error loading all free requests:', error);
      toast.error('Ошибка загрузки заявок All Free');
    } finally {
      setLoading(false);
    }
  };

  const handleApproval = async (visitId, action, rejectionReason = null) => {
    setIsProcessing(true);
    try {
      const response = await fetch(`${API_BASE}/admin/all-free-approve`, {
        method: 'POST',
        headers: { 
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
          'Content-Type': 'application/json' 
        },
        body: JSON.stringify({
          visit_id: visitId,
          action: action,
          rejection_reason: rejectionReason
        })
      });

      if (response.ok) {
        const result = await response.json();
        toast.success(result.message);
        
        // Обновляем список
        loadAllFreeRequests();
        
        // Закрываем модальное окно
        setShowApprovalModal(false);
        setSelectedRequest(null);
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

  const pendingCount = allFreeRequests.filter(req => req.approval_status === 'pending').length;

  return (
    <Card className="p-6">
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
              <Bell size={24} className="text-orange-600" />
              Заявки All Free
              {pendingCount > 0 && (
                <Badge variant="warning" className="ml-2">
                  {pendingCount} новых
                </Badge>
              )}
            </h2>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Одобрение и отклонение заявок на бесплатные услуги
            </p>
          </div>
          
          <div className="flex items-center gap-3">
            {/* Фильтр по статусу */}
            <div className="flex items-center gap-2">
              <Filter size={16} className="text-gray-500" />
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-orange-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
              >
                <option value="pending">Ожидают одобрения</option>
                <option value="approved">Одобренные</option>
                <option value="rejected">Отклоненные</option>
                <option value="all">Все</option>
              </select>
            </div>
            
            {/* Кнопка обновления */}
            <Button
              onClick={loadAllFreeRequests}
              disabled={loading}
              variant="outline"
              className="flex items-center gap-2"
            >
              <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
              Обновить
            </Button>
          </div>
        </div>

        {/* Статистика */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-yellow-100 rounded-lg">
                <Clock size={20} className="text-yellow-600" />
              </div>
              <div>
                <p className="text-sm text-gray-600 dark:text-gray-400">Ожидают</p>
                <p className="text-xl font-semibold">
                  {allFreeRequests.filter(req => req.approval_status === 'pending').length}
                </p>
              </div>
            </div>
          </Card>
          
          <Card className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-green-100 rounded-lg">
                <CheckCircle size={20} className="text-green-600" />
              </div>
              <div>
                <p className="text-sm text-gray-600 dark:text-gray-400">Одобрено</p>
                <p className="text-xl font-semibold">
                  {allFreeRequests.filter(req => req.approval_status === 'approved').length}
                </p>
              </div>
            </div>
          </Card>
          
          <Card className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-red-100 rounded-lg">
                <XCircle size={20} className="text-red-600" />
              </div>
              <div>
                <p className="text-sm text-gray-600 dark:text-gray-400">Отклонено</p>
                <p className="text-xl font-semibold">
                  {allFreeRequests.filter(req => req.approval_status === 'rejected').length}
                </p>
              </div>
            </div>
          </Card>
          
          <Card className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-100 rounded-lg">
                <DollarSign size={20} className="text-blue-600" />
              </div>
              <div>
                <p className="text-sm text-gray-600 dark:text-gray-400">Общая сумма</p>
                <p className="text-xl font-semibold">
                  {formatPrice(
                    allFreeRequests
                      .filter(req => req.approval_status === 'approved')
                      .reduce((sum, req) => sum + Number(req.total_original_amount), 0)
                  )}
                </p>
              </div>
            </div>
          </Card>
        </div>

        {/* Список заявок */}
        {loading ? (
          <div className="text-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-600 mx-auto" />
            <p className="text-gray-500 mt-2">Загрузка...</p>
          </div>
        ) : allFreeRequests.length === 0 ? (
          <div className="text-center py-8">
            <AlertCircle size={48} className="text-gray-400 mx-auto mb-4" />
            <p className="text-gray-500">Заявок All Free не найдено</p>
          </div>
        ) : (
          <div className="grid gap-4">
            {allFreeRequests.map((request) => (
              <Card
                key={request.id}
                className="p-6 border border-gray-200 dark:border-gray-700 hover:shadow-md transition-shadow"
              >
                {/* Header карточки */}
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <Badge className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(request.approval_status)}`}>
                      {getStatusIcon(request.approval_status)}
                      <span className="ml-2">{getStatusText(request.approval_status)}</span>
                    </Badge>
                    
                    <span className="text-sm text-gray-500 dark:text-gray-400">
                      Заявка #{request.id}
                    </span>
                  </div>
                  
                  <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                    <Calendar size={14} />
                    {new Date(request.created_at).toLocaleDateString('ru-RU')}
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
                      <div>
                        <div className="text-sm">{request.patient_name || 'Не указан'}</div>
                        {request.patient_phone && (
                          <div className="text-xs text-gray-500 flex items-center gap-1">
                            <Phone size={12} />
                            {request.patient_phone}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                  
                  {request.doctor_name && (
                    <div>
                      <label className="block text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">
                        Врач
                      </label>
                      <div className="flex items-center gap-2">
                        <Stethoscope size={16} className="text-gray-400" />
                        <div>
                          <div className="text-sm">{request.doctor_name}</div>
                          <div className="text-xs text-gray-500">
                            {getSpecialtyText(request.doctor_specialty)}
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">
                      Дата и время
                    </label>
                    <div className="text-sm">
                      {request.visit_date ? new Date(request.visit_date).toLocaleDateString('ru-RU') : 'Не указана'}
                      {request.visit_time && ` в ${request.visit_time}`}
                    </div>
                  </div>
                </div>

                {/* Услуги */}
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-600 dark:text-gray-400 mb-2">
                    Услуги
                  </label>
                  <div className="flex items-center gap-2 mb-2">
                    <Package size={16} className="text-gray-400" />
                    <div className="flex flex-wrap gap-2">
                      {request.services.map((service, index) => (
                        <Badge key={index} variant="secondary" className="text-xs">
                          {service}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-2">
                    <DollarSign size={16} className="text-orange-600" />
                    <span className="text-lg font-semibold text-orange-600">
                      {formatPrice(request.total_original_amount)}
                    </span>
                    <span className="text-sm text-gray-500">→ БЕСПЛАТНО</span>
                  </div>
                </div>

                {/* Примечания */}
                {request.notes && (
                  <div className="mb-4">
                    <label className="block text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">
                      Примечания
                    </label>
                    <div className="text-sm bg-gray-50 dark:bg-gray-700 p-3 rounded-md">
                      {request.notes}
                    </div>
                  </div>
                )}

                {/* Действия */}
                {request.approval_status === 'pending' && (
                  <div className="flex gap-3 pt-4 border-t border-gray-200 dark:border-gray-700">
                    <Button
                      onClick={() => handleApproval(request.id, 'approve')}
                      disabled={isProcessing}
                      className="flex items-center gap-2 bg-green-600 hover:bg-green-700"
                    >
                      <CheckCircle size={16} />
                      Одобрить
                    </Button>
                    
                    <Button
                      onClick={() => {
                        setSelectedRequest(request);
                        setShowApprovalModal(true);
                      }}
                      disabled={isProcessing}
                      variant="outline"
                      className="flex items-center gap-2 text-red-600 border-red-600 hover:bg-red-50"
                    >
                      <XCircle size={16} />
                      Отклонить
                    </Button>
                  </div>
                )}
              </Card>
            ))}
          </div>
        )}

        {/* Модальное окно для отклонения */}
        {showApprovalModal && selectedRequest && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full">
              <div className="p-6">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                  Отклонить заявку All Free
                </h3>
                
                <div className="mb-4">
                  <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                    Заявка #{selectedRequest.id}
                  </p>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    Сумма: {formatPrice(selectedRequest.total_original_amount)}
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
                  <Button
                    onClick={() => handleApproval(selectedRequest.id, 'reject', rejectionReason)}
                    disabled={isProcessing || !rejectionReason.trim()}
                    className="flex-1 flex items-center justify-center gap-2 bg-red-600 hover:bg-red-700"
                  >
                    {isProcessing ? (
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
                    ) : (
                      <XCircle size={16} />
                    )}
                    Отклонить
                  </Button>
                  
                  <Button
                    onClick={() => {
                      setShowApprovalModal(false);
                      setSelectedRequest(null);
                      setRejectionReason('');
                    }}
                    disabled={isProcessing}
                    variant="outline"
                    className="flex-1"
                  >
                    Отмена
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
};

export default AllFreeApproval;

