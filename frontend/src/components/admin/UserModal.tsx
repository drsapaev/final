
import { useTranslation } from '../../i18n/useTranslation';
import { useState, useEffect } from 'react';
import { User, Mail, Lock, Shield, Save, AlertCircle, Stethoscope } from 'lucide-react';
import { Modal } from '../ui/macos';
import { Button } from '../ui/macos';
import { Checkbox } from '../ui/macos';
import {
  Select,
  Input } from '../ui/macos';
import { useRoles } from '../../hooks/useRoles';
import { api } from '../../api/client';

import logger from '../../utils/logger';
import React from "react";

/**
 * UserModal - macOS-styled modal for creating/editing users
 * Phase 1 refactoring: migrated from native components to macOS design system
 */

interface UserModalUser {
  username?: string;
  email?: string;
  full_name?: string;
  role?: string;
  is_active?: boolean;
  profile?: { full_name?: string } | null;
  [key: string]: unknown;
}

interface UserModalProps {
  isOpen: boolean;
  onClose: () => void;
  user?: UserModalUser | null;
  onSave: (userData: Record<string, unknown>) => Promise<void> | void;
  loading?: boolean;
}

// Owner decision 2026-09-01: canonical onboarding creates doctors as
// User(role=Doctor) + doctor_profile. Legacy doctor-role spellings are
// compatibility-only and must not be offered when CREATING a user; in edit
// mode the user's existing legacy role stays selectable so a plain save
// never performs a hidden role migration.
const LEGACY_DOCTOR_ROLE_VALUES = new Set([
  'cardio', 'derma', 'dentist',
  'cardiologist', 'dermatologist',
  'cardiology', 'dermatology', 'dentistry',
]);

const isLegacyDoctorRoleValue = (value: string) =>
  LEGACY_DOCTOR_ROLE_VALUES.has(String(value).trim().toLowerCase());

// Форм-обёртки вынесены на уровень модуля: компоненты, определённые ВНУТРИ
// UserModal, пересоздавали свой тип на каждом рендере — React размонтировал
// поддерево вместе с <input>, и после первой же введённой буквы пропадал
// фокус/каретка (приходилось кликать в поле заново на каждый символ).
interface FormFieldProps {
  label?: React.ReactNode;
  required?: boolean;
  icon?: React.ComponentType<{ className?: string }>;
  error?: string;
  children?: React.ReactNode;
}

const ErrorMessage = ({ message }: { message?: React.ReactNode }) => (
  <div className="admin-field-error-xs">
    <AlertCircle className="admin-icon-12" />
    {message}
  </div>
);

// Strict onboarding numeric parsing (Codex P2): no silent prefix-truncation
// like parseInt("12abc") → 12. Non-empty invalid input must surface a field
// error and block submit; the backend schema remains authoritative.
// - integer limits: whole-number strings only, then range-checked
// - price: explicit normalization of space/underspace thousands separators
//   ("150 000" → 150000); anything else non-numeric stays invalid
const WHOLE_NUMBER_RE = /^[0-9]+$/;
const NORMALIZED_PRICE_RE = /^[0-9]+(\.[0-9]{1,2})?$/;

const parseStrictWholeNumber = (raw: string): number | null => {
  const trimmed = raw.trim();
  if (!WHOLE_NUMBER_RE.test(trimmed)) return null;
  return Number.parseInt(trimmed, 10);
};

const parseStrictPrice = (raw: string): number | null => {
  const normalized = raw.trim().replace(/[\s\u00A0]/g, '');
  if (!NORMALIZED_PRICE_RE.test(normalized)) return null;
  return Number.parseFloat(normalized);
};

const FormField = ({ label, required, icon: Icon, error, children }: FormFieldProps) => (
  <div className="admin-mb-16">
    <label className="admin-usermodal-label">
      {label} {required && <span className="admin-required-asterisk">*</span>}
    </label>
    <div className="admin-pos-relative">
      {Icon && (
        <Icon className="admin-usermodal-field-icon" />
      )}
      {children}
    </div>
    {error && <ErrorMessage message={error} />}
  </div>
);

