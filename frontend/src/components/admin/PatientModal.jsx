import React, { useState, useEffect } from 'react';
import { X, Save, User, Mail, Phone, MapPin, Calendar, IdCard, AlertCircle, Heart } from 'lucide-react';
import { Card, Button } from '../../design-system/components';

const PatientModal = ({ 
  isOpen, 
  onClose, 
  patient = null, 
  onSave, 
  loading = false 
}) => {
  const [formData, setFormData] = useState({
    firstName: '',
    lastName: '',
    middleName: '',
    email: '',
    phone: '',
    birthDate: '',
    gender: '',
    address: '',
    passport: '',
    insuranceNumber: '',
    emergencyContact: '',
    emergencyPhone: '',
    bloodType: '',
    allergies: '',
    chronicDiseases: '',
    notes: ''
  });
  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Инициализация формы при открытии
  useEffect(() => {
    if (isOpen) {
      if (patient) {
        setFormData({
          firstName: patient.firstName || '',
          lastName: patient.lastName || '',
          middleName: patient.middleName || '',
          email: patient.email || '',
          phone: patient.phone || '',
          birthDate: patient.birthDate || '',
          gender: patient.gender || '',
          address: patient.address || '',
          passport: patient.passport || '',
          insuranceNumber: patient.insuranceNumber || '',
          emergencyContact: patient.emergencyContact || '',
          emergencyPhone: patient.emergencyPhone || '',
          bloodType: patient.bloodType || '',
          allergies: patient.allergies || '',
          chronicDiseases: patient.chronicDiseases || '',
          notes: patient.notes || ''
        });
      } else {
        setFormData({
          firstName: '',
          lastName: '',
          middleName: '',
          email: '',
          phone: '',
          birthDate: '',
          gender: '',
          address: '',
          passport: '',
          insuranceNumber: '',
          emergencyContact: '',
          emergencyPhone: '',
          bloodType: '',
          allergies: '',
          chronicDiseases: '',
          notes: ''
        });
      }
      setErrors({});
    }
  }, [isOpen, patient]);

  const validateForm = () => {
    const newErrors = {};

    if (!formData.firstName.trim()) {
      newErrors.firstName = 'Имя обязательно';
    }

    if (!formData.lastName.trim()) {
      newErrors.lastName = 'Фамилия обязательна';
    }

    if (!formData.phone.trim()) {
      newErrors.phone = 'Телефон обязателен';
    } else if (!/^\+998\s?\d{2}\s?\d{3}\s?\d{2}\s?\d{2}$/.test(formData.phone.replace(/\s/g, ''))) {
      newErrors.phone = 'Некорректный формат телефона';
    }

    if (formData.email && !/\S+@\S+\.\S+/.test(formData.email)) {
      newErrors.email = 'Некорректный email';
    }

    if (!formData.birthDate) {
      newErrors.birthDate = 'Дата рождения обязательна';
    } else {
      const birthDate = new Date(formData.birthDate);
      const today = new Date();
      const age = today.getFullYear() - birthDate.getFullYear();
      if (age < 0 || age > 120) {
        newErrors.birthDate = 'Некорректная дата рождения';
      }
    }

    if (!formData.gender) {
      newErrors.gender = 'Пол обязателен';
    }

    if (!formData.passport.trim()) {
      newErrors.passport = 'Паспортные данные обязательны';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!validateForm()) return;

    setIsSubmitting(true);
    try {
      const patientData = {
        firstName: formData.firstName.trim(),
        lastName: formData.lastName.trim(),
        middleName: formData.middleName.trim(),
        email: formData.email.trim() || null,
        phone: formData.phone.trim(),
        birthDate: formData.birthDate,
        gender: formData.gender,
        address: formData.address.trim() || null,
        passport: formData.passport.trim(),
        insuranceNumber: formData.insuranceNumber.trim() || null,
        emergencyContact: formData.emergencyContact.trim() || null,
        emergencyPhone: formData.emergencyPhone.trim() || null,
        bloodType: formData.bloodType || null,
        allergies: formData.allergies.trim() || null,
        chronicDiseases: formData.chronicDiseases.trim() || null,
        notes: formData.notes.trim() || null
      };

      await onSave(patientData);
      onClose();
    } catch (error) {
      console.error('Ошибка сохранения пациента:', error);
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

  const formatPhone = (value) => {
    const cleaned = value.replace(/\D/g, '');
    if (cleaned.startsWith('998')) {
      const match = cleaned.match(/^998(\d{2})(\d{3})(\d{2})(\d{2})$/);
      if (match) {
        return `+998 ${match[1]} ${match[2]} ${match[3]} ${match[4]}`;
      }
    }
    return value;
  };

  const handlePhoneChange = (e) => {
    const formatted = formatPhone(e.target.value);
    handleChange('phone', formatted);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <Card className="w-full max-w-4xl max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          {/* Заголовок */}
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
              {patient ? 'Редактировать пациента' : 'Добавить пациента'}
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
            {/* Личная информация */}
            <div className="space-y-4">
              <h3 className="text-lg font-medium" style={{ color: 'var(--text-primary)' }}>
                Личная информация
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Фамилия */}
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                    Фамилия *
                  </label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" 
                          style={{ color: 'var(--text-tertiary)' }} />
                    <input
                      type="text"
                      value={formData.lastName}
                      onChange={(e) => handleChange('lastName', e.target.value)}
                      className={`w-full pl-10 pr-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                        errors.lastName ? 'border-red-500' : 'border-gray-300'
                      }`}
                      style={{ 
                        background: 'var(--bg-primary)', 
                        color: 'var(--text-primary)',
                        borderColor: errors.lastName ? 'var(--danger-color)' : 'var(--border-color)'
                      }}
                      placeholder="Иванов"
                    />
                  </div>
                  {errors.lastName && (
                    <p className="text-sm text-red-500 mt-1 flex items-center">
                      <AlertCircle className="w-4 h-4 mr-1" />
                      {errors.lastName}
                    </p>
                  )}
                </div>

                {/* Имя */}
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                    Имя *
                  </label>
                  <input
                    type="text"
                    value={formData.firstName}
                    onChange={(e) => handleChange('firstName', e.target.value)}
                    className={`w-full px-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                      errors.firstName ? 'border-red-500' : 'border-gray-300'
                    }`}
                    style={{ 
                      background: 'var(--bg-primary)', 
                      color: 'var(--text-primary)',
                      borderColor: errors.firstName ? 'var(--danger-color)' : 'var(--border-color)'
                    }}
                    placeholder="Иван"
                  />
                  {errors.firstName && (
                    <p className="text-sm text-red-500 mt-1 flex items-center">
                      <AlertCircle className="w-4 h-4 mr-1" />
                      {errors.firstName}
                    </p>
                  )}
                </div>

                {/* Отчество */}
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                    Отчество
                  </label>
                  <input
                    type="text"
                    value={formData.middleName}
                    onChange={(e) => handleChange('middleName', e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    style={{ 
                      background: 'var(--bg-primary)', 
                      color: 'var(--text-primary)',
                      borderColor: 'var(--border-color)'
                    }}
                    placeholder="Иванович"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Дата рождения */}
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                    Дата рождения *
                  </label>
                  <div className="relative">
                    <Calendar className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" 
                              style={{ color: 'var(--text-tertiary)' }} />
                    <input
                      type="date"
                      value={formData.birthDate}
                      onChange={(e) => handleChange('birthDate', e.target.value)}
                      className={`w-full pl-10 pr-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                        errors.birthDate ? 'border-red-500' : 'border-gray-300'
                      }`}
                      style={{ 
                        background: 'var(--bg-primary)', 
                        color: 'var(--text-primary)',
                        borderColor: errors.birthDate ? 'var(--danger-color)' : 'var(--border-color)'
                      }}
                    />
                  </div>
                  {errors.birthDate && (
                    <p className="text-sm text-red-500 mt-1 flex items-center">
                      <AlertCircle className="w-4 h-4 mr-1" />
                      {errors.birthDate}
                    </p>
                  )}
                </div>

                {/* Пол */}
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                    Пол *
                  </label>
                  <select
                    value={formData.gender}
                    onChange={(e) => handleChange('gender', e.target.value)}
                    className={`w-full px-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                      errors.gender ? 'border-red-500' : 'border-gray-300'
                    }`}
                    style={{ 
                      background: 'var(--bg-primary)', 
                      color: 'var(--text-primary)',
                      borderColor: errors.gender ? 'var(--danger-color)' : 'var(--border-color)'
                    }}
                  >
                    <option value="">Выберите пол</option>
                    <option value="male">Мужской</option>
                    <option value="female">Женский</option>
                  </select>
                  {errors.gender && (
                    <p className="text-sm text-red-500 mt-1 flex items-center">
                      <AlertCircle className="w-4 h-4 mr-1" />
                      {errors.gender}
                    </p>
                  )}
                </div>
              </div>
            </div>

            {/* Контактная информация */}
            <div className="space-y-4">
              <h3 className="text-lg font-medium" style={{ color: 'var(--text-primary)' }}>
                Контактная информация
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Телефон */}
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                    Телефон *
                  </label>
                  <div className="relative">
                    <Phone className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" 
                           style={{ color: 'var(--text-tertiary)' }} />
                    <input
                      type="tel"
                      value={formData.phone}
                      onChange={handlePhoneChange}
                      className={`w-full pl-10 pr-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                        errors.phone ? 'border-red-500' : 'border-gray-300'
                      }`}
                      style={{ 
                        background: 'var(--bg-primary)', 
                        color: 'var(--text-primary)',
                        borderColor: errors.phone ? 'var(--danger-color)' : 'var(--border-color)'
                      }}
                      placeholder="+998 90 123 45 67"
                    />
                  </div>
                  {errors.phone && (
                    <p className="text-sm text-red-500 mt-1 flex items-center">
                      <AlertCircle className="w-4 h-4 mr-1" />
                      {errors.phone}
                    </p>
                  )}
                </div>

                {/* Email */}
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                    Email
                  </label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" 
                          style={{ color: 'var(--text-tertiary)' }} />
                    <input
                      type="email"
                      value={formData.email}
                      onChange={(e) => handleChange('email', e.target.value)}
                      className={`w-full pl-10 pr-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                        errors.email ? 'border-red-500' : 'border-gray-300'
                      }`}
                      style={{ 
                        background: 'var(--bg-primary)', 
                        color: 'var(--text-primary)',
                        borderColor: errors.email ? 'var(--danger-color)' : 'var(--border-color)'
                      }}
                      placeholder="ivan@example.com"
                    />
                  </div>
                  {errors.email && (
                    <p className="text-sm text-red-500 mt-1 flex items-center">
                      <AlertCircle className="w-4 h-4 mr-1" />
                      {errors.email}
                    </p>
                  )}
                </div>
              </div>

              {/* Адрес */}
              <div>
                <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                  Адрес
                </label>
                <div className="relative">
                  <MapPin className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" 
                           style={{ color: 'var(--text-tertiary)' }} />
                  <input
                    type="text"
                    value={formData.address}
                    onChange={(e) => handleChange('address', e.target.value)}
                    className="w-full pl-10 pr-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    style={{ 
                      background: 'var(--bg-primary)', 
                      color: 'var(--text-primary)',
                      borderColor: 'var(--border-color)'
                    }}
                    placeholder="г. Ташкент, ул. Навои, д. 1"
                  />
                </div>
              </div>
            </div>

            {/* Документы */}
            <div className="space-y-4">
              <h3 className="text-lg font-medium" style={{ color: 'var(--text-primary)' }}>
                Документы
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Паспорт */}
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                    Паспортные данные *
                  </label>
                  <div className="relative">
                    <IdCard className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" 
                             style={{ color: 'var(--text-tertiary)' }} />
                    <input
                      type="text"
                      value={formData.passport}
                      onChange={(e) => handleChange('passport', e.target.value)}
                      className={`w-full pl-10 pr-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                        errors.passport ? 'border-red-500' : 'border-gray-300'
                      }`}
                      style={{ 
                        background: 'var(--bg-primary)', 
                        color: 'var(--text-primary)',
                        borderColor: errors.passport ? 'var(--danger-color)' : 'var(--border-color)'
                      }}
                      placeholder="AA1234567"
                    />
                  </div>
                  {errors.passport && (
                    <p className="text-sm text-red-500 mt-1 flex items-center">
                      <AlertCircle className="w-4 h-4 mr-1" />
                      {errors.passport}
                    </p>
                  )}
                </div>

                {/* Страховой номер */}
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                    Страховой номер
                  </label>
                  <input
                    type="text"
                    value={formData.insuranceNumber}
                    onChange={(e) => handleChange('insuranceNumber', e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    style={{ 
                      background: 'var(--bg-primary)', 
                      color: 'var(--text-primary)',
                      borderColor: 'var(--border-color)'
                    }}
                    placeholder="12345678901234"
                  />
                </div>
              </div>
            </div>

            {/* Экстренный контакт */}
            <div className="space-y-4">
              <h3 className="text-lg font-medium" style={{ color: 'var(--text-primary)' }}>
                Экстренный контакт
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                    Контактное лицо
                  </label>
                  <input
                    type="text"
                    value={formData.emergencyContact}
                    onChange={(e) => handleChange('emergencyContact', e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    style={{ 
                      background: 'var(--bg-primary)', 
                      color: 'var(--text-primary)',
                      borderColor: 'var(--border-color)'
                    }}
                    placeholder="Иванова Мария Ивановна"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                    Телефон экстренного контакта
                  </label>
                  <input
                    type="tel"
                    value={formData.emergencyPhone}
                    onChange={(e) => handleChange('emergencyPhone', e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    style={{ 
                      background: 'var(--bg-primary)', 
                      color: 'var(--text-primary)',
                      borderColor: 'var(--border-color)'
                    }}
                    placeholder="+998 90 987 65 43"
                  />
                </div>
              </div>
            </div>

            {/* Медицинская информация */}
            <div className="space-y-4">
              <h3 className="text-lg font-medium" style={{ color: 'var(--text-primary)' }}>
                Медицинская информация
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                    Группа крови
                  </label>
                  <div className="relative">
                    <Heart className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" 
                            style={{ color: 'var(--text-tertiary)' }} />
                    <select
                      value={formData.bloodType}
                      onChange={(e) => handleChange('bloodType', e.target.value)}
                      className="w-full pl-10 pr-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      style={{ 
                        background: 'var(--bg-primary)', 
                        color: 'var(--text-primary)',
                        borderColor: 'var(--border-color)'
                      }}
                    >
                      <option value="">Не указано</option>
                      <option value="A+">A+</option>
                      <option value="A-">A-</option>
                      <option value="B+">B+</option>
                      <option value="B-">B-</option>
                      <option value="AB+">AB+</option>
                      <option value="AB-">AB-</option>
                      <option value="O+">O+</option>
                      <option value="O-">O-</option>
                    </select>
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                    Аллергии
                  </label>
                  <input
                    type="text"
                    value={formData.allergies}
                    onChange={(e) => handleChange('allergies', e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    style={{ 
                      background: 'var(--bg-primary)', 
                      color: 'var(--text-primary)',
                      borderColor: 'var(--border-color)'
                    }}
                    placeholder="Пенициллин, пыльца"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                  Хронические заболевания
                </label>
                <input
                  type="text"
                  value={formData.chronicDiseases}
                  onChange={(e) => handleChange('chronicDiseases', e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  style={{ 
                    background: 'var(--bg-primary)', 
                    color: 'var(--text-primary)',
                    borderColor: 'var(--border-color)'
                  }}
                  placeholder="Гипертония, диабет"
                />
              </div>
            </div>

            {/* Дополнительная информация */}
            <div className="space-y-4">
              <h3 className="text-lg font-medium" style={{ color: 'var(--text-primary)' }}>
                Дополнительная информация
              </h3>
              <div>
                <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                  Заметки
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
                  rows="3"
                  placeholder="Дополнительная информация о пациенте..."
                />
              </div>
            </div>

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
                    {patient ? 'Сохранить изменения' : 'Добавить пациента'}
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

export default PatientModal;
