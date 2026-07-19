
import { useTranslation } from '../../i18n/useTranslation';
import { useState, useEffect } from 'react';
import { User, Mail, Lock, Shield, Save, AlertCircle } from 'lucide-react';
import { Modal } from '../ui/macos';
import { Button } from '../ui/macos';
import { Checkbox } from '../ui/macos';
import {
  Select,
  Input } from '../ui/macos';
import { useRoles } from '../../hooks/useRoles';

import logger from '../../utils/logger';
import PropTypes from 'prop-types';
import React from "react";

/**
 * UserModal - macOS-styled modal for creating/editing users
 * Phase 1 refactoring: migrated from native components to macOS design system
 */
const UserModal = ({
  isOpen,
  onClose,
  user = null,
  onSave,
  loading = false
}) => {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [formData, setFormData] = useState<Record<string, any>>({
    username: '',
    email: '',
    full_name: '',
    role: 'Patient',
    is_active: true,
    password: '',
    confirmPassword: ''
  });
  const [errors, setErrors] = useState<Record<string, any>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Load roles from API (Phase 4: DB-driven roles - completed)
  const { roleOptions: apiRoleOptions } = useRoles({ includeAll: false });

  // Fallback roles if API fails
  const roleOptions = apiRoleOptions.length > 0 ? apiRoleOptions : [
    { value: 'Admin', label: t('admin2.umdl_role_admin') },
    { value: 'Doctor', label: t('admin2.umdl_role_doctor_general') },
    { value: 'cardio', label: t('admin2.umdl_role_cardio') },
    { value: 'derma', label: t('admin2.umdl_role_derma') },
    { value: 'dentist', label: t('admin2.umdl_role_dentist') },
    { value: 'Nurse', label: t('admin2.umdl_role_nurse') },
    { value: 'Receptionist', label: t('admin2.umdl_role_receptionist') },
    { value: 'Cashier', label: t('admin2.umdl_role_cashier') },
    { value: 'Lab', label: t('admin2.umdl_role_lab') },
    { value: 'Patient', label: t('admin2.umdl_role_patient') }
  ];

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
          confirmPassword: ''
        });
      } else {
        setFormData({
          username: '',
          email: '',
          full_name: '',
          role: 'Patient',
          is_active: true,
          password: '',
          confirmPassword: ''
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

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
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

      await onSave(userData);
      onClose();
    } catch (error) {
      logger.error('Ошибка сохранения пользователя:', error);
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

  // Error message component
  const ErrorMessage = ({ message }) => (
    <div className="admin-field-error-xs">
      <AlertCircle className="admin-icon-12" />
      {message}
    </div>
  );


  ErrorMessage.propTypes = {
    ...(ErrorMessage.propTypes || {}),
    message: PropTypes.any,
  };

  // Form field wrapper with icon
  const FormField = ({ label, required, icon: Icon, error, children }) => (
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


  const FormFieldAny = FormField as unknown as React.ComponentType<Record<string, unknown>>;

FormField.propTypes = {
    ...(FormField.propTypes || {}),
    children: PropTypes.any,
    error: PropTypes.any,
    icon: PropTypes.any,
    label: PropTypes.any,
    required: PropTypes.any,
  };

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
        <FormFieldAny
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
        </FormFieldAny>

        {/* Full Name */}
        <FormFieldAny label={t('admin2.umdl_field_full_name')}>
          <Input
            type="text"
            value={formData.full_name}
            onChange={(e) => handleChange('full_name', e.target.value)}
            placeholder={t('admin2.umdl_ph_full_name')}
          />
        </FormFieldAny>

        {/* Email */}
        <FormFieldAny
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
        </FormFieldAny>

        {/* Role */}
        <FormFieldAny label={t('admin2.umdl_field_role')} icon={Shield}>
          <Select
            value={formData.role}
            onChange={(value) => handleChange('role', value)}
            options={roleOptions}
            size="large"
            className="admin-input-pl-40"
          />
        </FormFieldAny>

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
        <FormFieldAny
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
        </FormFieldAny>

        {/* Confirm Password */}
        {formData.password && (
          <FormFieldAny
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
          </FormFieldAny>
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


UserModal.propTypes = {
  ...(UserModal.propTypes || {}),
  isOpen: PropTypes.any,
  loading: PropTypes.any,
  onClose: PropTypes.any,
  onSave: PropTypes.any,
  user: PropTypes.any,
};

export default UserModal;
