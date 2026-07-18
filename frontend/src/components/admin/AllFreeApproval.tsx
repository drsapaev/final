import type { CSSProperties } from 'react';

import { useState, useEffect, useCallback } from 'react';
import {
  CheckCircle,
  XCircle,
  Clock,
  DollarSign,
  User,
  Calendar,
  AlertCircle,

  Filter,
  RefreshCw,
  Phone,
  Stethoscope,
  Package,
  Bell } from
'lucide-react';
import {
  MacOSCard, Badge, Button, Select as SelectRaw,
} from '../ui/macos';
import { useTheme } from '../../contexts/ThemeContext';
import { toast } from 'react-toastify';
import { api } from '../../api/client';

import logger from '../../utils/logger';
import { useTranslation } from '../../i18n/useTranslation';
import React from "react";
const Select = SelectRaw as unknown as React.ComponentType<Record<string, unknown>>;

const ALL_FREE_ACTION_CAN_FIELD = {
  approve: 'can_approve',
  reject: 'can_reject'
};

const hasBackendAllFreeAction = (request, action) => {
  const normalizedAction = String(action || '').trim().toLowerCase();
  if (!normalizedAction) {
    return false;
  }

  if (Array.isArray(request?.available_actions)) {
    return request.available_actions.some(
      (availableAction) => String(availableAction || '').trim().toLowerCase() === normalizedAction
    );
  }

  const canField = ALL_FREE_ACTION_CAN_FIELD[normalizedAction];
  if (canField && Object.prototype.hasOwnProperty.call(request || {}, canField)) {
    return Boolean(request[canField]);
  }

  return false;
};
/**
 * Компонент для одобрения/отклонения заявок All Free в админке
 */
