import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import PropTypes from 'prop-types';
import {
  User,
  Calendar,
  CreditCard,
  ArrowLeft,
  ArrowRight,
  Check,
  Search,
  Phone,

  MapPin } from
'lucide-react';
import ModernDialog from '../dialogs/ModernDialog';
import { useTheme } from '../../contexts/ThemeContext';
import { toast } from 'react-toastify';
import logger from '../../utils/logger';
import './AppointmentWizard.css';

const AppointmentWizard = ({
  isOpen,
  onClose,
  onComplete,
  doctors = [],
  services = {},
  initialData = {}
}) => {
  const { theme, getColor } = useTheme();

  // Отладка (отключена для избежания спама)
  // logger.log('AppointmentWizard render:', { isOpen, doctors: doctors.length, services: Object.keys(services).length });
  const [currentStep, setCurrentStep] = useState(1);
  const [isProcessing, setIsProcessing] = useState(false);

  // Данные мастера
  const [wizardData, setWizardData] = useState({
    patient: {
      fio: '',
      birth_date: '',
      phone: '',
      email: '',
      address: '',
      ...initialData.patient
    },
    appointment: {
      doctor_id: '',
      services: [],
      date: new Date().toISOString().split('T')[0],
      time: '',
      visit_type: 'Платный',
      notes: '',
      ...initialData.appointment
    },
    payment: {
      method: 'Карта',
      amount: 0,
      ...initialData.payment
    }
  });

  // Сброс данных при открытии мастера
  useEffect(() => {
    if (isOpen) {
      setWizardData({
        patient: {
          fio: '',
          birth_date: '',
          phone: '',
          email: '',
          address: ''
        },
        appointment: {
          doctor_id: '',
          services: [],
          date: new Date().toISOString().split('T')[0],
          time: '',
          visit_type: 'Платный',
          notes: ''
        },
        payment: {
          method: 'Карта',
          amount: 0
        }
      });
      setCurrentStep(1);
      setSelectedPatientId(null);
      setPatientSuggestions([]);
      setShowSuggestions(false);
      setErrors({});
    }
  }, [isOpen]);

  // Ошибки валидации
  const [errors, setErrors] = useState({});

  // Поиск пациентов
  const [patientSuggestions, setPatientSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [, setSelectedPatientId] = useState(null);

  // Refs для фокуса
  const fioRef = useRef(null);
  const phoneRef = useRef(null);

  const steps = [
  {
    id: 1,
    title: 'Пациент',
    icon: <User size={20} />,
    description: 'Данные пациента'
  },
  {
    id: 2,
    title: 'Запись',
    icon: <Calendar size={20} />,
    description: 'Детали записи'
  },
  {
    id: 3,
    title: 'Оплата',
    icon: <CreditCard size={20} />,
    description: 'Способ оплаты'
  }];
  const handleActivationKeyDown = (event, onActivate) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onActivate();
    }
  };


  // Сброс данных при открытии
  useEffect(() => {
    if (isOpen) {
      setCurrentStep(1);
      setErrors({});
      setIsProcessing(false);
      setShowSuggestions(false);
      setSelectedPatientId(null);

      // Фокус на первое поле
      setTimeout(() => {
        if (fioRef.current) {
          fioRef.current.focus();
        }
      }, 100);
    }
  }, [isOpen]);

  // Валидация шагов
  const validateStep = (step) => {
    const newErrors = {};

    if (step === 1) {
      if (!(wizardData.patient?.fio || '').trim()) {
        newErrors.fio = 'Введите ФИО пациента';
      }
      if (!wizardData.patient?.birth_date) {
        newErrors.birth_date = 'Укажите дату рождения';
      }
      if (!(wizardData.patient?.phone || '').trim()) {
        newErrors.phone = 'Введите номер телефона';
      } else if (!/^\+?[0-9\s-()]{10,}$/.test(wizardData.patient?.phone || '')) {
        newErrors.phone = 'Некорректный формат телефона';
      }
    }

    if (step === 2) {
      // Проверяем, нужен ли врач для выбранных услуг
      const selectedServices = wizardData.appointment.services;
      const needsDoctor = selectedServices.some((serviceId) => {
        // Поиск услуги во всех категориях
        let service = null;
        for (const [, categoryServices] of Object.entries(services)) {
          const servicesArray = Array.isArray(categoryServices) ? categoryServices :
          categoryServices?.services || [];
          service = servicesArray.find((s) => (s.id || s.service_id) === serviceId);
          if (service) break;
        }

        // Услуги, которые НЕ требуют врача
        const serviceName = (service?.name || service?.service_name || '').toLowerCase();
        const nodoctorServices = ['экг', 'эхокг', 'анализ', 'процедур'];
        return !nodoctorServices.some((keyword) => serviceName.includes(keyword));
      });

      if (needsDoctor && !wizardData.appointment.doctor_id) {
        newErrors.doctor_id = 'Для выбранных услуг требуется врач';
      }

      if (wizardData.appointment.services.length === 0) {
        newErrors.services = 'Выберите минимум одну услугу';
      }
      if (!wizardData.appointment.date) {
        newErrors.date = 'Укажите дату приема';
      }
    }

    if (step === 3) {
      if (!wizardData.payment.method) {
        newErrors.method = 'Выберите способ оплаты';
      }
      if (!wizardData.payment.amount || wizardData.payment.amount <= 0) {
        newErrors.amount = 'Укажите сумму к оплате';
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // Поиск пациентов
  const searchPatients = async (query) => {
    if (query.length < 2) {
      setPatientSuggestions([]);
      setShowSuggestions(false);
      return;
    }

    try {
      // Здесь должен быть реальный API вызов
      // Пока используем заглушку
      const mockPatients = [
      {
        id: 1,
        fio: 'Иванов Иван Иванович',
        birth_date: '1985-05-15',
        phone: '+7 (999) 123-45-67',
        email: 'ivanov@example.com'
      },
      {
        id: 2,
        fio: 'Петрова Анна Сергеевна',
        birth_date: '1990-08-22',
        phone: '+7 (999) 234-56-78',
        email: 'petrova@example.com'
      }];


      const filtered = mockPatients.filter((p) =>
      p.fio.toLowerCase().includes(query.toLowerCase()) ||
      p.phone.includes(query)
      );

      setPatientSuggestions(filtered);
      setShowSuggestions(filtered.length > 0);
    } catch (error) {
      logger.error('Error searching patients:', error);
    }
  };

  // Обновление данных
  const updateWizardData = useCallback((section, field, value) => {
    setWizardData((prev) => ({
      ...prev,
      [section]: {
        ...prev[section],
        [field]: value
      }
    }));

    // Очистка ошибки при изменении поля
    setErrors((prev) => {
      if (prev[field]) {
        return { ...prev, [field]: null };
      }
      return prev;
    });
  }, []);

  // Простые стабильные обработчики без зависимостей
  const handleFioChange = useCallback((e) => {
    const value = e.target.value;
    setWizardData((prev) => ({
      ...prev,
      patient: { ...prev.patient, fio: value }
    }));
    // Поиск пациентов вызываем отдельно
    if (value.trim()) {
      searchPatients(value);
    }
  }, []);

  const handlePhoneChange = useCallback((e) => {
    let value = e.target.value.replace(/\D/g, ''); // Только цифры

    // Форматирование для Узбекистана +998-xx-xxx-xx-xx
    if (value.length === 0) {
      setWizardData((prev) => ({
        ...prev,
        patient: { ...prev.patient, phone: '' }
      }));
      return;
    }

    // Автоматически добавляем +998 если не указан код страны
    if (!value.startsWith('998')) {
      value = '998' + value;
    }

    // Форматирование
    let formatted = '+998';
    if (value.length > 3) {
      formatted += ' (' + value.slice(3, 5);
      if (value.length > 5) {
        formatted += ') ' + value.slice(5, 8);
        if (value.length > 8) {
          formatted += '-' + value.slice(8, 10);
          if (value.length > 10) {
            formatted += '-' + value.slice(10, 12);
          }
        }
      }
    }

    setWizardData((prev) => ({
      ...prev,
      patient: { ...prev.patient, phone: formatted }
    }));
  }, []);

  const handleBirthDateChange = useCallback((e) => {
    setWizardData((prev) => ({
      ...prev,
      patient: { ...prev.patient, birth_date: e.target.value }
    }));
  }, []);

  const handleAddressChange = useCallback((e) => {
    setWizardData((prev) => ({
      ...prev,
      patient: { ...prev.patient, address: e.target.value }
    }));
  }, []);

  // Навигация по шагам
  const goToStep = (step) => {
    if (step < currentStep || validateStep(currentStep)) {
      setCurrentStep(step);
    }
  };

  const nextStep = () => {
    if (validateStep(currentStep)) {
      if (currentStep < steps.length) {
        setCurrentStep(currentStep + 1);
      } else {
        handleComplete();
      }
    }
  };

  const prevStep = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1);
    }
  };

  // Завершение мастера
  const handleComplete = async () => {
    if (!validateStep(currentStep)) return;

    setIsProcessing(true);

    try {
      if (onComplete) {
        await onComplete(wizardData);
      }

      toast.success('Запись успешно создана!');
      onClose();
    } catch (error) {
      logger.error('Error completing wizard:', error);
      toast.error('Ошибка при создании записи: ' + error.message);
    } finally {
      setIsProcessing(false);
    }
  };


  // Вычисляем сумму с помощью useMemo для избежания бесконечного цикла
  const calculatedTotal = useMemo(() => {
    return wizardData.appointment.services.reduce((total, serviceId) => {
      // Поиск услуги во всех категориях с учетом разных форматов
      let service = null;
      for (const [, categoryServices] of Object.entries(services)) {
        const servicesArray = Array.isArray(categoryServices) ? categoryServices :
        categoryServices?.services || [];
        service = servicesArray.find((s) => (s.id || s.service_id) === serviceId);
        if (service) break;
      }
      return total + (service?.price || service?.cost || 0);
    }, 0);
  }, [wizardData.appointment.services, services]);

  // Проверка, есть ли введенные данные
  const hasUserData = useMemo(() => {
    const { patient, appointment } = wizardData;

    // Проверяем только значимые поля, которые пользователь мог изменить
    const hasPatientData = (patient?.fio || '').trim() !== '' ||
    (patient?.phone || '').trim() !== '' ||
    (patient?.birth_date || '').trim() !== '';

    const hasAppointmentData = (appointment?.services || []).length > 0 ||
    (appointment?.doctor_id || '').trim() !== '';

    return hasPatientData || hasAppointmentData;
  }, [wizardData]);

  // Безопасное закрытие с подтверждением
  const handleSafeClose = useCallback(() => {
    if (hasUserData && !isProcessing) {
      const shouldClose = window.confirm(
        'У вас есть несохраненные данные. Вы уверены, что хотите закрыть мастер регистрации?'
      );
      if (shouldClose) {
        onClose();
      }
    } else {
      onClose();
    }
  }, [hasUserData, isProcessing, onClose]);

  // Обработчик клавиши Escape
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && isOpen && !isProcessing) {
        e.preventDefault();
        handleSafeClose();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      return () => document.removeEventListener('keydown', handleEscape);
    }
  }, [isOpen, isProcessing, handleSafeClose]);

  const actions = [
  {
    label: 'Отмена',
    variant: 'secondary',
    onClick: handleSafeClose,
    disabled: isProcessing
  },
  ...(currentStep > 1 ? [{
    label: 'Назад',
    variant: 'secondary',
    icon: <ArrowLeft size={16} />,
    onClick: prevStep,
    disabled: isProcessing
  }] : []),
  {
    label: currentStep === steps.length ?
    isProcessing ? 'Создание...' : 'Создать запись' :
    'Далее',
    variant: 'primary',
    icon: currentStep === steps.length ?
    isProcessing ? null : <Check size={16} /> :
    <ArrowRight size={16} />,
    onClick: nextStep,
    disabled: isProcessing
  }];


  return (
    <ModernDialog
      isOpen={isOpen}
      onClose={handleSafeClose}
      title="Новая запись"
      actions={actions}
      maxWidth="42rem"
      closeOnBackdrop={false}
      closeOnEscape={false}
      className="appointment-wizard">
      
      <div className="wizard-container">
        {/* Индикатор шагов */}
        <div className="wizard-steps">
          {steps.map((step, index) => {
          const canNavigateStep = currentStep > step.id || currentStep === step.id;
          return <div
            key={step.id}
            className={`wizard-step ${currentStep === step.id ? 'active' : ''} ${currentStep > step.id ? 'completed' : ''}`}
            role="button"
            aria-disabled={!canNavigateStep}
            tabIndex={canNavigateStep ? 0 : -1}
            onClick={canNavigateStep ? () => goToStep(step.id) : undefined}
            onKeyDown={canNavigateStep ? (event) => handleActivationKeyDown(event, () => goToStep(step.id)) : undefined}
            style={{
              cursor: canNavigateStep ? 'pointer' : 'default'
            }}>
            
              <div className="step-icon">
                {currentStep > step.id ? <Check size={16} /> : step.icon}
              </div>
              <div className="step-content">
                <div className="step-title">{step.title}</div>
                <div className="step-description">{step.description}</div>
              </div>
              {index < steps.length - 1 && <div className="step-connector" />}
            </div>;
        })}
        </div>

        {/* Контент шагов */}
        <div className="wizard-content">
          {currentStep === 1 &&
          <PatientStep
            data={wizardData.patient}
            errors={errors}
            suggestions={patientSuggestions}
            showSuggestions={showSuggestions}
            onUpdate={(field, value) => updateWizardData('patient', field, value)}
            onSearch={searchPatients}
            handleFioChange={handleFioChange}
            handlePhoneChange={handlePhoneChange}
            handleBirthDateChange={handleBirthDateChange}
            handleAddressChange={handleAddressChange}
            onSelectPatient={(patient) => {
              setWizardData((prev) => ({
                ...prev,
                patient: {
                  ...patient,
                  birth_date: patient.birth_date || prev.patient.birth_date
                }
              }));
              setSelectedPatientId(patient.id);
              setShowSuggestions(false);
            }}
            fioRef={fioRef}
            phoneRef={phoneRef}
            theme={theme}
            getColor={getColor} />

          }

          {currentStep === 2 &&
          <AppointmentStep
            data={wizardData.appointment}
            errors={errors}
            doctors={doctors}
            services={services}
            onUpdate={(field, value) => updateWizardData('appointment', field, value)}
            theme={theme}
            getColor={getColor} />

          }

          {currentStep === 3 &&
          <PaymentStep
            data={wizardData.payment}
            errors={errors}
            total={calculatedTotal}
            onUpdate={(field, value) => updateWizardData('payment', field, value)}
            theme={theme}
            getColor={getColor} />

          }
        </div>
      </div>
    </ModernDialog>);

};

