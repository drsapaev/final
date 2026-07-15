import { useTranslation } from '../../i18n/useTranslation';
import { useState, useEffect } from 'react';
import { Save, User, Mail, Phone, MapPin, Calendar, IdCard, AlertCircle } from 'lucide-react';
import logger from '../../utils/logger';
import {
  Button,
  Input,
  Select,
  Textarea,
  Modal,
  Alert,
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
  const { t } = useTranslation();
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
  const [submitError, setSubmitError] = useState(null);
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
      setSubmitError(null);
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
      setSubmitError(error?.response?.data?.detail || error?.message || 'Ошибка сохранения пациента');
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
        title: t('admin2.unsaved_changes_title'),
        message: 'У вас есть несохранённые изменения. Закрыть окно?',
        description: 'Изменения будут потеряны.',
        confirmLabel: t('admin2.close_without_saving'),
        cancelLabel: t('admin2.cancel'),
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
      {submitError ? (
        <Alert type="error" className="admin-mb-12">{submitError}</Alert>
      ) : null}
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Личная информация */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium admin-text-primary">
            Личная информация
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Фамилия */}
            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
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
              <p className="admin-fs-xs-error-mt-4-d-flex-ai-center-gap-4-12">
                  <AlertCircle className="admin-icon-14" />
                  {errors.lastName}
                </p>
              }
            </div>

            {/* Имя */}
            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
                Имя *
              </label>
              <Input
                type="text"
                value={formData.firstName}
                onChange={(e) => handleChange('firstName', e.target.value)}
                placeholder="Иван"
                error={errors.firstName} />

              {errors.firstName &&
              <p className="admin-fs-xs-error-mt-4-d-flex-ai-center-gap-4-11">
                  <AlertCircle className="admin-icon-14" />
                  {errors.firstName}
                </p>
              }
            </div>

            {/* Отчество */}
            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
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
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
                Дата рождения *
              </label>
              <Input
                type="date"
                value={formData.birthDate}
                onChange={(e) => handleChange('birthDate', e.target.value)}
                error={errors.birthDate}
                icon={Calendar} />

              {formData.birthDate &&
              <p className="admin-fs-xs-secondary-mt-4-ml-2">
                  Возраст: {new Date().getFullYear() - new Date(formData.birthDate).getFullYear()} лет
                </p>
              }
              {errors.birthDate &&
              <p className="admin-fs-xs-error-mt-4-d-flex-ai-center-gap-4-10">
                  <AlertCircle className="admin-icon-14" />
                  {errors.birthDate}
                </p>
              }
            </div>

            {/* Пол */}
            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
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
              <p className="admin-fs-xs-error-mt-4-d-flex-ai-center-gap-4-9">
                  <AlertCircle className="admin-icon-14" />
                  {errors.gender}
                </p>
              }
            </div>
          </div>
        </div>

        {/* Контактная информация */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium admin-text-primary">
            Контактная информация
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Телефон */}
            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
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
              <p className="admin-fs-xs-error-mt-4-d-flex-ai-center-gap-4-8">
                  <AlertCircle className="admin-icon-14" />
                  {errors.phone}
                </p>
              }
            </div>

            {/* Email */}
            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
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
              <p className="admin-fs-xs-error-mt-4-d-flex-ai-center-gap-4-7">
                  <AlertCircle className="admin-icon-14" />
                  {errors.email}
                </p>
              }
            </div>
          </div>

          {/* Адрес */}
          <div>
            <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
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
          <h3 className="text-lg font-medium admin-text-primary">
            Документы
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Паспорт */}
            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
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
              <p className="admin-fs-xs-error-mt-4-d-flex-ai-center-gap-4-6">
                  <AlertCircle className="admin-icon-14" />
                  {errors.passport}
                </p>
              }
              {!errors.passport &&
              <p className="admin-fs-xs-secondary-mt-4">
                  Если поле заполнено, документ будет сохранён как passport.
                </p>
              }
            </div>

            {/* Страховой номер */}
            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
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
          <h3 className="text-lg font-medium admin-text-primary">
            Экстренный контакт
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
                Контактное лицо
              </label>
              <Input
                type="text"
                value={formData.emergencyContact}
                onChange={(e) => handleChange('emergencyContact', e.target.value)}
                placeholder="Иванова Мария Ивановна" />

            </div>
            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
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
          <h3 className="text-lg font-medium admin-text-primary">
            Медицинская информация
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
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
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
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
            <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
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
          <h3 className="text-lg font-medium admin-text-primary">
            Дополнительная информация
          </h3>
          <div>
            <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
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
        <div className="admin-d-flex-gap-12-pt-16-1">
          <Button
            type="submit"
            disabled={isSubmitting || loading}
            aria-label={patient ? 'Save patient changes' : 'Add patient'}
            className="admin-flex-1">

            {isSubmitting ?
            <>
                <div className="admin-w-16-h-16-bd-2px-solid-transparen-bd-t-2px-solid-currentCol-radius-50pct-anim-spin-1s-linear-infin-mr-8" />
                Сохранение...
              </> :

            <>
                <Save className="admin-icon-16-mr-8" />
                {patient ? 'Сохранить изменения' : 'Добавить пациента'}
              </>
            }
          </Button>
          <Button
            type="button"
            variant="outline"

            onClick={handleClose}
            disabled={isSubmitting}
            className="admin-flex-1">

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
