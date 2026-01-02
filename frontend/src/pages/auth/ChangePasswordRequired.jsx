import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api/client';
import { Lock, Eye, EyeOff, AlertCircle, CheckCircle } from 'lucide-react';
import { MacOSCard, MacOSButton, MacOSInput } from '../../components/ui/macos';
import { useTheme } from '../../contexts/ThemeContext';
import logger from '../../utils/logger';

/**
 * Компонент для обязательной смены пароля при первом входе
 * Показывается когда must_change_password = true
 */
export default function ChangePasswordRequired({ currentPassword }) {
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
            await api.post('/auth/password-change', {
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
            const errorMessage = err.response?.data?.detail || err.message || 'Ошибка смены пароля';
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
        padding: '20px',
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
        fontSize: '24px',
        fontWeight: '700',
        marginBottom: '8px',
        color: 'var(--mac-text-primary)',
        textAlign: 'center'
    };

    const subtitleStyle = {
        fontSize: '14px',
        color: 'var(--mac-text-secondary)',
        marginBottom: '24px',
        textAlign: 'center'
    };

    const inputContainerStyle = {
        position: 'relative',
        marginBottom: '16px'
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
        padding: '4px'
    };

    const requirementsStyle = {
        marginBottom: '20px',
        padding: '12px',
        borderRadius: '8px',
        background: theme === 'light' ? 'rgba(0,0,0,0.03)' : 'rgba(255,255,255,0.05)'
    };

    const requirementItemStyle = (passed) => ({
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        fontSize: '13px',
        color: passed ? getColor('success', 500) : 'var(--mac-text-tertiary)',
        marginBottom: '4px'
    });

    return (
        <div style={containerStyle}>
            <MacOSCard style={cardStyle}>
                <div style={{ textAlign: 'center', marginBottom: '20px' }}>
                    <Lock size={48} color={getColor('warning', 500)} style={{ marginBottom: '12px' }} />
                    <h1 style={titleStyle}>Смена пароля</h1>
                    <p style={subtitleStyle}>
                        Для безопасности вашего аккаунта необходимо сменить временный пароль
                    </p>
                </div>

                {error && (
                    <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        padding: '12px',
                        marginBottom: '16px',
                        borderRadius: '8px',
                        background: `${getColor('danger', 100)}`,
                        color: getColor('danger', 700),
                        fontSize: '14px'
                    }}>
                        <AlertCircle size={16} />
                        {error}
                    </div>
                )}

                {success && (
                    <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        padding: '12px',
                        marginBottom: '16px',
                        borderRadius: '8px',
                        background: `${getColor('success', 100)}`,
                        color: getColor('success', 700),
                        fontSize: '14px'
                    }}>
                        <CheckCircle size={16} />
                        {success}
                    </div>
                )}

                <form onSubmit={handleSubmit}>
                    {/* Current Password */}
                    <div style={inputContainerStyle}>
                        <MacOSInput
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
                            onClick={() => setShowCurrentPassword(!showCurrentPassword)}
                        >
                            {showCurrentPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                        </button>
                    </div>

                    {/* New Password */}
                    <div style={inputContainerStyle}>
                        <MacOSInput
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
                            onClick={() => setShowNewPassword(!showNewPassword)}
                        >
                            {showNewPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                        </button>
                    </div>

                    {/* Password Requirements */}
                    <div style={requirementsStyle}>
                        <div style={{ fontSize: '12px', fontWeight: '600', marginBottom: '8px', color: 'var(--mac-text-secondary)' }}>
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
                        <MacOSInput
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
                            gap: '8px',
                            fontSize: '13px',
                            color: doPasswordsMatch ? getColor('success', 500) : getColor('danger', 500),
                            marginBottom: '16px'
                        }}>
                            {doPasswordsMatch ? <CheckCircle size={14} /> : <AlertCircle size={14} />}
                            {doPasswordsMatch ? 'Пароли совпадают' : 'Пароли не совпадают'}
                        </div>
                    )}

                    <MacOSButton
                        type="submit"
                        variant="primary"
                        disabled={loading || !isPasswordValid || !doPasswordsMatch}
                        style={{ width: '100%', marginTop: '8px' }}
                    >
                        {loading ? 'Сохранение...' : 'Сменить пароль'}
                    </MacOSButton>
                </form>
            </MacOSCard>
        </div>
    );
}
