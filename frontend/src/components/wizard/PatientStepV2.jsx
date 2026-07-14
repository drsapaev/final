/**
 * PatientStepV2 — Step 1 of AppointmentWizardV2.
 *
 * UX Audit Stage 3 (Wizard issue 5.2):
 * Вынесен из AppointmentWizardV2.jsx (4175 → ~3400 строк после всех split'ов).
 * Этот компонент отвечает за ввод данных пациента: ФИО, телефон, дата рождения,
 * пол, поиск существующего пациента.
 *
 * Props передаются из родительского AppointmentWizardV2.
 */

import PropTypes from 'prop-types';
import { Search, Phone, Calendar, AlertCircle, RefreshCw } from 'lucide-react';
import { Input,
  Checkbox } from '../ui/macos';
import { formatDateDisplay } from '../../utils/dateUtils';
import { normalizeGenderForForm } from './wizardUtils';
// UX Audit R-3.3: largest inline style blocks migrated to CSS classes.
import './PatientStepV2.css';

const PatientStepV2 = ({
  data = {}, // ✅ Default empty object to prevent crash
  errors,
  suggestions,
  showSuggestions,
  isSearching = false, // UX Audit Registrar #11
  onSearch,
  onSelectPatient,
  onUpdate,
  onPhoneChange,
  onBirthDateChange,
  formattedBirthDate,
  fioRef,
  phoneRef,
  cart,
  onUpdateCart,
  phoneError
}) => {
  const safeData = data || {};
  const selectedGender = normalizeGenderForForm(safeData.gender);

  return (
    // UX Audit R-3.3: main container inline style → .patient-step-v2 class
    <div className="patient-step-v2">
      <div className="patient-step-v2__form-grid">
        {/* ФИО с поиском */}
        <div className="patient-step-v2__field">
          <label className="patient-step-v2__label">
            ФИО пациента *
          </label>
          <div className="patient-step-v2__field-relative">
            <Input
              ref={fioRef}
              type="text"
              value={safeData.fio || ''}
              onChange={(e) => onSearch(e.target.value)}
              placeholder="Введите ФИО для поиска или создания"
              error={!!errors.fio}
              icon={Search}
              iconPosition="left"
              size="md"
              autoFocus />


            {/* Индикатор Новый/Существующий */}
            <div className="patient-step-v2__search-status">
              {safeData.id ?
              <>
                  <div className="patient-step-v2__status-dot-inline patient-step-v2__status-dot-inline--existing" />
                  <span className="patient-step-v2__status-text-inline--existing">Существующий</span>
                </> :

              (safeData.fio || '').length > 0 &&
              <>
                    <div className="patient-step-v2__status-dot-inline patient-step-v2__status-dot-inline--new" />
                    <span className="patient-step-v2__status-text-inline--new">Новый</span>
                  </>

              }
            </div>
          </div>

          {errors.fio &&
          <span className="patient-step-v2__error-inline">
              <AlertCircle size={14} />
              {errors.fio}
            </span>
          }

          {/* UX Audit Registrar #11: loading indicator во время поиска пациентов. */}
          {isSearching &&
          <div style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0,
            zIndex: 100,
            marginTop: 'var(--mac-spacing-1)',
            padding: 'var(--mac-spacing-3)',
            background: 'var(--mac-bg-primary)',
            border: '1px solid var(--mac-border)',
            borderRadius: 'var(--mac-radius-md)',
            boxShadow: 'var(--mac-shadow-lg)',
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--mac-spacing-2)',
            color: 'var(--mac-text-secondary)',
            fontSize: 'var(--mac-font-size-sm)',
          }}>
            <RefreshCw size={14} className="spin" style={{ animation: 'spin 1s linear infinite' }} />
            Поиск пациентов...
          </div>
          }

          {/* UX Audit #9: Empty state — patients not found. */}
          {showSuggestions && !isSearching && suggestions.length === 0 && safeData.fio && safeData.fio.trim().length >= 2 &&
          <div style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0,
            zIndex: 100,
            marginTop: 'var(--mac-spacing-1)',
            padding: 'var(--mac-spacing-3)',
            background: 'var(--mac-bg-primary)',
            border: '1px solid var(--mac-border)',
            borderRadius: 'var(--mac-radius-md)',
            boxShadow: 'var(--mac-shadow-lg)',
            color: 'var(--mac-text-secondary)',
            fontSize: 'var(--mac-font-size-sm)',
            textAlign: 'center',
          }}>
            Пациенты не найдены. Будет создан новый пациент.
          </div>
          }

          {/* Саджесты */}
          {showSuggestions && suggestions.length > 0 &&
          <div style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0,
            zIndex: 100,
            marginTop: 'var(--mac-spacing-1)',
            background: 'var(--mac-bg-primary)',
            border: '1px solid var(--mac-border)',
            borderRadius: 'var(--mac-radius-md)',
            boxShadow: 'var(--mac-shadow-lg)',
            maxHeight: '200px',
            overflowY: 'auto'
          }}>
              {suggestions.map((patient) =>
            <button
              type="button"
              key={patient.id}
              onClick={() => onSelectPatient(patient)}
              style={{
                padding: 'var(--mac-spacing-3)',
                cursor: 'pointer',
                width: '100%',
                textAlign: 'left',
                border: 'none',
                background: 'transparent',
                borderBottom: '1px solid var(--mac-border)',
                transition: 'background-color 0.2s'
              }}
              onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)'}
              onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}>

                  <div style={{ fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-primary)' }}>
                    {patient.fio || `${patient.last_name} ${patient.first_name}`}
                  </div>
                  <div style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-secondary)', display: 'flex', gap: 'var(--mac-spacing-2)' }}>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 'var(--mac-spacing-1)' }}><Phone size={12} aria-hidden="true" />{patient.phone}</span>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 'var(--mac-spacing-1)' }}><Calendar size={12} aria-hidden="true" />{formatDateDisplay(patient.birth_date)}</span>
                  </div>
                </button>
            )}
            </div>
          }
        </div>

        {/* Пол (рядом с ФИО) */}
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--mac-spacing-2)'
        }}>
          <label style={{
            fontSize: 'var(--mac-font-size-sm)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: 'var(--mac-text-primary)'
          }}>
            Пол *
          </label>
          <div
            role="radiogroup"
            aria-label="Пол пациента"
            aria-required="true"
            tabIndex={-1}
            onKeyDown={(e) => {
              // UX Audit R-2.4: ARIA radiogroup keyboard navigation.
              // Arrow keys move between options, Tab moves out.
              if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
              e.preventDefault();
              const next = selectedGender === 'male' ? 'female' : 'male';
              onUpdate('gender', next);
            }}
            style={{
            display: 'flex',
            background: 'var(--mac-bg-secondary)',
            padding: 'var(--mac-spacing-1)',
            borderRadius: 'var(--mac-radius-md)',
            border: '1px solid var(--mac-border)',
            height: '36px'
          }}>
            {['male', 'female'].map((gender) =>
            <button
              key={gender}
              type="button"
              role="radio"
              aria-checked={selectedGender === gender}
              tabIndex={selectedGender === gender ? 0 : -1}
              onClick={() => onUpdate('gender', gender)}
              style={{
                flex: 1,
                padding: 'var(--mac-spacing-2)',
                border: 'none',
                borderRadius: 'var(--mac-radius-sm)',
                background: selectedGender === gender ? 'var(--mac-bg-primary)' : 'transparent',
                color: selectedGender === gender ? 'var(--mac-text-primary)' : 'var(--mac-text-secondary)',
                boxShadow: selectedGender === gender ? 'var(--mac-shadow-sm)' : 'none',
                cursor: 'pointer',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: selectedGender === gender ? '600' : '400',
                transition: 'all 0.2s ease'
              }}>

                {gender === 'male' ? 'Мужской' : 'Женский'}
              </button>
            )}
          </div>
          {errors.gender &&
          <span className="patient-step-v2__error-inline">
              <AlertCircle size={14} />
              {errors.gender}
            </span>
          }
        </div>

        {/* Телефон */}
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--mac-spacing-2)'
        }}>
          <label style={{
            fontSize: 'var(--mac-font-size-sm)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: 'var(--mac-text-primary)'
          }}>
            Телефон <span className="patient-step-v2__field-hint">(необязательно)</span>
          </label>
          <Input
            ref={phoneRef}
            type="tel"
            value={data.phone}
            onChange={(e) => onPhoneChange(e.target.value)}
            placeholder="+998 XX XXX XX XX"
            error={!!errors.phone || !!phoneError}
            icon={Phone}
            iconPosition="left"
            size="md" />

          {!data.phone && !errors.phone &&
          <span style={{
            fontSize: 'var(--mac-font-size-xs)',
            color: 'var(--mac-text-tertiary)',
            fontStyle: 'italic'
          }}>
              Для детей и пожилых можно не указывать. Номер можно вводить без +998 — мы приведём его к формату +998XXXXXXXXX.
            </span>
          }
          {errors.phone &&
          <span className="patient-step-v2__error-inline">
              <AlertCircle size={14} />
              {errors.phone}
            </span>
          }
          {phoneError &&
          <div style={{
            marginTop: 'var(--mac-spacing-1)',
            padding: 'var(--mac-spacing-2)',
            background: 'color-mix(in srgb, var(--mac-error), transparent 82%)',
            border: '1px solid color-mix(in srgb, var(--mac-error), transparent 70%)',
            borderRadius: 'var(--mac-radius-sm)',
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--mac-spacing-1)'
          }}>
              <span style={{
              fontSize: 'var(--mac-font-size-xs)',
              color: 'var(--mac-error)',
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--mac-spacing-1)',
              fontWeight: 'var(--mac-font-weight-medium)'
            }}>
                <AlertCircle size={14} />
                {phoneError.message}
              </span>
              <button
              type="button"
              onClick={() => onSelectPatient(phoneError.patient)}
              style={{
                background: 'var(--mac-accent-blue, #007aff)',
                color: 'var(--mac-text-on-accent)',
                border: 'none',
                borderRadius: 'var(--mac-radius-sm)',
                padding: 'var(--mac-spacing-1) var(--mac-spacing-2)',
                fontSize: 'var(--mac-font-size-xs)',
                cursor: 'pointer',
                alignSelf: 'flex-start'
              }}>

                Выбрать {phoneError?.patient?.fio || 'этого пациента'}
              </button>
            </div>
          }
        </div>

        {/* Дата рождения */}
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--mac-spacing-2)'
        }}>
          <label style={{
            fontSize: 'var(--mac-font-size-sm)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: 'var(--mac-text-primary)'
          }}>
            Дата рождения <span className="patient-step-v2__field-hint">(необязательно)</span>
          </label>
          <Input
            type="text"
            value={formattedBirthDate}
            onChange={(e) => onBirthDateChange(e.target.value)}
            placeholder="ДД.ММ.ГГГГ"
            maxLength={10}
            error={!!errors.birth_date}
            icon={Calendar}
            iconPosition="left"
            size="md"
            aria-label="Дата рождения" />

          {errors.birth_date &&
          <span className="patient-step-v2__error-inline">
              <AlertCircle size={14} />
              {errors.birth_date}
            </span>
          }
        </div>

        {/* Адрес */}
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--mac-spacing-2)',
          gridColumn: '1 / -1'
        }}>
          <label style={{
            fontSize: 'var(--mac-font-size-sm)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: 'var(--mac-text-primary)'
          }}>
            Адрес
          </label>
          <Input
            type="text"
            value={data.address}
            onChange={(e) => onUpdate('address', e.target.value)}
            placeholder="Адрес проживания"
            size="md" />

        </div>

      </div>

      {/* Тип визита - перенесено из PaymentStepV2 */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--mac-spacing-2)',
        gridColumn: '1 / -1'
      }}>
        <label style={{
          fontSize: 'var(--mac-font-size-sm)',
          fontWeight: 'var(--mac-font-weight-medium)',
          color: 'var(--mac-text-primary)'
        }}>
          Тип визита
        </label>
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--mac-spacing-2)'
        }}>
          <label style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--mac-spacing-2)',
            padding: 'var(--mac-spacing-3)',
            border: '1px solid var(--mac-border)',
            borderRadius: 'var(--mac-radius-md)',
            cursor: 'pointer',
            transition: 'all var(--mac-duration-normal) var(--mac-ease)',
            background: 'var(--mac-bg-primary)'
          }}
          onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)'}
          onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-primary)'}>

            <input
              type="radio"
              name="discount_mode"
              value="none"
              aria-label="Select paid visit discount mode"
              checked={cart?.discount_mode === 'none'}
              onChange={(e) => onUpdateCart('discount_mode', e.target.value)}
              style={{ margin: 0 }} />

            <span style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-primary)'
            }}>
              Платный
            </span>
          </label>

          <label style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--mac-spacing-2)',
            padding: 'var(--mac-spacing-3)',
            border: '1px solid var(--mac-border)',
            borderRadius: 'var(--mac-radius-md)',
            cursor: 'pointer',
            transition: 'all var(--mac-duration-normal) var(--mac-ease)',
            background: 'var(--mac-bg-primary)'
          }}
          onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)'}
          onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-primary)'}>

            <input
              type="radio"
              name="discount_mode"
              value="repeat"
              aria-label="Select repeat visit discount mode"
              checked={cart?.discount_mode === 'repeat'}
              onChange={(e) => onUpdateCart('discount_mode', e.target.value)}
              style={{ margin: 0 }} />

            <span style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-primary)'
            }}>
              Повторный (бесплатная консультация)
            </span>
          </label>

          <label style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--mac-spacing-2)',
            padding: 'var(--mac-spacing-3)',
            border: '1px solid var(--mac-border)',
            borderRadius: 'var(--mac-radius-md)',
            cursor: 'pointer',
            transition: 'all var(--mac-duration-normal) var(--mac-ease)',
            background: 'var(--mac-bg-primary)'
          }}
          onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)'}
          onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-primary)'}>

            <input
              type="radio"
              name="discount_mode"
              value="benefit"
              aria-label="Select benefit discount mode"
              checked={cart?.discount_mode === 'benefit'}
              onChange={(e) => onUpdateCart('discount_mode', e.target.value)}
              style={{ margin: 0 }} />

            <span style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-primary)'
            }}>
              Льготный (бесплатная консультация)
            </span>
          </label>
        </div>

        <div style={{ marginTop: 'var(--mac-spacing-2)' }}>
          <label style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--mac-spacing-2)',
            padding: 'var(--mac-spacing-3)',
            border: '1px solid var(--mac-border)',
            borderRadius: 'var(--mac-radius-md)',
            cursor: 'pointer',
            transition: 'all var(--mac-duration-normal) var(--mac-ease)',
            background: 'var(--mac-bg-primary)'
          }}
          onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)'}
          onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-primary)'}>

            <Checkbox aria-label="Request all services free approval" checked={cart?.all_free} onChange={(e) => onUpdateCart('all_free', e.target.checked)}
              style={{ margin: 0 }} />

            <span style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-primary)'
            }}>
              All Free (требует одобрения администратора)
            </span>
          </label>
          {cart?.all_free &&
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--mac-spacing-2)',
            padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
            background: 'var(--mac-warning)',
            border: '1px solid var(--mac-warning-hover)',
            borderRadius: 'var(--mac-radius-sm)',
            color: 'var(--mac-text-primary)',
            fontSize: 'var(--mac-font-size-xs)',
            marginTop: 'var(--mac-spacing-2)'
          }}>
              <AlertCircle size={16} />
              Заявка будет отправлена на одобрение администратору
            </div>
          }
        </div>
      </div>
    </div>);

};

PatientStepV2.propTypes = {
  data: PropTypes.object,
  errors: PropTypes.object,
  suggestions: PropTypes.array,
  showSuggestions: PropTypes.bool,
  onSearch: PropTypes.func,
  onSelectPatient: PropTypes.func,
  onUpdate: PropTypes.func,
  onPhoneChange: PropTypes.func,
  onBirthDateChange: PropTypes.func,
  formattedBirthDate: PropTypes.string,
  fioRef: PropTypes.any,
  phoneRef: PropTypes.any,
  cart: PropTypes.object,
  onUpdateCart: PropTypes.func,
  phoneError: PropTypes.object
};

export default PatientStepV2;
