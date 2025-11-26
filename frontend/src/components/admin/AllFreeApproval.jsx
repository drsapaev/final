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
import { Card, Badge, Button } from '../ui/macos';
import { useTheme } from '../../contexts/ThemeContext';
import { toast } from 'react-toastify';
import { api } from '../../api/client';

/**
 * Компонент для одобрения/отклонения заявок All Free в админке
 */
const AllFreeApproval = () => {
  const { theme, getColor } = useTheme();
  const [allFreeRequests, setAllFreeRequests] = useState([]);
  const [allRequestsForStats, setAllRequestsForStats] = useState([]); // ✅ Для статистики - все заявки
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('pending');
  const [selectedRequest, setSelectedRequest] = useState(null);
  const [showApprovalModal, setShowApprovalModal] = useState(false);
  const [rejectionReason, setRejectionReason] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);

  useEffect(() => {
    loadAllFreeRequests();
    // ✅ Загружаем все заявки для статистики
    loadAllRequestsForStats();
  }, [statusFilter]);

  // ✅ Отдельная функция для загрузки всех заявок для статистики
  const loadAllRequestsForStats = async () => {
    try {
      // ✅ ИСПРАВЛЕНО: Используем лимит 100 (максимум на бэкенде)
      // Если заявок больше 100, можно сделать несколько запросов, но обычно этого достаточно
      const response = await api.get('/admin/all-free-requests?status_filter=all&limit=100');
      const data = response.data;
      setAllRequestsForStats(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error('[AllFreeApproval] Ошибка загрузки всех заявок для статистики:', error);
    }
  };

  const loadAllFreeRequests = async () => {
    setLoading(true);
    try {
      const response = await api.get(`/admin/all-free-requests?status_filter=${statusFilter}&limit=100`);
      const data = response.data;
      console.log('[AllFreeApproval] Получено заявок:', data.length, data);
      setAllFreeRequests(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error('[AllFreeApproval] Ошибка при загрузке заявок All Free:', error);
      toast.error(error.response?.data?.detail || 'Ошибка загрузки заявок All Free');
    } finally {
      setLoading(false);
    }
  };

  const handleApproval = async (visitId, action, rejectionReason = null) => {
    setIsProcessing(true);
    try {
      const response = await api.post('/admin/all-free-approve', {
        visit_id: visitId,
        action: action,
        rejection_reason: rejectionReason
      });

      toast.success(response.data?.message || 'Заявка обработана');
      
      // ✅ ИСПРАВЛЕНО: Обновляем все заявки для статистики и список с текущим фильтром
      await loadAllRequestsForStats();
      loadAllFreeRequests();
      
      // Закрываем модальное окно
      setShowApprovalModal(false);
      setSelectedRequest(null);
      setRejectionReason('');
    } catch (error) {
      console.error('Error processing approval:', error);
      toast.error(error.response?.data?.detail || 'Ошибка обработки запроса');
    } finally {
      setIsProcessing(false);
    }
  };

  const formatPrice = (price) => {
    return Number(price).toLocaleString('ru-RU') + ' UZS';
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'pending': return 'var(--mac-warning)';
      case 'approved': return 'var(--mac-success)';
      case 'rejected': return 'var(--mac-error)';
      default: return 'var(--mac-text-tertiary)';
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

  // ✅ Используем allRequestsForStats для статистики, чтобы она была точной независимо от фильтра
  const pendingCount = allRequestsForStats.filter(req => req.approval_status === 'pending').length;
  const approvedCount = allRequestsForStats.filter(req => req.approval_status === 'approved').length;
  const rejectedCount = allRequestsForStats.filter(req => req.approval_status === 'rejected').length;
  const totalAmount = allRequestsForStats
    .filter(req => req.approval_status === 'approved')
    .reduce((sum, req) => sum + Number(req.total_original_amount || 0), 0);

  return (
    <Card 
      variant="default"
      padding="default"
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h2 style={{ 
              fontSize: '24px', 
              fontWeight: '700', 
              color: 'var(--mac-text-primary)', 
              display: 'flex', 
              alignItems: 'center', 
              gap: '8px',
              margin: 0
            }}>
              <Bell size={24} style={{ color: 'var(--mac-warning)' }} />
              Заявки All Free
              {pendingCount > 0 && (
                <Badge variant="warning" style={{ marginLeft: '8px' }}>
                  {pendingCount} новых
                </Badge>
              )}
            </h2>
            <p style={{ 
              color: 'var(--mac-text-secondary)', 
              marginTop: '4px',
              margin: '4px 0 0 0'
            }}>
              Одобрение и отклонение заявок на бесплатные услуги
            </p>
          </div>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {/* Фильтр по статусу */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Filter size={16} style={{ color: 'var(--mac-text-tertiary)' }} />
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                style={{
                  padding: '8px 12px',
                  border: '1px solid var(--mac-border)',
                  borderRadius: 'var(--mac-radius-sm)',
                  background: 'var(--mac-bg-primary)',
                  color: 'var(--mac-text-primary)',
                  fontSize: '14px',
                  outline: 'none'
                }}
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
            >
              <RefreshCw size={16} style={{ 
                animation: loading ? 'spin 1s linear infinite' : 'none',
                marginRight: '8px'
              }} />
              Обновить
            </Button>
          </div>
        </div>

        {/* Статистика */}
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
          gap: '16px' 
        }}>
          <Card 
            variant="default"
            padding="default"
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{ 
                padding: '8px', 
                backgroundColor: 'var(--mac-warning-bg)', 
                borderRadius: 'var(--mac-radius-md)' 
              }}>
                <Clock size={20} style={{ color: 'var(--mac-warning)' }} />
              </div>
              <div>
                <p style={{ 
                  fontSize: '14px', 
                  color: 'var(--mac-text-secondary)',
                  margin: 0
                }}>
                  Ожидают
                </p>
                <p style={{ 
                  fontSize: '20px', 
                  fontWeight: '600',
                  color: 'var(--mac-text-primary)',
                  margin: '4px 0 0 0'
                }}>
                  {pendingCount}
                </p>
              </div>
            </div>
          </Card>
          
          <Card 
            variant="default"
            padding="default"
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{ 
                padding: '8px', 
                backgroundColor: 'var(--mac-success-bg)', 
                borderRadius: 'var(--mac-radius-md)' 
              }}>
                <CheckCircle size={20} style={{ color: 'var(--mac-success)' }} />
              </div>
              <div>
                <p style={{ 
                  fontSize: '14px', 
                  color: 'var(--mac-text-secondary)',
                  margin: 0
                }}>
                  Одобрено
                </p>
                <p style={{ 
                  fontSize: '20px', 
                  fontWeight: '600',
                  color: 'var(--mac-text-primary)',
                  margin: '4px 0 0 0'
                }}>
                  {approvedCount}
                </p>
              </div>
            </div>
          </Card>
          
          <Card 
            variant="default"
            padding="default"
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{ 
                padding: '8px', 
                backgroundColor: 'var(--mac-error-bg)', 
                borderRadius: 'var(--mac-radius-md)' 
              }}>
                <XCircle size={20} style={{ color: 'var(--mac-error)' }} />
              </div>
              <div>
                <p style={{ 
                  fontSize: '14px', 
                  color: 'var(--mac-text-secondary)',
                  margin: 0
                }}>
                  Отклонено
                </p>
                <p style={{ 
                  fontSize: '20px', 
                  fontWeight: '600',
                  color: 'var(--mac-text-primary)',
                  margin: '4px 0 0 0'
                }}>
                  {rejectedCount}
                </p>
              </div>
            </div>
          </Card>
          
          <Card 
            variant="default"
            padding="default"
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{ 
                padding: '8px', 
                backgroundColor: 'var(--mac-info-bg)', 
                borderRadius: 'var(--mac-radius-md)' 
              }}>
                <DollarSign size={20} style={{ color: 'var(--mac-info)' }} />
              </div>
              <div>
                <p style={{ 
                  fontSize: '14px', 
                  color: 'var(--mac-text-secondary)',
                  margin: 0
                }}>
                  Общая сумма
                </p>
                <p style={{ 
                  fontSize: '20px', 
                  fontWeight: '600',
                  color: 'var(--mac-text-primary)',
                  margin: '4px 0 0 0'
                }}>
                  {formatPrice(totalAmount)}
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