// Компонент шага "Пациент"
const PatientStep = React.memo(({
  data,
  errors,
  suggestions,
  showSuggestions,
  onSelectPatient,
  fioRef,
  phoneRef,
  getColor,
  handleFioChange,
  handlePhoneChange,
  handleBirthDateChange,
  handleAddressChange
}) =>
<div className="wizard-step-content">
    <h3 style={{ color: getColor('textPrimary'), marginBottom: '24px' }}>
      Данные пациента
    </h3>
    
    <div className="form-grid">
      {/* ФИО с поиском */}
      <div className="form-field full-width">
        <label>ФИО пациента *</label>
        <div className="search-field">
          <input
          key="fio-input"
          ref={fioRef}
          type="text"
          value={data.fio}
          onChange={handleFioChange}
          placeholder="Введите ФИО для поиска..."
          className={errors.fio ? 'error' : ''} />
        
          <Search size={16} className="search-icon" />
          
          {showSuggestions && suggestions.length > 0 &&
        <div className="suggestions-dropdown">
              {suggestions.map((patient) =>
          <div
            key={patient.id}
            className="suggestion-item"
            role="button"
            tabIndex={0}
            onClick={() => onSelectPatient(patient)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                onSelectPatient(patient);
              }
            }}>
            
                  <div className="suggestion-name">{patient.fio}</div>
                  <div className="suggestion-details">
                    {patient.phone} • {patient.birth_date}
                  </div>
                </div>
          )}
            </div>
        }
        </div>
        {errors.fio && <span className="error-text">{errors.fio}</span>}
      </div>

      {/* Дата рождения */}
      <div className="form-field">
        <label>Дата рождения *</label>
          <input
        key="birth-date-input"
        type="date"
        value={data.birth_date}
        onChange={handleBirthDateChange}
        className={errors.birth_date ? 'error' : ''} />
      
        {errors.birth_date && <span className="error-text">{errors.birth_date}</span>}
      </div>


      {/* Телефон */}
      <div className="form-field">
        <label>Телефон *</label>
        <div className="input-with-icon">
          <Phone size={16} className="input-icon" />
            <input
          key="phone-input"
          ref={phoneRef}
          type="tel"
          value={data.phone}
          onChange={handlePhoneChange}
          placeholder="+998-xx-xxx-xx-xx"
          className={errors.phone ? 'error' : ''}
          maxLength={17} />
        
        </div>
        {errors.phone && <span className="error-text">{errors.phone}</span>}
      </div>


      {/* Адрес */}
      <div className="form-field full-width">
        <label>Адрес</label>
        <div className="input-with-icon">
          <MapPin size={16} className="input-icon" />
          <input
          key="address-input"
          type="text"
          value={data.address}
          onChange={handleAddressChange}
          placeholder="Адрес проживания" />
        
        </div>
      </div>
    </div>
  </div>
);
PatientStep.displayName = 'PatientStep';

