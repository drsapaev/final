import React, { useState, useEffect } from 'react';
import { X, Save, User, Mail, Lock, Shield, CheckCircle, AlertCircle } from 'lucide-react';
import { Card, Button } from '../ui/native';

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
      console.error('Ошибка сохранения пользователя:', error);
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

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <Card className="w-full max-w-md max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          {/* Заголовок */}
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
              {user ? 'Редактировать пользователя' : 'Добавить пользователя'}
            </h2>
            <button
              onClick={onClose}
              className="p-1 hover:bg-gray-100 rounded-lg transition-colors"
              style={{ color: 'var(--text-secondary)' }}
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Форма */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Имя пользователя */}
            <div>
              <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                Имя пользователя *
              </label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" 
                      style={{ color: 'var(--text-tertiary)' }} />
                <input
                  type="text"
                  value={formData.username}
                  onChange={(e) => handleChange('username', e.target.value)}
                  className={`w-full pl-10 pr-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                    errors.username ? 'border-red-500' : 'border-gray-300'
                  }`}
                  style={{ 
                    background: 'var(--bg-primary)', 
                    color: 'var(--text-primary)',
                    borderColor: errors.username ? 'var(--danger-color)' : 'var(--border-color)'
                  }}
                  placeholder="Введите имя пользователя"
                />
              </div>
              {errors.username && (
                <p className="text-sm text-red-500 mt-1 flex items-center">
                  <AlertCircle className="w-4 h-4 mr-1" />
                  {errors.username}
                </p>
              )}
            </div>

            {/* Полное имя */}
            <div>
              <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                Полное имя
              </label>
              <input
                type="text"
                value={formData.full_name}
                onChange={(e) => handleChange('full_name', e.target.value)}
                className="w-full px-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                style={{ 
                  background: 'var(--bg-primary)', 
                  color: 'var(--text-primary)',
                  borderColor: 'var(--border-color)'
                }}
                placeholder="Введите полное имя"
              />
            </div>

            {/* Email */}
            <div>
              <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                Email *
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" 
                      style={{ color: 'var(--text-tertiary)' }} />
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => handleChange('email', e.target.value)}
                  className={`w-full pl-10 pr-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                    errors.email ? 'border-red-500' : 'border-gray-300'
                  }`}
                  style={{ 
                    background: 'var(--bg-primary)', 
                    color: 'var(--text-primary)',
                    borderColor: errors.email ? 'var(--danger-color)' : 'var(--border-color)'
                  }}
                  placeholder="Введите email"
                />
              </div>
              {errors.email && (
                <p className="text-sm text-red-500 mt-1 flex items-center">
                  <AlertCircle className="w-4 h-4 mr-1" />
                  {errors.email}
                </p>
              )}
            </div>

            {/* Роль */}
            <div>
              <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                Роль
              </label>
              <div className="relative">
                <Shield className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" 
                        style={{ color: 'var(--text-tertiary)' }} />
                <select
                  value={formData.role}
                  onChange={(e) => handleChange('role', e.target.value)}
                  className="w-full pl-10 pr-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  style={{ 
                    background: 'var(--bg-primary)', 
                    color: 'var(--text-primary)',
                    borderColor: 'var(--border-color)'
                  }}
                >
                  <option value="Patient">Пациент</option>
                  <option value="Admin">Администратор</option>
                  <option value="Doctor">Врач</option>
                  <option value="Nurse">Медсестра</option>
                  <option value="Receptionist">Регистратор</option>
                </select>
              </div>
            </div>

            {/* Статус */}
            <div>
              <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                Статус
              </label>
              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  id="is_active"
                  checked={formData.is_active}
                  onChange={(e) => handleChange('is_active', e.target.checked)}
                  className="w-4 h-4 rounded border focus:ring-2 focus:ring-blue-500"
                />
                <label htmlFor="is_active" className="text-sm" style={{ color: 'var(--text-primary)' }}>
                  Активный пользователь
                </label>
              </div>
            </div>

            {/* Пароль */}
            <div>
              <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                {user ? 'Новый пароль (оставьте пустым, чтобы не изменять)' : 'Пароль *'}
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" 
                      style={{ color: 'var(--text-tertiary)' }} />
                <input
                  type="password"
                  value={formData.password}
                  onChange={(e) => handleChange('password', e.target.value)}
                  className={`w-full pl-10 pr-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                    errors.password ? 'border-red-500' : 'border-gray-300'
                  }`}
                  style={{ 
                    background: 'var(--bg-primary)', 
                    color: 'var(--text-primary)',
                    borderColor: errors.password ? 'var(--danger-color)' : 'var(--border-color)'
                  }}
                  placeholder="Введите пароль"
                />
              </div>
              {errors.password && (
                <p className="text-sm text-red-500 mt-1 flex items-center">
                  <AlertCircle className="w-4 h-4 mr-1" />
                  {errors.password}
                </p>
              )}
            </div>

            {/* Подтверждение пароля */}
            {formData.password && (
              <div>
                <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                  Подтверждение пароля *
                </label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" 
                        style={{ color: 'var(--text-tertiary)' }} />
                  <input
                    type="password"
                    value={formData.confirmPassword}
                    onChange={(e) => handleChange('confirmPassword', e.target.value)}
                    className={`w-full pl-10 pr-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                      errors.confirmPassword ? 'border-red-500' : 'border-gray-300'
                    }`}
                    style={{ 
                      background: 'var(--bg-primary)', 
                      color: 'var(--text-primary)',
                      borderColor: errors.confirmPassword ? 'var(--danger-color)' : 'var(--border-color)'
                    }}
                    placeholder="Подтвердите пароль"
                  />
                </div>
                {errors.confirmPassword && (
                  <p className="text-sm text-red-500 mt-1 flex items-center">
                    <AlertCircle className="w-4 h-4 mr-1" />
                    {errors.confirmPassword}
                  </p>
                )}
              </div>
            )}

            {/* Кнопки */}
            <div className="flex gap-3 pt-4">
              <Button
                type="submit"
                disabled={isSubmitting || loading}
                className="flex-1"
                style={{ 
                  background: 'var(--accent-color)',
                  color: 'white'
                }}
              >
                {isSubmitting ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin mr-2" />
                    Сохранение...
                  </>
                ) : (
                  <>
                    <Save className="w-4 h-4 mr-2" />
                    {user ? 'Сохранить изменения' : 'Создать пользователя'}
                  </>
                )}
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={onClose}
                disabled={isSubmitting}
              >
                Отмена
              </Button>
            </div>
          </form>
        </div>
      </Card>
    </div>
  );
};

export default UserModal;

