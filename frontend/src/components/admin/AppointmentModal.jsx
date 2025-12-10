import React, { useState, useEffect } from 'react';
import { X, Save, Calendar, Clock, User, Stethoscope, AlertCircle, Phone, Mail } from 'lucide-react';
import logger from '../../utils/logger';
import { 
  MacOSCard, 
  MacOSButton, 
  MacOSInput,
  MacOSSelect,
  MacOSTextarea,
  MacOSModal
} from '../ui/macos';

const AppointmentModal = ({ 
  isOpen, 
  onClose, 
  appointment = null, 
  onSave, 
  loading = false,
  doctors = [],
  patients = []
}) => {
  const [formData, setFormData] = useState({
    patientId: '',
    doctorId: '',
    appointmentDate: '',
    appointmentTime: '',
    duration: 30,
    status: 'pending',
    reason: '',
    notes: '',
    phone: '',
    email: ''
  });
  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Инициализация формы при открытии
  useEffect(() => {
    if (isOpen) {
      if (appointment) {
        setFormData({
          patientId: appointment.patientId || '',
          doctorId: appointment.doctorId || '',
          appointmentDate: appointment.appointmentDate || '',
          appointmentTime: appointment.appointmentTime || '',
          duration: appointment.duration || 30,
          status: appointment.status || 'pending',
          reason: appointment.reason || '',
          notes: appointment.notes || '',
          phone: appointment.phone || '',
          email: appointment.email || ''
        });
      } else {
        // Устанавливаем завтрашний день по умолчанию
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        const tomorrowStr = tomorrow.toISOString().split('T')[0];
        
        setFormData({
          patientId: '',
          doctorId: '',
          appointmentDate: tomorrowStr,
          appointmentTime: '09:00',
          duration: 30,
          status: 'pending',
          reason: '',
          notes: '',
          phone: '',
          email: ''
        });
      }
      setErrors({});
    }
  }, [isOpen, appointment]);

  const validateForm = () => {
    const newErrors = {};

    if (!formData.patientId) {
      newErrors.patientId = 'Пациент обязателен';
    }

    if (!formData.doctorId) {
      newErrors.doctorId = 'Врач обязателен';
    }

    if (!formData.appointmentDate) {
      newErrors.appointmentDate = 'Дата записи обязательна';
    } else {
      const appointmentDate = new Date(formData.appointmentDate);
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      
      if (appointmentDate < today) {
        newErrors.appointmentDate = 'Дата записи не может быть в прошлом';
      }
    }

    if (!formData.appointmentTime) {
      newErrors.appointmentTime = 'Время записи обязательно';
    }

    if (!formData.reason.trim()) {
      newErrors.reason = 'Причина обращения обязательна';
    }

    if (formData.duration < 15 || formData.duration > 120) {
      newErrors.duration = 'Длительность должна быть от 15 до 120 минут';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!validateForm()) return;

    setIsSubmitting(true);
    try {
      const appointmentData = {
        patientId: parseInt(formData.patientId),
        doctorId: parseInt(formData.doctorId),
        appointmentDate: formData.appointmentDate,
        appointmentTime: formData.appointmentTime,
        duration: parseInt(formData.duration),
        status: formData.status,
        reason: formData.reason.trim(),
        notes: formData.notes.trim() || null,
        phone: formData.phone.trim() || null,
        email: formData.email.trim() || null
      };

      await onSave(appointmentData);
      onClose();
    } catch (error) {
      logger.error('Ошибка сохранения записи:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: null }));
    }
  };

  const getPatientName = (patientId) => {
    const patient = patients.find(p => p.id === parseInt(patientId));
    return patient ? `${patient.lastName} ${patient.firstName} ${patient.middleName}` : '';
  };

  const getDoctorName = (doctorId) => {
    const doctor = doctors.find(d => d.id === parseInt(doctorId));
    return doctor ? `${doctor.name} (${doctor.specialization})` : '';
  };

  if (!isOpen) return null;

  return (
    <MacOSModal
      isOpen={isOpen}
      onClose={onClose}
      title={appointment ? 'Редактировать запись' : 'Создать запись на прием'}
      size="lg"
    >
          {/* Форма */}
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Основная информация */}
            <div style={{ marginBottom: '24px' }}>
              <h3 style={{ 
                fontSize: 'var(--mac-font-size-lg)', 
                fontWeight: 'var(--mac-font-weight-semibold)', 
                color: 'var(--mac-text-primary)',
                marginBottom: '16px'
              }}>
                Основная информация
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '16px' }}>
                {/* Пациент */}
                <div>
                  <label style={{ 
                    display: 'block', 
                    fontSize: 'var(--mac-font-size-sm)', 
                    fontWeight: 'var(--mac-font-weight-medium)', 
                    color: 'var(--mac-text-primary)',
                    marginBottom: '8px'
                  }}>
                    Пациент *
                  </label>
                  <MacOSSelect
                    value={formData.patientId}
                    onChange={(e) => handleChange('patientId', e.target.value)}
                    options={[
                      { value: '', label: 'Выберите пациента' },
                      ...patients.map(patient => ({
                        value: patient.id,
                        label: `${patient.lastName} ${patient.firstName} ${patient.middleName} - ${patient.phone}`
                      }))
                    ]}
                    error={errors.patientId}
                    icon={<User style={{ width: '16px', height: '16px' }} />}
                  />
                  {errors.patientId && (
                    <p style={{ 
                      fontSize: 'var(--mac-font-size-xs)', 
                      color: 'var(--mac-error)', 
                      marginTop: '4px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px'
                    }}>
                      <AlertCircle style={{ width: '14px', height: '14px' }} />
                      {errors.patientId}
                    </p>
                  )}
                </div>

                {/* Врач */}
                <div>
                  <label style={{ 
                    display: 'block', 
                    fontSize: 'var(--mac-font-size-sm)', 
                    fontWeight: 'var(--mac-font-weight-medium)', 
                    color: 'var(--mac-text-primary)',
                    marginBottom: '8px'
                  }}>
                    Врач *
                  </label>
                  <MacOSSelect
                    value={formData.doctorId}
                    onChange={(e) => handleChange('doctorId', e.target.value)}
                    options={[
                      { value: '', label: 'Выберите врача' },
                      ...doctors.map(doctor => ({
                        value: doctor.id,
                        label: `${doctor.name} - ${doctor.specialization}`
                      }))
                    ]}
                    error={errors.doctorId}
                    icon={<Stethoscope style={{ width: '16px', height: '16px' }} />}
                  />
                  {errors.doctorId && (
                    <p style={{ 
                      fontSize: 'var(--mac-font-size-xs)', 
                      color: 'var(--mac-error)', 
                      marginTop: '4px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px'
                    }}>
                      <AlertCircle style={{ width: '14px', height: '14px' }} />
                      {errors.doctorId}
                    </p>
                  )}
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
                {/* Дата записи */}
                <div>
                  <label style={{ 
                    display: 'block', 
                    fontSize: 'var(--mac-font-size-sm)', 
                    fontWeight: 'var(--mac-font-weight-medium)', 
                    color: 'var(--mac-text-primary)',
                    marginBottom: '8px'
                  }}>
                    Дата записи *
                  </label>
                  <MacOSInput
                    type="date"
                    value={formData.appointmentDate}
                    onChange={(e) => handleChange('appointmentDate', e.target.value)}
                    error={errors.appointmentDate}
                    icon={Calendar}
                  />
                  {errors.appointmentDate && (
                    <p style={{ 
                      fontSize: 'var(--mac-font-size-xs)', 
                      color: 'var(--mac-error)', 
                      marginTop: '4px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px'
                    }}>
                      <AlertCircle style={{ width: '14px', height: '14px' }} />
                      {errors.appointmentDate}
                    </p>
                  )}
                </div>

                {/* Время записи */}
                <div>
                  <label style={{ 
                    display: 'block', 
                    fontSize: 'var(--mac-font-size-sm)', 
                    fontWeight: 'var(--mac-font-weight-medium)', 
                    color: 'var(--mac-text-primary)',
                    marginBottom: '8px'
                  }}>
                    Время записи *
                  </label>
                  <MacOSInput
                    type="time"
                    value={formData.appointmentTime}
                    onChange={(e) => handleChange('appointmentTime', e.target.value)}
                    error={errors.appointmentTime}
                    icon={Clock}
                  />
                  {errors.appointmentTime && (
                    <p style={{ 
                      fontSize: 'var(--mac-font-size-xs)', 
                      color: 'var(--mac-error)', 
                      marginTop: '4px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px'
                    }}>
                      <AlertCircle style={{ width: '14px', height: '14px' }} />
                      {errors.appointmentTime}
                    </p>
                  )}
                </div>

                {/* Длительность */}
                <div>
                  <label style={{ 
                    display: 'block', 
                    fontSize: 'var(--mac-font-size-sm)', 
                    fontWeight: 'var(--mac-font-weight-medium)', 
                    color: 'var(--mac-text-primary)',
                    marginBottom: '8px'
                  }}>
                    Длительность (мин)
                  </label>
                  <MacOSInput
                    type="number"
                    value={formData.duration}
                    onChange={(e) => handleChange('duration', e.target.value)}
                    error={errors.duration}
                    min="15"
                    max="120"
                    step="15"
                  />
                  {errors.duration && (
                    <p style={{ 
                      fontSize: 'var(--mac-font-size-xs)', 
                      color: 'var(--mac-error)', 
                      marginTop: '4px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px'
                    }}>
                      <AlertCircle style={{ width: '14px', height: '14px' }} />
                      {errors.duration}
                    </p>
                  )}
                </div>
              </div>

              {/* Статус */}
              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)',
                  marginBottom: '8px'
                }}>
                  Статус записи
                </label>
                <MacOSSelect
                  value={formData.status}
                  onChange={(e) => handleChange('status', e.target.value)}
                  options={[
                    { value: 'pending', label: 'Ожидает' },
                    { value: 'confirmed', label: 'Подтверждена' },
                    { value: 'paid', label: 'Оплачена' },
                    { value: 'in_visit', label: 'На приеме' },
                    { value: 'completed', label: 'Завершена' },
                    { value: 'cancelled', label: 'Отменена' },
                    { value: 'no_show', label: 'Не явился' }
                  ]}
                />
              </div>
            </div>

            {/* Детали записи */}
            <div style={{ marginBottom: '24px' }}>
              <h3 style={{ 
                fontSize: 'var(--mac-font-size-lg)', 
                fontWeight: 'var(--mac-font-weight-semibold)', 
                color: 'var(--mac-text-primary)',
                marginBottom: '16px'
              }}>
                Детали записи
              </h3>
              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)',
                  marginBottom: '8px'
                }}>
                  Причина обращения *
                </label>
                <MacOSTextarea
                  value={formData.reason}
                  onChange={(e) => handleChange('reason', e.target.value)}
                  error={errors.reason}
                  rows={3}
                  placeholder="Опишите причину обращения к врачу"
                />
                {errors.reason && (
                  <p style={{ 
                    fontSize: 'var(--mac-font-size-xs)', 
                    color: 'var(--mac-error)', 
                    marginTop: '4px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}>
                    <AlertCircle style={{ width: '14px', height: '14px' }} />
                    {errors.reason}
                  </p>
                )}
              </div>

              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)',
                  marginBottom: '8px'
                }}>
                  Дополнительные заметки
                </label>
                <MacOSTextarea
                  value={formData.notes}
                  onChange={(e) => handleChange('notes', e.target.value)}
                  rows={2}
                  placeholder="Дополнительная информация о записи"
                />
              </div>
            </div>

            {/* Контактная информация */}
            <div style={{ marginBottom: '24px' }}>
              <h3 style={{ 
                fontSize: 'var(--mac-font-size-lg)', 
                fontWeight: 'var(--mac-font-weight-semibold)', 
                color: 'var(--mac-text-primary)',
                marginBottom: '16px'
              }}>
                Контактная информация
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '16px' }}>
                <div>
                  <label style={{ 
                    display: 'block', 
                    fontSize: 'var(--mac-font-size-sm)', 
                    fontWeight: 'var(--mac-font-weight-medium)', 
                    color: 'var(--mac-text-primary)',
                    marginBottom: '8px'
                  }}>
                    Телефон для связи
                  </label>
                  <MacOSInput
                    type="tel"
                    value={formData.phone}
                    onChange={(e) => handleChange('phone', e.target.value)}
                    placeholder="+998 90 123 45 67"
                    icon={Phone}
                  />
                </div>
                <div>
                  <label style={{ 
                    display: 'block', 
                    fontSize: 'var(--mac-font-size-sm)', 
                    fontWeight: 'var(--mac-font-weight-medium)', 
                    color: 'var(--mac-text-primary)',
                    marginBottom: '8px'
                  }}>
                    Email для уведомлений
                  </label>
                  <MacOSInput
                    type="email"
                    value={formData.email}
                    onChange={(e) => handleChange('email', e.target.value)}
                    placeholder="patient@example.com"
                    icon={Mail}
                  />
                </div>
              </div>
            </div>

            {/* Предварительный просмотр */}
            {(formData.patientId && formData.doctorId) && (
              <div style={{ marginBottom: '24px' }}>
                <h3 style={{ 
                  fontSize: 'var(--mac-font-size-lg)', 
                  fontWeight: 'var(--mac-font-weight-semibold)', 
                  color: 'var(--mac-text-primary)',
                  marginBottom: '16px'
                }}>
                  Предварительный просмотр
                </h3>
                <div style={{ 
                  padding: '16px', 
                  borderRadius: 'var(--mac-border-radius-lg)', 
                  background: 'var(--mac-bg-secondary)', 
                  border: '1px solid var(--mac-border)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px'
                }}>
                  <p style={{ 
                    fontSize: 'var(--mac-font-size-sm)', 
                    color: 'var(--mac-text-secondary)',
                    margin: 0
                  }}>
                    <strong style={{ color: 'var(--mac-text-primary)' }}>Пациент:</strong> {getPatientName(formData.patientId)}
                  </p>
                  <p style={{ 
                    fontSize: 'var(--mac-font-size-sm)', 
                    color: 'var(--mac-text-secondary)',
                    margin: 0
                  }}>
                    <strong style={{ color: 'var(--mac-text-primary)' }}>Врач:</strong> {getDoctorName(formData.doctorId)}
                  </p>
                  <p style={{ 
                    fontSize: 'var(--mac-font-size-sm)', 
                    color: 'var(--mac-text-secondary)',
                    margin: 0
                  }}>
                    <strong style={{ color: 'var(--mac-text-primary)' }}>Дата и время:</strong> {formData.appointmentDate} в {formData.appointmentTime}
                  </p>
                  <p style={{ 
                    fontSize: 'var(--mac-font-size-sm)', 
                    color: 'var(--mac-text-secondary)',
                    margin: 0
                  }}>
                    <strong style={{ color: 'var(--mac-text-primary)' }}>Длительность:</strong> {formData.duration} минут
                  </p>
                  <p style={{ 
                    fontSize: 'var(--mac-font-size-sm)', 
                    color: 'var(--mac-text-secondary)',
                    margin: 0
                  }}>
                    <strong style={{ color: 'var(--mac-text-primary)' }}>Статус:</strong> {formData.status === 'pending' ? 'Ожидает' : 
                                                formData.status === 'confirmed' ? 'Подтверждена' :
                                                formData.status === 'paid' ? 'Оплачена' :
                                                formData.status === 'in_visit' ? 'На приеме' :
                                                formData.status === 'completed' ? 'Завершена' :
                                                formData.status === 'cancelled' ? 'Отменена' : 'Не явился'}
                  </p>
                </div>
              </div>
            )}

            {/* Кнопки */}
            <div style={{ display: 'flex', gap: '12px', paddingTop: '16px' }}>
              <MacOSButton
                type="submit"
                disabled={isSubmitting || loading}
                className="flex-1"
                style={{ 
                  background: 'var(--accent-color)',
                  color: 'white'
                }}
              >
                {isSubmitting ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin mr-2" />
                    Сохранение...
                  </>
                ) : (
                  <>
                    <Save className="w-4 h-4 mr-2" />
                    {appointment ? 'Сохранить изменения' : 'Создать запись'}
                  </>
                )}
              </MacOSButton>
              <MacOSButton
                type="button"
                variant="outline"
                onClick={onClose}
                disabled={isSubmitting}
              >
                Отмена
              </MacOSButton>
            </div>
          </form>
    </MacOSModal>
  );
};

export default AppointmentModal;