// Компонент шага "Запись"
const AppointmentStep = ({
  data,
  errors,
  doctors,
  services,
  onUpdate,
  getColor
}) =>
<div className="wizard-step-content">
    <h3 style={{ color: getColor('textPrimary'), marginBottom: '24px' }}>
      Детали записи
    </h3>
    
    <div className="form-grid">
      {/* Врач */}
      <div className="form-field full-width">
        <label>Врач {data.services.some((serviceId) => {
          // Проверяем, нужен ли врач для выбранных услуг
          let service = null;
          for (const [, categoryServices] of Object.entries(services)) {
            const servicesArray = Array.isArray(categoryServices) ? categoryServices :
            categoryServices?.services || [];
            service = servicesArray.find((s) => (s.id || s.service_id) === serviceId);
            if (service) break;
          }
          const serviceName = (service?.name || service?.service_name || '').toLowerCase();
          // Услуги, которые НЕ требуют врача (можно выполнить без консультации)
          const nodoctorServices = ['экг', 'эхокг', 'анализ', 'физиотерапия', 'массаж', 'ингаляция'];
          // Если название услуги содержит "с консультацией", то врач нужен
          if (serviceName.includes('с консультацией')) return true;
          // Иначе проверяем, есть ли в названии ключевые слова услуг без врача
          return !nodoctorServices.some((keyword) => serviceName.includes(keyword));
        }) ? '*' : '(необязательно)'}</label>
        <select
        value={data.doctor_id}
        onChange={(e) => onUpdate('doctor_id', e.target.value)}
        className={errors.doctor_id ? 'error' : ''}>
        
          <option value="">Выберите врача</option>
          {doctors.map((doctor) => {
          const doctorName = doctor.full_name || doctor.name || (
          doctor.first_name && doctor.last_name ? `${doctor.first_name} ${doctor.last_name}` : '') ||
          doctor.username || `Врач #${doctor.id}`;
          const specialty = doctor.specialization || doctor.department || doctor.specialty || '';
          return (
            <option key={doctor.id} value={doctor.id}>
                {doctorName}{specialty ? ` - ${specialty}` : ''}
              </option>);

        })}
        </select>
        {errors.doctor_id && <span className="error-text">{errors.doctor_id}</span>}
      </div>

      {/* Дата и время */}
      <div className="form-field">
        <label>Дата приема *</label>
          <input
        key="appointment-date-input"
        type="date"
        value={data.date}
        onChange={(e) => onUpdate('date', e.target.value)}
        min={new Date().toISOString().split('T')[0]}
        className={errors.date ? 'error' : ''} />
      
        {errors.date && <span className="error-text">{errors.date}</span>}
      </div>

      <div className="form-field">
        <label>Время</label>
        <input
        type="time"
        value={data.time}
        onChange={(e) => onUpdate('time', e.target.value)} />
      
      </div>

      {/* Тип визита */}
      <div className="form-field">
        <label>Тип обращения</label>
        <select
        value={data.visit_type}
        onChange={(e) => onUpdate('visit_type', e.target.value)}>
        
          <option value="Платный">Платный</option>
          <option value="Повторный">Повторный</option>
          <option value="Льготный">Льготный</option>
        </select>
      </div>

      {/* Услуги */}
      <div className="form-field full-width">
        <label>Услуги *</label>
        <div className="services-grid">
          {Object.entries(services).map(([category, categoryServices]) => {
          // Обработка разных форматов данных услуг
          const servicesArray = Array.isArray(categoryServices) ? categoryServices :
          categoryServices?.services || [];

          return (
            <div key={category} className="service-category">
                <h4 className="category-title">{category}</h4>
                {servicesArray.map((service) =>
              <label key={service.id || service.service_id} className="service-item">
                    <input
                  type="checkbox"
                  checked={data.services.includes(service.id || service.service_id)}
                  onChange={(e) => {
                    const serviceId = service.id || service.service_id;
                    const newServices = e.target.checked ?
                    [...data.services, serviceId] :
                    data.services.filter((id) => id !== serviceId);
                    onUpdate('services', newServices);
                  }} />
                
                    <span className="service-name">{service.name || service.service_name}</span>
                    <span className="service-price">{(service.price || service.cost || 0).toLocaleString()} ₽</span>
                  </label>
              )}
              </div>);

        })}
        </div>
        {errors.services && <span className="error-text">{errors.services}</span>}
      </div>

      {/* Примечания */}
      <div className="form-field full-width">
        <label>Примечания</label>
        <textarea
        value={data.notes}
        onChange={(e) => onUpdate('notes', e.target.value)}
        placeholder="Дополнительная информация..."
        rows={3} />
      
      </div>
    </div>
  </div>;


