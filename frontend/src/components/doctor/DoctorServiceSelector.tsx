
import { api } from '../../api/client';
import { useState, useEffect, useCallback } from 'react';
import {
  Package,
  Heart,
  Activity,
  Stethoscope,
  TestTube,
  Plus,
  Minus,


  Clock,
  CheckCircle,
  Circle,

  AlertCircle } from
'lucide-react';
import {
  MacOSCard, Button, Skeleton as SkeletonRaw,
  Input } from '../ui/macos';

import logger from '../../utils/logger';
import tokenManager from '../../utils/tokenManager';
import PropTypes from 'prop-types';
import { useTranslation } from '../../i18n/useTranslation';
import React from "react";
const Skeleton = SkeletonRaw as unknown as React.ComponentType<Record<string, unknown>>;
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
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  // Проверяем демо-режим в самом начале
  const isDemoMode = window.location.pathname.includes('/medilab-demo');

  const [serviceSearch, setServiceSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [services, setServices] = useState<Record<string, any>>({});
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
    'consultation.cardiology': t('misc.dss_konsultatsiya_kardiologa'),
    'consultation.dermatology': t('misc.dss_konsultatsiya_dermatologa'),
    'consultation.stomatology': t('misc.dss_konsultatsiya_stomatologa'),
    'diagnostics.ecg': t('misc.dss_ekg'),
    'diagnostics.echo': t('misc.dss_ehokg'),
    'procedure.cosmetology': t('misc.dss_kosmetologicheskie_protsedur'),
    'laboratory.blood': t('misc.dss_analizy_krovi')
  };

  const loadServices = useCallback(async () => {
    // Проверяем демо-режим только по пути
    const isDemoMode = window.location.pathname.includes('/medilab-demo');

    if (isDemoMode) {
      logger.log('DoctorServiceSelector: Skipping loadServices in demo mode');
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError('');

      const token = tokenManager.getAccessToken();
      const response = await fetch(`/doctor/${specialty}/services`, {
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
      logger.error('Ошибка загрузки услуг врача:', err);
      setError(t('misc.dss_oshibka_zagruzki_uslug'));
    } finally {
      setLoading(false);
    }
  }, [specialty]);

  useEffect(() => {
    loadServices();
  }, [loadServices]);

  const handleServiceToggle = (service) => {
    const existingIndex = selectedServices.findIndex((s) => s.id === service.id);

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
    const newServices = selectedServices.map((service) => {
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

    const newServices = selectedServices.map((service) => {
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
    return selectedServices.some((s) => s.id === serviceId);
  };

  const getTotalCost = () => {
    return selectedServices.reduce((total, service) => total + (service.total || service.price * service.quantity), 0);
  };

  const getTotalDuration = () => {
    return selectedServices.reduce((total, service) => total + service.duration_minutes * service.quantity, 0);
  };
  const handleActivationKeyDown = (event, onActivate) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onActivate();
    }
  };

  if (isDemoMode) {
    logger.log('DoctorServiceSelector: Skipping render in demo mode');
    return null;
  }

  if (loading) {
    return (
      <MacOSCard style={{ padding: 'var(--mac-spacing-6)' }}>
        <Skeleton />
      </MacOSCard>);

  }

  if (error) {
    return (
      <MacOSCard style={{ padding: 'var(--mac-spacing-6)', display: 'flex', alignItems: 'center', color: 'var(--mac-red-600)' }}>
        <AlertCircle size={20 as unknown as "small" | "default" | "large" | "xlarge"} style={{ marginRight: 'var(--mac-spacing-2)' }} />
        <span>{error}</span>
      </MacOSCard>);

  }

  return (
    <div className={className} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-4)' }}>
      {/* Итоговая информация */}
      {selectedServices.length > 0 &&
      <MacOSCard style={{
        padding: 'var(--mac-spacing-4)',
        background: 'linear-gradient(135deg, var(--mac-success-bg) 0%, var(--mac-success-bg-light) 100%)',
        border: '1px solid var(--mac-success-border)'
      }}>
          <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))',
          gap: 'var(--mac-spacing-4)',
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
            }}>{t('misc.dss_uslug')}</div>
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
            }}>{t('misc.dss_minut')}</div>
            </div>
            <div>
              <div style={{
              fontSize: 'var(--mac-font-size-2xl)',
              fontWeight: 'var(--mac-font-weight-bold)',
              color: 'var(--mac-success)'
            }}>
                {getTotalCost().toLocaleString()} UZS
              </div>
              <div style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-secondary)'
            }}>{t('misc.dss_stoimost')}</div>
            </div>
          </div>
        </MacOSCard>
      }

      {/* Выбранные услуги */}
      {selectedServices.length > 0 &&
      <MacOSCard style={{ padding: 'var(--mac-spacing-4)' }}>
          <h3 style={{
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-medium)',
          marginBottom: 'var(--mac-spacing-3)',
          color: 'var(--mac-text-primary)'
        }}>{t('misc.dss_vybrannye_uslugi')}</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-2)' }}>
            {selectedServices.map((service) =>
          <div
            key={service.id}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: 'var(--mac-spacing-3)',
              background: 'var(--mac-bg-secondary)',
              borderRadius: 'var(--mac-radius-lg)',
              transition: 'all var(--mac-duration-fast) var(--mac-ease)'
            }}>
            
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  <CheckCircle size={16 as unknown as "small" | "default" | "large" | "xlarge"} style={{ marginRight: 'var(--mac-spacing-3)', color: 'var(--mac-success)' }} />
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
              gap: 'var(--mac-spacing-3)'
            }}>
                  {/* Количество */}
                  <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--mac-spacing-2)'
              }}>
                    <Button
                  type="button"
                  size="small"
                  variant="ghost"
                  title={`Decrease quantity for ${service.name}`}
                  aria-label={`Decrease quantity for ${service.name}`}
                  onClick={() => handleQuantityChange(service.id, service.quantity - 1)}
                  disabled={service.quantity <= 1}>

                      <Minus aria-hidden="true" size={14 as unknown as "small" | "default" | "large" | "xlarge"} />
                    </Button>
                    <span style={{
                  width: '32px',
                  textAlign: 'center',
                  fontWeight: 'var(--mac-font-weight-medium)',
                  color: 'var(--mac-text-primary)'
                }}>{service.quantity}</span>
                    <Button
                  type="button"
                  size="small"
                  variant="ghost"
                  title={`Increase quantity for ${service.name}`}
                  aria-label={`Increase quantity for ${service.name}`}
                  onClick={() => handleQuantityChange(service.id, service.quantity + 1)}>

                      <Plus aria-hidden="true" size={14 as unknown as "small" | "default" | "large" | "xlarge"} />
                    </Button>
                  </div>

                  {/* Цена */}
                  {canEditPrices ?
              <Input
                type="number"
                aria-label={t('misc.dss_tsena_uslugi_service_name', { name: service.name })}
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
                  e.currentTarget.style.borderColor = 'var(--mac-accent)';
                  e.currentTarget.style.boxShadow = 'var(--mac-focus-ring)';
                }}
                onBlur={(e) => {
                  e.currentTarget.style.borderColor = 'var(--mac-border)';
                  e.currentTarget.style.boxShadow = 'none';
                }}
                min="0" /> :


              <span style={{
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)'
              }}>{service.price.toLocaleString()}</span>
              }

                  <span style={{
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-tertiary)'
              }}>{service.currency}</span>

                  {/* Убрать услугу */}
                  <Button
                type="button"
                size="small"
                variant="ghost"
                title={`Remove service ${service.name}`}
                aria-label={`Remove service ${service.name}`}
                onClick={() => handleServiceToggle(service)}>

                    <Minus aria-hidden="true" size={14 as unknown as "small" | "default" | "large" | "xlarge"} />
                  </Button>
                </div>
              </div>
          )}
          </div>
        </MacOSCard>
      }

      {/* Доступные услуги */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-4)' }}>
        {Object.entries(services).map(([categoryCode, categoryData]) => {
          const CategoryIcon = categoryIcons[categoryCode] || Package;
          const categoryName = categoryNames[categoryCode] || categoryData.category.name_ru;

          return (
            <MacOSCard key={categoryCode} style={{ padding: 'var(--mac-spacing-4)' }}>
              <h3 style={{
                fontSize: 'var(--mac-font-size-lg)',
                fontWeight: 'var(--mac-font-weight-medium)',
                marginBottom: 'var(--mac-spacing-3)',
                display: 'flex',
                alignItems: 'center',
                color: 'var(--mac-text-primary)'
              }}>
                <CategoryIcon size={20 as unknown as "small" | "default" | "large" | "xlarge"} style={{ marginRight: 'var(--mac-spacing-2)', color: 'var(--mac-info)' }} />
                {categoryName}
              </h3>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-2)' }}>
                {categoryData.services.map((service) => {
                  const isSelected = isServiceSelected(service.id);

                  return (
                    <div
                      key={service.id}
                      role="button"
                      tabIndex={0}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: 'var(--mac-spacing-3)',
                        borderRadius: 'var(--mac-radius-lg)',
                        border: `1px solid ${isSelected ? 'var(--mac-info-border)' : 'var(--mac-border)'}`,
                        backgroundColor: isSelected ? 'var(--mac-info-bg)' : 'var(--mac-bg-secondary)',
                        cursor: 'pointer',
                        transition: 'all var(--mac-duration-normal) var(--mac-ease)'
                      }}
                      onClick={() => handleServiceToggle(service)}
                      onKeyDown={(event) => handleActivationKeyDown(event, () => handleServiceToggle(service))}
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
                      }}>
                      
                      <div style={{ display: 'flex', alignItems: 'center' }}>
                        {isSelected ?
                        <CheckCircle size={20 as unknown as "small" | "default" | "large" | "xlarge"} style={{ marginRight: 'var(--mac-spacing-3)', color: 'var(--mac-info)' }} /> :

                        <Circle size={20 as unknown as "small" | "default" | "large" | "xlarge"} style={{ marginRight: 'var(--mac-spacing-3)', color: 'var(--mac-text-tertiary)' }} />
                        }
                        <div>
                          <div style={{
                            fontWeight: 'var(--mac-font-weight-medium)',
                            color: 'var(--mac-text-primary)'
                          }}>
                            {service.name}
                          </div>
                          {service.code &&
                          <div style={{
                            fontSize: 'var(--mac-font-size-sm)',
                            color: 'var(--mac-text-tertiary)'
                          }}>
                              Код: {service.code}
                            </div>
                          }
                        </div>
                      </div>

                      <div style={{ textAlign: 'right' }}>
                        <div style={{
                          fontWeight: 'var(--mac-font-weight-bold)',
                          color: 'var(--mac-text-primary)',
                          marginBottom: 'var(--mac-spacing-1)'
                        }}>
                          {service.price.toLocaleString()} {service.currency}
                        </div>
                        <div style={{
                          fontSize: 'var(--mac-font-size-sm)',
                          color: 'var(--mac-text-tertiary)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'flex-end',
                          gap: 'var(--mac-spacing-1)'
                        }}>
                          <Clock size={12 as unknown as "small" | "default" | "large" | "xlarge"} />
                          {service.duration_minutes} мин
                        </div>
                      </div>
                    </div>);

                })}
              </div>
            </MacOSCard>);

        })}
      </div>

      {Object.keys(services).length === 0 &&
      <MacOSCard style={{ padding: '32px', textAlign: 'center' }}>
          <Package size={48} style={{
          margin: '0 auto 16px auto',
          color: 'var(--mac-text-tertiary)'
        }} />
          <h3 style={{
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-medium)',
          color: 'var(--mac-text-primary)',
          marginBottom: 'var(--mac-spacing-2)'
        }}>
            Услуги не найдены
          </h3>
          <p style={{
          color: 'var(--mac-text-secondary)'
        }}>
            Добавьте услуги для специальности «{specialty}» в админ панели
          </p>
        </MacOSCard>
      }
    </div>);

};


DoctorServiceSelector.propTypes = {
  ...(DoctorServiceSelector.propTypes || {}),
  canEditPrices: PropTypes.bool,
  className: PropTypes.string,
  onServicesChange: PropTypes.func,
  selectedServices: PropTypes.arrayOf(PropTypes.object),
  specialty: PropTypes.string,
};

export default DoctorServiceSelector;
