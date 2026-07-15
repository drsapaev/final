import { t } from '../../i18n/adapter';
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
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    full_name: '',
    role: 'Patient',
    is_active: true,
    password: '',
    confirmPassword: ''
  });
  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Load roles from API (Phase 4: DB-driven roles - completed)
  const { roleOptions: apiRoleOptions } = useRoles({ includeAll: false });

  // Fallback roles if API fails
  const roleOptions = apiRoleOptions.length > 0 ? apiRoleOptions : [
    { value: 'Admin', label: 'Администратор' },
    { value: 'Doctor', label: 'Врач (общий)' },
    { value: 'cardio', label: 'Кардиолог' },
    { value: 'derma', label: 'Дерматолог' },
    { value: 'dentist', label: 'Стоматолог' },
    { value: 'Nurse', label: 'Медсестра' },
    { value: 'Receptionist', label: 'Регистратор' },
    { value: 'Cashier', label: 'Кассир' },
    { value: 'Lab', label: 'Лаборант' },
    { value: 'Patient', label: 'Пациент' }
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
    const newErrors = {};

    if (!formData.username.trim()) {
      newErrors.username = 'Имя пользователя обязательно';
    } else if (formData.username.length < 3) {
      newErrors.username = 'Имя пользователя должно содержать минимум 3 символа';
    }

    if (!formData.email.trim()) {
      newErrors.email = 'Email обязателен';
    } else if (!/\S+@\S+\.\S+/.test(formData.email)) {
      newErrors.email = 'Некорректный email';
    }

    if (!user && !formData.password) {
      newErrors.password = 'Пароль обязателен';
    }

    if (formData.password && formData.password.length < 8) {
      newErrors.password = 'Пароль должен содержать минимум 8 символов';
    }

    if (formData.password !== formData.confirmPassword) {
      newErrors.confirmPassword = 'Пароли не совпадают';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!validateForm()) return;

    setIsSubmitting(true);
    try {
      const userData = {
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
      title={user ? 'Редактировать пользователя' : 'Добавить пользователя'}
      size="md"
      closable
    >
      <form onSubmit={handleSubmit}>
        {/* Username */}
        <FormField
          label="Имя пользователя"
          required
          icon={User}
          error={errors.username}
        >
          <Input
            type="text"
            value={formData.username}
            onChange={(e) => handleChange('username', e.target.value)}
            placeholder="Введите имя пользователя"
            error={!!errors.username}
            className="admin-input-pl-40"
          />
        </FormField>

        {/* Full Name */}
        <FormField label="Полное имя">
          <Input
            type="text"
            value={formData.full_name}
            onChange={(e) => handleChange('full_name', e.target.value)}
            placeholder="Введите полное имя"
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
            placeholder="Введите email"
            error={!!errors.email}
            className="admin-input-pl-40"
          />
        </FormField>

        {/* Role */}
        <FormField label="Роль" icon={Shield}>
          <Select
            value={formData.role}
            onChange={(value) => handleChange('role', value)}
            options={roleOptions}
            size="large"
            className="admin-input-pl-40"
          />
        </FormField>

        {/* Status */}
        <div className="admin-mb-16">
          <label className="admin-usermodal-label-mb-8">
            Статус
          </label>
          <Checkbox
            checked={formData.is_active}
            onChange={(checked) => handleChange('is_active', checked)}
            label="Активный пользователь"
          />
        </div>

        {/* Password */}
        <FormField
          label={user ? 'Новый пароль (оставьте пустым, чтобы не изменять)' : 'Пароль'}
          required={!user}
          icon={Lock}
          error={errors.password}
        >
          <Input
            type="password"
            value={formData.password}
            onChange={(e) => handleChange('password', e.target.value)}
            placeholder="Введите пароль"
            error={!!errors.password}
            className="admin-input-pl-40"
          />
        </FormField>

        {/* Confirm Password */}
        {formData.password && (
          <FormField
            label="Подтверждение пароля"
            required
            icon={Lock}
            error={errors.confirmPassword}
          >
            <Input
              type="password"
              value={formData.confirmPassword}
              onChange={(e) => handleChange('confirmPassword', e.target.value)}
              placeholder="Подтвердите пароль"
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
            Отмена
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
                Сохранение...
              </>
            ) : (
              <>
                <Save className="admin-icon-14-mr-6" />
                {user ? 'Сохранить изменения' : 'Создать пользователя'}
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
