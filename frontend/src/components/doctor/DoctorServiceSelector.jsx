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
import { MacOSCard, MacOSButton, MacOSBadge, MacOSLoadingSkeleton } from '../ui/macos';

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
  // Проверяем демо-режим в самом начале
  const isDemoMode = window.location.pathname.includes('/medilab-demo');
  
  // В демо-режиме не рендерим компонент
  if (isDemoMode) {
    console.log('DoctorServiceSelector: Skipping render in demo mode');
    return null;
  }
  
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
    // Проверяем демо-режим только по пути
    const isDemoMode = window.location.pathname.includes('/medilab-demo');
    
    if (isDemoMode) {
      console.log('DoctorServiceSelector: Skipping loadServices in demo mode');
      setLoading(false);
      return;
    }
    
    try {
      setLoading(true);
      setError('');

      const token = localStorage.getItem('auth_token') || localStorage.getItem('token');
      const response = await fetch(`/api/v1/doctor/${specialty}/services`, {
        headers: { 'Authorization': `Bearer ${token || ''}` }
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
      <MacOSCard style={{ padding: '24px' }}>
        <MacOSLoadingSkeleton />
      </MacOSCard>
    );
  }

  if (error) {
    return (
      <MacOSCard style={{ padding: '24px', display: 'flex', alignItems: 'center', color: 'var(--mac-red-600)' }}>
        <AlertCircle size={20} style={{ marginRight: '8px' }} />
        <span>{error}</span>
      </MacOSCard>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* Итоговая информация */}
      {selectedServices.length > 0 && (
        <MacOSCard style={{
          padding: '16px',
          background: 'linear-gradient(135deg, var(--mac-success-bg) 0%, var(--mac-success-bg-light) 100%)',
          border: '1px solid var(--mac-success-border)'
        }}>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))',
            gap: '16px',
            textAlign: 'center'
          }}>
            <div>
              <div style={{
                fontSize: 'var(--mac-font-size-2xl)',
                fontWeight: 'var(--mac-font-weight-bold)',
                color: 'var(--mac-success)'
              }}>{selectedServices.length}</div>
              <div style={{
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-secondary)'
              }}>Услуг</div>
            </div>
            <div>
              <div style={{
                fontSize: 'var(--mac-font-size-2xl)',
                fontWeight: 'var(--mac-font-weight-bold)',
                color: 'var(--mac-info)'
              }}>{getTotalDuration()}</div>
              <div style={{
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-secondary)'
              }}>Минут</div>
            </div>
            <div>
              <div style={{
                fontSize: 'var(--mac-font-size-2xl)',
                fontWeight: 'var(--mac-font-weight-bold)',
                color: 'var(--mac-purple)'
              }}>
                {getTotalCost().toLocaleString()} UZS
              </div>
              <div style={{
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-secondary)'
              }}>Стоимость</div>
            </div>
          </div>
        </MacOSCard>
      )}

      {/* Выбранные услуги */}
      {selectedServices.length > 0 && (
        <MacOSCard style={{ padding: '16px' }}>
          <h3 style={{
            fontSize: 'var(--mac-font-size-lg)',
            fontWeight: 'var(--mac-font-weight-medium)',
            marginBottom: '12px',
            color: 'var(--mac-text-primary)'
          }}>Выбранные услуги:</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {selectedServices.map((service, index) => (
              <div
                key={service.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '12px',
                  background: 'var(--mac-bg-secondary)',
                  borderRadius: 'var(--mac-radius-lg)',
                  transition: 'all var(--mac-duration-fast) var(--mac-ease)'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'var(--mac-bg-hover)';
                  e.currentTarget.style.transform = 'translateY(-2px)';
                  e.currentTarget.style.boxShadow = 'var(--mac-shadow-md)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'var(--mac-bg-secondary)';
                  e.currentTarget.style.transform = 'translateY(0)';
                  e.currentTarget.style.boxShadow = 'none';
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  <CheckCircle size={16} style={{ marginRight: '12px', color: 'var(--mac-success)' }} />
                  <div>
                    <div style={{
                      fontWeight: 'var(--mac-font-weight-medium)',
                      color: 'var(--mac-text-primary)'
                    }}>{service.name}</div>
                    <div style={{
                      fontSize: 'var(--mac-font-size-sm)',
                      color: 'var(--mac-text-tertiary)'
                    }}>
                      {service.duration_minutes} мин
                    </div>
                  </div>
                </div>
                
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px'
                }}>
                  {/* Количество */}
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px'
                  }}>
                    <MacOSButton
                      size="sm"
                      variant="ghost"
                      onClick={() => handleQuantityChange(service.id, service.quantity - 1)}
                      disabled={service.quantity <= 1}
                    >
                      <Minus size={14} />
                    </MacOSButton>
                    <span style={{
                      width: '32px',
                      textAlign: 'center',
                      fontWeight: 'var(--mac-font-weight-medium)',
                      color: 'var(--mac-text-primary)'
                    }}>{service.quantity}</span>
                    <MacOSButton
                      size="sm"
                      variant="ghost"
                      onClick={() => handleQuantityChange(service.id, service.quantity + 1)}
                    >
                      <Plus size={14} />
                    </MacOSButton>
                  </div>
                  
                  {/* Цена */}
                  {canEditPrices ? (
                    <input
                      type="number"
                      value={service.price}
                      onChange={(e) => handlePriceChange(service.id, parseFloat(e.target.value) || 0)}
                      style={{
                        width: '96px',
                        paddingLeft: '8px',
                        paddingRight: '8px',
                        paddingTop: '4px',
                        paddingBottom: '4px',
                        fontSize: 'var(--mac-font-size-sm)',
                        border: '1px solid var(--mac-border)',
                        borderRadius: 'var(--mac-radius-md)',
                        backgroundColor: 'var(--mac-bg-primary)',
                        color: 'var(--mac-text-primary)',
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
                      min="0"
                    />
                  ) : (
                    <span style={{
                      fontWeight: 'var(--mac-font-weight-medium)',
                      color: 'var(--mac-text-primary)'
                    }}>{service.price.toLocaleString()}</span>
                  )}
                  
                  <span style={{
                    fontSize: 'var(--mac-font-size-sm)',
                    color: 'var(--mac-text-tertiary)'
                  }}>{service.currency}</span>
                  
                  {/* Убрать услугу */}
                  <MacOSButton
                    size="sm"
                    variant="ghost"
                    onClick={() => handleServiceToggle(service)}
                  >
                    <Minus size={14} />
                  </MacOSButton>
                </div>
              </div>
            ))}
          </div>
        </MacOSCard>
      )}

      {/* Доступные услуги */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {Object.entries(services).map(([categoryCode, categoryData]) => {
          const CategoryIcon = categoryIcons[categoryCode] || Package;
          const categoryName = categoryNames[categoryCode] || categoryData.category.name_ru;
          
          return (
            <MacOSCard key={categoryCode} style={{ padding: '16px' }}>
              <h3 style={{
                fontSize: 'var(--mac-font-size-lg)',
                fontWeight: 'var(--mac-font-weight-medium)',
                marginBottom: '12px',
                display: 'flex',
                alignItems: 'center',
                color: 'var(--mac-text-primary)'
              }}>
                <CategoryIcon size={20} style={{ marginRight: '8px', color: 'var(--mac-info)' }} />
                {categoryName}
              </h3>
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {categoryData.services.map(service => {
                  const isSelected = isServiceSelected(service.id);
                  
                  return (
                    <div
                      key={service.id}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '12px',
                        borderRadius: 'var(--mac-radius-lg)',
                        border: `1px solid ${isSelected ? 'var(--mac-info-border)' : 'var(--mac-border)'}`,
                        backgroundColor: isSelected ? 'var(--mac-info-bg)' : 'var(--mac-bg-secondary)',
                        cursor: 'pointer',
                        transition: 'all var(--mac-duration-normal) var(--mac-ease)'
                      }}
                      onClick={() => handleServiceToggle(service)}
                      onMouseEnter={(e) => {
                        if (!isSelected) {
                          e.currentTarget.style.backgroundColor = 'var(--mac-bg-hover)';
                          e.currentTarget.style.transform = 'translateX(4px)';
                          e.currentTarget.style.boxShadow = 'var(--mac-shadow-sm)';
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (!isSelected) {
                          e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)';
                          e.currentTarget.style.transform = 'translateX(0)';
                          e.currentTarget.style.boxShadow = 'none';
                        }
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center' }}>
                        {isSelected ? (
                          <CheckCircle size={20} style={{ marginRight: '12px', color: 'var(--mac-info)' }} />
                        ) : (
                          <Circle size={20} style={{ marginRight: '12px', color: 'var(--mac-text-tertiary)' }} />
                        )}
                        <div>
                          <div style={{
                            fontWeight: 'var(--mac-font-weight-medium)',
                            color: 'var(--mac-text-primary)'
                          }}>
                            {service.name}
                          </div>
                          {service.code && (
                            <div style={{
                              fontSize: 'var(--mac-font-size-sm)',
                              color: 'var(--mac-text-tertiary)'
                            }}>
                              Код: {service.code}
                            </div>
                          )}
                        </div>
                      </div>
                      
                      <div style={{ textAlign: 'right' }}>
                        <div style={{
                          fontWeight: 'var(--mac-font-weight-bold)',
                          color: 'var(--mac-text-primary)',
                          marginBottom: '4px'
                        }}>
                          {service.price.toLocaleString()} {service.currency}
                        </div>
                        <div style={{
                          fontSize: 'var(--mac-font-size-sm)',
                          color: 'var(--mac-text-tertiary)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'flex-end',
                          gap: '4px'
                        }}>
                          <Clock size={12} />
                          {service.duration_minutes} мин
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </MacOSCard>
          );
        })}
      </div>

      {Object.keys(services).length === 0 && (
        <MacOSCard style={{ padding: '32px', textAlign: 'center' }}>
          <Package size={48} style={{
            margin: '0 auto 16px auto',
            color: 'var(--mac-text-tertiary)'
          }} />
          <h3 style={{
            fontSize: 'var(--mac-font-size-lg)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: 'var(--mac-text-primary)',
            marginBottom: '8px'
          }}>
            Услуги не найдены
          </h3>
          <p style={{
            color: 'var(--mac-text-secondary)'
          }}>
            Добавьте услуги для специальности "{specialty}" в админ панели
          </p>
        </MacOSCard>
      )}
    </div>
  );
};

export default DoctorServiceSelector;