// Компонент шага "Оплата"
const PaymentStep = ({
  data,
  errors,
  total,
  onUpdate,
  getColor
}) =>
<div className="wizard-step-content">
    <h3 style={{ color: getColor('textPrimary'), marginBottom: '24px' }}>
      Оплата услуг
    </h3>
    
    <div className="form-grid">
      {/* Итоговая сумма */}
      <div className="form-field full-width">
        <div className="total-summary">
          <div className="total-label">Итого к оплате:</div>
          <div className="total-amount">{total.toLocaleString()} ₽</div>
        </div>
      </div>

      {/* Способ оплаты */}
      <div className="form-field full-width">
        <label>Способ оплаты *</label>
        <div className="payment-methods">
          {[
        { value: 'Карта', label: 'Банковская карта', icon: '💳' },
        { value: 'Наличные', label: 'Наличные', icon: '💵' },
        { value: 'Перевод', label: 'Банковский перевод', icon: '📱' },
        { value: 'Онлайн', label: 'Онлайн платеж', icon: '🌐' }].
        map((method) =>
        <label key={method.value} className="payment-method">
              <input
            type="radio"
            name="payment_method"
            value={method.value}
            checked={data.method === method.value}
            onChange={(e) => onUpdate('method', e.target.value)} />
          
              <div className="method-content">
                <span className="method-icon">{method.icon}</span>
                <span className="method-label">{method.label}</span>
              </div>
            </label>
        )}
        </div>
        {errors.method && <span className="error-text">{errors.method}</span>}
      </div>

      {/* Сумма к оплате */}
      <div className="form-field">
        <label>Сумма к оплате *</label>
        <input
        type="number"
        value={data.amount}
        onChange={(e) => onUpdate('amount', parseFloat(e.target.value) || 0)}
        min="0"
        step="0.01"
        className={errors.amount ? 'error' : ''} />
      
        {errors.amount && <span className="error-text">{errors.amount}</span>}
      </div>
    </div>
  </div>;

