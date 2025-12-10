import React, { useState, useEffect } from 'react';
import { 
  DollarSign, 
  Save, 
  AlertCircle, 
  CheckCircle, 
  Clock, 
  X,
  FileText,
  Edit3
} from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import { toast } from 'react-toastify';

import logger from '../../utils/logger';
const API_BASE = (import.meta?.env?.VITE_API_BASE || 'http://localhost:8000/api/v1');

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
  const { theme, getColor } = useTheme();
  const [newPrice, setNewPrice] = useState('');
  const [reason, setReason] = useState('');
  const [details, setDetails] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [priceOverrides, setPriceOverrides] = useState([]);
  const [loadingOverrides, setLoadingOverrides] = useState(false);

  // Предустановленные причины для быстрого выбора
  const commonReasons = [
    'Увеличенный объем работы',
    'Дополнительные материалы',
    'Сложность процедуры',
    'Индивидуальный подход',
    'Комбинированная процедура'
  ];

  useEffect(() => {
    if (isOpen && visitId) {
      loadPriceOverrides();
    }
  }, [isOpen, visitId]);

  const loadPriceOverrides = async () => {
    setLoadingOverrides(true);
    try {
      const response = await fetch(`${API_BASE}/derma/price-overrides?visit_id=${visitId}`);
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
    
    if (!newPrice || !reason) {
      toast.error('Заполните цену и причину изменения');
      return;
    }

    const priceNum = Number(newPrice.replace(/[^0-9.-]/g, ''));
    if (isNaN(priceNum) || priceNum <= 0) {
      toast.error('Введите корректную цену');
      return;
    }

    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE}/derma/price-override`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          visit_id: visitId,
          service_id: serviceId,
          new_price: priceNum,
          reason: reason,
          details: details || null
        })
      });

      if (response.ok) {
        const result = await response.json();
        toast.success('Изменение цены отправлено на одобрение');
        
        // Обновляем список изменений
        loadPriceOverrides();
        
        // Очищаем форму
        setNewPrice('');
        setReason('');
        setDetails('');
        
        // Уведомляем родительский компонент
        onPriceOverrideCreated?.(result);
      } else {
        const errorData = await response.json();
        toast.error(errorData.detail || 'Ошибка создания изменения цены');
      }
    } catch (error) {
      logger.error('Error creating price override:', error);
      toast.error('Ошибка создания изменения цены');
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
      case 'pending': return 'Ожидает одобрения';
      case 'approved': return 'Одобрено';
      case 'rejected': return 'Отклонено';
      default: return status;
    }
  };

  if (!isOpen) return null;

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      backgroundColor: 'rgba(0, 0, 0, 0.5)',
      backdropFilter: 'blur(4px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 50,
      padding: '16px'
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
          padding: '24px',
          borderBottom: '1px solid var(--mac-border)'
        }}>
          <div>
            <h3 style={{
              fontSize: 'var(--mac-font-size-lg)',
              fontWeight: 'var(--mac-font-weight-semibold)',
              color: 'var(--mac-text-primary)'
            }}>
              Изменение цены процедуры
            </h3>
            <p style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-secondary)',
              marginTop: '4px'
            }}>
              {serviceName} • Базовая цена: {formatPrice(originalPrice)}
            </p>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--mac-text-secondary)',
              cursor: 'pointer',
              transition: 'all var(--mac-duration-fast) var(--mac-ease)',
              padding: '4px'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = 'var(--mac-text-primary)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = 'var(--mac-text-secondary)';
            }}
          >
            <X size={24} />
          </button>
        </div>

        {/* Content */}
        <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Форма изменения цены */}
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <label style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-secondary)',
                marginBottom: '8px'
              }}>
                Новая цена (UZS)
              </label>
              <div style={{ position: 'relative' }}>
                <DollarSign size={16} style={{
                  position: 'absolute',
                  left: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: 'var(--mac-text-tertiary)'
                }} />
                <input
                  type="text"
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
                    e.target.style.borderColor = 'var(--mac-accent)';
                    e.target.style.boxShadow = 'var(--mac-focus-ring)';
                  }}
                  onBlur={(e) => {
                    e.target.style.borderColor = 'var(--mac-border)';
                    e.target.style.boxShadow = 'none';
                  }}
                  placeholder="Например: 120000"
                  inputMode="numeric"
                />
              </div>
            </div>

            <div>
              <label style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-secondary)',
                marginBottom: '8px'
              }}>
                Причина изменения
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
                  marginBottom: '8px',
                  transition: 'all var(--mac-duration-fast) var(--mac-ease)'
                }}
                onFocus={(e) => {
                  e.target.style.borderColor = 'var(--mac-accent)';
                  e.target.style.boxShadow = 'var(--mac-focus-ring)';
                }}
                onBlur={(e) => {
                  e.target.style.borderColor = 'var(--mac-border)';
                  e.target.style.boxShadow = 'none';
                }}
              >
                <option value="">Выберите причину</option>
                {commonReasons.map((reasonText, index) => (
                  <option key={index} value={reasonText}>{reasonText}</option>
                ))}
                <option value="custom">Другая причина</option>
              </select>
              
              {reason === 'custom' && (
                <input
                  type="text"
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
                    e.target.style.borderColor = 'var(--mac-accent)';
                    e.target.style.boxShadow = 'var(--mac-focus-ring)';
                  }}
                  onBlur={(e) => {
                    e.target.style.borderColor = 'var(--mac-border)';
                    e.target.style.boxShadow = 'none';
                  }}
                  placeholder="Введите причину"
                />
              )}
            </div>

            <div>
              <label style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-secondary)',
                marginBottom: '8px'
              }}>
                Подробное описание (необязательно)
              </label>
              <textarea
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
                  e.target.style.borderColor = 'var(--mac-accent)';
                  e.target.style.boxShadow = 'var(--mac-focus-ring)';
                }}
                onBlur={(e) => {
                  e.target.style.borderColor = 'var(--mac-border)';
                  e.target.style.boxShadow = 'none';
                }}
                placeholder="Дополнительные детали об изменении цены..."
              />
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
              onMouseEnter={(e) => {
                if (!isLoading && newPrice && reason) {
                  e.target.style.background = 'var(--mac-accent-orange-hover)';
                  e.target.style.transform = 'translateY(-1px)';
                }
              }}
              onMouseLeave={(e) => {
                if (!isLoading && newPrice && reason) {
                  e.target.style.background = 'var(--mac-accent-orange)';
                  e.target.style.transform = 'translateY(0)';
                }
              }}
            >
              {isLoading ? (
                <div style={{
                  animation: 'spin 1s linear infinite',
                  borderRadius: '50%',
                  height: '16px',
                  width: '16px',
                  borderBottom: '2px solid white',
                  marginRight: '8px'
                }} />
              ) : (
                <Save size={16} style={{ marginRight: '8px' }} />
              )}
              {isLoading ? 'Отправка...' : 'Отправить на одобрение'}
            </button>
          </form>

          {/* История изменений цен */}
          <div>
            <h4 style={{
              fontSize: 'var(--mac-font-size-base)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              marginBottom: '12px',
              display: 'flex',
              alignItems: 'center'
            }}>
              <FileText size={16} style={{ marginRight: '8px' }} />
              История изменений цен
            </h4>
            
            {loadingOverrides ? (
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
              </div>
            ) : priceOverrides.length === 0 ? (
              <p style={{
                color: 'var(--mac-text-tertiary)',
                fontSize: 'var(--mac-font-size-sm)'
              }}>
                Изменений цен пока нет
              </p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {priceOverrides.map((override) => (
                  <div
                    key={override.id}
                    style={{
                      border: '1px solid var(--mac-border)',
                      borderRadius: 'var(--mac-radius-lg)',
                      padding: '16px'
                    }}
                  >
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      marginBottom: '8px'
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
                          <span style={{ marginLeft: '4px' }}>{getStatusText(override.status)}</span>
                        </span>
                      </div>
                      <span style={{
                        fontSize: 'var(--mac-font-size-sm)',
                        color: 'var(--mac-text-tertiary)'
                      }}>
                        {new Date(override.created_at).toLocaleDateString('ru-RU')}
                      </span>
                    </div>
                    
                    <div style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(2, 1fr)',
                      gap: '16px',
                      fontSize: 'var(--mac-font-size-sm)',
                      marginBottom: '8px'
                    }}>
                      <div>
                        <span style={{ color: 'var(--mac-text-secondary)' }}>Было:</span>
                        <span style={{
                          marginLeft: '8px',
                          fontWeight: 'var(--mac-font-weight-medium)',
                          color: 'var(--mac-text-primary)'
                        }}>{formatPrice(override.original_price)}</span>
                      </div>
                      <div>
                        <span style={{ color: 'var(--mac-text-secondary)' }}>Стало:</span>
                        <span style={{
                          marginLeft: '8px',
                          fontWeight: 'var(--mac-font-weight-medium)',
                          color: 'var(--mac-accent-orange)'
                        }}>{formatPrice(override.new_price)}</span>
                      </div>
                    </div>
                    
                    <div style={{ marginTop: '8px' }}>
                      <span style={{
                        color: 'var(--mac-text-secondary)',
                        fontSize: 'var(--mac-font-size-sm)'
                      }}>Причина:</span>
                      <span style={{
                        marginLeft: '8px',
                        fontSize: 'var(--mac-font-size-sm)',
                        color: 'var(--mac-text-primary)'
                      }}>{override.reason}</span>
                    </div>
                    
                    {override.details && (
                      <div style={{ marginTop: '4px' }}>
                        <span style={{
                          color: 'var(--mac-text-secondary)',
                          fontSize: 'var(--mac-font-size-sm)'
                        }}>Детали:</span>
                        <span style={{
                          marginLeft: '8px',
                          fontSize: 'var(--mac-font-size-sm)',
                          color: 'var(--mac-text-primary)'
                        }}>{override.details}</span>
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

export default PriceOverrideManager;

