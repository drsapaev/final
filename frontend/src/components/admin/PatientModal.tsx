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
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  // P-013 fix: shared ConfirmDialog hook (replaces 1 window.confirm() call).
  const [confirmRaw, confirmDialog] = useConfirm();
  const confirm = confirmRaw as unknown as (opts: Record<string, unknown>) => Promise<boolean>;
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
  } as Record<string, unknown>);
  const [errors, setErrors] = useState<Record<string, string>>({});

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
    const newErrors: Record<string, string> = {};

    if (!String(formData.firstName ?? '').trim()) {
      newErrors.firstName = t('admin2.pm_err_first_name_required');
    }

    if (!String(formData.lastName ?? '').trim()) {
      newErrors.lastName = t('admin2.pm_err_last_name_required');
    }

    if (!String(formData.phone ?? '').trim()) {
      newErrors.phone = t('admin2.pm_err_phone_required');
    } else if (!/^\+998\s?\d{2}\s?\d{3}\s?\d{2}\s?\d{2}$/.test(String(formData.phone ?? '').replace(/\s/g, ''))) {
      newErrors.phone = t('admin2.pm_err_phone_format');
    }

    if (formData.email && !/\S+@\S+\.\S+/.test(String(formData.email ?? ''))) {
      newErrors.email = t('admin2.pm_err_email_format');
    }

    if (!formData.birthDate) {
      newErrors.birthDate = t('admin2.pm_err_birth_date_required');
    } else {
      const birthDate = new Date(String(formData.birthDate));
      const today = new Date();
      const age = today.getFullYear() - birthDate.getFullYear();
      if (age < 0 || age > 120) {
        newErrors.birthDate = t('admin2.pm_err_birth_date_invalid');
      }
    }

    if (!formData.gender) {
      newErrors.gender = t('admin2.pm_err_gender_required');
    }

    // Passport is now optional for quick registration
    // if (!String(formData.passport ?? '').trim()) {
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
        firstName: String(formData.firstName ?? '').trim(),
        lastName: String(formData.lastName ?? '').trim(),
        middleName: String(formData.middleName ?? '').trim(),
        email: String(formData.email ?? '').trim() || null,
        phone: String(formData.phone ?? '').trim(),
        birthDate: formData.birthDate,
        gender: formData.gender,
        address: String(formData.address ?? '').trim() || null,
        passport: String(formData.passport ?? '').trim(),
        insuranceNumber: String(formData.insuranceNumber ?? '').trim() || null,
        emergencyContact: String(formData.emergencyContact ?? '').trim() || null,
        emergencyPhone: String(formData.emergencyPhone ?? '').trim() || null,
        bloodType: formData.bloodType || null,
        allergies: String(formData.allergies ?? '').trim() || null,
        chronicDiseases: String(formData.chronicDiseases ?? '').trim() || null,
        notes: String(formData.notes ?? '').trim() || null
      };

      await onSave(patientData);
      onClose();
    } catch (error) {
      logger.error('Ошибка сохранения пациента:', error);
      setSubmitError(error?.response?.data?.detail || error?.message || t('admin2.pm_err_save'));
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
        message: t('admin2.pm_unsaved_msg'),
        description: t('admin2.pm_unsaved_desc'),
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
      title={patient ? t('admin2.pm_title_edit') : t('admin2.pm_title_create')}
      size="lg">


      {/* Форма */}
      {submitError ? (
        <Alert type="error" className="admin-mb-12">{submitError}</Alert>
      ) : null}
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Личная информация */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium admin-text-primary">
            {t('admin2.pm_section_personal')}
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Фамилия */}
            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
                {t('admin2.pm_label_last_name')}
              </label>
              <Input
                type="text"
                value={String(formData.lastName ?? '')}
                onChange={(e) => handleChange('lastName', e.target.value)}
                placeholder={t('admin2.pm_ph_last_name')}
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
                {t('admin2.pm_label_first_name')}
              </label>
              <Input
                type="text"
                value={String(formData.firstName ?? '')}
                onChange={(e) => handleChange('firstName', e.target.value)}
                placeholder={t('admin2.pm_ph_first_name')}
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
                {t('admin2.pm_label_middle_name')}
              </label>
              <Input
                type="text"
                value={String(formData.middleName ?? '')}
                onChange={(e) => handleChange('middleName', e.target.value)}
                placeholder={t('admin2.pm_ph_middle_name')} />

            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Дата рождения */}
            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
                {t('admin2.pm_label_birth_date')}
              </label>
              <Input
                type="date"
                value={String(formData.birthDate ?? '')}
                onChange={(e) => handleChange('birthDate', e.target.value)}
                error={errors.birthDate}
                icon={Calendar} />

              {formData.birthDate &&
              <p className="admin-fs-xs-secondary-mt-4-ml-2">
                  {t('admin2.pm_age_text', { age: new Date().getFullYear() - new Date(String(formData.birthDate)).getFullYear() })}
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
                {t('admin2.pm_label_gender')}
              </label>
              <Select
                value={String(formData.gender ?? '')}
                onChange={(value) => handleChange('gender', value)}
                options={[
                { value: '', label: t('admin2.pm_gender_placeholder') },
                { value: 'male', label: t('admin2.pm_gender_male') },
                { value: 'female', label: t('admin2.pm_gender_female') }]
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
            {t('admin2.pm_section_contacts')}
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Телефон */}
            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
                {t('admin2.pm_label_phone')}
              </label>
              <Input
                type="tel"
                value={String(formData.phone ?? '')}
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
                value={String(formData.email ?? '')}
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
              {t('admin2.pm_label_address')}
            </label>
            <Input
              type="text"
              value={String(formData.address ?? '')}
              onChange={(e) => handleChange('address', e.target.value)}
              placeholder={t('admin2.pm_ph_address')}
              icon={MapPin} />

          </div>
        </div>

        {/* Документы */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium admin-text-primary">
            {t('admin2.pm_section_documents')}
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Паспорт */}
            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
                {t('admin2.pm_label_passport')}
              </label>
              <Input
                type="text"
                value={String(formData.passport ?? '')}
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
                  {t('admin2.pm_passport_hint')}
                </p>
              }
            </div>

            {/* Страховой номер */}
            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
                {t('admin2.pm_label_insurance')}
              </label>
              <Input
                type="text"
                value={String(formData.insuranceNumber ?? '')}
                onChange={(e) => handleChange('insuranceNumber', e.target.value)}
                placeholder="12345678901234" />

            </div>
          </div>
        </div>

        {/* Экстренный контакт */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium admin-text-primary">
            {t('admin2.pm_section_emergency')}
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
                {t('admin2.pm_label_emergency_contact')}
              </label>
              <Input
                type="text"
                value={String(formData.emergencyContact ?? '')}
                onChange={(e) => handleChange('emergencyContact', e.target.value)}
                placeholder={t('admin2.pm_ph_emergency_contact')} />

            </div>
            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
                {t('admin2.pm_label_emergency_phone')}
              </label>
              <Input
                type="tel"
                value={String(formData.emergencyPhone ?? '')}
                onChange={(e) => handleChange('emergencyPhone', e.target.value)}
                placeholder="+998 90 987 65 43"
                icon={Phone} />

            </div>
          </div>
        </div>

        {/* Медицинская информация */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium admin-text-primary">
            {t('admin2.pm_section_medical')}
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
                {t('admin2.pm_label_blood_type')}
              </label>
              <Select
                value={String(formData.bloodType ?? '')}
                onChange={(value) => handleChange('bloodType', value)}
                options={[
                { value: '', label: t('admin2.pm_blood_type_not_specified') },
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
                {t('admin2.pm_label_allergies')}
              </label>
              <Input
                type="text"
                value={String(formData.allergies ?? '')}
                onChange={(e) => handleChange('allergies', e.target.value)}
                placeholder={t('admin2.pm_ph_allergies')} />

            </div>
          </div>
          <div>
            <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
              {t('admin2.pm_label_chronic')}
            </label>
            <Textarea
              value={String(formData.chronicDiseases ?? '')}
              onChange={(e) => handleChange('chronicDiseases', e.target.value)}
              placeholder={t('admin2.pm_ph_chronic')}
              rows={3} />

          </div>
        </div>

        {/* Дополнительная информация */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium admin-text-primary">
            {t('admin2.pm_section_additional')}
          </h3>
          <div>
            <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
              {t('admin2.pm_label_notes')}
            </label>
            <Textarea
              value={String(formData.notes ?? '')}
              onChange={(e) => handleChange('notes', e.target.value)}
              placeholder={t('admin2.pm_ph_notes')}
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
                {t('admin2.pm_btn_saving')}
              </> :

            <>
                <Save className="admin-icon-16-mr-8" />
                {patient ? t('admin2.pm_btn_save') : t('admin2.pm_btn_create')}
              </>
            }
          </Button>
          <Button
            type="button"
            variant="outline"

            onClick={handleClose}
            disabled={isSubmitting}
            className="admin-flex-1">

            {t('admin2.pm_btn_cancel')}
          </Button>
        </div>
      </form>
      {/* P-013 fix: portal-mounted ConfirmDialog rendered once per panel */}
      {confirmDialog as unknown as React.ReactNode}
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
