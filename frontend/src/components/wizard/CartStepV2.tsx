
/**
 * CartStepV2 — Step 2 of AppointmentWizardV2.
 *
 * UX Audit Stage 3 (Wizard issue 5.2):
 * Вынесен из AppointmentWizardV2.jsx.
 * Этот компонент отвечает за корзину услуг: выбор категории, поиск услуг,
 * добавление в корзину, редактирование позиций, повторные назначения.
 *
 * Props передаются из родительского AppointmentWizardV2.
 */

import { useMemo, useCallback } from 'react';
import PropTypes from 'prop-types';
import { AlertCircle, X } from 'lucide-react';
import { Button as ButtonRaw, Tooltip,
  Checkbox } from '../ui/macos';
import { normalizeCategoryCode } from '../../utils/serviceCodeUtils';
import { MIXED_REPEAT_WARNING, categories } from './wizardUtils';
// UX Audit R-3.3: largest inline style blocks migrated to CSS classes.
import './CartStepV2.css';
import { useTranslation } from '../../i18n/useTranslation';
import React from "react";
const Button = ButtonRaw as unknown as React.ComponentType<Record<string, unknown>>;

const CartStepV2 = ({
  cart,
  onAddToCart,
  onRemoveFromCart,
  servicesData,
  doctorsData,
  errors,
  // New props from parent
  activeCategory,
  searchQuery,
  editMode = false,
  getServiceName, // ✅ SSOT: Функция для получения названий услуг
  onUpdateItem,
  repeatEligibilityByItemId,
  isRepeatEligibilityLoading,
  onApplyRepeatSuggestion,
  repeatSuggestionSummary
}) => {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  // Local state removed - lifted to AppointmentWizardV2

  // Categories are now defined globally at the top of the file


  // Фильтрация и группировка услуг
  const getDisplayedServices = () => {
    if (!Array.isArray(servicesData)) return [];

    const filtered = servicesData;

    // 1. Фильтрация по поиску (Глобальный поиск)
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      return filtered.filter((service) =>
      service.name.toLowerCase().includes(query) ||
      service.service_code && String(service.service_code).toLowerCase().includes(query) ||
      !service.service_code && service.code && String(service.code).toLowerCase().includes(query)
      );
    }

    // 2. Фильтрация по категории (если нет поиска)
    // Edit mode loads every service, but category tabs still filter what is displayed.
    return filtered.filter((service) => {
      const normalizedCategory = service.category_code ? normalizeCategoryCode(service.category_code) : 'other';
      const isConsultation = service.name.toLowerCase().includes(t('misc.csv_konsultatsiya'));

      // ✅ Проверка на ЭКГ, ЭхоКГ и рентгенографию по service_code и названию
      const serviceCode = service.service_code ? String(service.service_code).toUpperCase() : '';
      const serviceName = service.name ? service.name.toLowerCase() : '';

      const isECG = serviceCode === 'K10' ||
      serviceCode.includes('ECG') ||
      serviceName.includes(t('misc.csv_ekg'));

      const isEchoCG = serviceCode === 'K11' ||
      serviceCode.includes('ECHO') ||
      serviceName.includes(t('misc.csv_ehokg')) ||
      serviceName.includes(t('misc.csv_eho_kg'));

      // ✅ Рентгенография зубов: S-коды (стоматология) + название содержит "рентген"
      const isDentalXRay = serviceCode.startsWith('S') && serviceCode.match(/^S\d+$/) && (
      serviceName.includes(t('misc.csv_rentgen')) || serviceName.includes(t('misc.csv_rentgeno')) || serviceName.includes('x-ray') || serviceName.includes('xray') || serviceName.includes(t('misc.csv_rentgenografiya')));

      switch (activeCategory) {
        case 'specialists':
          // ✅ Консультации + ЭКГ + ЭхоКГ + рентгенография зубов
          return isConsultation || isECG || isEchoCG || isDentalXRay;
        case 'laboratory':
          return normalizedCategory === 'laboratory';
        case 'procedures':
          // Процедуры (нормализованные значения: 'procedures')
          // ✅ Исключаем ЭКГ, ЭхоКГ и рентгенографию из процедур
          return normalizedCategory === 'procedures' && !isConsultation && !isECG && !isEchoCG && !isDentalXRay;
        case 'other':
          // Всё остальное (не консультации и не лаборатория и не процедуры и не ЭКГ/ЭхоКГ/рентген)
          return !isConsultation && normalizedCategory === 'other' && !isECG && !isEchoCG && !isDentalXRay;
        default:
          return true;
      }
    });
  };

  const displayedServices = getDisplayedServices();

  // PR-23 P0 #2: clicking a service that's already in cart increments quantity
  // instead of toggling it off. Remove is via the X button in the cart mini-card.
  const handleServiceToggle = (service) => {
    const existingItem = cart?.items?.find((item) => item.service_id === service.id);

    if (existingItem) {
      // Already in cart → increment quantity
      onUpdateItem?.(existingItem.id, 'quantity', (existingItem.quantity || 1) + 1);
    } else {
      onAddToCart(service);
    }
  };

  // Общая сумма корзины
  const cartTotal = useMemo(() => {
    if (!Array.isArray(cart?.items)) return 0;
    let total = 0;
    cart.items.forEach((item) => {
      let itemPrice = (item.service_price || 0) * (item.quantity || 1);
      const service = servicesData?.find((s) => s.id === item.service_id);
      if (service && service.is_consultation) {
        if (cart.discount_mode === 'repeat' || cart.discount_mode === 'benefit') {
          itemPrice = 0;
        }
      }
      if (cart.all_free) itemPrice = 0;
      total += itemPrice;
    });
    return Math.round(total);
  }, [cart?.items, cart?.discount_mode, cart?.all_free, servicesData]);

  const normalizedDoctorsData = useMemo(() => {
    if (Array.isArray(doctorsData)) {
      return doctorsData.filter(Boolean);
    }

    if (!doctorsData || typeof doctorsData !== 'object') {
      return [];
    }

    return Object.values(doctorsData)
      .flatMap((value) => (Array.isArray(value) ? value : [value]))
      .filter(Boolean);
  }, [doctorsData]);

  const consultationRows = useMemo(() =>
  (cart?.items || []).
  map((item) => {
    const service = servicesData?.find((s) => s.id === item.service_id);
    if (!service?.is_consultation) {
      return null;
    }
    const doctor = normalizedDoctorsData.find((d) => String(d.id) === String(item.doctor_id));
    return {
      itemId: item.id,
      serviceName: getServiceName ? getServiceName(item) : service.name,
      doctorName: doctor?.name || doctor?.full_name || null,
      eligibility: repeatEligibilityByItemId?.[item.id] || null
    };
  }).
  filter(Boolean),
  [cart?.items, servicesData, normalizedDoctorsData, getServiceName, repeatEligibilityByItemId]);

  const getDoctorDisplayName = useCallback((doctor) => {
    if (!doctor) return '';
    return (
      doctor.user?.full_name ||
      doctor.user?.username ||
      doctor.full_name ||
      doctor.name ||
      t('misc.csv_vrach_doctor_id', { id: doctor.id })
    );
  }, []);

  return (
    // UX Audit R-3.3: main container inline style → .cart-step-v2 class
    <div className="cart-step-v2">
      {/* Верхняя панель: Поиск и Категории */}
      {/* Верхняя панель: Поиск и Категории */}


      {/* Основная область: Сетка услуг (Скролл внутри) */}
      <div className="cart-step-v2__services-area">
        {searchQuery &&
        <div className="cart-step-v2__search-info">
            Результаты поиска: {displayedServices.length}
          </div>
        }

        <div className="cart-step-v2__services-grid">
          {displayedServices.map((service) => {
            // ✅ ИСПРАВЛЕНО: Проверяем также по service_code для edit режима (когда service_id еще null)
            const isInCart = cart?.items?.some((item) => {
              if (item.service_id === service.id) return true;
              // Если service_id еще не разрешен, проверяем по коду (включая варианты с нулями: p09, P09, P9)
              if (!item.service_id && service.service_code) {
                const itemCode = String(item.service_name || item._temp_name || '').toUpperCase().trim();
                const serviceCode = String(service.service_code).toUpperCase().trim();
                // Прямое сравнение
                if (itemCode === serviceCode) return true;
                // Сравнение без ведущих нулей (p09 = p9)
                const itemCodeNoZero = itemCode.replace(/^([A-Z])0+(\d+)$/, '$1$2');
                const serviceCodeNoZero = serviceCode.replace(/^([A-Z])0+(\d+)$/, '$1$2');
                if (itemCodeNoZero === serviceCodeNoZero) return true;
              }
              return false;
            });
            return (
              <label
                key={service.id}
                className={`compact-service-card ${isInCart ? 'selected' : ''}`}>

                <Checkbox aria-label={`Select as SelectRaw service ${service.name || service.service_code || service.id}`} checked={isInCart} onChange={() => handleServiceToggle(service)}
                  className="cart-step-v2__service-checkbox" />

                <div className="cart-step-v2__service-info">
                  <div className="service-name-text cart-step-v2__service-name-row" title={service.name}>
                    {/* PR-25: show service code badge for unambiguous identification */}
                    {service.service_code && (
                      <span className="cart-step-v2__service-code">
                        {String(service.service_code).toUpperCase()}
                      </span>
                    )}
                    <span className="cart-step-v2__service-name">{service.name}</span>
                  </div>
                  <div className="service-price-text">
                    {service.price?.toLocaleString()} сум
                  </div>
                </div>
              </label>);

          })}

          {displayedServices.length === 0 &&
          <div className="cart-step-v2__empty-services">
              Услуги не найдены
            </div>
          }
        </div>
      </div>

      {/* Нижняя панель: Корзина */}
      <div className="cart-step-v2__bottom-panel">
        <div className="cart-step-v2__summary-row">
          <span>Выбрано: {cart?.items?.reduce((sum, item) => sum + (item.quantity || 1), 0) || 0} шт.</span>
          <span className="cart-step-v2__cart-total">
            Итого: {cartTotal.toLocaleString()} сум
          </span>
        </div>

        {consultationRows.length > 0 &&
        <div className="cart-step-v2__consultation-section">
            <div className="cart-step-v2__consultation-row">
              <span className="cart-step-v2__consultation-title">
                Повторная скидка для консультаций
              </span>
              <Button
              size="small"
              onClick={onApplyRepeatSuggestion}
              disabled={Boolean(isRepeatEligibilityLoading)}>
                Применить повторную скидку
              </Button>
            </div>

            {repeatSuggestionSummary?.hasMixed &&
          <div className="cart-step-v2__mixed-warning">
                {MIXED_REPEAT_WARNING}
              </div>
          }

            {consultationRows.map((row) => {
            const isEligible = Boolean(row.eligibility?.eligible);
            const reason = row.eligibility?.reason || t('misc.csv_proverka_nedostupna');
            const discount = Number(row.eligibility?.repeat_discount_percent || 0);
            return (
              <div key={row.itemId} className="cart-step-v2__consultation-row">
                  <div className="cart-step-v2__consultation-info">
                    <div className="cart-step-v2__consultation-service-name" title={row.serviceName}>
                      {row.serviceName}
                    </div>
                    <div className="cart-step-v2__consultation-doctor">
                      {row.doctorName ? t('misc.csv_vrach_row_doctorname', { doctorName: row.doctorName }) : t('misc.csv_vrach_ne_vybran')}
                    </div>
                  </div>
                  {/* QW-10 fix: wrapped repeat-eligibility badge in Tooltip with explanation. */}
                  {/* Previously only had native title={reason} — users didn't know WHAT the badge meant. */}
                  <Tooltip
                    content={isRepeatEligibilityLoading && !row.eligibility ?
                      t('misc.csv_proveryaem_istoriyu_vizitov_') :
                      isEligible ?
                      t('misc.csv_etomu_patsientu_polozhena_po', { discount: discount, reason: reason }) :
                      t('misc.csv_povtornaya_skidka_nedostupna', { reason: reason })
                    }
                    position="top"
                    delay={300}>
                  <div style={{
                  flexShrink: 0,
                  padding: '2px 8px',
                  borderRadius: '999px',
                  fontSize: 'var(--mac-font-size-xs)',
                  fontWeight: 'var(--mac-font-weight-semibold)',
                  color: isEligible ? 'var(--mac-success)' : 'var(--mac-warning)',
                  background: isEligible ?
                  'color-mix(in srgb, var(--mac-success), transparent 90%)' :
                  'color-mix(in srgb, var(--mac-warning), transparent 88%)',
                  border: isEligible ?
                  '1px solid color-mix(in srgb, var(--mac-success), transparent 75%)' :
                  '1px solid color-mix(in srgb, var(--mac-warning), transparent 70%)'
                }}>
                    {isRepeatEligibilityLoading && !row.eligibility ?
                  t('misc.csv_proverka') :
                  isEligible ?
                  t('misc.csv_dostupna_povtornaya_skidka_d', { discount: discount }) :
                  t('misc.csv_povtornaya_skidka_nedostupna_2', { reason: reason })}
                  </div>
                  </Tooltip>
                </div>);
          })}
          </div>
        }

        {/* UX Audit Registrar #10: Группировка корзины по специалистам.
            Показывает сколько визитов будет создано, когда услуги у разных врачей.
            Раньше был плоский список без визуальной группировки. */}
        {cart?.items?.length > 0 && (() => {
          const doctorGroups = new Map();
          cart.items.forEach((item) => {
            const docId = item.doctor_id || 'no_doctor';
            const docName = item.doctor_name || (item.doctor_id ? t('misc.csv_vrach_item_doctor_id', { doctor_id: item.doctor_id }) : t('misc.csv_bez_vracha'));
            if (!doctorGroups.has(docId)) {
              doctorGroups.set(docId, { id: docId, name: docName, items: [] });
            }
            doctorGroups.get(docId).items.push(item);
          });
          const groupCount = doctorGroups.size;
          if (groupCount > 1) {
            return (
              <div style={{
                marginBottom: 'var(--mac-spacing-2)',
                padding: '6px 10px',
                background: 'color-mix(in srgb, var(--mac-accent-blue, #007aff), transparent 88%)',
                border: '1px solid color-mix(in srgb, var(--mac-accent-blue, #007aff), transparent 75%)',
                borderRadius: 'var(--mac-radius-sm)',
                fontSize: 'var(--mac-font-size-xs)',
                fontWeight: 'var(--mac-font-weight-semibold)',
                color: 'var(--mac-accent-blue, #007aff)',
              }}>
                Будет создано визитов: {groupCount} · Услуг: {cart.items.length}
              </div>
            );
          }
          return null;
        })()}

        {/* Горизонтальный скролл корзины */}
        {cart?.items?.length > 0 ?
        <div style={{
          display: 'flex',
          gap: 'var(--mac-spacing-2)',
          overflowX: 'auto',
          paddingBottom: '4px'
        }}>
            {cart.items.map((item) => {
            // ✅ SSOT: Используем единую функцию для получения названия услуги
            const displayName = getServiceName ? getServiceName(item) : item.service_name || t('misc.csv_neizvestnaya_usluga');
            const service = servicesData?.find((s) => s.id === item.service_id);
            const requiresDoctor = Boolean(service?.requires_doctor || service?.is_consultation);

            // PR-23 P0 #1: filter doctors by service specialty/department_key
            // so registrar can't assign a cardiologist to a dermatology consult
            const serviceDepartmentKey = String(service?.department_key || '').toLowerCase().trim();
            const filteredDoctors = serviceDepartmentKey
              ? normalizedDoctorsData.filter((d) => {
                  const docSpecialty = String(d.specialty || '').toLowerCase().trim();
                  // Match if doctor's specialty matches service's department_key,
                  // or if doctor has no specialty (show all as fallback)
                  return !docSpecialty || docSpecialty === serviceDepartmentKey ||
                    docSpecialty.includes(serviceDepartmentKey) || serviceDepartmentKey.includes(docSpecialty);
                })
              : normalizedDoctorsData;
            const doctorOptions = filteredDoctors.length > 0 ? filteredDoctors : normalizedDoctorsData;

            return (
              <div key={item.id} style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'stretch',
                gap: 'var(--mac-spacing-1)',
                padding: '6px 8px',
                background: 'var(--mac-bg-secondary)',
                border: '1px solid var(--mac-border)',
                borderRadius: 'var(--mac-radius-sm)',
                fontSize: 'var(--mac-font-size-xs)',
                minWidth: requiresDoctor ? '240px' : 'auto'
              }}>
                  <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 'var(--mac-spacing-2)',
                  whiteSpace: 'nowrap'
                }}>
                    <span className="cart-step-v2__cart-item-name" title={displayName}>
                      {displayName}
                    </span>
                    {/* PR-23 P0 #2: quantity stepper */}
                    <div className="cart-step-v2__qty-controls">
                      <button
                        onClick={() => {
                          const newQty = (item.quantity || 1) - 1;
                          if (newQty <= 0) {
                            onRemoveFromCart(item.id);
                          } else {
                            onUpdateItem?.(item.id, 'quantity', newQty);
                          }
                        }}
                        aria-label={`Decrease quantity for ${displayName}`}
                        className="cart-step-v2__qty-btn">−</button>
                      <span className="cart-step-v2__qty-value">{item.quantity || 1}</span>
                      <button
                        onClick={() => onUpdateItem?.(item.id, 'quantity', (item.quantity || 1) + 1)}
                        aria-label={`Increase quantity for ${displayName}`}
                        className="cart-step-v2__qty-btn">+</button>
                    </div>
                    <button
                    onClick={() => onRemoveFromCart(item.id)}
                    aria-label={`Remove ${displayName} from appointment cart`}
                    style={{
                      border: 'none',
                      background: 'transparent',
                      color: 'var(--mac-danger)',
                      cursor: 'pointer',
                      padding: 0,
                      display: 'flex'
                    }}>

                      <X size={14 as unknown as "small" | "default" | "large" | "xlarge"} />
                    </button>
                  </div>
                  {requiresDoctor &&
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-1)' }}>
                      <label style={{
                    fontSize: 'var(--mac-font-size-xs)',
                    color: 'var(--mac-text-secondary)'
                  }}>
                        Врач для консультации
                      </label>
                      <select
                    value={item.doctor_id || ''}
                    onChange={(e) => onUpdateItem?.(item.id, 'doctor_id', e.target.value ? Number(e.target.value) : null)}
                    style={{
                      width: '100%',
                      fontSize: 'var(--mac-font-size-xs)',
                      padding: '4px 6px',
                      borderRadius: 'var(--mac-radius-sm)',
                      border: '1px solid var(--mac-border)',
                      background: 'var(--mac-bg-primary)',
                      color: 'var(--mac-text-primary)'
                    }}>

                        <option value="">{t('misc.csv_vyberite_vracha')}</option>
                        {doctorOptions.map((doctor, index) =>
                    <option key={`${doctor.id ?? 'doctor'}-${doctor.specialty ?? ''}-${index}`} value={doctor.id}>
                            {getDoctorDisplayName(doctor)}{doctor.specialty ? ` · ${doctor.specialty}` : t('misc.csv_doctor_cabinet_kab_doctor_ca')}
                          </option>)}
                      </select>
                      {filteredDoctors.length === 0 && normalizedDoctorsData.length > 0 && (
                        <span className="cart-step-v2__discount-hint">
                          Нет врача для этого отделения — показаны все
                        </span>
                      )}
                    </div>
                }
                </div>);

          })}
          </div> :

        <div className="cart-step-v2__footer-hint">
            Корзина пуста
          </div>
        }

        {/* Ошибки валидации */}
        {(errors.cart || errors.doctors || errors.repeat) &&
        <div style={{
          padding: 'var(--mac-spacing-2)',
          background: 'color-mix(in srgb, var(--mac-error), transparent 82%)',
          border: '1px solid color-mix(in srgb, var(--mac-error), transparent 70%)',
          borderRadius: 'var(--mac-radius-sm)',
          color: 'var(--mac-error)',
          fontSize: 'var(--mac-font-size-xs)',
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--mac-spacing-2)'
        }}>
            <AlertCircle size={14 as unknown as "small" | "default" | "large" | "xlarge"} />
            {errors.cart || errors.doctors || errors.repeat}
          </div>
        }
      </div>
    </div>);

};

CartStepV2.propTypes = {
  cart: PropTypes.object,
  onAddToCart: PropTypes.func,
  onRemoveFromCart: PropTypes.func,
  servicesData: PropTypes.array,
  doctorsData: PropTypes.oneOfType([PropTypes.array, PropTypes.object]),
  errors: PropTypes.object,
  activeCategory: PropTypes.string,
  searchQuery: PropTypes.string,
  editMode: PropTypes.bool,
  getServiceName: PropTypes.func,
  onUpdateItem: PropTypes.func,
  repeatEligibilityByItemId: PropTypes.object,
  isRepeatEligibilityLoading: PropTypes.bool,
  onApplyRepeatSuggestion: PropTypes.func,
  repeatSuggestionSummary: PropTypes.object
};


export default CartStepV2;
