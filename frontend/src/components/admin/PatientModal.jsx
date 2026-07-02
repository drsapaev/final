import { useState, useEffect } from 'react';
import { Save, User, Mail, Phone, MapPin, Calendar, IdCard, AlertCircle } from 'lucide-react';
import logger from '../../utils/logger';
import {
  Button,
  Input,
  Select,
  Textarea,
  Modal,
} from '../ui/macos';
import PropTypes from 'prop-types';
// P-013 fix: shared ConfirmDialog hook replacing window.confirm() calls.
import { useConfirm } from '../common/ConfirmDialog';

const PatientModal = ({
  isOpen,
  onClose,
  patient = null,
  onSave,
  loading = false
}) => {
  // P-013 fix: shared ConfirmDialog hook (replaces 1 window.confirm() call).
  const [confirm, confirmDialog] = useConfirm();
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
  const [isDirty, setIsDirty] = useState(false);

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
      setIsDirty(false);
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

    // Passport is now optional for quick registration
    // if (!formData.passport.trim()) {
    //   newErrors.passport = 'Паспортные данные обязательны';
    // }

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
      logger.error('Ошибка сохранения пациента:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    setIsDirty(true);
    if (errors[field]) {
      setErrors((prev) => ({ ...prev, [field]: null }));
    }
  };

  const handleClose = async () => {
    if (isDirty) {
      // P-013 fix: replaced window.confirm() with shared useConfirm hook.
      const ok = await confirm({
        title: 'Несохранённые изменения',
        message: 'У вас есть несохранённые изменения. Закрыть окно?',
        description: 'Изменения будут потеряны.',
        confirmLabel: 'Закрыть без сохранения',
        cancelLabel: 'Отмена',
        intent: 'warning',
      });
      if (ok) {
        onClose();
      }
    } else {
      onClose();
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
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={patient ? 'Редактировать пациента' : 'Добавить пациента'}
      size="lg">


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
              <label style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '8px'
              }}>
                Фамилия *
              </label>
              <Input
                type="text"
                value={formData.lastName}
                onChange={(e) => handleChange('lastName', e.target.value)}
                placeholder="Иванов"
                error={errors.lastName}
                icon={User} />

              {errors.lastName &&
              <p style={{
                fontSize: 'var(--mac-font-size-xs)',
                color: 'var(--mac-error)',
                marginTop: '4px',
                display: 'flex',
                alignItems: 'center',
                gap: '4px'
              }}>
                  <AlertCircle style={{ width: '14px', height: '14px' }} />
                  {errors.lastName}
                </p>
              }
            </div>

            {/* Имя */}
            <div>
              <label style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '8px'
              }}>
                Имя *
              </label>
              <Input
                type="text"
                value={formData.firstName}
                onChange={(e) => handleChange('firstName', e.target.value)}
                placeholder="Иван"
                error={errors.firstName} />

              {errors.firstName &&
              <p style={{
                fontSize: 'var(--mac-font-size-xs)',
                color: 'var(--mac-error)',
                marginTop: '4px',
                display: 'flex',
                alignItems: 'center',
                gap: '4px'
              }}>
                  <AlertCircle style={{ width: '14px', height: '14px' }} />
                  {errors.firstName}
                </p>
              }
            </div>

            {/* Отчество */}
            <div>
              <label style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '8px'
              }}>
                Отчество
              </label>
              <Input
                type="text"
                value={formData.middleName}
                onChange={(e) => handleChange('middleName', e.target.value)}
                placeholder="Иванович" />

            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Дата рождения */}
            <div>
              <label style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '8px'
              }}>
                Дата рождения *
              </label>
              <Input
                type="date"
                value={formData.birthDate}
                onChange={(e) => handleChange('birthDate', e.target.value)}
                error={errors.birthDate}
                icon={Calendar} />

              {formData.birthDate &&
              <p style={{
                fontSize: 'var(--mac-font-size-xs)',
                color: 'var(--mac-text-secondary)',
                marginTop: '4px',
                marginLeft: '2px'
              }}>
                  Возраст: {new Date().getFullYear() - new Date(formData.birthDate).getFullYear()} лет
                </p>
              }
              {errors.birthDate &&
              <p style={{
                fontSize: 'var(--mac-font-size-xs)',
                color: 'var(--mac-error)',
                marginTop: '4px',
                display: 'flex',
                alignItems: 'center',
                gap: '4px'
              }}>
                  <AlertCircle style={{ width: '14px', height: '14px' }} />
                  {errors.birthDate}
                </p>
              }
            </div>

            {/* Пол */}
            <div>
              <label style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '8px'
              }}>
                Пол *
              </label>
              <Select
                value={formData.gender}
                onChange={(value) => handleChange('gender', value)}
                options={[
                { value: '', label: 'Выберите пол' },
                { value: 'male', label: 'Мужской' },
                { value: 'female', label: 'Женский' }]
                }
                error={errors.gender}
                size="large" />

              {errors.gender &&
              <p style={{
                fontSize: 'var(--mac-font-size-xs)',
                color: 'var(--mac-error)',
                marginTop: '4px',
                display: 'flex',
                alignItems: 'center',
                gap: '4px'
              }}>
                  <AlertCircle style={{ width: '14px', height: '14px' }} />
                  {errors.gender}
                </p>
              }
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
              <label style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '8px'
              }}>
                Телефон *
              </label>
              <Input
                type="tel"
                value={formData.phone}
                onChange={handlePhoneChange}
                placeholder="+998 90 123 45 67"
                error={errors.phone}
                icon={Phone} />

              {errors.phone &&
              <p style={{
                fontSize: 'var(--mac-font-size-xs)',
                color: 'var(--mac-error)',
                marginTop: '4px',
                display: 'flex',
                alignItems: 'center',
                gap: '4px'
              }}>
                  <AlertCircle style={{ width: '14px', height: '14px' }} />
                  {errors.phone}
                </p>
              }
            </div>

            {/* Email */}
            <div>
              <label style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '8px'
              }}>
                Email
              </label>
              <Input
                type="email"
                value={formData.email}
                onChange={(e) => handleChange('email', e.target.value)}
                placeholder="ivan@example.com"
                error={errors.email}
                icon={Mail} />

              {errors.email &&
              <p style={{
                fontSize: 'var(--mac-font-size-xs)',
                color: 'var(--mac-error)',
                marginTop: '4px',
                display: 'flex',
                alignItems: 'center',
                gap: '4px'
              }}>
                  <AlertCircle style={{ width: '14px', height: '14px' }} />
                  {errors.email}
                </p>
              }
            </div>
          </div>

          {/* Адрес */}
          <div>
            <label style={{
              display: 'block',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              marginBottom: '8px'
            }}>
              Адрес
            </label>
            <Input
              type="text"
              value={formData.address}
              onChange={(e) => handleChange('address', e.target.value)}
              placeholder="г. Ташкент, ул. Навои, д. 1"
              icon={MapPin} />

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
              <label style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '8px'
              }}>
                Номер паспорта
              </label>
              <Input
                type="text"
                value={formData.passport}
                onChange={(e) => handleChange('passport', e.target.value)}
                placeholder="AA1234567"
                error={errors.passport}
                icon={IdCard} />

              {errors.passport &&
              <p style={{
                fontSize: 'var(--mac-font-size-xs)',
                color: 'var(--mac-error)',
                marginTop: '4px',
                display: 'flex',
                alignItems: 'center',
                gap: '4px'
              }}>
                  <AlertCircle style={{ width: '14px', height: '14px' }} />
                  {errors.passport}
                </p>
              }
              {!errors.passport &&
              <p style={{
                fontSize: 'var(--mac-font-size-xs)',
                color: 'var(--mac-text-secondary)',
                marginTop: '4px'
              }}>
                  Если поле заполнено, документ будет сохранён как passport.
                </p>
              }
            </div>

            {/* Страховой номер */}
            <div>
              <label style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '8px'
              }}>
                Страховой номер
              </label>
              <Input
                type="text"
                value={formData.insuranceNumber}
                onChange={(e) => handleChange('insuranceNumber', e.target.value)}
                placeholder="12345678901234" />

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
              <label style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '8px'
              }}>
                Контактное лицо
              </label>
              <Input
                type="text"
                value={formData.emergencyContact}
                onChange={(e) => handleChange('emergencyContact', e.target.value)}
                placeholder="Иванова Мария Ивановна" />

            </div>
            <div>
              <label style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '8px'
              }}>
                Телефон экстренного контакта
              </label>
              <Input
                type="tel"
                value={formData.emergencyPhone}
                onChange={(e) => handleChange('emergencyPhone', e.target.value)}
                placeholder="+998 90 987 65 43"
                icon={Phone} />

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
              <label style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '8px'
              }}>
                Группа крови
              </label>
              <Select
                value={formData.bloodType}
                onChange={(value) => handleChange('bloodType', value)}
                options={[
                { value: '', label: 'Не указано' },
                { value: 'A+', label: 'A+' },
                { value: 'A-', label: 'A-' },
                { value: 'B+', label: 'B+' },
                { value: 'B-', label: 'B-' },
                { value: 'AB+', label: 'AB+' },
                { value: 'AB-', label: 'AB-' },
                { value: 'O+', label: 'O+' },
                { value: 'O-', label: 'O-' }]
                }
                size="large" />

            </div>
            <div>
              <label style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '8px'
              }}>
                Аллергии
              </label>
              <Input
                type="text"
                value={formData.allergies}
                onChange={(e) => handleChange('allergies', e.target.value)}
                placeholder="Пенициллин, пыльца" />

            </div>
          </div>
          <div>
            <label style={{
              display: 'block',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              marginBottom: '8px'
            }}>
              Хронические заболевания
            </label>
            <Textarea
              value={formData.chronicDiseases}
              onChange={(e) => handleChange('chronicDiseases', e.target.value)}
              placeholder="Гипертония, диабет"
              rows={3} />

          </div>
        </div>

        {/* Дополнительная информация */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium" style={{ color: 'var(--text-primary)' }}>
            Дополнительная информация
          </h3>
          <div>
            <label style={{
              display: 'block',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              marginBottom: '8px'
            }}>
              Заметки
            </label>
            <Textarea
              value={formData.notes}
              onChange={(e) => handleChange('notes', e.target.value)}
              placeholder="Дополнительная информация о пациенте..."
              rows={3} />

          </div>
        </div>

        {/* Кнопки */}
        <div style={{ display: 'flex', gap: '12px', paddingTop: '16px' }}>
          <Button
            type="submit"
            disabled={isSubmitting || loading}
            aria-label={patient ? 'Save patient changes' : 'Add patient'}
            style={{ flex: 1 }}>

            {isSubmitting ?
            <>
                <div style={{
                width: '16px',
                height: '16px',
                border: '2px solid transparent',
                borderTop: '2px solid currentColor',
                borderRadius: '50%',
                animation: 'spin 1s linear infinite',
                marginRight: '8px'
              }} />
                Сохранение...
              </> :

            <>
                <Save style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                {patient ? 'Сохранить изменения' : 'Добавить пациента'}
              </>
            }
          </Button>
          <Button
            type="button"
            variant="outline"

            onClick={handleClose}
            disabled={isSubmitting}
            style={{ flex: 1 }}>

            Отмена
          </Button>
        </div>
      </form>
      {/* P-013 fix: portal-mounted ConfirmDialog rendered once per panel */}
      {confirmDialog}
    </Modal>);

};


PatientModal.propTypes = {
  ...(PatientModal.propTypes || {}),
  isOpen: PropTypes.any,
  loading: PropTypes.any,
  onClose: PropTypes.any,
  onSave: PropTypes.any,
  patient: PropTypes.any,
};

export default PatientModal;
