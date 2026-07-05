import { api } from '../../api/client';
import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import logger from '../../utils/logger';
import { getApiOrigin } from '../../api/runtime';
import tokenManager from '../../utils/tokenManager';
import {
  Calendar,
  Clock,
  User,



  X,
  Plus,
  Trash2,
  CheckCircle,
  AlertCircle } from
'lucide-react';

/**
 * Универсальный компонент для назначения следующих визитов
 * Используется во всех панелях врачей
 */
const ScheduleNextModal = ({
  isOpen,
  onClose,
  onSuccess,
  patient,
  theme,
  specialtyFilter = null // Фильтр услуг по специальности
}) => {
  const { getColor, getSpacing, getFontSize } = theme;

  // Состояния формы
  const [formData, setFormData] = useState({
    patient_id: '',
    visit_date: '',
    visit_time: '',
    services: [{ service_id: '', quantity: 1 }],
    discount_mode: 'none',
    all_free: false,
    confirmation_channel: 'telegram'
  });

  const [patients, setPatients] = useState([]);
  const [services, setServices] = useState([]);
  const [filteredServices, setFilteredServices] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Загрузка данных при открытии модала
  useEffect(() => {
    if (isOpen) {
      loadPatients();
      loadServices();

      // Если передан пациент, устанавливаем его
      if (patient) {
        setFormData((prev) => ({ ...prev, patient_id: patient.id }));
      }
    }
  }, [isOpen, patient]);

  // Фильтрация услуг по специальности
  useEffect(() => {
    if (services.length > 0) {
      let filtered = services;

      // Применяем фильтр по специальности если указан
      if (specialtyFilter) {
        filtered = services.filter((service) => {
          const category = service.category?.toLowerCase();
          const name = service.name?.toLowerCase();

          switch (specialtyFilter) {
            case 'cardiology':
              return category?.includes('кардио') ||
              name?.includes('кардио') ||
              name?.includes('экг') ||
              service.code?.startsWith('K');
            case 'dermatology':
              return category?.includes('дерма') ||
              name?.includes('дерма') ||
              name?.includes('кожа') ||
              service.code?.startsWith('D');
            case 'dentistry':
              return category?.includes('стомат') ||
              name?.includes('зуб') ||
              name?.includes('стомат') ||
              service.code?.startsWith('S');
            default:
              return true;
          }
        });
      }

      setFilteredServices(filtered);
    }
  }, [services, specialtyFilter]);

  const loadPatients = async () => {
    try {
      const token = tokenManager.getAccessToken();
      const apiBase = getApiOrigin();
      const response = await fetch('patients/', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setPatients(data);
      }
    } catch (err) {
      logger.error('Ошибка загрузки пациентов:', err);
    }
  };

  const loadServices = async () => {
    try {
      const token = tokenManager.getAccessToken();
      const apiBase = getApiOrigin();
      const response = await fetch('services', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setServices(data);
      }
    } catch (err) {
      logger.error('Ошибка загрузки услуг:', err);
    }
  };

  const handleInputChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    setError('');
  };

  const handleServiceChange = (index, field, value) => {
    const newServices = [...formData.services];
    newServices[index] = { ...newServices[index], [field]: value };
    setFormData((prev) => ({ ...prev, services: newServices }));
  };

  const addService = () => {
    setFormData((prev) => ({
      ...prev,
      services: [...prev.services, { service_id: '', quantity: 1 }]
    }));
  };

  const removeService = (index) => {
    if (formData.services.length > 1) {
      const newServices = formData.services.filter((_, i) => i !== index);
      setFormData((prev) => ({ ...prev, services: newServices }));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccess('');

    try {
      // Валидация
      if (!formData.patient_id) {
        throw new Error('Выберите пациента');
      }
      if (!formData.visit_date) {
        throw new Error('Выберите дату визита');
      }
      if (formData.services.some((s) => !s.service_id)) {
        throw new Error('Выберите все услуги');
      }

      const token = tokenManager.getAccessToken();
      const apiBase = getApiOrigin();
      const response = await fetch('doctor/visits/schedule-next', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(formData)
      });

      if (response.ok) {
        const result = await response.json();
        const normalizedFormData = {
          ...formData,
          patient_id: formData.patient_id ? Number(formData.patient_id) : null,
          services: formData.services.map((service) => ({
            ...service,
            service_id: service.service_id ? Number(service.service_id) : service.service_id,
            quantity: Number(service.quantity || 1)
          }))
        };

        logger.info('[DOC-05] schedule-next succeeded', {
          visitId: result?.visit_id,
          patientId: normalizedFormData.patient_id,
          confirmationChannel: result?.confirmation?.channel || normalizedFormData.confirmation_channel
        });

        if (typeof onSuccess === 'function') {
          try {
            onSuccess(result, normalizedFormData);
          } catch (callbackError) {
            logger.error('[DOC-05] schedule-next success callback failed', callbackError);
          }
        }

        setSuccess(`Визит успешно назначен! Токен подтверждения: ${result.confirmation.token}`);

        // Сброс формы через 2 секунды
        setTimeout(() => {
          onClose();
          resetForm();
        }, 2000);
      } else {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Ошибка при создании визита');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const resetForm = () => {
    setFormData({
      patient_id: '',
      visit_date: '',
      visit_time: '',
      services: [{ service_id: '', quantity: 1 }],
      discount_mode: 'none',
      all_free: false,
      confirmation_channel: 'telegram'
    });
    setError('');
    setSuccess('');
  };

  if (!isOpen) return null;

  // Стили
  const overlayStyle = {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'color-mix(in srgb, black, transparent 50%)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
    padding: getSpacing('md')
  };

  const modalStyle = {
    backgroundColor: getColor('background'),
    borderRadius: '16px',
    padding: getSpacing('xl'),
    maxWidth: '600px',
    width: '100%',
    maxHeight: '90vh',
    overflowY: 'auto',
    boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'
  };

  const headerStyle = {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: getSpacing('lg'),
    paddingBottom: getSpacing('md'),
    borderBottom: `1px solid ${getColor('border')}`
  };

  const titleStyle = {
    fontSize: getFontSize('xl'),
    fontWeight: '700',
    color: getColor('text'),
    margin: 0
  };

  const closeButtonStyle = {
    background: 'none',
    border: 'none',
    color: getColor('text-secondary'),
    cursor: 'pointer',
    padding: getSpacing('sm'),
    borderRadius: '8px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center'
  };

  const formGroupStyle = {
    marginBottom: getSpacing('lg')
  };

  const labelStyle = {
    display: 'block',
    fontSize: getFontSize('sm'),
    fontWeight: '600',
    color: getColor('text'),
    marginBottom: getSpacing('sm')
  };

  const inputStyle = {
    width: '100%',
    padding: getSpacing('md'),
    border: `1px solid ${getColor('border')}`,
    borderRadius: '8px',
    fontSize: getFontSize('sm'),
    backgroundColor: getColor('background'),
    color: getColor('text')
  };

  const selectStyle = {
    ...inputStyle,
    cursor: 'pointer'
  };

  const buttonStyle = {
    padding: `${getSpacing('md')} ${getSpacing('lg')}`,
    border: 'none',
    borderRadius: '8px',
    fontSize: getFontSize('sm'),
    fontWeight: '600',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    gap: getSpacing('sm')
  };

  const primaryButtonStyle = {
    ...buttonStyle,
    backgroundColor: getColor('primary'),
    color: 'white'
  };

  const secondaryButtonStyle = {
    ...buttonStyle,
    backgroundColor: getColor('secondary'),
    color: getColor('text')
  };

  const dangerButtonStyle = {
    ...buttonStyle,
    backgroundColor: getColor('danger'),
    color: 'white'
  };

  const serviceRowStyle = {
    display: 'flex',
    gap: getSpacing('md'),
    alignItems: 'end',
    marginBottom: getSpacing('md')
  };

  const alertStyle = {
    padding: getSpacing('md'),
    borderRadius: '8px',
    marginBottom: getSpacing('lg'),
    display: 'flex',
    alignItems: 'center',
    gap: getSpacing('sm')
  };

  const errorStyle = {
    ...alertStyle,
    backgroundColor: getColor('danger-light'),
    color: getColor('danger'),
    border: `1px solid ${getColor('danger')}`
  };

  const successStyle = {
    ...alertStyle,
    backgroundColor: getColor('success-light'),
    color: getColor('success'),
    border: `1px solid ${getColor('success')}`
  };

  // Определяем заголовок в зависимости от специальности
  const getModalTitle = () => {
    switch (specialtyFilter) {
      case 'cardiology':
        return 'Назначить следующий визит - Кардиология';
      case 'dermatology':
        return 'Назначить следующий визит - Дерматология';
      case 'dentistry':
        return 'Назначить следующий визит - Стоматология';
      default:
        return 'Назначить следующий визит';
    }
  };
  const handleActivationKeyDown = (event, action) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      action();
    }
  };

  return (
    <div
      style={overlayStyle}
      role="button"
      tabIndex={0}
      onClick={onClose}
      onKeyDown={(event) => handleActivationKeyDown(event, onClose)}>
      <div style={modalStyle} onClickCapture={(e) => e.stopPropagation()}>
        {/* Заголовок */}
        <div style={headerStyle}>
          <h2 style={titleStyle}>{getModalTitle()}</h2>
          <button
            style={closeButtonStyle}
            onClick={onClose}
            aria-label="Close schedule next visit modal"
          >
            <X size={20} />
          </button>
        </div>

        {/* Сообщения об ошибках и успехе */}
        {error &&
        <div style={errorStyle}>
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        }

        {success &&
        <div style={successStyle}>
            <CheckCircle size={16} />
            <span>{success}</span>
          </div>
        }

        {/* Форма */}
        <form onSubmit={handleSubmit}>
          {/* Пациент */}
          <div style={formGroupStyle}>
            <label htmlFor="schedule-next-patient" style={labelStyle}>
              <User size={16} style={{ display: 'inline', marginRight: getSpacing('xs') }} />
              Пациент
            </label>
            <select
              id="schedule-next-patient"
              aria-label="Schedule next visit patient"
              style={selectStyle}
              value={formData.patient_id}
              onChange={(e) => handleInputChange('patient_id', e.target.value)}
              required>
              
              <option value="">Выберите пациента</option>
              {patients.map((p) =>
              <option key={p.id} value={p.id}>
                  {p.first_name} {p.last_name} - {p.phone}
                </option>
              )}
            </select>
          </div>

          {/* Дата и время */}
          <div style={{ display: 'flex', gap: getSpacing('md') }}>
            <div style={{ ...formGroupStyle, flex: 1 }}>
              <label htmlFor="schedule-next-visit-date" style={labelStyle}>
                <Calendar size={16} style={{ display: 'inline', marginRight: getSpacing('xs') }} />
                Дата визита
              </label>
              <input
                id="schedule-next-visit-date"
                type="date"
                aria-label="Schedule next visit date"
                style={inputStyle}
                value={formData.visit_date}
                onChange={(e) => handleInputChange('visit_date', e.target.value)}
                min={new Date().toISOString().split('T')[0]}
                required />
              
            </div>

            <div style={{ ...formGroupStyle, flex: 1 }}>
              <label htmlFor="schedule-next-visit-time" style={labelStyle}>
                <Clock size={16} style={{ display: 'inline', marginRight: getSpacing('xs') }} />
                Время
              </label>
              <input
                id="schedule-next-visit-time"
                type="time"
                aria-label="Schedule next visit time"
                style={inputStyle}
                value={formData.visit_time}
                onChange={(e) => handleInputChange('visit_time', e.target.value)}
                required />
              
            </div>
          </div>

          {/* Услуги */}
          <div style={formGroupStyle}>
            <label style={labelStyle}>
              Услуги {specialtyFilter && `(${specialtyFilter === 'cardiology' ? 'Кардиология' :
              specialtyFilter === 'dermatology' ? 'Дерматология' :
              specialtyFilter === 'dentistry' ? 'Стоматология' : ''})`}
            </label>
            {formData.services.map((service, index) =>
            <div key={index} style={serviceRowStyle}>
                <div style={{ flex: 2 }}>
                  <select
                  id={`schedule-next-service-${index}`}
                  aria-label={`Schedule next visit service ${index + 1}`}
                  style={selectStyle}
                  value={service.service_id}
                  onChange={(e) => handleServiceChange(index, 'service_id', e.target.value)}
                  required>
                  
                    <option value="">Выберите услугу</option>
                    {filteredServices.map((s) =>
                  <option key={s.id} value={s.id}>
                        {s.name} - {s.price} сум
                      </option>
                  )}
                  </select>
                </div>
                <div style={{ flex: 1 }}>
                  <input
                  id={`schedule-next-service-quantity-${index}`}
                  type="number"
                  aria-label={`Schedule next visit service ${index + 1} quantity`}
                  style={inputStyle}
                  value={service.quantity}
                  onChange={(e) => handleServiceChange(index, 'quantity', parseInt(e.target.value))}
                  min="1"
                  placeholder="Кол-во" />
                
                </div>
                <button
                type="button"
                style={dangerButtonStyle}
                onClick={() => removeService(index)}
                disabled={formData.services.length === 1}
                aria-label={`Remove service ${index + 1}`}>
                
                  <Trash2 size={16} />
                </button>
              </div>
            )}
            <button
              type="button"
              style={secondaryButtonStyle}
              onClick={addService}>
              
              <Plus size={16} />
              Добавить услугу
            </button>
          </div>

          {/* Тип визита */}
          <div style={formGroupStyle}>
            <label htmlFor="schedule-next-discount-mode" style={labelStyle}>Тип визита</label>
            <select
              id="schedule-next-discount-mode"
              aria-label="Schedule next visit type"
              style={selectStyle}
              value={formData.discount_mode}
              onChange={(e) => handleInputChange('discount_mode', e.target.value)}>
              
              <option value="none">Платный</option>
              <option value="repeat">Повторный</option>
              <option value="benefit">Льготный</option>
            </select>
          </div>

          {/* Канал подтверждения */}
          <div style={formGroupStyle}>
            <label htmlFor="schedule-next-confirmation-channel" style={labelStyle}>Канал подтверждения</label>
            <select
              id="schedule-next-confirmation-channel"
              aria-label="Schedule next visit confirmation channel"
              style={selectStyle}
              value={formData.confirmation_channel}
              onChange={(e) => handleInputChange('confirmation_channel', e.target.value)}>
              
              <option value="telegram">
                📱 Telegram
              </option>
              <option value="pwa">
                📲 PWA (мобильное приложение)
              </option>
              <option value="phone">
                📞 Телефон (регистратура)
              </option>
            </select>
          </div>

          {/* Кнопки */}
          <div style={{ display: 'flex', gap: getSpacing('md'), justifyContent: 'flex-end' }}>
            <button
              type="button"
              style={secondaryButtonStyle}
              onClick={onClose}
              disabled={loading}>
              
              Отмена
            </button>
            <button
              type="submit"
              style={primaryButtonStyle}
              disabled={loading}>
              
              {loading ? 'Создание...' : 'Назначить визит'}
            </button>
          </div>
        </form>
      </div>
    </div>);

};

ScheduleNextModal.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onSuccess: PropTypes.func,
  patient: PropTypes.shape({
    id: PropTypes.oneOfType([PropTypes.string, PropTypes.number])
  }),
  theme: PropTypes.shape({
    getColor: PropTypes.func.isRequired,
    getSpacing: PropTypes.func.isRequired,
    getFontSize: PropTypes.func.isRequired
  }).isRequired,
  specialtyFilter: PropTypes.oneOf(['cardiology', 'dermatology', 'dentistry', null])
};

export default ScheduleNextModal;
