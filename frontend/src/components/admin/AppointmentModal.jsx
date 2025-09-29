import React, { useState, useEffect } from 'react';
import { X, Save, Calendar, Clock, User, Stethoscope, AlertCircle, Phone, Mail } from 'lucide-react';
import { Card, Button } from '../ui/native';

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
      console.error('Ошибка сохранения записи:', error);
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
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <Card className="w-full max-w-3xl max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          {/* Заголовок */}
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
              {appointment ? 'Редактировать запись' : 'Создать запись на прием'}
            </h2>
            <button
              onClick={onClose}
              className="p-1 hover:bg-gray-100 rounded-lg transition-colors"
              style={{ color: 'var(--text-secondary)' }}
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Форма */}
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Основная информация */}
            <div className="space-y-4">
              <h3 className="text-lg font-medium" style={{ color: 'var(--text-primary)' }}>
                Основная информация
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Пациент */}
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                    Пациент *
                  </label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" 
                          style={{ color: 'var(--text-tertiary)' }} />
                    <select
                      value={formData.patientId}
                      onChange={(e) => handleChange('patientId', e.target.value)}
                      className={`w-full pl-10 pr-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                        errors.patientId ? 'border-red-500' : 'border-gray-300'
                      }`}
                      style={{ 
                        background: 'var(--bg-primary)', 
                        color: 'var(--text-primary)',
                        borderColor: errors.patientId ? 'var(--danger-color)' : 'var(--border-color)'
                      }}
                    >
                      <option value="">Выберите пациента</option>
                      {patients.map(patient => (
                        <option key={patient.id} value={patient.id}>
                          {patient.lastName} {patient.firstName} {patient.middleName} - {patient.phone}
                        </option>
                      ))}
                    </select>
                  </div>
                  {errors.patientId && (
                    <p className="text-sm text-red-500 mt-1 flex items-center">
                      <AlertCircle className="w-4 h-4 mr-1" />
                      {errors.patientId}
                    </p>
                  )}
                </div>

                {/* Врач */}
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                    Врач *
                  </label>
                  <div className="relative">
                    <Stethoscope className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" 
                                 style={{ color: 'var(--text-tertiary)' }} />
                    <select
                      value={formData.doctorId}
                      onChange={(e) => handleChange('doctorId', e.target.value)}
                      className={`w-full pl-10 pr-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                        errors.doctorId ? 'border-red-500' : 'border-gray-300'
                      }`}
                      style={{ 
                        background: 'var(--bg-primary)', 
                        color: 'var(--text-primary)',
                        borderColor: errors.doctorId ? 'var(--danger-color)' : 'var(--border-color)'
                      }}
                    >
                      <option value="">Выберите врача</option>
                      {doctors.map(doctor => (
                        <option key={doctor.id} value={doctor.id}>
                          {doctor.name} - {doctor.specialization}
                        </option>
                      ))}
                    </select>
                  </div>
                  {errors.doctorId && (
                    <p className="text-sm text-red-500 mt-1 flex items-center">
                      <AlertCircle className="w-4 h-4 mr-1" />
                      {errors.doctorId}
                    </p>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Дата записи */}
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                    Дата записи *
                  </label>
                  <div className="relative">
                    <Calendar className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" 
                              style={{ color: 'var(--text-tertiary)' }} />
                    <input
                      type="date"
                      value={formData.appointmentDate}
                      onChange={(e) => handleChange('appointmentDate', e.target.value)}
                      className={`w-full pl-10 pr-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                        errors.appointmentDate ? 'border-red-500' : 'border-gray-300'
                      }`}
                      style={{ 
                        background: 'var(--bg-primary)', 
                        color: 'var(--text-primary)',
                        borderColor: errors.appointmentDate ? 'var(--danger-color)' : 'var(--border-color)'
                      }}
                    />
                  </div>
                  {errors.appointmentDate && (
                    <p className="text-sm text-red-500 mt-1 flex items-center">
                      <AlertCircle className="w-4 h-4 mr-1" />
                      {errors.appointmentDate}
                    </p>
                  )}
                </div>

                {/* Время записи */}
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                    Время записи *
                  </label>
                  <div className="relative">
                    <Clock className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" 
                           style={{ color: 'var(--text-tertiary)' }} />
                    <input
                      type="time"
                      value={formData.appointmentTime}
                      onChange={(e) => handleChange('appointmentTime', e.target.value)}
                      className={`w-full pl-10 pr-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                        errors.appointmentTime ? 'border-red-500' : 'border-gray-300'
                      }`}
                      style={{ 
                        background: 'var(--bg-primary)', 
                        color: 'var(--text-primary)',
                        borderColor: errors.appointmentTime ? 'var(--danger-color)' : 'var(--border-color)'
                      }}
                    />
                  </div>
                  {errors.appointmentTime && (
                    <p className="text-sm text-red-500 mt-1 flex items-center">
                      <AlertCircle className="w-4 h-4 mr-1" />
                      {errors.appointmentTime}
                    </p>
                  )}
                </div>

                {/* Длительность */}
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                    Длительность (мин)
                  </label>
                  <input
                    type="number"
                    value={formData.duration}
                    onChange={(e) => handleChange('duration', e.target.value)}
                    className={`w-full px-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                      errors.duration ? 'border-red-500' : 'border-gray-300'
                    }`}
                    style={{ 
                      background: 'var(--bg-primary)', 
                      color: 'var(--text-primary)',
                      borderColor: errors.duration ? 'var(--danger-color)' : 'var(--border-color)'
                    }}
                    min="15"
                    max="120"
                    step="15"
                  />
                  {errors.duration && (
                    <p className="text-sm text-red-500 mt-1 flex items-center">
                      <AlertCircle className="w-4 h-4 mr-1" />
                      {errors.duration}
                    </p>
                  )}
                </div>
              </div>

              {/* Статус */}
              <div>
                <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                  Статус записи
                </label>
                <select
                  value={formData.status}
                  onChange={(e) => handleChange('status', e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  style={{ 
                    background: 'var(--bg-primary)', 
                    color: 'var(--text-primary)',
                    borderColor: 'var(--border-color)'
                  }}
                >
                  <option value="pending">Ожидает</option>
                  <option value="confirmed">Подтверждена</option>
                  <option value="paid">Оплачена</option>
                  <option value="in_visit">На приеме</option>
                  <option value="completed">Завершена</option>
                  <option value="cancelled">Отменена</option>
                  <option value="no_show">Не явился</option>
                </select>
              </div>
            </div>

            {/* Детали записи */}
            <div className="space-y-4">
              <h3 className="text-lg font-medium" style={{ color: 'var(--text-primary)' }}>
                Детали записи
              </h3>
              <div>
                <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                  Причина обращения *
                </label>
                <textarea
                  value={formData.reason}
                  onChange={(e) => handleChange('reason', e.target.value)}
                  className={`w-full px-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                    errors.reason ? 'border-red-500' : 'border-gray-300'
                  }`}
                  style={{ 
                    background: 'var(--bg-primary)', 
                    color: 'var(--text-primary)',
                    borderColor: errors.reason ? 'var(--danger-color)' : 'var(--border-color)'
                  }}
                  rows="3"
                  placeholder="Опишите причину обращения к врачу..."
                />
                {errors.reason && (
                  <p className="text-sm text-red-500 mt-1 flex items-center">
                    <AlertCircle className="w-4 h-4 mr-1" />
                    {errors.reason}
                  </p>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                  Дополнительные заметки
                </label>
                <textarea
                  value={formData.notes}
                  onChange={(e) => handleChange('notes', e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  style={{ 
                    background: 'var(--bg-primary)', 
                    color: 'var(--text-primary)',
                    borderColor: 'var(--border-color)'
                  }}
                  rows="2"
                  placeholder="Дополнительная информация о записи..."
                />
              </div>
            </div>

            {/* Контактная информация */}
            <div className="space-y-4">
              <h3 className="text-lg font-medium" style={{ color: 'var(--text-primary)' }}>
                Контактная информация
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                    Телефон для связи
                  </label>
                  <div className="relative">
                    <Phone className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" 
                           style={{ color: 'var(--text-tertiary)' }} />
                    <input
                      type="tel"
                      value={formData.phone}
                      onChange={(e) => handleChange('phone', e.target.value)}
                      className="w-full pl-10 pr-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      style={{ 
                        background: 'var(--bg-primary)', 
                        color: 'var(--text-primary)',
                        borderColor: 'var(--border-color)'
                      }}
                      placeholder="+998 90 123 45 67"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                    Email для уведомлений
                  </label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" 
                          style={{ color: 'var(--text-tertiary)' }} />
                    <input
                      type="email"
                      value={formData.email}
                      onChange={(e) => handleChange('email', e.target.value)}
                      className="w-full pl-10 pr-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      style={{ 
                        background: 'var(--bg-primary)', 
                        color: 'var(--text-primary)',
                        borderColor: 'var(--border-color)'
                      }}
                      placeholder="patient@example.com"
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Предварительный просмотр */}
            {(formData.patientId && formData.doctorId) && (
              <div className="space-y-4">
                <h3 className="text-lg font-medium" style={{ color: 'var(--text-primary)' }}>
                  Предварительный просмотр
                </h3>
                <div className="p-4 rounded-lg" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }}>
                  <div className="space-y-2">
                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                      <strong>Пациент:</strong> {getPatientName(formData.patientId)}
                    </p>
                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                      <strong>Врач:</strong> {getDoctorName(formData.doctorId)}
                    </p>
                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                      <strong>Дата и время:</strong> {formData.appointmentDate} в {formData.appointmentTime}
                    </p>
                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                      <strong>Длительность:</strong> {formData.duration} минут
                    </p>
                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                      <strong>Статус:</strong> {formData.status === 'pending' ? 'Ожидает' : 
                                              formData.status === 'confirmed' ? 'Подтверждена' :
                                              formData.status === 'paid' ? 'Оплачена' :
                                              formData.status === 'in_visit' ? 'На приеме' :
                                              formData.status === 'completed' ? 'Завершена' :
                                              formData.status === 'cancelled' ? 'Отменена' : 'Не явился'}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Кнопки */}
            <div className="flex gap-3 pt-4">
              <Button
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
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={onClose}
                disabled={isSubmitting}
              >
                Отмена
              </Button>
            </div>
          </form>
        </div>
      </Card>
    </div>
  );
};

export default AppointmentModal;

