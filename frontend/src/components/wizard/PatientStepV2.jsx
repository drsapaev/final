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
import { useTranslation } from '../../i18n/adapter';

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
          <div className="patient-step-v2__search-loading">
            <RefreshCw size={14} className="patient-step-v2__search-spinner" />
            Поиск пациентов...
          </div>
          }

          {/* UX Audit #9: Empty state — patients not found. */}
          {showSuggestions && !isSearching && suggestions.length === 0 && safeData.fio && safeData.fio.trim().length >= 2 &&
          <div className="patient-step-v2__search-empty">
            Пациенты не найдены. Будет создан новый пациент.
          </div>
          }

          {/* Саджесты */}
          {showSuggestions && suggestions.length > 0 &&
          <div className="patient-step-v2__suggestions-dropdown">
              {suggestions.map((patient) =>
            <button
              type="button"
              key={patient.id}
              onClick={() => onSelectPatient(patient)}
              className="patient-step-v2__suggestion-btn">

                  <div className="patient-step-v2__suggestion-name">
                    {patient.fio || `${patient.last_name} ${patient.first_name}`}
                  </div>
                  <div className="patient-step-v2__suggestion-details">
                    <span className="patient-step-v2__suggestion-detail"><Phone size={12} aria-hidden="true" />{patient.phone}</span>
                    <span className="patient-step-v2__suggestion-detail"><Calendar size={12} aria-hidden="true" />{formatDateDisplay(patient.birth_date)}</span>
                  </div>
                </button>
            )}
            </div>
          }
        </div>

        {/* Пол (рядом с ФИО) */}
        <div className="patient-step-v2__field-group">
          <label className="patient-step-v2__field-label">
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
            className="patient-step-v2__gender-radiogroup">
            {['male', 'female'].map((gender) =>
            <button
              key={gender}
              type="button"
              role="radio"
              aria-checked={selectedGender === gender}
              tabIndex={selectedGender === gender ? 0 : -1}
              onClick={() => onUpdate('gender', gender)}
              className={`patient-step-v2__gender-radio ${selectedGender === gender ? 'patient-step-v2__gender-radio--selected' : 'patient-step-v2__gender-radio--unselected'}`}>

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
        <div className="patient-step-v2__field-group">
          <label className="patient-step-v2__field-label">
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
          <span className="patient-step-v2__phone-hint">
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
          <div className="patient-step-v2__phone-error-block">
              <span className="patient-step-v2__phone-error-text">
                <AlertCircle size={14} />
                {phoneError.message}
              </span>
              <button
              type="button"
              onClick={() => onSelectPatient(phoneError.patient)}
              className="patient-step-v2__phone-error-btn">

                Выбрать {phoneError?.patient?.fio || 'этого пациента'}
              </button>
            </div>
          }
        </div>

        {/* Дата рождения */}
        <div className="patient-step-v2__field-group">
          <label className="patient-step-v2__field-label">
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
        <div className="patient-step-v2__field-group--full">
          <label className="patient-step-v2__field-label">
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
      <div className="patient-step-v2__field-group--full">
        <label className="patient-step-v2__field-label">
          Тип визита
        </label>
        <div className="patient-step-v2__field-group">
          <label className="patient-step-v2__discount-card">

            <input
              type="radio"
              name="discount_mode"
              value="none"
              aria-label="Select paid visit discount mode"
              checked={cart?.discount_mode === 'none'}
              onChange={(e) => onUpdateCart('discount_mode', e.target.value)}
              className="patient-step-v2__discount-radio-input" />

            <span className="patient-step-v2__discount-card-text">
              Платный
            </span>
          </label>

          <label className="patient-step-v2__discount-card">

            <input
              type="radio"
              name="discount_mode"
              value="repeat"
              aria-label="Select repeat visit discount mode"
              checked={cart?.discount_mode === 'repeat'}
              onChange={(e) => onUpdateCart('discount_mode', e.target.value)}
              className="patient-step-v2__discount-radio-input" />

            <span className="patient-step-v2__discount-card-text">
              Повторный (бесплатная консультация)
            </span>
          </label>

          <label className="patient-step-v2__discount-card">

            <input
              type="radio"
              name="discount_mode"
              value="benefit"
              aria-label="Select benefit discount mode"
              checked={cart?.discount_mode === 'benefit'}
              onChange={(e) => onUpdateCart('discount_mode', e.target.value)}
              className="patient-step-v2__discount-radio-input" />

            <span className="patient-step-v2__discount-card-text">
              Льготный (бесплатная консультация)
            </span>
          </label>
        </div>

        <div className="patient-step-v2__discount-section-wrapper">
          <label className="patient-step-v2__discount-card">

            <Checkbox aria-label="Request all services free approval" checked={cart?.all_free} onChange={(e) => onUpdateCart('all_free', e.target.checked)}
              className="patient-step-v2__discount-radio-input" />

            <span className="patient-step-v2__discount-card-text">
              All Free (требует одобрения администратора)
            </span>
          </label>
          {cart?.all_free &&
          <div className="patient-step-v2__all-free-warning">
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
