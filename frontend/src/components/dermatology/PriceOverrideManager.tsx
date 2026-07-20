import { useTranslation } from '../../i18n/useTranslation';
import { useState, useEffect, useCallback } from 'react';
import {
  DollarSign,
  Save,
  AlertCircle,
  CheckCircle,
  Clock,
  X,
  FileText } from

'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import notify from '../../services/notify';

import { api } from '../../api/client';
import logger from '../../utils/logger';
import PropTypes from 'prop-types';
import { Input } from '../ui/macos';
import { formatRegistrarDate } from '../../utils/dateUtils';

/**
 * Компонент для управления изменениями цен дерматологом
 */
const PriceOverrideManager = ({
  visitId,
  serviceId,
  serviceName,
  originalPrice,
  onPriceOverrideCreated,
  isOpen,
  onClose
}) => {
  useTheme();
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [newPrice, setNewPrice] = useState('');
  const [reason, setReason] = useState('');
  const [details, setDetails] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [priceOverrides, setPriceOverrides] = useState([]);
  const [loadingOverrides, setLoadingOverrides] = useState(false);

  // Предустановленные причины для быстрого выбора
  const commonReasons = [
  t('derma.derma_price_reason_increased_volume'),
  t('derma.derma_price_reason_additional_materials'),
  t('derma.derma_price_reason_complexity'),
  t('derma.derma_price_reason_individual'),
  t('derma.derma_price_reason_combined')];

  const loadPriceOverrides = useCallback(async () => {
    setLoadingOverrides(true);
    try {
      const response = await api.get('/derma/price-overrides', {
        params: { visit_id: visitId }
      }) as any;
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

    if (!newPrice || !reason) {
      notify.error(t('final.price_override_fields_required'));
      return;
    }

    const priceNum = Number(newPrice.replace(/[^0-9.-]/g, ''));
    if (isNaN(priceNum) || priceNum <= 0) {
      notify.error(t('final.price_override_invalid'));
      return;
    }

    setIsLoading(true);
    try {
      const response = await api.post('/derma/price-override', {
        visit_id: visitId,
        service_id: serviceId,
        new_price: priceNum,
        reason: reason,
        details: details || null
      }) as any;

      if (response.status >= 200 && response.status < 300) {
        const result = response.data;
        notify.success(t('final.price_override_sent'));

        // Обновляем список изменений
        loadPriceOverrides();

        // Очищаем форму
        setNewPrice('');
        setReason('');
        setDetails('');

        // Уведомляем родительский компонент
        onPriceOverrideCreated?.(result);
      }
    } catch (error) {
      logger.error('Error creating price override:', error);
      notify.error(error?.response?.data?.detail || t('derma.derma_price_create_failed'));
    } finally {
      setIsLoading(false);
    }
  };

  const formatPrice = (price) => {
    return Number(price).toLocaleString('ru-RU') + ' UZS';
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
      case 'pending':return t('derma.derma_price_status_pending');
      case 'approved':return t('derma.derma_price_status_approved');
      case 'rejected':return t('derma.derma_price_status_rejected');
      default:return status;
    }
  };

  if (!isOpen) return null;

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      backgroundColor: 'color-mix(in srgb, black, transparent 50%)',
      backdropFilter: 'blur(4px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 50,
      padding: 'var(--mac-spacing-4)'
    }}>
      <div style={{
        background: 'var(--mac-bg-primary)',
        borderRadius: 'var(--mac-radius-lg)',
        boxShadow: 'var(--mac-shadow-xl)',
        maxWidth: '672px',
        width: '100%',
        maxHeight: '90vh',
        overflowY: 'auto'
      }}>
        {/* Header */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: 'var(--mac-spacing-6)',
          borderBottom: '1px solid var(--mac-border)'
        }}>
          <div>
            <h3 style={{
              fontSize: 'var(--mac-font-size-lg)',
              fontWeight: 'var(--mac-font-weight-semibold)',
              color: 'var(--mac-text-primary)'
            }}>
              {t('derma.derma_price_dialog_title')}
            </h3>
            <p style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-secondary)',
              marginTop: 'var(--mac-spacing-1)'
            }}>
              {t('derma.derma_price_dialog_subtitle', { serviceName, base_price: formatPrice(originalPrice) })}
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label={t('derma.derma_price_close_aria')}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--mac-text-secondary)',
              cursor: 'pointer',
              transition: 'all var(--mac-duration-fast) var(--mac-ease)',
              padding: 'var(--mac-spacing-1)'
            }}
            onMouseEnter={(e: React.MouseEvent<HTMLElement>) => {
              e.currentTarget.style.color = 'var(--mac-text-primary)';
            }}
            onMouseLeave={(e: React.MouseEvent<HTMLElement>) => {
              e.currentTarget.style.color = 'var(--mac-text-secondary)';
            }}>
            
            <X size={24} />
          </button>
        </div>

        {/* Content */}
        <div style={{ padding: 'var(--mac-spacing-6)', display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-6)' }}>
          {/* Форма изменения цены */}
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-4)' }}>
            <div>
              <label style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-secondary)',
                marginBottom: 'var(--mac-spacing-2)'
              }}>
                {t('derma.derma_price_new_price_label')}
              </label>
              <div style={{ position: 'relative' }}>
                <DollarSign size={16} style={{
                  position: 'absolute',
                  left: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: 'var(--mac-text-tertiary)'
                }} />
                <Input
                  type="text"
                  aria-label={t('derma.derma_price_new_price_aria')}
                  value={newPrice}
                  onChange={(e) => setNewPrice(e.target.value)}
                  style={{
                    width: '100%',
                    paddingLeft: '40px',
                    paddingRight: '12px',
                    paddingTop: '8px',
                    paddingBottom: '8px',
                    border: '1px solid var(--mac-border)',
                    borderRadius: 'var(--mac-radius-md)',
                    backgroundColor: 'var(--mac-bg-primary)',
                    color: 'var(--mac-text-primary)',
                    fontSize: 'var(--mac-font-size-base)',
                    transition: 'all var(--mac-duration-fast) var(--mac-ease)'
                  }}
                  onFocus={(e) => {
                    (e.target as HTMLElement).style.borderColor = 'var(--mac-accent)';
                    (e.target as HTMLElement).style.boxShadow = 'var(--mac-focus-ring)';
                  }}
                  onBlur={(e) => {
                    (e.target as HTMLElement).style.borderColor = 'var(--mac-border)';
                    (e.target as HTMLElement).style.boxShadow = 'none';
                  }}
                  placeholder={t('derma.derma_price_ph_new_price')}
                  inputMode="numeric" />
                
              </div>
            </div>

            <div>
              <label style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-secondary)',
                marginBottom: 'var(--mac-spacing-2)'
              }}>
                {t('derma.derma_price_reason_label')}
              </label>
              <select
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                style={{
                  width: '100%',
                  paddingLeft: '12px',
                  paddingRight: '12px',
                  paddingTop: '8px',
                  paddingBottom: '8px',
                  border: '1px solid var(--mac-border)',
                  borderRadius: 'var(--mac-radius-md)',
                  backgroundColor: 'var(--mac-bg-primary)',
                  color: 'var(--mac-text-primary)',
                  fontSize: 'var(--mac-font-size-base)',
                  marginBottom: 'var(--mac-spacing-2)',
                  transition: 'all var(--mac-duration-fast) var(--mac-ease)'
                }}
                onFocus={(e) => {
                  (e.target as HTMLElement).style.borderColor = 'var(--mac-accent)';
                  (e.target as HTMLElement).style.boxShadow = 'var(--mac-focus-ring)';
                }}
                onBlur={(e) => {
                  (e.target as HTMLElement).style.borderColor = 'var(--mac-border)';
                  (e.target as HTMLElement).style.boxShadow = 'none';
                }}>
                
                <option value="">{t('derma.derma_price_select_reason')}</option>
                {commonReasons.map((reasonText, index) =>
                <option key={index} value={reasonText}>{reasonText}</option>
                )}
                <option value="custom">{t('derma.derma_price_other_reason')}</option>
              </select>
              
              {reason === 'custom' &&
              <Input
                type="text"
                aria-label={t('derma.derma_price_other_reason_aria')}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                style={{
                  width: '100%',
                  paddingLeft: '12px',
                  paddingRight: '12px',
                  paddingTop: '8px',
                  paddingBottom: '8px',
                  border: '1px solid var(--mac-border)',
                  borderRadius: 'var(--mac-radius-md)',
                  backgroundColor: 'var(--mac-bg-primary)',
                  color: 'var(--mac-text-primary)',
                  fontSize: 'var(--mac-font-size-base)',
                  transition: 'all var(--mac-duration-fast) var(--mac-ease)'
                }}
                onFocus={(e) => {
                  (e.target as HTMLElement).style.borderColor = 'var(--mac-accent)';
                  (e.target as HTMLElement).style.boxShadow = 'var(--mac-focus-ring)';
                }}
                onBlur={(e) => {
                  (e.target as HTMLElement).style.borderColor = 'var(--mac-border)';
                  (e.target as HTMLElement).style.boxShadow = 'none';
                }}
                placeholder={t('derma.derma_price_ph_custom_reason')} />

              }
            </div>

            <div>
              <label style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-secondary)',
                marginBottom: 'var(--mac-spacing-2)'
              }}>
                {t('derma.derma_price_details_label')}
              </label>
              <textarea
                aria-label={t('derma.derma_price_details_aria')}
                value={details}
                onChange={(e) => setDetails(e.target.value)}
                rows={3}
                style={{
                  width: '100%',
                  paddingLeft: '12px',
                  paddingRight: '12px',
                  paddingTop: '8px',
                  paddingBottom: '8px',
                  border: '1px solid var(--mac-border)',
                  borderRadius: 'var(--mac-radius-md)',
                  backgroundColor: 'var(--mac-bg-primary)',
                  color: 'var(--mac-text-primary)',
                  fontSize: 'var(--mac-font-size-base)',
                  resize: 'vertical',
                  transition: 'all var(--mac-duration-fast) var(--mac-ease)',
                  fontFamily: 'inherit'
                }}
                onFocus={(e) => {
                  (e.target as HTMLElement).style.borderColor = 'var(--mac-accent)';
                  (e.target as HTMLElement).style.boxShadow = 'var(--mac-focus-ring)';
                }}
                onBlur={(e) => {
                  (e.target as HTMLElement).style.borderColor = 'var(--mac-border)';
                  (e.target as HTMLElement).style.boxShadow = 'none';
                }}
                placeholder={t('derma.derma_price_ph_details')} />
              
            </div>

            <button
              type="submit"
              disabled={isLoading || !newPrice || !reason}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                paddingLeft: '16px',
                paddingRight: '16px',
                paddingTop: '8px',
                paddingBottom: '8px',
                background: 'var(--mac-accent-orange)',
                color: 'white',
                borderRadius: 'var(--mac-radius-md)',
                border: 'none',
                cursor: isLoading || !newPrice || !reason ? 'not-allowed' : 'pointer',
                opacity: isLoading || !newPrice || !reason ? '0.5' : '1',
                transition: 'all var(--mac-duration-normal) var(--mac-ease)',
                fontWeight: 'var(--mac-font-weight-medium)'
              }}
              onMouseEnter={(e: React.MouseEvent<HTMLElement>) => {
                if (!isLoading && newPrice && reason) {
                  (e.target as HTMLElement).style.background = 'var(--mac-accent-orange-hover)';
                  (e.target as HTMLElement).style.transform = 'translateY(-1px)';
                }
              }}
              onMouseLeave={(e: React.MouseEvent<HTMLElement>) => {
                if (!isLoading && newPrice && reason) {
                  (e.target as HTMLElement).style.background = 'var(--mac-accent-orange)';
                  (e.target as HTMLElement).style.transform = 'translateY(0)';
                }
              }}>
              
              {isLoading ?
              <div style={{
                animation: 'spin 1s linear infinite',
                borderRadius: '50%',
                height: '16px',
                width: '16px',
                borderBottom: '2px solid white',
                marginRight: 'var(--mac-spacing-2)'
              }} /> :

              <Save size={16} style={{ marginRight: 'var(--mac-spacing-2)' }} />
              }
              {isLoading ? t('derma.derma_price_submitting') : t('derma.derma_price_submit')}
            </button>
          </form>

          {/* История изменений цен */}
          <div>
            <h4 style={{
              fontSize: 'var(--mac-font-size-base)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              marginBottom: 'var(--mac-spacing-3)',
              display: 'flex',
              alignItems: 'center'
            }}>
              <FileText size={16} style={{ marginRight: 'var(--mac-spacing-2)' }} />
              {t('derma.derma_price_history_title')}
            </h4>
            
            {loadingOverrides ?
            <div style={{
              textAlign: 'center',
              paddingTop: '16px',
              paddingBottom: '16px'
            }}>
                <div style={{
                animation: 'spin 1s linear infinite',
                borderRadius: '50%',
                height: '24px',
                width: '24px',
                borderBottom: '2px solid var(--mac-accent-orange)',
                margin: '0 auto'
              }} />
              </div> :
            priceOverrides.length === 0 ?
            <p style={{
              color: 'var(--mac-text-tertiary)',
              fontSize: 'var(--mac-font-size-sm)'
            }}>
                {t('derma.derma_price_history_empty')}
              </p> :

            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-3)' }}>
                {priceOverrides.map((override) =>
              <div
                key={override.id}
                style={{
                  border: '1px solid var(--mac-border)',
                  borderRadius: 'var(--mac-radius-lg)',
                  padding: 'var(--mac-spacing-4)'
                }}>
                
                    <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: 'var(--mac-spacing-2)'
                }}>
                      <div style={{
                    display: 'flex',
                    alignItems: 'center'
                  }}>
                        <span style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      paddingLeft: '8px',
                      paddingRight: '8px',
                      paddingTop: '4px',
                      paddingBottom: '4px',
                      borderRadius: 'var(--mac-radius-full)',
                      fontSize: 'var(--mac-font-size-xs)',
                      fontWeight: 'var(--mac-font-weight-medium)',
                      ...(override.status === 'pending' ? {
                        color: 'var(--mac-warning)',
                        backgroundColor: 'var(--mac-warning-bg)'
                      } : override.status === 'approved' ? {
                        color: 'var(--mac-success)',
                        backgroundColor: 'var(--mac-success-bg)'
                      } : {
                        color: 'var(--mac-danger)',
                        backgroundColor: 'var(--mac-danger-bg)'
                      })
                    }}>
                          {getStatusIcon(override.status)}
                          <span style={{ marginLeft: 'var(--mac-spacing-1)' }}>{getStatusText(override.status)}</span>
                        </span>
                      </div>
                      <span style={{
                    fontSize: 'var(--mac-font-size-sm)',
                    color: 'var(--mac-text-tertiary)'
                  }}>
                        {formatRegistrarDate(override.created_at, 'ru-RU')}
                      </span>
                    </div>
                    
                    <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(2, 1fr)',
                  gap: 'var(--mac-spacing-4)',
                  fontSize: 'var(--mac-font-size-sm)',
                  marginBottom: 'var(--mac-spacing-2)'
                }}>
                      <div>
                        <span style={{ color: 'var(--mac-text-secondary)' }}>{t('derma.derma_price_was')}</span>
                        <span style={{
                      marginLeft: 'var(--mac-spacing-2)',
                      fontWeight: 'var(--mac-font-weight-medium)',
                      color: 'var(--mac-text-primary)'
                    }}>{formatPrice(override.original_price)}</span>
                      </div>
                      <div>
                        <span style={{ color: 'var(--mac-text-secondary)' }}>{t('derma.derma_price_became')}</span>
                        <span style={{
                      marginLeft: 'var(--mac-spacing-2)',
                      fontWeight: 'var(--mac-font-weight-medium)',
                      color: 'var(--mac-accent-orange)'
                    }}>{formatPrice(override.new_price)}</span>
                      </div>
                    </div>
                    
                    <div style={{ marginTop: 'var(--mac-spacing-2)' }}>
                      <span style={{
                    color: 'var(--mac-text-secondary)',
                    fontSize: 'var(--mac-font-size-sm)'
                  }}>{t('derma.derma_price_reason_inline')}</span>
                      <span style={{
                    marginLeft: 'var(--mac-spacing-2)',
                    fontSize: 'var(--mac-font-size-sm)',
                    color: 'var(--mac-text-primary)'
                  }}>{override.reason}</span>
                    </div>
                    
                    {override.details &&
                <div style={{ marginTop: 'var(--mac-spacing-1)' }}>
                        <span style={{
                    color: 'var(--mac-text-secondary)',
                    fontSize: 'var(--mac-font-size-sm)'
                  }}>{t('derma.derma_price_details_inline')}</span>
                        <span style={{
                    marginLeft: 'var(--mac-spacing-2)',
                    fontSize: 'var(--mac-font-size-sm)',
                    color: 'var(--mac-text-primary)'
                  }}>{override.details}</span>
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


PriceOverrideManager.propTypes = {
  ...(PriceOverrideManager.propTypes || {}),
  isOpen: PropTypes.any,
  onClose: PropTypes.any,
  onPriceOverrideCreated: PropTypes.any,
  originalPrice: PropTypes.any,
  serviceId: PropTypes.any,
  serviceName: PropTypes.any,
  visitId: PropTypes.any,
};

export default PriceOverrideManager;
