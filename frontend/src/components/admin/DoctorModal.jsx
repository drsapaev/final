import React, { useState, useEffect } from 'react';
import { X, Save, User, Mail, Phone, MapPin, GraduationCap, Clock, AlertCircle } from 'lucide-react';
import { Card, Button } from '../ui/native';

const DoctorModal = ({ 
  isOpen, 
  onClose, 
  doctor = null, 
  onSave, 
  loading = false 
}) => {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    specialization: '',
    department: '',
    experience: '',
    schedule: '',
    status: 'active',
    bio: ''
  });
  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Инициализация формы при открытии
  useEffect(() => {
    if (isOpen) {
      if (doctor) {
        setFormData({
          name: doctor.name || '',
          email: doctor.email || '',
          phone: doctor.phone || '',
          specialization: doctor.specialization || '',
          department: doctor.department || '',
          experience: doctor.experience || '',
          schedule: doctor.schedule || '',
          status: doctor.status || 'active',
          bio: doctor.bio || ''
        });
      } else {
        setFormData({
          name: '',
          email: '',
          phone: '',
          specialization: '',
          department: '',
          experience: '',
          schedule: '',
          status: 'active',
          bio: ''
        });
      }
      setErrors({});
    }
  }, [isOpen, doctor]);

  const validateForm = () => {
    const newErrors = {};

    if (!formData.name.trim()) {
      newErrors.name = 'Имя обязательно';
    }

    if (!formData.email.trim()) {
      newErrors.email = 'Email обязателен';
    } else if (!/\S+@\S+\.\S+/.test(formData.email)) {
      newErrors.email = 'Некорректный email';
    }

    if (!formData.specialization.trim()) {
      newErrors.specialization = 'Специализация обязательна';
    }

    if (!formData.department.trim()) {
      newErrors.department = 'Отделение обязательно';
    }

    if (formData.experience && isNaN(formData.experience)) {
      newErrors.experience = 'Опыт должен быть числом';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!validateForm()) return;

    setIsSubmitting(true);
    try {
      const doctorData = {
        name: formData.name.trim(),
        email: formData.email.trim(),
        phone: formData.phone.trim(),
        specialization: formData.specialization.trim(),
        department: formData.department.trim(),
        experience: formData.experience ? parseInt(formData.experience) : 0,
        schedule: formData.schedule.trim(),
        status: formData.status,
        bio: formData.bio.trim()
      };

      await onSave(doctorData);
      onClose();
    } catch (error) {
      console.error('Ошибка сохранения врача:', error);
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

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <Card className="w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          {/* Заголовок */}
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
              {doctor ? 'Редактировать врача' : 'Добавить врача'}
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
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Имя */}
              <div>
                <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                  Имя *
                </label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" 
                        style={{ color: 'var(--text-tertiary)' }} />
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => handleChange('name', e.target.value)}
                    className={`w-full pl-10 pr-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                      errors.name ? 'border-red-500' : 'border-gray-300'
                    }`}
                    style={{ 
                      background: 'var(--bg-primary)', 
                      color: 'var(--text-primary)',
                      borderColor: errors.name ? 'var(--danger-color)' : 'var(--border-color)'
                    }}
                    placeholder="Введите имя"
                  />
                </div>
                {errors.name && (
                  <p className="text-sm text-red-500 mt-1 flex items-center">
                    <AlertCircle className="w-4 h-4 mr-1" />
                    {errors.name}
                  </p>
                )}
              </div>

              {/* Email */}
              <div>
                <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                  Email *
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
                    placeholder="Введите email"
                  />
                </div>
                {errors.email && (
                  <p className="text-sm text-red-500 mt-1 flex items-center">
                    <AlertCircle className="w-4 h-4 mr-1" />
                    {errors.email}
                  </p>
                )}
              </div>

              {/* Телефон */}
              <div>
                <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                  Телефон
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

              {/* Специализация */}
              <div>
                <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                  Специализация *
                </label>
                <div className="relative">
                  <GraduationCap className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" 
                                 style={{ color: 'var(--text-tertiary)' }} />
                  <input
                    type="text"
                    value={formData.specialization}
                    onChange={(e) => handleChange('specialization', e.target.value)}
                    className={`w-full pl-10 pr-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                      errors.specialization ? 'border-red-500' : 'border-gray-300'
                    }`}
                    style={{ 
                      background: 'var(--bg-primary)', 
                      color: 'var(--text-primary)',
                      borderColor: errors.specialization ? 'var(--danger-color)' : 'var(--border-color)'
                    }}
                    placeholder="Кардиолог, Терапевт, Хирург..."
                  />
                </div>
                {errors.specialization && (
                  <p className="text-sm text-red-500 mt-1 flex items-center">
                    <AlertCircle className="w-4 h-4 mr-1" />
                    {errors.specialization}
                  </p>
                )}
              </div>

              {/* Отделение */}
              <div>
                <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                  Отделение *
                </label>
                <div className="relative">
                  <MapPin className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" 
                           style={{ color: 'var(--text-tertiary)' }} />
                  <select
                    value={formData.department}
                    onChange={(e) => handleChange('department', e.target.value)}
                    className={`w-full pl-10 pr-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                      errors.department ? 'border-red-500' : 'border-gray-300'
                    }`}
                    style={{ 
                      background: 'var(--bg-primary)', 
                      color: 'var(--text-primary)',
                      borderColor: errors.department ? 'var(--danger-color)' : 'var(--border-color)'
                    }}
                  >
                    <option value="">Выберите отделение</option>
                    <option value="cardiology">Кардиология</option>
                    <option value="dermatology">Дерматология</option>
                    <option value="dentistry">Стоматология</option>
                    <option value="general">Общее</option>
                    <option value="surgery">Хирургия</option>
                    <option value="pediatrics">Педиатрия</option>
                    <option value="neurology">Неврология</option>
                  </select>
                </div>
                {errors.department && (
                  <p className="text-sm text-red-500 mt-1 flex items-center">
                    <AlertCircle className="w-4 h-4 mr-1" />
                    {errors.department}
                  </p>
                )}
              </div>

              {/* Опыт работы */}
              <div>
                <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                  Опыт работы (лет)
                </label>
                <input
                  type="number"
                  value={formData.experience}
                  onChange={(e) => handleChange('experience', e.target.value)}
                  className={`w-full px-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                    errors.experience ? 'border-red-500' : 'border-gray-300'
                  }`}
                  style={{ 
                    background: 'var(--bg-primary)', 
                    color: 'var(--text-primary)',
                    borderColor: errors.experience ? 'var(--danger-color)' : 'var(--border-color)'
                  }}
                  placeholder="5"
                  min="0"
                  max="50"
                />
                {errors.experience && (
                  <p className="text-sm text-red-500 mt-1 flex items-center">
                    <AlertCircle className="w-4 h-4 mr-1" />
                    {errors.experience}
                  </p>
                )}
              </div>

              {/* График работы */}
              <div>
                <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                  График работы
                </label>
                <div className="relative">
                  <Clock className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" 
                         style={{ color: 'var(--text-tertiary)' }} />
                  <input
                    type="text"
                    value={formData.schedule}
                    onChange={(e) => handleChange('schedule', e.target.value)}
                    className="w-full pl-10 pr-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    style={{ 
                      background: 'var(--bg-primary)', 
                      color: 'var(--text-primary)',
                      borderColor: 'var(--border-color)'
                    }}
                    placeholder="Пн-Пт 9:00-18:00"
                  />
                </div>
              </div>

              {/* Статус */}
              <div>
                <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                  Статус
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
                  <option value="active">Активен</option>
                  <option value="inactive">Неактивен</option>
                  <option value="on_leave">В отпуске</option>
                </select>
              </div>
            </div>

            {/* Биография */}
            <div>
              <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                Биография
              </label>
              <textarea
                value={formData.bio}
                onChange={(e) => handleChange('bio', e.target.value)}
                className="w-full px-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                style={{ 
                  background: 'var(--bg-primary)', 
                  color: 'var(--text-primary)',
                  borderColor: 'var(--border-color)'
                }}
                rows="3"
                placeholder="Краткая информация о враче..."
              />
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
                    {doctor ? 'Сохранить изменения' : 'Добавить врача'}
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

export default DoctorModal;

