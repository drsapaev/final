import React, { useState, useEffect } from 'react';
import { User, Mail, Lock, Shield, Save, AlertCircle } from 'lucide-react';
import MacOSModal from '../ui/macos/MacOSModal';
import MacOSInput from '../ui/macos/MacOSInput';
import MacOSSelect from '../ui/macos/MacOSSelect';
import MacOSButton from '../ui/macos/MacOSButton';
import MacOSCheckbox from '../ui/macos/MacOSCheckbox';
import { useRoles } from '../../hooks/useRoles';

import logger from '../../utils/logger';

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
    { value: 'Doctor', label: 'Врач' },
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
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '4px',
      marginTop: '4px',
      fontSize: 'var(--mac-font-size-xs, 12px)',
      color: 'var(--mac-error, #FF3B30)'
    }}>
      <AlertCircle style={{ width: '12px', height: '12px' }} />
      {message}
    </div>
  );

  // Form field wrapper with icon
  const FormField = ({ label, required, icon: Icon, error, children }) => (
    <div style={{ marginBottom: '16px' }}>
      <label style={{
        display: 'block',
        marginBottom: '6px',
        fontSize: 'var(--mac-font-size-sm, 13px)',
        fontWeight: '500',
        color: 'var(--mac-text-primary, #1d1d1f)'
      }}>
        {label} {required && <span style={{ color: 'var(--mac-error, #FF3B30)' }}>*</span>}
      </label>
      <div style={{ position: 'relative' }}>
        {Icon && (
          <Icon style={{
            position: 'absolute',
            left: '12px',
            top: '50%',
            transform: 'translateY(-50%)',
            width: '16px',
            height: '16px',
            color: 'var(--mac-text-tertiary, #86868b)',
            zIndex: 1,
            pointerEvents: 'none'
          }} />
        )}
        {children}
      </div>
      {error && <ErrorMessage message={error} />}
    </div>
  );

  return (
    <MacOSModal
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
          <MacOSInput
            type="text"
            value={formData.username}
            onChange={(e) => handleChange('username', e.target.value)}
            placeholder="Введите имя пользователя"
            error={!!errors.username}
            style={{ paddingLeft: '40px' }}
          />
        </FormField>

        {/* Full Name */}
        <FormField label="Полное имя">
          <MacOSInput
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
          <MacOSInput
            type="email"
            value={formData.email}
            onChange={(e) => handleChange('email', e.target.value)}
            placeholder="Введите email"
            error={!!errors.email}
            style={{ paddingLeft: '40px' }}
          />
        </FormField>

        {/* Role */}
        <FormField label="Роль" icon={Shield}>
          <MacOSSelect
            value={formData.role}
            onChange={(e) => handleChange('role', e.target.value)}
            options={roleOptions}
            style={{ paddingLeft: '40px' }}
          />
        </FormField>

        {/* Status */}
        <div style={{ marginBottom: '16px' }}>
          <label style={{
            display: 'block',
            marginBottom: '8px',
            fontSize: 'var(--mac-font-size-sm, 13px)',
            fontWeight: '500',
            color: 'var(--mac-text-primary, #1d1d1f)'
          }}>
            Статус
          </label>
          <MacOSCheckbox
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
          <MacOSInput
            type="password"
            value={formData.password}
            onChange={(e) => handleChange('password', e.target.value)}
            placeholder="Введите пароль"
            error={!!errors.password}
            style={{ paddingLeft: '40px' }}
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
            <MacOSInput
              type="password"
              value={formData.confirmPassword}
              onChange={(e) => handleChange('confirmPassword', e.target.value)}
              placeholder="Подтвердите пароль"
              error={!!errors.confirmPassword}
              style={{ paddingLeft: '40px' }}
            />
          </FormField>
        )}

        {/* Action Buttons */}
        <div style={{
          display: 'flex',
          gap: '12px',
          justifyContent: 'flex-end',
          marginTop: '24px',
          paddingTop: '16px',
          borderTop: '1px solid var(--mac-border, rgba(0, 0, 0, 0.1))'
        }}>
          <MacOSButton
            type="button"
            variant="secondary"
            onClick={onClose}
            disabled={isSubmitting}
          >
            Отмена
          </MacOSButton>
          <MacOSButton
            type="submit"
            variant="primary"
            disabled={isSubmitting || loading}
          >
            {isSubmitting ? (
              <>
                <div style={{
                  width: '14px',
                  height: '14px',
                  border: '2px solid rgba(255,255,255,0.3)',
                  borderTopColor: 'white',
                  borderRadius: '50%',
                  animation: 'spin 0.8s linear infinite',
                  marginRight: '8px'
                }} />
                Сохранение...
              </>
            ) : (
              <>
                <Save style={{ width: '14px', height: '14px', marginRight: '6px' }} />
                {user ? 'Сохранить изменения' : 'Создать пользователя'}
              </>
            )}
          </MacOSButton>
        </div>
      </form>

      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </MacOSModal>
  );
};

export default UserModal;