const UserModal = ({
  isOpen,
  onClose,
  user = null,
  onSave,
  loading = false
}: UserModalProps) => {
  const { t: rawT } = useTranslation(); const t = rawT;
  const [formData, setFormData] = useState<Record<string, any>>({
    username: '',
    email: '',
    full_name: '',
    role: 'Patient',
    is_active: true,
    password: '',
    confirmPassword: '',
    doctorSpecialty: '',
    doctorCabinet: '',
    doctorPrice: '',
    doctorStartNumber: '',
    doctorMaxOnline: ''
  });
  const [errors, setErrors] = useState<Record<string, any>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [specialtyOptions, setSpecialtyOptions] = useState<{ value: string; label: string }[]>([]);

  // Load roles from API (Phase 4: DB-driven roles - completed)
  const { roleOptions: apiRoleOptions } = useRoles({ includeAll: false });

  // Fallback roles if API fails
  const baseRoleOptions = apiRoleOptions.length > 0 ? apiRoleOptions : [
    { value: 'Admin', label: t('admin2.umdl_role_admin') },
    { value: 'Doctor', label: t('admin2.umdl_role_doctor_general') },
    { value: 'Nurse', label: t('admin2.umdl_role_nurse') },
    { value: 'Registrar', label: t('admin2.umdl_role_registrar') },
    { value: 'Receptionist', label: t('admin2.umdl_role_receptionist') },
    { value: 'Cashier', label: t('admin2.umdl_role_cashier') },
    { value: 'Lab', label: t('admin2.umdl_role_lab') },
    { value: 'Patient', label: t('admin2.umdl_role_patient') }
  ];

  // Canonical onboarding: legacy doctor-role spellings are hidden in create
  // mode. Edit mode keeps the user's current (possibly legacy) role so a
  // plain save does not silently migrate the role.
  const createRoleOptions = baseRoleOptions.filter(
    (option) => !isLegacyDoctorRoleValue(String(option.value))
  );
  const roleOptions = user && !createRoleOptions.some((option) => option.value === user.role)
    ? [...createRoleOptions, { value: user.role as string, label: user.role as string }]
    : createRoleOptions;

  const isDoctorOnboarding = !user && formData.role === 'Doctor';

  // Canonical specialty vocabulary for the onboarding block (Admin-only
  // endpoint; SSOT lives in backend app/core/specialties.py).
  useEffect(() => {
    if (!isOpen || user) return;
    let cancelled = false;
    api
      .get('/admin/doctors/specialty-vocabulary')
      .then((response: { data?: unknown }) => {
        const data = response?.data;
        const items: Array<{ code?: string }> = Array.isArray(data)
          ? (data as Array<{ code?: string }>)
          : ((data as { items?: Array<{ code?: string }> })?.items ?? []);
        if (!cancelled) {
          setSpecialtyOptions(
            items
              .filter((item) => Boolean(item?.code))
              .map((item) => ({
                value: String(item.code),
                label: t(`admin2.umdl_spec_${item.code}`),
              }))
          );
        }
      })
      .catch((fetchError: unknown) => {
        if (!cancelled) setSpecialtyOptions([]);
        logger.error('Error fetching doctor specialty vocabulary:', fetchError);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, user]);

  // Инициализация формы при открытии
  useEffect(() => {
    if (isOpen) {
      if (user) {
        setFormData({
          username: user.username || '',
          email: user.email || '',
          full_name: user.profile?.full_name || user.full_name || '',
          role: user.role || 'Patient',
          is_active: user.is_active !== undefined ? user.is_active : true,
          password: '',
          confirmPassword: '',
          doctorSpecialty: '',
          doctorCabinet: '',
          doctorPrice: '',
          doctorStartNumber: '',
          doctorMaxOnline: ''
        });
      } else {
        setFormData({
          username: '',
          email: '',
          full_name: '',
          role: 'Patient',
          is_active: true,
          password: '',
          confirmPassword: '',
          doctorSpecialty: '',
          doctorCabinet: '',
          doctorPrice: '',
          doctorStartNumber: '',
          doctorMaxOnline: ''
        });
      }
      setErrors({});
    }
  }, [isOpen, user]);

  const validateForm = () => {
    const newErrors: Record<string, string> = {};

    if (!formData.username.trim()) {
      newErrors.username = t('admin2.umdl_err_username_required');
    } else if (formData.username.length < 3) {
      newErrors.username = t('admin2.umdl_err_username_min');
    }

    if (!formData.email.trim()) {
      newErrors.email = t('admin2.umdl_err_email_required');
    } else if (!/\S+@\S+\.\S+/.test(formData.email)) {
      newErrors.email = t('admin2.umdl_err_email_invalid');
    }

    if (!user && !formData.password) {
      newErrors.password = t('admin2.umdl_err_password_required');
    }

    if (formData.password && formData.password.length < 8) {
      newErrors.password = t('admin2.umdl_err_password_min');
    }

    if (formData.password !== formData.confirmPassword) {
      newErrors.confirmPassword = t('admin2.umdl_err_passwords_mismatch');
    }

    // Canonical doctor onboarding: specialty is mandatory — a new system
    // doctor can no longer be created incomplete ("general" sentinel).
    if (isDoctorOnboarding && !formData.doctorSpecialty) {
      newErrors.doctorSpecialty = t('admin2.umdl_err_doctor_specialty_required');
    }

    // Strict numeric validation (Codex P2): partially-numeric or garbage
    // input is a FIELD ERROR that blocks submit — never a silently dropped
    // or prefix-truncated value. Mirrors the backend ranges exactly.
    if (isDoctorOnboarding) {
      const priceRaw = formData.doctorPrice.trim();
      if (priceRaw !== '' && parseStrictPrice(priceRaw) === null) {
        newErrors.doctorPrice = t('admin2.umdl_err_doctor_price_format');
      }
      const startRaw = formData.doctorStartNumber.trim();
      if (startRaw !== '') {
        const parsed = parseStrictWholeNumber(startRaw);
        if (parsed === null || parsed < 1 || parsed > 100) {
          newErrors.doctorStartNumber = t('admin2.umdl_err_doctor_number_range');
        }
      }
      const maxRaw = formData.doctorMaxOnline.trim();
      if (maxRaw !== '') {
        const parsed = parseStrictWholeNumber(maxRaw);
        if (parsed === null || parsed < 1 || parsed > 100) {
          newErrors.doctorMaxOnline = t('admin2.umdl_err_doctor_number_range');
        }
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (!validateForm()) return;

    setIsSubmitting(true);
    try {
      const userData: Record<string, any> = {
        username: formData.username.trim(),
        email: formData.email.trim(),
        full_name: formData.full_name.trim(),
        role: formData.role,
        is_active: formData.is_active
      };

      if (formData.password) {
        userData.password = formData.password;
      }

      // doctor_profile is attached ONLY for the canonical doctor onboarding
      // path — switching Doctor → non-doctor before submit cannot leak stale
      // form state into the payload. Numeric values were range/format-checked
      // in validateForm (strict parsing: no prefix truncation); empty fields
      // stay omitted so backend defaults apply.
      if (isDoctorOnboarding) {
        const doctorProfile: Record<string, unknown> = {
          specialty: formData.doctorSpecialty,
        };
        if (formData.doctorCabinet.trim()) {
          doctorProfile.cabinet = formData.doctorCabinet.trim();
        }
        if (formData.doctorPrice.trim() !== '') {
          doctorProfile.price_default = parseStrictPrice(formData.doctorPrice.trim());
        }
        if (formData.doctorStartNumber.trim() !== '') {
          doctorProfile.start_number_online = parseStrictWholeNumber(formData.doctorStartNumber.trim());
        }
        if (formData.doctorMaxOnline.trim() !== '') {
          doctorProfile.max_online_per_day = parseStrictWholeNumber(formData.doctorMaxOnline.trim());
        }
        userData.doctor_profile = doctorProfile;
      }

      await onSave(userData);
      onClose();
    } catch (error) {
      logger.error('Ошибка сохранения пользователя:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleChange = (field: string, value: unknown) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: null }));
    }
  };



  // audit/strict: removed self-referencing propTypes spread



// audit/strict: removed self-referencing propTypes spread

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={user ? t('admin2.umdl_title_edit') : t('admin2.umdl_title_add')}
      size="default"
      closable
    >
      <form onSubmit={handleSubmit}>
        {/* Username */}
        <FormField
          label={t('admin2.umdl_field_username')}
          required
          icon={User}
          error={errors.username}
        >
          <Input
            type="text"
            value={formData.username}
            onChange={(e) => handleChange('username', e.target.value)}
            placeholder={t('admin2.umdl_ph_username')}
            error={!!errors.username}
            className="admin-input-pl-40"
          />
        </FormField>

        {/* Full Name */}
        <FormField label={t('admin2.umdl_field_full_name')}>
          <Input
            type="text"
            value={formData.full_name}
            onChange={(e) => handleChange('full_name', e.target.value)}
            placeholder={t('admin2.umdl_ph_full_name')}
          />
        </FormField>

        {/* Email */}
        <FormField
          label="Email"
          required
          icon={Mail}
          error={errors.email}
        >
          <Input
            type="email"
            value={formData.email}
            onChange={(e) => handleChange('email', e.target.value)}
            placeholder={t('admin2.umdl_ph_email')}
            error={!!errors.email}
            className="admin-input-pl-40"
          />
        </FormField>

        {/* Role */}
        <FormField label={t('admin2.umdl_field_role')} icon={Shield}>
          <Select
            value={formData.role}
            onValueChange={(value) => handleChange('role', value)}
            options={roleOptions}
            size="large"
            className="admin-input-pl-40"
          />
        </FormField>

        {/* Doctor profile block — canonical new-doctor onboarding only */}
        {isDoctorOnboarding && (
          <div className="admin-doctor-onboarding-block">
            <div className="admin-flex-center-12 admin-mb-8">
              <Stethoscope className="admin-icon-16" />
              <span className="admin-font-semibold">
                {t('admin2.umdl_doctor_profile_section')}
              </span>
            </div>
            <p className="admin-patients-subtitle admin-mb-12">
              {t('admin2.umdl_doctor_hint')}
            </p>
            <FormField
              label={t('admin2.umdl_doctor_specialty')}
              required
              error={errors.doctorSpecialty}
            >
              <Select
                value={formData.doctorSpecialty}
                onValueChange={(value) => handleChange('doctorSpecialty', value)}
                options={[
                  { value: '', label: t('admin2.umdl_doctor_specialty_ph') },
                  ...specialtyOptions,
                ]}
                size="large"
              />
            </FormField>
            <div className="admin-doctor-onboarding-grid">
              <FormField label={t('admin2.umdl_doctor_cabinet')}>
                <Input
                  type="text"
                  value={formData.doctorCabinet}
                  onChange={(e) => handleChange('doctorCabinet', e.target.value)}
                  placeholder="12"
                />
              </FormField>
              <FormField label={t('admin2.umdl_doctor_price')} error={errors.doctorPrice}>
                <Input
                  type="text"
                  inputMode="decimal"
                  value={formData.doctorPrice}
                  onChange={(e) => handleChange('doctorPrice', e.target.value)}
                  placeholder="150000"
                  error={!!errors.doctorPrice}
                />
              </FormField>
              <FormField label={t('admin2.umdl_doctor_start_number')} error={errors.doctorStartNumber}>
                <Input
                  type="text"
                  inputMode="numeric"
                  value={formData.doctorStartNumber}
                  onChange={(e) => handleChange('doctorStartNumber', e.target.value)}
                  placeholder="1"
                  error={!!errors.doctorStartNumber}
                />
              </FormField>
              <FormField label={t('admin2.umdl_doctor_max_online')} error={errors.doctorMaxOnline}>
                <Input
                  type="text"
                  inputMode="numeric"
                  value={formData.doctorMaxOnline}
                  onChange={(e) => handleChange('doctorMaxOnline', e.target.value)}
                  placeholder="15"
                  error={!!errors.doctorMaxOnline}
                />
              </FormField>
            </div>
          </div>
        )}

        {/* Status */}
        <div className="admin-mb-16">
          <label className="admin-usermodal-label-mb-8">
            {t('admin2.umdl_field_status')}
          </label>
          <Checkbox
            checked={formData.is_active}
            onChange={(checked) => handleChange('is_active', checked)}
            label={t('admin2.umdl_active_user')}
          />
        </div>

        {/* Password */}
        <FormField
          label={user ? t('admin2.umdl_field_password_new') : t('admin2.umdl_field_password')}
          required={!user}
          icon={Lock}
          error={errors.password}
        >
          <Input
            type="password"
            value={formData.password}
            onChange={(e) => handleChange('password', e.target.value)}
            placeholder={t('admin2.umdl_ph_password')}
            error={!!errors.password}
            className="admin-input-pl-40"
          />
        </FormField>

        {/* Confirm Password */}
        {formData.password && (
          <FormField
            label={t('admin2.umdl_field_password_confirm')}
            required
            icon={Lock}
            error={errors.confirmPassword}
          >
            <Input
              type="password"
              value={formData.confirmPassword}
              onChange={(e) => handleChange('confirmPassword', e.target.value)}
              placeholder={t('admin2.umdl_ph_password_confirm')}
              error={!!errors.confirmPassword}
              className="admin-input-pl-40"
            />
          </FormField>
        )}

        {/* Action Buttons */}
        <div className="admin-usermodal-actions">
          <Button
            type="button"
            variant="secondary"
            onClick={onClose}
            disabled={isSubmitting}
          >
            {t('admin2.umdl_btn_cancel')}
          </Button>
          <Button
            type="submit"
            variant="primary"
            aria-label={user ? 'Save user changes' : 'Create user'}
            disabled={isSubmitting || loading}
          >
            {isSubmitting ? (
              <>
                <div className="admin-spinner-14-white" />
                {t('admin2.umdl_btn_saving')}
              </>
            ) : (
              <>
                <Save className="admin-icon-14-mr-6" />
                {user ? t('admin2.umdl_btn_save_changes') : t('admin2.umdl_btn_create')}
              </>
            )}
          </Button>
        </div>
      </form>

      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </Modal>
  );
};


// audit/strict: removed self-referencing propTypes spread

export default UserModal;
