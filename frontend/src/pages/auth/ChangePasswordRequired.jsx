import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api/client';
import { Lock, Eye, EyeOff, AlertCircle, CheckCircle } from 'lucide-react';
import {
  MacOSCard, Button, Input,
} from '../../components/ui/macos';
import { useTheme } from '../../contexts/ThemeContext';
import { getErrorMessage } from '../../utils/errorHandler';
import logger from '../../utils/logger';
import PropTypes from 'prop-types';
import { useTranslation } from '../../i18n/adapter';

/**
 * Компонент для обязательной смены пароля при первом входе
 * Показывается когда must_change_password = true
 */
export default function ChangePasswordRequired({ currentPassword }) {
  const { t } = useTranslation();
    const navigate = useNavigate();
    const { theme, getColor } = useTheme();

    const [formData, setFormData] = useState({
        currentPassword: currentPassword || '',
        newPassword: '',
        confirmPassword: ''
    });

    const [showCurrentPassword, setShowCurrentPassword] = useState(false);
    const [showNewPassword, setShowNewPassword] = useState(false);
    const [showConfirmPassword, setShowConfirmPassword] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');

    // Проверка требований к паролю
    const passwordRequirements = [
        { label: 'Минимум 8 символов', test: (p) => p.length >= 8 },
        { label: 'Заглавная буква', test: (p) => /[A-Z]/.test(p) },
        { label: 'Строчная буква', test: (p) => /[a-z]/.test(p) },
        { label: 'Цифра', test: (p) => /[0-9]/.test(p) },
        { label: 'Специальный символ (!@#$%^&*)', test: (p) => /[!@#$%^&*(),.?":{}|<>]/.test(p) }
    ];

    const isPasswordValid = passwordRequirements.every(req => req.test(formData.newPassword));
    const doPasswordsMatch = formData.newPassword === formData.confirmPassword && formData.newPassword !== '';

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setSuccess('');

        if (!isPasswordValid) {
            setError('Пароль не соответствует требованиям безопасности');
            return;
        }

        if (!doPasswordsMatch) {
            setError('Пароли не совпадают');
            return;
        }

        if (formData.newPassword === formData.currentPassword) {
            setError('Новый пароль должен отличаться от текущего');
            return;
        }

        try {
            setLoading(true);
            await api.post('/authentication/password-change', {
                current_password: formData.currentPassword,
                new_password: formData.newPassword
            });

            setSuccess('Пароль успешно изменен! Перенаправление...');

            // Перенаправляем на страницу входа через 2 секунды
            setTimeout(() => {
                navigate('/login', {
                    state: { message: 'Пароль успешно изменен. Пожалуйста, войдите с новым паролем.' }
                });
            }, 2000);

        } catch (err) {
            const errorMessage = getErrorMessage(
                err,
                'Не удалось сменить пароль. Проверьте соединение и попробуйте снова.'
            );
            setError(errorMessage);
            logger.error('Ошибка смены пароля:', err);
        } finally {
            setLoading(false);
        }
    };

    const containerStyle = {
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 'var(--mac-spacing-5)',
        background: theme === 'light'
            ? 'linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)'
            : 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)'
    };

    const cardStyle = {
        width: '100%',
        maxWidth: '450px',
        padding: '32px'
    };

    const titleStyle = {
        fontSize: 'var(--mac-font-size-3xl)',
        fontWeight: 'var(--mac-font-weight-bold)',
        marginBottom: 'var(--mac-spacing-2)',
        color: 'var(--mac-text-primary)',
        textAlign: 'center'
    };

    const subtitleStyle = {
        fontSize: 'var(--mac-font-size-base)',
        color: 'var(--mac-text-secondary)',
        marginBottom: 'var(--mac-spacing-6)',
        textAlign: 'center'
    };

    const inputContainerStyle = {
        position: 'relative',
        marginBottom: 'var(--mac-spacing-4)'
    };

    const toggleButtonStyle = {
        position: 'absolute',
        right: '12px',
        top: '50%',
        transform: 'translateY(-50%)',
        background: 'none',
        border: 'none',
        cursor: 'pointer',
        color: 'var(--mac-text-secondary)',
        padding: 'var(--mac-spacing-1)'
    };

    const requirementsStyle = {
        marginBottom: 'var(--mac-spacing-5)',
        padding: 'var(--mac-spacing-3)',
        borderRadius: 'var(--mac-radius-md)',
        background: theme === 'light' ? 'rgba(0,0,0,0.03)' : 'rgba(255,255,255,0.05)'
    };

    const requirementItemStyle = (passed) => ({
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--mac-spacing-2)',
        fontSize: 'var(--mac-font-size-sm)',
        color: passed ? getColor('success', 500) : 'var(--mac-text-tertiary)',
        marginBottom: 'var(--mac-spacing-1)'
    });

    return (
        <div style={containerStyle}>
            <MacOSCard style={cardStyle}>
                <div style={{ textAlign: 'center', marginBottom: 'var(--mac-spacing-5)' }}>
                    <Lock size={48} color={getColor('warning', 500)} style={{ marginBottom: 'var(--mac-spacing-3)' }} />
                    <h1 style={titleStyle}>Смена пароля</h1>
                    <p style={subtitleStyle}>
                        Для безопасности вашего аккаунта необходимо сменить временный пароль
                    </p>
                </div>

                {error && (
                    <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 'var(--mac-spacing-2)',
                        padding: 'var(--mac-spacing-3)',
                        marginBottom: 'var(--mac-spacing-4)',
                        borderRadius: 'var(--mac-radius-md)',
                        background: `${getColor('danger', 100)}`,
                        color: getColor('danger', 700),
                        fontSize: 'var(--mac-font-size-base)'
                    }}>
                        <AlertCircle size={16} />
                        {error}
                    </div>
                )}

                {success && (
                    <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 'var(--mac-spacing-2)',
                        padding: 'var(--mac-spacing-3)',
                        marginBottom: 'var(--mac-spacing-4)',
                        borderRadius: 'var(--mac-radius-md)',
                        background: `${getColor('success', 100)}`,
                        color: getColor('success', 700),
                        fontSize: 'var(--mac-font-size-base)'
                    }}>
                        <CheckCircle size={16} />
                        {success}
                    </div>
                )}

                <form onSubmit={handleSubmit}>
                    {/* Current Password */}
                    <div style={inputContainerStyle}>
                        <Input
                            type={showCurrentPassword ? 'text' : 'password'}
                            placeholder="Текущий пароль"
                            value={formData.currentPassword}
                            onChange={(e) => setFormData({ ...formData, currentPassword: e.target.value })}
                            required
                            style={{ paddingRight: '40px' }}
                        />
                        <button
                            type="button"
                            style={toggleButtonStyle}
                            aria-label={showCurrentPassword ? 'Скрыть текущий пароль' : 'Показать текущий пароль'}
                            onClick={() => setShowCurrentPassword(!showCurrentPassword)}
                        >
                            {showCurrentPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                        </button>
                    </div>

                    {/* New Password */}
                    <div style={inputContainerStyle}>
                        <Input
                            type={showNewPassword ? 'text' : 'password'}
                            placeholder="Новый пароль"
                            value={formData.newPassword}
                            onChange={(e) => setFormData({ ...formData, newPassword: e.target.value })}
                            required
                            style={{ paddingRight: '40px' }}
                        />
                        <button
                            type="button"
                            style={toggleButtonStyle}
                            aria-label={showNewPassword ? 'Скрыть новый пароль' : 'Показать новый пароль'}
                            onClick={() => setShowNewPassword(!showNewPassword)}
                        >
                            {showNewPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                        </button>
                    </div>

                    {/* Password Requirements */}
                    <div style={requirementsStyle}>
                        <div style={{ fontSize: 'var(--mac-font-size-xs)', fontWeight: 'var(--mac-font-weight-semibold)', marginBottom: 'var(--mac-spacing-2)', color: 'var(--mac-text-secondary)' }}>
                            Требования к паролю:
                        </div>
                        {passwordRequirements.map((req, index) => (
                            <div key={index} style={requirementItemStyle(req.test(formData.newPassword))}>
                                {req.test(formData.newPassword) ? <CheckCircle size={14} /> : <AlertCircle size={14} />}
                                {req.label}
                            </div>
                        ))}
                    </div>

                    {/* Confirm Password */}
                    <div style={inputContainerStyle}>
                        <Input
                            type={showConfirmPassword ? 'text' : 'password'}
                            placeholder="Подтвердите новый пароль"
                            value={formData.confirmPassword}
                            onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })}
                            required
                            style={{ paddingRight: '40px' }}
                        />
                        <button
                            type="button"
                            style={toggleButtonStyle}
                            aria-label={showConfirmPassword ? 'Скрыть подтверждение пароля' : 'Показать подтверждение пароля'}
                            onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                        >
                            {showConfirmPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                        </button>
                    </div>

                    {/* Match indicator */}
                    {formData.confirmPassword && (
                        <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 'var(--mac-spacing-2)',
                            fontSize: 'var(--mac-font-size-sm)',
                            color: doPasswordsMatch ? getColor('success', 500) : getColor('danger', 500),
                            marginBottom: 'var(--mac-spacing-4)'
                        }}>
                            {doPasswordsMatch ? <CheckCircle size={14} /> : <AlertCircle size={14} />}
                            {doPasswordsMatch ? 'Пароли совпадают' : 'Пароли не совпадают'}
                        </div>
                    )}

                    <Button
                        type="submit"
                        variant="primary"
                        disabled={loading || !isPasswordValid || !doPasswordsMatch}
                        style={{ width: '100%', marginTop: 'var(--mac-spacing-2)' }}
                    >
                        {loading ? 'Сохранение...' : 'Сменить пароль'}
                    </Button>
                </form>
            </MacOSCard>
        </div>
    );
}


ChangePasswordRequired.propTypes = {
  ...(ChangePasswordRequired.propTypes || {}),
  currentPassword: PropTypes.any,
};
