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
import { Search, Phone, Calendar, AlertCircle } from 'lucide-react';
import { Input } from '../ui/macos';
import { formatDateDisplay } from '../../utils/dateUtils';
import { normalizeGenderForForm } from './wizardUtils';
import { RefreshCw } from 'lucide-react';

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
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      gap: 'var(--mac-spacing-6)',
      animation: 'slideIn 0.3s ease-out',
      height: '100%',
      overflowY: 'auto',
      paddingRight: '4px',
      padding: '12px 0' // 12px vertical padding
    }}>
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: 'var(--mac-spacing-5)',
        alignItems: 'start'
      }}>
        {/* ФИО с поиском */}
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--mac-spacing-2)',
          position: 'relative'
        }}>
          <label style={{
            fontSize: 'var(--mac-font-size-sm)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: 'var(--mac-text-primary)'
          }}>
            ФИО пациента *
          </label>
          <div style={{ position: 'relative' }}>
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
            <div style={{
              position: 'absolute',
              right: '12px',
              top: '50%',
              transform: 'translateY(-50%)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: 'var(--mac-font-size-xs)',
              pointerEvents: 'none'
            }}>
              {safeData.id ?
              <>
                  <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--mac-primary)' }} />
                  <span style={{ color: 'var(--mac-primary)', fontWeight: '500' }}>Существующий</span>
                </> :

              (safeData.fio || '').length > 0 &&
              <>
                    <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--mac-success)' }} />
                    <span style={{ color: 'var(--mac-success)', fontWeight: '500' }}>Новый</span>
                  </>

              }
            </div>
          </div>

          {errors.fio &&
          <span style={{
            fontSize: 'var(--mac-font-size-xs)',
            color: 'var(--mac-danger)',
            display: 'flex',
            alignItems: 'center',
            gap: '4px'
          }}>
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
            marginTop: '4px',
            padding: 'var(--mac-spacing-3)',
            background: 'var(--mac-bg-primary)',
            border: '1px solid var(--mac-border)',
            borderRadius: 'var(--mac-radius-md)',
            boxShadow: 'var(--mac-shadow-lg)',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            color: 'var(--mac-text-secondary)',
            fontSize: '13px',
          }}>
            <RefreshCw size={14} className="spin" style={{ animation: 'spin 1s linear infinite' }} />
            Поиск пациентов...
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
            marginTop: '4px',
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
                  <div style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-secondary)', display: 'flex', gap: '8px' }}>
                    <span>📱 {patient.phone}</span>
                    <span>🎂 {formatDateDisplay(patient.birth_date)}</span>
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
          <div style={{
            display: 'flex',
            background: 'var(--mac-bg-secondary)',
            padding: '4px',
            borderRadius: 'var(--mac-radius-md)',
            border: '1px solid var(--mac-border)',
            height: '36px'
          }}>
            {['male', 'female'].map((gender) =>
            <button
              key={gender}
              type="button"
              onClick={() => onUpdate('gender', gender)}
              style={{
                flex: 1,
                padding: '8px',
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
          <span style={{
            fontSize: 'var(--mac-font-size-xs)',
            color: 'var(--mac-danger)',
            display: 'flex',
            alignItems: 'center',
            gap: '4px'
          }}>
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
            Телефон <span style={{ color: 'var(--mac-text-tertiary)', fontWeight: 'normal' }}>(необязательно)</span>
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
          <span style={{
            fontSize: 'var(--mac-font-size-xs)',
            color: 'var(--mac-danger)',
            display: 'flex',
            alignItems: 'center',
            gap: '4px'
          }}>
              <AlertCircle size={14} />
              {errors.phone}
            </span>
          }
          {phoneError &&
          <div style={{
            marginTop: '4px',
            padding: '8px',
            background: 'color-mix(in srgb, var(--mac-error), transparent 82%)',
            border: '1px solid color-mix(in srgb, var(--mac-error), transparent 70%)',
            borderRadius: 'var(--mac-radius-sm)',
            display: 'flex',
            flexDirection: 'column',
            gap: '4px'
          }}>
              <span style={{
              fontSize: 'var(--mac-font-size-xs)',
              color: 'var(--mac-error)',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              fontWeight: '500'
            }}>
                <AlertCircle size={14} />
                {phoneError.message}
              </span>
              <button
              type="button"
              onClick={() => onSelectPatient(phoneError.patient)}
              style={{
                background: 'var(--mac-error)',
                color: 'var(--mac-text-on-accent)',
                border: 'none',
                borderRadius: '4px',
                padding: '4px 8px',
                fontSize: '11px',
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
            Дата рождения
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
            size="md" />

          {errors.birth_date &&
          <span style={{
            fontSize: 'var(--mac-font-size-xs)',
            color: 'var(--mac-danger)',
            display: 'flex',
            alignItems: 'center',
            gap: '4px'
          }}>
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

            <input
              type="checkbox"
              aria-label="Request all services free approval"
              checked={cart?.all_free}
              onChange={(e) => onUpdateCart('all_free', e.target.checked)}
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
