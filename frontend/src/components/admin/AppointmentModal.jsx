import { useState, useEffect, useMemo } from 'react';
import { Save, Calendar, Clock, AlertCircle, Phone, Mail } from 'lucide-react';
import logger from '../../utils/logger';
import {
  Button,
  Badge,
  Input,
  Select,
  Textarea,
  Modal,
  Alert,
} from '../ui/macos';
import PropTypes from 'prop-types';
import { useTranslation } from '../../i18n/useTranslation';

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
    status: '',
    reason: '',
    notes: '',
    phone: '',
    email: ''
  });
  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const selectedDoctor = useMemo(
    () => doctors.find((doctor) => doctor.id === parseInt(formData.doctorId, 10)) || null,
    [doctors, formData.doctorId]
  );

  // Инициализация формы при открытии
  useEffect(() => {
    if (isOpen) {
      if (appointment) {
        setFormData({
          patientId: appointment.patientId || appointment.patient_id || '',
          doctorId: appointment.doctorId || appointment.doctor_id || '',
          appointmentDate: appointment.appointmentDate || '',
          appointmentTime: appointment.appointmentTime || '',
          duration: appointment.duration || 30,
          status: appointment.status || '',
          reason: appointment.reason || appointment.notes || '',
          notes: appointment.notes || '',
          phone: appointment.phone || '',
          email: appointment.email || ''
        });
      } else {
        setFormData({
          patientId: '',
          doctorId: '',
          appointmentDate: '',
          appointmentTime: '',
          duration: 30,
          status: '',
          reason: '',
          notes: '',
          phone: '',
          email: ''
        });
      }
      setErrors({});
    setSubmitError(null);
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
        reason: formData.reason.trim(),
        notes: formData.notes.trim() || null,
        phone: formData.phone.trim() || null,
        email: formData.email.trim() || null
      };
      if (formData.status) {
        appointmentData.status = formData.status;
      }

      await onSave(appointmentData);
      onClose();
    } catch (error) {
      logger.error('Ошибка сохранения записи:', error);
      setSubmitError(error?.response?.data?.detail || error?.message || 'Ошибка сохранения записи');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    if (errors[field]) {
      setErrors((prev) => ({ ...prev, [field]: null }));
    }
  };

  const getPatientDisplayName = (patient) => {
    if (!patient) return '';
    return (
      patient.fullName ||
      patient.full_name ||
      [patient.lastName || patient.last_name, patient.firstName || patient.first_name, patient.middleName || patient.middle_name]
        .filter(Boolean)
        .join(' ')
    );
  };

  const getPatientName = (patientId) => {
    const patient = patients.find((p) => p.id === parseInt(patientId));
    return getPatientDisplayName(patient);
  };

  const getDoctorDisplayName = (doctor) => {
    if (!doctor) return '';
    return doctor.user?.full_name || doctor.user?.username || doctor.name || `Врач #${doctor.id}`;
  };

  const getDoctorName = (doctorId) => {
    const doctor = doctors.find((d) => d.id === parseInt(doctorId));
    return doctor ? `${getDoctorDisplayName(doctor)} (${doctor.specialty || doctor.specialization || '—'})` : '';
  };

  if (!isOpen) return null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={appointment ? 'Редактировать запись' : 'Создать запись на прием'}
      size="lg">
      
          {/* Submit error (P1 fix: show save errors instead of swallowing) */}
          {submitError ? (
            <Alert type="error" className="admin-mb-12">{submitError}</Alert>
          ) : null}

          {/* Форма */}
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Основная информация */}
            <div className="admin-mb-24">
              <h3 className="admin-fs-lg-fw-semi-primary-mb-16">
                Основная информация
              </h3>
              <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-16">
                {/* Пациент */}
                <div>
                  <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
                    Пациент *
                  </label>
                  <Select
                value={formData.patientId}
                onChange={(value) => handleChange('patientId', value)}
                options={[
                { value: '', label: 'Выберите пациента' },
                ...patients.map((patient) => ({
                  value: String(patient.id),
                  label: `${getPatientDisplayName(patient)}${patient.phone ? ` - ${patient.phone}` : ''}`
                }))]
                }
                error={errors.patientId}
                size="large" />
              
                  {errors.patientId &&
              <p className="admin-fs-xs-error-mt-4-d-flex-ai-center-gap-4-5">
                      <AlertCircle className="admin-icon-14" />
                      {errors.patientId}
                    </p>
              }
                </div>

                {/* Врач */}
                <div>
                  <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
                    Врач *
                  </label>
                  <Select
                value={formData.doctorId}
                onChange={(value) => handleChange('doctorId', value)}
                options={[
                { value: '', label: 'Выберите врача' },
                ...doctors.map((doctor) => ({
                  value: String(doctor.id),
                  label: `${getDoctorDisplayName(doctor)} - ${doctor.specialty || doctor.specialization || '—'}${doctor.active === false ? ' • неактивен' : ''}${doctor.user?.is_active === false ? ' • аккаунт неактивен' : ''}${doctor.cabinet ? ` • кабинет ${doctor.cabinet}` : ''}`
                }))]
                }
                error={errors.doctorId}
                size="large" />
              
                  {errors.doctorId &&
              <p className="admin-fs-xs-error-mt-4-d-flex-ai-center-gap-4-4">
                      <AlertCircle className="admin-icon-14" />
                      {errors.doctorId}
                    </p>
              }
                </div>
              </div>

              <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-16">
                {/* Дата записи */}
                <div>
                  <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
                    Дата записи *
                  </label>
                  <Input
                type="date"
                value={formData.appointmentDate}
                onChange={(e) => handleChange('appointmentDate', e.target.value)}
                error={errors.appointmentDate}
                icon={Calendar} />
              
                  {errors.appointmentDate &&
              <p className="admin-fs-xs-error-mt-4-d-flex-ai-center-gap-4-3">
                      <AlertCircle className="admin-icon-14" />
                      {errors.appointmentDate}
                    </p>
              }
                </div>

                {/* Время записи */}
                <div>
                  <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
                    Время записи *
                  </label>
                  <Input
                type="time"
                value={formData.appointmentTime}
                onChange={(e) => handleChange('appointmentTime', e.target.value)}
                error={errors.appointmentTime}
                icon={Clock} />
              
                  {errors.appointmentTime &&
              <p className="admin-fs-xs-error-mt-4-d-flex-ai-center-gap-4-2">
                      <AlertCircle className="admin-icon-14" />
                      {errors.appointmentTime}
                    </p>
              }
                </div>

                {/* Длительность */}
                <div>
                  <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
                    Длительность (мин)
                  </label>
                  <Input
                type="number"
                value={formData.duration}
                onChange={(e) => handleChange('duration', e.target.value)}
                error={errors.duration}
                min="15"
                max="120"
                step="15" />
              
                  {errors.duration &&
              <p className="admin-fs-xs-error-mt-4-d-flex-ai-center-gap-4-1">
                      <AlertCircle className="admin-icon-14" />
                      {errors.duration}
                    </p>
              }
                </div>
              </div>

              {/* Статус */}
              <div>
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
                  Статус записи
                </label>
                <Select
              value={formData.status}
              onChange={(value) => handleChange('status', value)}
              options={[
              { value: '', label: 'По умолчанию backend' },
              { value: 'pending', label: 'Ожидает' },
              { value: 'confirmed', label: 'Подтверждена' },
              { value: 'paid', label: 'Оплачена' },
              { value: 'in_visit', label: 'На приеме' },
              { value: 'completed', label: 'Завершена' },
              { value: 'cancelled', label: 'Отменена' },
              { value: 'no_show', label: 'Не явился' }]
              }
              size="large" />
            
              </div>
            </div>

            {/* Детали записи */}
            <div className="admin-mb-24">
              <h3 className="admin-fs-lg-fw-semi-primary-mb-16">
                Детали записи
              </h3>
              <div>
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
                  Причина обращения *
                </label>
                <Textarea
              value={formData.reason}
              onChange={(e) => handleChange('reason', e.target.value)}
              error={errors.reason}
              rows={3}
              placeholder="Опишите причину обращения к врачу" />
            
                {errors.reason &&
            <p className="admin-fs-xs-error-mt-4-d-flex-ai-center-gap-4">
                    <AlertCircle className="admin-icon-14" />
                    {errors.reason}
                  </p>
            }
              </div>

              <div>
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
                  Дополнительные заметки
                </label>
                <Textarea
              value={formData.notes}
              onChange={(e) => handleChange('notes', e.target.value)}
              rows={2}
              placeholder="Дополнительная информация о записи" />
            
              </div>
            </div>

            {/* Контактная информация */}
            <div className="admin-mb-24">
              <h3 className="admin-fs-lg-fw-semi-primary-mb-16">
                Контактная информация
              </h3>
              <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-16">
                <div>
                  <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
                    Телефон для связи
                  </label>
                  <Input
                type="tel"
                value={formData.phone}
                onChange={(e) => handleChange('phone', e.target.value)}
                placeholder="+998 90 123 45 67"
                icon={Phone} />
              
                </div>
                <div>
                  <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
                    Email для уведомлений
                  </label>
                  <Input
                type="email"
                value={formData.email}
                onChange={(e) => handleChange('email', e.target.value)}
                placeholder="patient@example.com"
                icon={Mail} />
              
                </div>
              </div>
            </div>

            {/* Предварительный просмотр */}
            {formData.patientId && formData.doctorId &&
        <div className="admin-mb-24">
                <h3 className="admin-fs-lg-fw-semi-primary-mb-16">
                  Предварительный просмотр
                </h3>
                <div className="admin-p-16-radius-var-mac-border-radiu-bg-bg-secondary-bd-1px-solid-var-mac-bo-d-flex-fd-column-gap-8">
                  <p className="admin-fs-sm-secondary-m-0">
                    <strong className="admin-text-primary">Пациент:</strong> {getPatientName(formData.patientId)}
                  </p>
                  <p className="admin-fs-sm-secondary-m-0">
                    <strong className="admin-text-primary">Врач:</strong> {getDoctorName(formData.doctorId)}
                  </p>
                  <div className="admin-d-flex-fw-wrap-gap-8-mt-8">
                    <Badge
                      variant={
                        selectedDoctor?.active === false || selectedDoctor?.user?.is_active === false
                          ? 'warning'
                          : 'success'
                      }
                    >
                      {selectedDoctor?.active === false
                        ? 'Врач неактивен'
                        : selectedDoctor?.user?.is_active === false
                          ? 'Аккаунт врача неактивен'
                          : 'Связь активна'}
                    </Badge>
                    <Badge variant={selectedDoctor?.cabinet ? 'info' : 'warning'}>
                      {selectedDoctor?.cabinet ? `Кабинет ${selectedDoctor.cabinet}` : 'Кабинет не задан'}
                    </Badge>
                  </div>
                  <p className="admin-fs-sm-secondary-m-0">
                    <strong className="admin-text-primary">Дата и время:</strong> {formData.appointmentDate} в {formData.appointmentTime}
                  </p>
                  <p className="admin-fs-sm-secondary-m-0">
                    <strong className="admin-text-primary">Длительность:</strong> {formData.duration} минут
                  </p>
                  <p className="admin-fs-sm-secondary-m-0">
                    <strong className="admin-text-primary">Статус:</strong> {formData.status === 'pending' ? 'Ожидает' :
              formData.status === 'confirmed' ? 'Подтверждена' :
              formData.status === 'paid' ? 'Оплачена' :
              formData.status === 'in_visit' ? 'На приеме' :
              formData.status === 'completed' ? 'Завершена' :
              formData.status === 'cancelled' ? 'Отменена' : 'Не явился'}
                  </p>
                </div>
              </div>
        }

            {/* Кнопки */}
            <div className="admin-d-flex-gap-12-pt-16">
              <Button
            type="submit"
            disabled={isSubmitting || loading}
            aria-label={appointment ? 'Save appointment changes' : 'Create appointment'}
            className="flex-1 admin-bg-var-accent-color-white"
            >
            
                {isSubmitting ?
            <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin mr-2" />
                    Сохранение...
                  </> :

            <>
                    <Save className="w-4 h-4 mr-2" />
                    {appointment ? 'Сохранить изменения' : 'Создать запись'}
                  </>
            }
              </Button>
              <Button
            type="button"
            variant="outline"
            onClick={onClose}
            disabled={isSubmitting}>
            
                Отмена
              </Button>
            </div>
          </form>
    </Modal>);

};


AppointmentModal.propTypes = {
  ...(AppointmentModal.propTypes || {}),
  appointment: PropTypes.any,
  doctors: PropTypes.any,
  isOpen: PropTypes.any,
  loading: PropTypes.any,
  onClose: PropTypes.any,
  onSave: PropTypes.any,
  patients: PropTypes.any,
};

export default AppointmentModal;