const AllFreeApproval = () => {
  useTheme();
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [allFreeRequests, setAllFreeRequests] = useState([]);
  const [allRequestsForStats, setAllRequestsForStats] = useState([]); // ✅ Для статистики - все заявки
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('pending');
  const [selectedRequest, setSelectedRequest] = useState(null);
  const [showApprovalModal, setShowApprovalModal] = useState(false);
  const [rejectionReason, setRejectionReason] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);

  // ✅ Отдельная функция для загрузки всех заявок для статистики
  const loadAllRequestsForStats = useCallback(async () => {
    try {
      // ✅ ИСПРАВЛЕНО: Используем лимит 100 (максимум на бэкенде)
      // Если заявок больше 100, можно сделать несколько запросов, но обычно этого достаточно
      const response = await api.get('/admin/all-free-requests?status_filter=all&limit=100');
      const data = response.data;
      setAllRequestsForStats(Array.isArray(data) ? data : []);
    } catch (error) {
      logger.error('[AllFreeApproval] Ошибка загрузки всех заявок для статистики:', error);
    }
  }, []);

  const loadAllFreeRequests = useCallback(async () => {
    setLoading(true);
    try {
      const response = await api.get(`/admin/all-free-requests?status_filter=${statusFilter}&limit=100`);
      const data = response.data;
      logger.log('[AllFreeApproval] Получено заявок:', data.length, data);
      setAllFreeRequests(Array.isArray(data) ? data : []);
    } catch (error) {
      logger.error('[AllFreeApproval] Ошибка при загрузке заявок All Free:', error);
      toast.error(error.response?.data?.detail || t('admin2.af_err_load'));
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    loadAllFreeRequests();
    // ✅ Загружаем все заявки для статистики
    loadAllRequestsForStats();
  }, [loadAllFreeRequests, loadAllRequestsForStats]);

  const handleApproval = async (visitId, action, rejectionReason = null) => {
    setIsProcessing(true);
    try {
      const response = await api.post('/admin/all-free-approve', {
        visit_id: visitId,
        action: action,
        rejection_reason: rejectionReason
      });

      toast.success(response.data?.message || t('admin2.af_toast_processed'));

      // ✅ ИСПРАВЛЕНО: Обновляем все заявки для статистики и список с текущим фильтром
      await loadAllRequestsForStats();
      loadAllFreeRequests();

      // Закрываем модальное окно
      setShowApprovalModal(false);
      setSelectedRequest(null);
      setRejectionReason('');
    } catch (error) {
      logger.error('Error processing approval:', error);
      toast.error(error.response?.data?.detail || t('admin2.af_err_process'));
    } finally {
      setIsProcessing(false);
    }
  };

  const formatPrice = (price) => {
    return Number(price).toLocaleString('ru-RU') + ' UZS';
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'pending':return 'var(--mac-warning)';
      case 'approved':return 'var(--mac-success)';
      case 'rejected':return 'var(--mac-error)';
      default:return 'var(--mac-text-tertiary)';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'pending':return <Clock size={16 as unknown as "small" | "default" | "large" | "xlarge"} />;
      case 'approved':return <CheckCircle size={16 as unknown as "small" | "default" | "large" | "xlarge"} />;
      case 'rejected':return <XCircle size={16 as unknown as "small" | "default" | "large" | "xlarge"} />;
      default:return <AlertCircle size={16 as unknown as "small" | "default" | "large" | "xlarge"} />;
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'pending':return t('admin2.af_status_pending');
      case 'approved':return t('admin2.af_status_approved');
      case 'rejected':return t('admin2.af_status_rejected');
      default:return status;
    }
  };

  const getSpecialtyText = (specialty) => {
    switch (specialty) {
      case 'dermatology':return t('admin2.af_specialty_dermatology');
      case 'cosmetology':return t('admin2.af_specialty_cosmetology');
      case 'stomatology':return t('admin2.af_specialty_stomatology');
      case 'dental':return t('admin2.af_specialty_dental');
      case 'cardiology':return t('admin2.af_specialty_cardiology');
      default:return specialty;
    }
  };

  // ✅ Используем allRequestsForStats для статистики, чтобы она была точной независимо от фильтра
  const pendingCount = allRequestsForStats.filter((req) => req.approval_status === 'pending').length;
  const approvedCount = allRequestsForStats.filter((req) => req.approval_status === 'approved').length;
  const rejectedCount = allRequestsForStats.filter((req) => req.approval_status === 'rejected').length;
  const totalAmount = allRequestsForStats.
  filter((req) => req.approval_status === 'approved').
  reduce((sum, req) => sum + Number(req.total_original_amount || 0), 0);

  return (
    <MacOSCard
      variant="default"
      padding="default">
      
      <div className="flex flex-col gap-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="admin-fs-24-fw-700-primary-d-flex-ai-center-gap-8-m-0">
              <Bell size={24 as unknown as "small" | "default" | "large" | "xlarge"} className="admin-warning" />
              {t('admin2.af_title')}
              {pendingCount > 0 &&
              <Badge variant="warning" className="admin-ml-8">
                  {t('admin2.af_new_badge', { count: pendingCount })}
                </Badge>
              }
            </h2>
            <p className="admin-secondary-mt-4-m-4px-0-0-0">
              {t('admin2.af_subtitle')}
            </p>
          </div>
          
          <div className="admin-flex-center-12">
            {/* Фильтр по статусу */}
            <div className="flex items-center justify-center gap-2">
              <Filter size={16 as unknown as "small" | "default" | "large" | "xlarge"} className="admin-tertiary" />
              <Select
                aria-label={t('admin2.af_filter_aria')}
                value={statusFilter}
                onChange={setStatusFilter}
                options={[
                  { value: 'pending', label: t('admin2.af_filter_pending') },
                  { value: 'approved', label: t('admin2.af_filter_approved') },
                  { value: 'rejected', label: t('admin2.af_filter_rejected') },
                  { value: 'all', label: t('admin2.af_filter_all') }
                ]}
                size="large"
                className="admin-minw-200" />
            </div>
            
            {/* Кнопка обновления */}
            <Button
              onClick={loadAllFreeRequests}
              disabled={loading}
              variant="outline">
              
              <RefreshCw size={16 as unknown as "small" | "default" | "large" | "xlarge"} className="admin-mr-8-anim-dyn" style={{ '--admin-anim0': loading ? 'spin 1s linear infinite' : 'none' } as CSSProperties} />
              {t('admin2.af_btn_refresh')}
            </Button>
          </div>
        </div>

        {/* Статистика */}
        <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-16">
          <MacOSCard
            variant="default"
            padding="default">
            
            <div className="admin-flex-center-12">
              <div className="admin-p-8-bgc-var-mac-warning-bg-radius-var-mac-radius-md">
                <Clock size={20 as unknown as "small" | "default" | "large" | "xlarge"} className="admin-warning" />
              </div>
              <div>
                <p className="admin-fs-14-secondary-m-0">
                  {t('admin2.af_stat_pending')}
                </p>
                <p className="admin-fs-20-fw-600-primary-m-4px-0-0-0-3">
                  {pendingCount}
                </p>
              </div>
            </div>
          </MacOSCard>
          
          <MacOSCard
            variant="default"
            padding="default">
            
            <div className="admin-flex-center-12">
              <div className="admin-p-8-bgc-var-mac-success-bg-radius-var-mac-radius-md">
                <CheckCircle size={20 as unknown as "small" | "default" | "large" | "xlarge"} className="admin-success" />
              </div>
              <div>
                <p className="admin-fs-14-secondary-m-0">
                  {t('admin2.af_stat_approved')}
                </p>
                <p className="admin-fs-20-fw-600-primary-m-4px-0-0-0-2">
                  {approvedCount}
                </p>
              </div>
            </div>
          </MacOSCard>
          
          <MacOSCard
            variant="default"
            padding="default">
            
            <div className="admin-flex-center-12">
              <div className="admin-p-8-bgc-var-mac-error-bg-radius-var-mac-radius-md">
                <XCircle size={20 as unknown as "small" | "default" | "large" | "xlarge"} className="admin-error" />
              </div>
              <div>
                <p className="admin-fs-14-secondary-m-0">
                  {t('admin2.af_stat_rejected')}
                </p>
                <p className="admin-fs-20-fw-600-primary-m-4px-0-0-0-1">
                  {rejectedCount}
                </p>
              </div>
            </div>
          </MacOSCard>
          
          <MacOSCard
            variant="default"
            padding="default">
            
            <div className="admin-flex-center-12">
              <div className="admin-p-8-bgc-var-mac-info-bg-radius-var-mac-radius-md">
                <DollarSign size={20 as unknown as "small" | "default" | "large" | "xlarge"} className="admin-info" />
              </div>
              <div>
                <p className="admin-fs-14-secondary-m-0">
                  {t('admin2.af_stat_total')}
                </p>
                <p className="admin-fs-20-fw-600-primary-m-4px-0-0-0">
                  {formatPrice(totalAmount)}
                </p>
              </div>
            </div>
          </MacOSCard>
        </div>

        {/* Список заявок */}
        {loading ?
        <div className="text-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-600 mx-auto" />
            <p className="text-gray-500 mt-2">{t('admin2.af_loading')}</p>
          </div> :
        allFreeRequests.length === 0 ?
        <div className="text-center py-8">
            <AlertCircle size={48} className="text-gray-400 mx-auto mb-4" />
            <p className="text-gray-500">{t('admin2.af_empty')}</p>
          </div> :

        <div className="grid gap-4">
            {allFreeRequests.map((request) =>
          <MacOSCard
            key={request.id}
            className="p-6 border border-gray-200 dark:border-gray-700 hover:shadow-md transition-shadow">
            
                {/* Header карточки */}
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <Badge className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(request.approval_status)}`}>
                      {getStatusIcon(request.approval_status)}
                      <span className="ml-2">{getStatusText(request.approval_status)}</span>
                    </Badge>
                    
                    <span className="text-sm text-gray-500 dark:text-gray-400">
                      {t('admin2.af_request_id', { id: request.id })}
                    </span>
                  </div>
                  
                  <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                    <Calendar size={14 as unknown as "small" | "default" | "large" | "xlarge"} />
                    {new Date(request.created_at).toLocaleDateString('ru-RU')}
                  </div>
                </div>

                {/* Основная информация */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">
                      {t('admin2.af_label_patient')}
                    </label>
                    <div className="flex items-center gap-2">
                      <User size={16 as unknown as "small" | "default" | "large" | "xlarge"} className="text-gray-400" />
                      <div>
                        <div className="text-sm">{request.patient_name || t('admin2.af_not_specified_patient')}</div>
                        {request.patient_phone &&
                    <div className="text-xs text-gray-500 flex items-center gap-1">
                            <Phone size={12 as unknown as "small" | "default" | "large" | "xlarge"} />
                            {request.patient_phone}
                          </div>
                    }
                      </div>
                    </div>
                  </div>
                  
                  {request.doctor_name &&
              <div>
                      <label className="block text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">
                        {t('admin2.af_label_doctor')}
                      </label>
                      <div className="flex items-center gap-2">
                        <Stethoscope size={16 as unknown as "small" | "default" | "large" | "xlarge"} className="text-gray-400" />
                        <div>
                          <div className="text-sm">{request.doctor_name}</div>
                          <div className="text-xs text-gray-500">
                            {getSpecialtyText(request.doctor_specialty)}
                          </div>
                        </div>
                      </div>
                    </div>
              }
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">
                      {t('admin2.af_label_datetime')}
                    </label>
                    <div className="text-sm">
                      {request.visit_date ? new Date(request.visit_date).toLocaleDateString('ru-RU') : t('admin2.af_not_specified_date')}
                      {request.visit_time && t('admin2.af_at_time', { time: request.visit_time })}
                    </div>
                  </div>
                </div>

                {/* Услуги */}
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-600 dark:text-gray-400 mb-2">
                    {t('admin2.af_label_services')}
                  </label>
                  <div className="flex items-center gap-2 mb-2">
                    <Package size={16 as unknown as "small" | "default" | "large" | "xlarge"} className="text-gray-400" />
                    <div className="flex flex-wrap gap-2">
                      {request.services.map((service, index) =>
                  <Badge key={index} variant="secondary" className="text-xs">
                          {service}
                        </Badge>
                  )}
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-2">
                    <DollarSign size={16 as unknown as "small" | "default" | "large" | "xlarge"} className="text-orange-600" />
                    <span className="text-lg font-semibold text-orange-600">
                      {formatPrice(request.total_original_amount)}
                    </span>
                    <span className="text-sm text-gray-500">{t('admin2.af_free')}</span>
                  </div>
                </div>

                {/* Примечания */}
                {request.notes &&
            <div className="mb-4">
                    <label className="block text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">
                      {t('admin2.af_label_notes')}
                    </label>
                    <div className="text-sm bg-gray-50 dark:bg-gray-700 p-3 rounded-md">
                      {request.notes}
                    </div>
                  </div>
            }

                {/* Действия */}
                {(hasBackendAllFreeAction(request, 'approve') || hasBackendAllFreeAction(request, 'reject')) &&
            <div className="flex gap-3 pt-4 border-t border-gray-200 dark:border-gray-700">
                    {hasBackendAllFreeAction(request, 'approve') &&
                    <Button
                onClick={() => handleApproval(request.id, 'approve')}
                disabled={isProcessing}
                className="flex items-center gap-2 bg-green-600 hover:bg-green-700">
                
                      <CheckCircle size={16 as unknown as "small" | "default" | "large" | "xlarge"} />
                      {t('admin2.af_btn_approve')}
                    </Button>
              }

                    {hasBackendAllFreeAction(request, 'reject') &&
                    <Button
                onClick={() => {
                  setSelectedRequest(request);
                  setShowApprovalModal(true);
                }}
                disabled={isProcessing}
                variant="outline"
                className="flex items-center gap-2 text-red-600 border-red-600 hover:bg-red-50">
                
                      <XCircle size={16 as unknown as "small" | "default" | "large" | "xlarge"} />
                      {t('admin2.af_btn_reject')}
                    </Button>
              }
                  </div>
            }
              </MacOSCard>
          )}
          </div>
        }

        {/* Модальное окно для отклонения */}
        {showApprovalModal && selectedRequest &&
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full">
              <div className="p-6">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                  {t('admin2.af_modal_title')}
                </h3>
                
                <div className="mb-4">
                  <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                    {t('admin2.af_request_id', { id: selectedRequest.id })}
                  </p>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    {t('admin2.af_modal_amount', { amount: formatPrice(selectedRequest.total_original_amount) })}
                  </p>
                </div>
                
                <div className="mb-4">
                  <label htmlFor="all-free-rejection-reason" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    {t('admin2.af_modal_reason_label')}
                  </label>
                  <textarea
                  id="all-free-rejection-reason"
                  aria-label={t('admin2.af_modal_reason_aria')}
                  value={rejectionReason}
                  onChange={(e) => setRejectionReason(e.target.value)}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-red-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                  placeholder={t('admin2.af_modal_reason_placeholder')} />
                
                </div>
                
                <div className="flex gap-3">
                  <Button
                  onClick={() => handleApproval(selectedRequest.id, 'reject', rejectionReason)}
                  disabled={isProcessing || !rejectionReason.trim()}
                  className="flex-1 flex items-center justify-center gap-2 bg-red-600 hover:bg-red-700">
                  
                    {isProcessing ?
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" /> :

                  <XCircle size={16 as unknown as "small" | "default" | "large" | "xlarge"} />
                  }
                    {t('admin2.af_btn_reject')}
                  </Button>
                  
                  <Button
                  onClick={() => {
                    setShowApprovalModal(false);
                    setSelectedRequest(null);
                    setRejectionReason('');
                  }}
                  disabled={isProcessing}
                  variant="outline"
                  className="flex-1">
                  
                    {t('admin2.af_modal_cancel')}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        }
      </div>
    </MacOSCard>);

};

export default AllFreeApproval;
