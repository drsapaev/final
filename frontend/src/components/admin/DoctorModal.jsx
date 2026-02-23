import { useState, useEffect } from 'react';
import { Save, User, Mail, Phone, GraduationCap, Clock, AlertCircle, X } from 'lucide-react';
import {
  MacOSModal,
  MacOSInput,
  MacOSSelect,
  MacOSTextarea,
  MacOSButton,
  Label,
  MacOSAlert } from
'../ui/macos';
import { api } from '../../api/client';

import logger from '../../utils/logger';
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
  const [departments, setDepartments] = useState([]);
  const [loadingDepartments, setLoadingDepartments] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  // Загрузка отделений
  useEffect(() => {
    if (isOpen) {
      loadDepartments();
    }
  }, [isOpen]);

  const loadDepartments = async () => {
    try {
      setLoadingDepartments(true);
      // Используем публичный эндпоинт /departments с параметром active_only
      const response = await api.get('/departments', { params: { active_only: true } });
      // Backend returns {success: true, data: [...], count: N}
      const departments = response.data?.data || [];
      if (departments.length > 0) {
        const deptOptions = departments.map((dept) => ({
          value: dept.key || dept.department_key || dept.id?.toString(),
          label: dept.name_ru || dept.name || dept.key || 'Неизвестно'
        }));
        logger.log('🔵 Загружены отделения:', deptOptions);
        setDepartments(deptOptions);
      }
    } catch (error) {
      logger.error('Ошибка загрузки отделений:', error);
      // Fallback на статический список
      setDepartments([
      { value: 'cardiology', label: 'Кардиология' },
      { value: 'dermatology', label: 'Дерматология' },
      { value: 'dentistry', label: 'Стоматология' },
      { value: 'general', label: 'Общее' }]
      );
    } finally {
      setLoadingDepartments(false);
    }
  };

  // Инициализация формы при открытии
  useEffect(() => {
    if (isOpen) {
      if (doctor) {
        // Маппинг данных из API в формат формы
        // API возвращает: user.full_name, user.email, specialty, active
        // Форма ожидает: name, email, specialization, status
        const doctorName = doctor.user?.full_name || doctor.name || '';
        const doctorEmail = doctor.user?.email || doctor.email || '';
        const doctorPhone = doctor.user?.phone || doctor.phone || '';
        const doctorSpecialization = doctor.specialty || doctor.specialization || '';
        const doctorDepartment = doctor.specialty || doctor.department || doctor.department_key || '';
        const doctorStatus = doctor.active !== undefined ?
        doctor.active ? 'active' : 'inactive' :
        doctor.status || 'active';

        logger.log('🔵 Инициализация формы врача:', {
          doctor,
          mapped: { doctorName, doctorEmail, doctorPhone, doctorSpecialization, doctorDepartment, doctorStatus }
        });

        setFormData({
          name: doctorName,
          email: doctorEmail,
          phone: doctorPhone,
          specialization: doctorSpecialization,
          department: doctorDepartment,
          experience: doctor.experience || '',
          schedule: doctor.schedule || '',
          status: doctorStatus,
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
      setSubmitError(null);
    }
  }, [isOpen, doctor]);

  const validateForm = () => {
    const newErrors = {};

    if (!formData.name || !formData.name.trim()) {
      newErrors.name = 'Имя обязательно';
    }

    if (!formData.email || !formData.email.trim()) {
      newErrors.email = 'Email обязателен';
    } else if (!/\S+@\S+\.\S+/.test(formData.email)) {
      newErrors.email = 'Некорректный email';
    }

    if (!formData.specialization || !formData.specialization.trim()) {
      newErrors.specialization = 'Специализация обязательна';
    }

    // Проверяем department - может быть строкой или числом
    const departmentValue = formData.department;
    logger.log('🔍 Проверка department:', { departmentValue, type: typeof departmentValue, isEmpty: !departmentValue, isStringEmpty: typeof departmentValue === 'string' && !departmentValue.trim() });
    if (!departmentValue || typeof departmentValue === 'string' && !departmentValue.trim()) {
      newErrors.department = 'Отделение обязательно';
    }

    if (formData.experience && formData.experience !== '' && isNaN(formData.experience)) {
      newErrors.experience = 'Опыт должен быть числом';
    }

    setErrors(newErrors);
    const isValid = Object.keys(newErrors).length === 0;
    logger.log('🔍 Валидация:', { formData, newErrors, isValid });
    return { isValid, errors: newErrors };
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    e.stopPropagation();

    logger.log('🔵 handleSubmit вызван', { formData, isSubmitting, loading });

    // Валидация формы
    const validation = validateForm();
    logger.log('🔵 Валидация формы:', validation);

    if (!validation.isValid) {
      logger.log('❌ Форма не прошла валидацию:', validation.errors);
      // Прокручиваем к первой ошибке
      const firstErrorField = Object.keys(validation.errors)[0];
      if (firstErrorField) {
        setTimeout(() => {
          const errorElement = document.querySelector(`[name="${firstErrorField}"]`);
          if (errorElement) {
            errorElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
            errorElement.focus();
          }
        }, 100);
      }
      return;
    }

    setIsSubmitting(true);
    setSubmitError(null);

    try {
      const doctorData = {
        name: formData.name.trim(),
        email: formData.email.trim(),
        phone: formData.phone.trim(),
        specialization: formData.specialization.trim(),
        department: typeof formData.department === 'string' ? formData.department.trim() : String(formData.department || ''),
        experience: formData.experience ? parseInt(formData.experience) : 0,
        schedule: formData.schedule.trim(),
        status: formData.status,
        bio: formData.bio.trim()
      };

      logger.log('🔵 Отправляем данные врача:', doctorData);
      await onSave(doctorData);
      logger.log('✅ Врач успешно сохранен');
      onClose();
    } catch (error) {
      logger.error('❌ Ошибка сохранения врача:', error);
      const errorMessage = error.message || error.response?.data?.detail || 'Ошибка при сохранении врача';
      setSubmitError(errorMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleChange = (field, value) => {
    logger.log(`🔵 handleChange: ${field} =`, value, typeof value);
    setFormData((prev) => {
      const newData = { ...prev, [field]: value };
      logger.log('🔵 Новый formData:', newData);
      return newData;
    });
    if (errors[field]) {
      setErrors((prev) => ({ ...prev, [field]: null }));
    }
  };

  return (
    <MacOSModal
      isOpen={isOpen}
      onClose={onClose}
      title={doctor ? 'Редактировать врача' : 'Добавить врача'}
      size="lg">

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {submitError &&
        <MacOSAlert type="error" style={{ marginBottom: '16px' }}>
            {submitError}
          </MacOSAlert>
        }

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
          {/* Имя */}
          <div>
            <Label required style={{ display: 'block', marginBottom: '8px' }}>
              Имя
            </Label>
            <MacOSInput
              type="text"
              name="name"
              value={formData.name}
              onChange={(e) => handleChange('name', e.target.value)}
              placeholder="Введите имя"
              icon={User}
              iconPosition="left"
              error={errors.name} />

            {errors.name &&
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              marginTop: '4px',
              fontSize: '12px',
              color: 'var(--mac-error)'
            }}>
                <AlertCircle size={14} />
                {errors.name}
              </div>
            }
          </div>

          {/* Email */}
          <div>
            <Label required style={{ display: 'block', marginBottom: '8px' }}>
              Email
            </Label>
            <MacOSInput
              type="email"
              name="email"
              value={formData.email}
              onChange={(e) => handleChange('email', e.target.value)}
              placeholder="Введите email"
              icon={Mail}
              iconPosition="left"
              error={errors.email} />

            {errors.email &&
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              marginTop: '4px',
              fontSize: '12px',
              color: 'var(--mac-error)'
            }}>
                <AlertCircle size={14} />
                {errors.email}
              </div>
            }
          </div>

          {/* Телефон */}
          <div>
            <Label style={{ display: 'block', marginBottom: '8px' }}>
              Телефон
            </Label>
            <MacOSInput
              type="tel"
              value={formData.phone}
              onChange={(e) => handleChange('phone', e.target.value)}
              placeholder="+998 90 123 45 67"
              icon={Phone}
              iconPosition="left" />

          </div>

          {/* Специализация */}
          <div>
            <Label required style={{ display: 'block', marginBottom: '8px' }}>
              Специализация
            </Label>
            <MacOSInput
              type="text"
              name="specialization"
              value={formData.specialization}
              onChange={(e) => handleChange('specialization', e.target.value)}
              placeholder="Кардиолог, Терапевт, Хирург..."
              icon={GraduationCap}
              iconPosition="left"
              error={errors.specialization} />

            {errors.specialization &&
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              marginTop: '4px',
              fontSize: '12px',
              color: 'var(--mac-error)'
            }}>
                <AlertCircle size={14} />
                {errors.specialization}
              </div>
            }
          </div>

          {/* Отделение */}
          <div>
            <Label required style={{ display: 'block', marginBottom: '8px' }}>
              Отделение
            </Label>
            <MacOSSelect
              name="department"
              value={formData.department || ''}
              onChange={(e) => {
                const selectedValue = e.target.value;
                logger.log('🔵 MacOSSelect onChange:', selectedValue, 'type:', typeof selectedValue, 'event:', e);
                handleChange('department', selectedValue);
              }}
              options={[
              { value: '', label: 'Выберите отделение' },
              ...departments]
              }
              error={errors.department}
              disabled={loadingDepartments} />

            {errors.department &&
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              marginTop: '4px',
              fontSize: '12px',
              color: 'var(--mac-error)'
            }}>
                <AlertCircle size={14} />
                {errors.department}
              </div>
            }
          </div>

          {/* Опыт работы */}
          <div>
            <Label style={{ display: 'block', marginBottom: '8px' }}>
              Опыт работы (лет)
            </Label>
            <MacOSInput
              type="number"
              value={formData.experience}
              onChange={(e) => handleChange('experience', e.target.value)}
              placeholder="5"
              min="0"
              max="50"
              error={errors.experience} />

            {errors.experience &&
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              marginTop: '4px',
              fontSize: '12px',
              color: 'var(--mac-error)'
            }}>
                <AlertCircle size={14} />
                {errors.experience}
              </div>
            }
          </div>

          {/* График работы */}
          <div>
            <Label style={{ display: 'block', marginBottom: '8px' }}>
              График работы
            </Label>
            <MacOSInput
              type="text"
              value={formData.schedule}
              onChange={(e) => handleChange('schedule', e.target.value)}
              placeholder="Пн-Пт 9:00-18:00"
              icon={Clock}
              iconPosition="left" />

          </div>

          {/* Статус */}
          <div>
            <Label style={{ display: 'block', marginBottom: '8px' }}>
              Статус
            </Label>
            <MacOSSelect
              value={formData.status}
              onChange={(e) => handleChange('status', e.target.value)}
              options={[
              { value: 'active', label: 'Активен' },
              { value: 'inactive', label: 'Неактивен' },
              { value: 'on_leave', label: 'В отпуске' }]
              } />

          </div>
        </div>

        {/* Биография */}
        <div>
          <Label style={{ display: 'block', marginBottom: '8px' }}>
            Биография
          </Label>
          <MacOSTextarea
            value={formData.bio}
            onChange={(e) => handleChange('bio', e.target.value)}
            placeholder="Краткая информация о враче..."
            rows={3}
            autoResize={true}
            minRows={3}
            maxRows={6} />

        </div>

        {/* Кнопки */}
        <div style={{
          display: 'flex',
          gap: '12px',
          justifyContent: 'flex-end',
          paddingTop: '16px',
          borderTop: '1px solid var(--mac-separator)'
        }}>
          <MacOSButton
            type="button"
            variant="outline"
            onClick={onClose}
            disabled={isSubmitting || loading}
            icon={<X size={16} />}>

            Отмена
          </MacOSButton>
          <MacOSButton
            type="submit"
            disabled={isSubmitting || loading}
            icon={<Save size={16} />}>

            {isSubmitting ? 'Сохранение...' : doctor ? 'Сохранить изменения' : 'Добавить врача'}
          </MacOSButton>
        </div>
      </form>
    </MacOSModal>);

};

export default DoctorModal;