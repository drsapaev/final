
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
import React from "react";

const AppointmentModal = ({
  isOpen,
  onClose,
  appointment = null,
  onSave,
  loading = false,
  doctors = [],
  patients = []
}) => {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [formData, setFormData] = useState<Record<string, any>>({
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
  const [errors, setErrors] = useState<Record<string, any>>({});
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
    const newErrors: Record<string, string> = {};

    if (!formData.patientId) {
      newErrors.patientId = t('admin2.am_err_patient_required');
    }

    if (!formData.doctorId) {
      newErrors.doctorId = t('admin2.am_err_doctor_required');
    }

    if (!formData.appointmentDate) {
      newErrors.appointmentDate = t('admin2.am_err_date_required');
    } else {
      const appointmentDate = new Date(formData.appointmentDate);
      const today = new Date();
      today.setHours(0, 0, 0, 0);

      if (appointmentDate < today) {
        newErrors.appointmentDate = t('admin2.am_err_date_past');
      }
    }

    if (!formData.appointmentTime) {
      newErrors.appointmentTime = t('admin2.am_err_time_required');
    }

    if (!formData.reason.trim()) {
      newErrors.reason = t('admin2.am_err_reason_required');
    }

    if (formData.duration < 15 || formData.duration > 120) {
      newErrors.duration = t('admin2.am_err_duration_range');
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
      if ((formData as Record<string, any>).status) {
        (appointmentData as Record<string, any>).status = (formData as Record<string, any>).status;
      }

      await onSave(appointmentData);
      onClose();
    } catch (error) {
      logger.error('Ошибка сохранения записи:', error);
      setSubmitError(error?.response?.data?.detail || error?.message || t('admin2.am_err_save'));
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
    return doctor.user?.full_name || doctor.user?.username || doctor.name || t('admin2.am_doctor_fallback', { id: doctor.id });
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
      title={appointment ? t('admin2.am_title_edit') : t('admin2.am_title_create')}
      size="large">
      
          {/* Submit error (P1 fix: show save errors instead of swallowing) */}
          {submitError ? (
            <Alert type="error" className="admin-mb-12">{submitError}</Alert>
          ) : null}

          {/* Форма */}
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Основная информация */}
            <div className="admin-mb-24">
              <h3 className="admin-fs-lg-fw-semi-primary-mb-16">
                {t('admin2.am_section_main')}
              </h3>
              <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-16">
                {/* Пациент */}
                <div>
                  <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
                    {t('admin2.am_label_patient')}
                  </label>
                  <Select
                value={formData.patientId}
                onChange={(value) => handleChange('patientId', value)}
                options={[
                { value: '', label: t('admin2.am_placeholder_patient') },
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
                    {t('admin2.am_label_doctor')}
                  </label>
                  <Select
                value={formData.doctorId}
                onChange={(value) => handleChange('doctorId', value)}
                options={[
                { value: '', label: t('admin2.am_placeholder_doctor') },
                ...doctors.map((doctor) => ({
                  value: String(doctor.id),
                  label: `${getDoctorDisplayName(doctor)} - ${doctor.specialty || doctor.specialization || '—'}${doctor.active === false ? t('admin2.am_suffix_inactive') : ''}${doctor.user?.is_active === false ? t('admin2.am_suffix_account_inactive') : ''}${doctor.cabinet ? t('admin2.am_suffix_cabinet', { cabinet: doctor.cabinet }) : ''}`
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
                    {t('admin2.am_label_date')}
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
                    {t('admin2.am_label_time')}
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
                    {t('admin2.am_label_duration')}
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
                  {t('admin2.am_label_status')}
                </label>
                <Select
              value={(formData as Record<string, any>).status}
              onChange={(value) => handleChange('status', value)}
              options={[
              { value: '', label: t('admin2.am_status_default') },
              { value: 'pending', label: t('admin2.am_status_pending') },
              { value: 'confirmed', label: t('admin2.am_status_confirmed') },
              { value: 'paid', label: t('admin2.am_status_paid') },
              { value: 'in_visit', label: t('admin2.am_status_in_visit') },
              { value: 'completed', label: t('admin2.am_status_completed') },
              { value: 'cancelled', label: t('admin2.am_status_cancelled') },
              { value: 'no_show', label: t('admin2.am_status_no_show') }]
              }
              size="large" />
            
              </div>
            </div>

            {/* Детали записи */}
            <div className="admin-mb-24">
              <h3 className="admin-fs-lg-fw-semi-primary-mb-16">
                {t('admin2.am_section_details')}
              </h3>
              <div>
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
                  {t('admin2.am_label_reason')}
                </label>
                <Textarea
              value={formData.reason}
              onChange={(e) => handleChange('reason', e.target.value)}
              error={errors.reason}
              rows={3}
              placeholder={t('admin2.am_placeholder_reason')} />
            
                {errors.reason &&
            <p className="admin-fs-xs-error-mt-4-d-flex-ai-center-gap-4">
                    <AlertCircle className="admin-icon-14" />
                    {errors.reason}
                  </p>
            }
              </div>

              <div>
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
                  {t('admin2.am_label_notes')}
                </label>
                <Textarea
              value={formData.notes}
              onChange={(e) => handleChange('notes', e.target.value)}
              rows={2}
              placeholder={t('admin2.am_placeholder_notes')} />
            
              </div>
            </div>

            {/* Контактная информация */}
            <div className="admin-mb-24">
              <h3 className="admin-fs-lg-fw-semi-primary-mb-16">
                {t('admin2.am_section_contacts')}
              </h3>
              <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-16">
                <div>
                  <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
                    {t('admin2.am_label_phone')}
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
                    {t('admin2.am_label_email')}
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
                  {t('admin2.am_section_preview')}
                </h3>
                <div className="admin-p-16-radius-var-mac-border-radiu-bg-bg-secondary-bd-1px-solid-var-mac-bo-d-flex-fd-column-gap-8">
                  <p className="admin-fs-sm-secondary-m-0">
                    <strong className="admin-text-primary">{t('admin2.am_preview_patient')}</strong> {getPatientName(formData.patientId)}
                  </p>
                  <p className="admin-fs-sm-secondary-m-0">
                    <strong className="admin-text-primary">{t('admin2.am_preview_doctor')}</strong> {getDoctorName(formData.doctorId)}
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
                        ? t('admin2.am_badge_doctor_inactive')
                        : selectedDoctor?.user?.is_active === false
                          ? t('admin2.am_badge_doctor_account_inactive')
                          : t('admin2.am_badge_link_active')}
                    </Badge>
                    <Badge variant={selectedDoctor?.cabinet ? 'info' : 'warning'}>
                      {selectedDoctor?.cabinet ? t('admin2.am_badge_cabinet', { cabinet: selectedDoctor.cabinet }) : t('admin2.am_badge_cabinet_not_set')}
                    </Badge>
                  </div>
                  <p className="admin-fs-sm-secondary-m-0">
                    <strong className="admin-text-primary">{t('admin2.am_preview_datetime')}</strong> {formData.appointmentDate} {t('admin2.am_preview_at')} {formData.appointmentTime}
                  </p>
                  <p className="admin-fs-sm-secondary-m-0">
                    <strong className="admin-text-primary">{t('admin2.am_preview_duration_label')}</strong> {formData.duration} {t('admin2.am_preview_duration_minutes')}
                  </p>
                  <p className="admin-fs-sm-secondary-m-0">
                    <strong className="admin-text-primary">{t('admin2.am_preview_status')}</strong> {(formData as Record<string, any>).status === 'pending' ? t('admin2.am_status_pending') :
              (formData as Record<string, any>).status === 'confirmed' ? t('admin2.am_status_confirmed') :
              (formData as Record<string, any>).status === 'paid' ? t('admin2.am_status_paid') :
              (formData as Record<string, any>).status === 'in_visit' ? t('admin2.am_status_in_visit') :
              (formData as Record<string, any>).status === 'completed' ? t('admin2.am_status_completed') :
              (formData as Record<string, any>).status === 'cancelled' ? t('admin2.am_status_cancelled') : t('admin2.am_status_no_show')}
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
                    {t('admin2.am_btn_saving')}
                  </> :

            <>
                    <Save className="w-4 h-4 mr-2" />
                    {appointment ? t('admin2.am_btn_save') : t('admin2.am_btn_create')}
                  </>
            }
              </Button>
              <Button
            type="button"
            variant="outline"
            onClick={onClose}
            disabled={isSubmitting}>
            
                {t('admin2.am_btn_cancel')}
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