AppointmentWizard.propTypes = {
  isOpen: PropTypes.bool,
  onClose: PropTypes.func,
  onComplete: PropTypes.func,
  doctors: PropTypes.array,
  services: PropTypes.object,
  initialData: PropTypes.object
};

PatientStep.propTypes = {
  data: PropTypes.object,
  errors: PropTypes.object,
  suggestions: PropTypes.array,
  showSuggestions: PropTypes.bool,
  onSearch: PropTypes.func,
  onSelectPatient: PropTypes.func,
  onUpdate: PropTypes.func,
  searchRef: PropTypes.any,
  fioRef: PropTypes.any,
  phoneRef: PropTypes.any,
  handleFioChange: PropTypes.func,
  handlePhoneChange: PropTypes.func,
  handleBirthDateChange: PropTypes.func,
  handleAddressChange: PropTypes.func,
  getColor: PropTypes.func
};

AppointmentStep.propTypes = {
  data: PropTypes.object,
  errors: PropTypes.object,
  doctors: PropTypes.array,
  services: PropTypes.object,
  onUpdate: PropTypes.func,
  getColor: PropTypes.func
};

PaymentStep.propTypes = {
  data: PropTypes.object,
  errors: PropTypes.object,
  total: PropTypes.number,
  onUpdate: PropTypes.func,
  getColor: PropTypes.func
};


export default AppointmentWizard;
