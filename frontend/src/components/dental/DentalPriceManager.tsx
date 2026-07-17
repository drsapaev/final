// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { useTranslation } from '../../i18n/useTranslation';
import { useState, useEffect, useCallback } from 'react';
import {
  DollarSign,
  Save,
  AlertCircle,
  CheckCircle,
  Clock,
  X,
  FileText,
  Stethoscope,
  CheckSquare } from
'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import notify from '../../services/notify';

import { api } from '../../api/client';
import logger from '../../utils/logger';
import PropTypes from 'prop-types';
import { Input } from '../ui/macos';
import { formatRegistrarDate } from '../../utils/dateUtils';

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
  useTheme();
  const { t } = useTranslation();
  const [finalPrice, setFinalPrice] = useState('');
  const [reason, setReason] = useState('');
  const [details, setDetails] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [priceOverrides, setPriceOverrides] = useState([]);
  const [loadingOverrides, setLoadingOverrides] = useState(false);

  // Предустановленные причины для стоматологических процедур
  const dentalReasons = [
    t('dental.dental_dpm_reason_extra_manipulations'),
    t('dental.dental_dpm_reason_case_complexity'),
    t('dental.dental_dpm_reason_premium_materials'),
    t('dental.dental_dpm_reason_extended_time'),
    t('dental.dental_dpm_reason_complex_treatment'),
    t('dental.dental_dpm_reason_emergency'),
    t('dental.dental_dpm_reason_extra_anesthesia'),
    t('dental.dental_dpm_reason_retreatment')];

  const loadPriceOverrides = useCallback(async () => {
    setLoadingOverrides(true);
    try {
      const response = await api.get('/dental/price-overrides', {
        params: { visit_id: visitId }
      });
      setPriceOverrides(Array.isArray(response.data) ? response.data : []);
    } catch (error) {
      logger.error('Error loading price overrides:', error);
    } finally {
      setLoadingOverrides(false);
    }
  }, [visitId]);

  useEffect(() => {
    if (isOpen && visitId) {
      loadPriceOverrides();
    }
  }, [isOpen, visitId, loadPriceOverrides]);

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!finalPrice || !reason) {
      notify.error(t('dental2.price_fields_required'));
      return;
    }

    const priceNum = Number(finalPrice.replace(/[^0-9.-]/g, ''));
    if (isNaN(priceNum) || priceNum <= 0) {
      notify.error(t('dental2.invalid_price'));
      return;
    }

    setIsLoading(true);
    try {
      const response = await api.post('/dental/price-override', {
        visit_id: visitId,
        service_id: serviceId,
        new_price: priceNum,
        reason: reason,
        details: details || null,
        treatment_completed: true
      });

      if (response.status >= 200 && response.status < 300) {
        const result = response.data;
        notify.success(t('dental2.price_sent'));

        // Обновляем список изменений
        loadPriceOverrides();

        // Очищаем форму
        setFinalPrice('');
        setReason('');
        setDetails('');

        // Уведомляем родительский компонент
        onPriceSet?.(result);
      }
    } catch (error) {
      logger.error('Error setting price:', error);
      notify.error(error?.response?.data?.detail || t('dental.dental_dpm_error_set_price'));
    } finally {
      setIsLoading(false);
    }
  };

  const formatPrice = (price) => {
    return Number(price).toLocaleString('ru-RU') + ' UZS';
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'pending':return 'text-yellow-600 bg-yellow-100';
      case 'approved':return 'text-green-600 bg-green-100';
      case 'rejected':return 'text-red-600 bg-red-100';
      default:return 'text-gray-600 bg-gray-100';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'pending':return <Clock size={16} />;
      case 'approved':return <CheckCircle size={16} />;
      case 'rejected':return <X size={16} />;
      default:return <AlertCircle size={16} />;
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'pending':return t('dental.dental_dpm_status_pending');
      case 'approved':return t('dental.dental_dpm_status_approved');
      case 'rejected':return t('dental.dental_dpm_status_rejected');
      default:return status;
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
              {t('dental.dental_dpm_header_title')}
            </h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
              {t('dental.dental_dpm_header_subtitle', { serviceName, price: formatPrice(originalPrice) })}
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label={t('dental.dental_dpm_aria_close', { serviceName })}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
            
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
                {t('dental.dental_dpm_treatment_done')}
              </span>
            </div>
            <p className="text-sm text-blue-800 dark:text-blue-200">
              {t('dental.dental_dpm_treatment_done_hint')}
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="dental-final-price" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                {t('dental.dental_dpm_label_final_price')}
              </label>
              <div className="relative">
                <DollarSign size={16} className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
                <Input
                  id="dental-final-price"
                  type="text"
                  aria-label={t('dental.dental_dpm_aria_final_price')}
                  value={finalPrice}
                  onChange={(e) => setFinalPrice(e.target.value)}
                  className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                  placeholder={t('dental.dental_dpm_placeholder_price')}
                  inputMode="numeric" />
                
              </div>
            </div>

            <div>
              <label htmlFor="dental-price-reason" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                {t('dental.dental_dpm_label_reason')}
              </label>
              <select
                id="dental-price-reason"
                aria-label={t('dental.dental_dpm_aria_reason')}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white mb-2">
                
                <option value="">{t('dental.dental_dpm_select_reason')}</option>
                {dentalReasons.map((reasonText, index) =>
                <option key={index} value={reasonText}>{reasonText}</option>
                )}
                <option value="custom">{t('dental.dental_dpm_option_custom')}</option>
              </select>
              
              {reason === 'custom' &&
              <Input
                id="dental-custom-price-reason"
                type="text"
                aria-label={t('dental.dental_dpm_aria_custom_reason')}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                placeholder={t('dental.dental_dpm_placeholder_custom_reason')} />

              }
            </div>

            <div>
              <label htmlFor="dental-treatment-details" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                {t('dental.dental_dpm_label_details')}
              </label>
              <textarea
                id="dental-treatment-details"
                aria-label={t('dental.dental_dpm_aria_details')}
                value={details}
                onChange={(e) => setDetails(e.target.value)}
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                placeholder={t('dental.dental_dpm_placeholder_details')} />
              
            </div>

            <button
              type="submit"
              disabled={isLoading || !finalPrice || !reason}
              className="w-full flex items-center justify-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed">
              
              {isLoading ?
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2" /> :

              <Save size={16} className="mr-2" />
              }
              {isLoading ? t('dental.dental_dpm_btn_submit_loading') : t('dental.dental_dpm_btn_submit')}
            </button>
          </form>

          {/* История указанных цен */}
          <div>
            <h4 className="text-md font-medium text-gray-900 dark:text-white mb-3 flex items-center">
              <FileText size={16} className="mr-2" />
              {t('dental.dental_dpm_history_title')}
            </h4>
            
            {loadingOverrides ?
            <div className="text-center py-4">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600 mx-auto" />
              </div> :
            priceOverrides.length === 0 ?
            <p className="text-gray-500 dark:text-gray-400 text-sm">
                {t('dental.dental_dpm_history_empty')}
              </p> :

            <div className="space-y-3">
                {priceOverrides.map((override) =>
              <div
                key={override.id}
                className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center">
                        <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(override.status)}`}>
                          {getStatusIcon(override.status)}
                          <span className="ml-1">{getStatusText(override.status)}</span>
                        </span>
                      </div>
                      <span className="text-sm text-gray-500 dark:text-gray-400">
                        {formatRegistrarDate(override.created_at, 'ru-RU')}
                      </span>
                    </div>
                    
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <span className="text-gray-600 dark:text-gray-400">{t('dental.dental_dpm_history_planned')}</span>
                        <span className="ml-2 font-medium">{formatPrice(override.original_price)}</span>
                      </div>
                      <div>
                        <span className="text-gray-600 dark:text-gray-400">{t('dental.dental_dpm_history_final')}</span>
                        <span className="ml-2 font-medium text-blue-600">{formatPrice(override.new_price)}</span>
                      </div>
                    </div>
                    
                    <div className="mt-2">
                      <span className="text-gray-600 dark:text-gray-400 text-sm">{t('dental.dental_dpm_history_reason')}</span>
                      <span className="ml-2 text-sm">{override.reason}</span>
                    </div>
                    
                    {override.details &&
                <div className="mt-1">
                        <span className="text-gray-600 dark:text-gray-400 text-sm">{t('dental.dental_dpm_history_details')}</span>
                        <span className="ml-2 text-sm">{override.details}</span>
                      </div>
                }
                  </div>
              )}
              </div>
            }
          </div>
        </div>
      </div>
    </div>);

};


DentalPriceManager.propTypes = {
  ...(DentalPriceManager.propTypes || {}),
  isOpen: PropTypes.any,
  onClose: PropTypes.any,
  onPriceSet: PropTypes.any,
  originalPrice: PropTypes.any,
  serviceId: PropTypes.any,
  serviceName: PropTypes.any,
  visitId: PropTypes.any,
};

export default DentalPriceManager;
