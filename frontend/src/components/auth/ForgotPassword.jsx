import React, { useState } from 'react';
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  Button,
  Input,
  Label
} from '../ui/native';
import {
  Mail,
  Phone,
  ArrowLeft,
  Send,
  CheckCircle,
  AlertTriangle,
  RefreshCw,
  Shield,
  Key
} from 'lucide-react';
import { api } from '../../utils/api';
import { toast } from 'react-toastify';

const ForgotPassword = ({ onBack, onSuccess, language = 'RU' }) => {
  const [step, setStep] = useState('method'); // method, phone-verify, email-verify, reset-password
  const [method, setMethod] = useState('phone'); // phone, email
  const [contact, setContact] = useState('');
  const [resetToken, setResetToken] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const translations = {
    RU: {
      title: 'Восстановление пароля',
      subtitle: 'Выберите способ восстановления пароля',
      methodPhone: 'По номеру телефона',
      methodEmail: 'По электронной почте',
      phoneLabel: 'Номер телефона',
      emailLabel: 'Email адрес',
      continue: 'Продолжить',
      back: 'Назад',
      sending: 'Отправка...',
      newPassword: 'Новый пароль',
      confirmPassword: 'Подтвердите пароль',
      resetPassword: 'Сбросить пароль',
      resetting: 'Сброс...',
      success: 'Пароль успешно изменен!',
      backToLogin: 'Вернуться к входу',
      enterPhone: 'Введите номер телефона',
      enterEmail: 'Введите email адрес',
      phoneFormat: 'Формат: +998XXXXXXXXX',
      emailFormat: 'Формат: example@domain.com',
      passwordMismatch: 'Пароли не совпадают',
      passwordTooShort: 'Пароль должен содержать минимум 6 символов',
      invalidPhone: 'Неверный формат номера телефона',
      invalidEmail: 'Неверный формат email адреса'
    },
    UZ: {
      title: 'Parolni tiklash',
      subtitle: 'Parolni tiklash usulini tanlang',
      methodPhone: 'Telefon raqami orqali',
      methodEmail: 'Email orqali',
      phoneLabel: 'Telefon raqami',
      emailLabel: 'Email manzil',
      continue: 'Davom etish',
      back: 'Orqaga',
      sending: 'Yuborilmoqda...',
      newPassword: 'Yangi parol',
      confirmPassword: 'Parolni tasdiqlang',
      resetPassword: 'Parolni tiklash',
      resetting: 'Tiklanmoqda...',
      success: 'Parol muvaffaqiyatli o\'zgartirildi!',
      backToLogin: 'Kirishga qaytish',
      enterPhone: 'Telefon raqamini kiriting',
      enterEmail: 'Email manzilni kiriting',
      phoneFormat: 'Format: +998XXXXXXXXX',
      emailFormat: 'Format: example@domain.com',
      passwordMismatch: 'Parollar mos kelmaydi',
      passwordTooShort: 'Parol kamida 6 ta belgidan iborat bo\'lishi kerak',
      invalidPhone: 'Telefon raqami formati noto\'g\'ri',
      invalidEmail: 'Email manzil formati noto\'g\'ri'
    },
    EN: {
      title: 'Password Recovery',
      subtitle: 'Choose password recovery method',
      methodPhone: 'By phone number',
      methodEmail: 'By email address',
      phoneLabel: 'Phone number',
      emailLabel: 'Email address',
      continue: 'Continue',
      back: 'Back',
      sending: 'Sending...',
      newPassword: 'New password',
      confirmPassword: 'Confirm password',
      resetPassword: 'Reset Password',
      resetting: 'Resetting...',
      success: 'Password successfully changed!',
      backToLogin: 'Back to Login',
      enterPhone: 'Enter phone number',
      enterEmail: 'Enter email address',
      phoneFormat: 'Format: +998XXXXXXXXX',
      emailFormat: 'Format: example@domain.com',
      passwordMismatch: 'Passwords do not match',
      passwordTooShort: 'Password must be at least 6 characters',
      invalidPhone: 'Invalid phone number format',
      invalidEmail: 'Invalid email address format'
    }
  };

  const t = translations[language];

  const validatePhone = (phone) => {
    const phoneRegex = /^\+998\d{9}$/;
    return phoneRegex.test(phone);
  };

  const validateEmail = (email) => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  };

  const formatPhone = (value) => {
    const digits = value.replace(/\D/g, '');
    if (digits.startsWith('9') && digits.length <= 9) {
      return `+998${digits}`;
    }
    if (digits.startsWith('998')) {
      return `+${digits}`;
    }
    return value;
  };

  const handleMethodSelect = async () => {
    if (!contact.trim()) {
      toast.error(method === 'phone' ? t.enterPhone : t.enterEmail);
      return;
    }

    if (method === 'phone' && !validatePhone(contact)) {
      toast.error(t.invalidPhone);
      return;
    }

    if (method === 'email' && !validateEmail(contact)) {
      toast.error(t.invalidEmail);
      return;
    }

    if (method === 'phone') {
      await sendPhoneReset();
    } else {
      await sendEmailReset();
    }
  };

  const sendPhoneReset = async () => {
    setLoading(true);
    try {
      const response = await api.post('/password-reset/initiate', {
        phone: contact
      });

      if (response.data.success) {
        toast.success('Код для сброса пароля отправлен на ваш номер');
        setStep('phone-verify');
      }
    } catch (error) {
      console.error('Error sending phone reset:', error);
      toast.error('Ошибка отправки SMS для сброса пароля');
    } finally {
      setLoading(false);
    }
  };

  const sendEmailReset = async () => {
    setLoading(true);
    try {
      const response = await api.post('/password-reset/initiate', {
        email: contact
      });

      if (response.data.success) {
        toast.success('Ссылка для сброса пароля отправлена на email');
        setStep('email-verify');
      }
    } catch (error) {
      console.error('Error sending email reset:', error);
      toast.error('Ошибка отправки email для сброса пароля');
    } finally {
      setLoading(false);
    }
  };

  const [verificationCode, setVerificationCode] = useState('');

  const handleVerifyPhoneCode = async () => {
    if (!verificationCode || verificationCode.length !== 6) {
      toast.error('Введите 6-значный код');
      return;
    }

    setLoading(true);
    try {
      const response = await api.post('/password-reset/verify-phone', {
        phone: contact,
        verification_code: verificationCode
      });

      if (response.data.success) {
        setResetToken(response.data.reset_token);
        setStep('reset-password');
        toast.success('Телефон подтвержден. Теперь введите новый пароль');
      }
    } catch (error) {
      console.error('Error verifying phone code:', error);
      toast.error('Неверный код или код истек');
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordReset = async () => {
    if (!newPassword || newPassword.length < 6) {
      toast.error(t.passwordTooShort);
      return;
    }

    if (newPassword !== confirmPassword) {
      toast.error(t.passwordMismatch);
      return;
    }

    setLoading(true);
    try {
      const response = await api.post('/password-reset/confirm', {
        token: resetToken,
        new_password: newPassword
      });

      if (response.data.success) {
        setStep('success');
        toast.success(t.success);
        
        // Автоматически вернуться к логину через 3 секунды
        setTimeout(() => {
          if (onSuccess) {
            onSuccess();
          }
        }, 3000);
      }
    } catch (error) {
      console.error('Error resetting password:', error);
      toast.error('Ошибка сброса пароля');
    } finally {
      setLoading(false);
    }
  };

  const renderMethodSelection = () => (
    <div className="space-y-6">
      <div className="text-center">
        <h2 className="text-xl font-semibold mb-2">{t.title}</h2>
        <p className="text-gray-600">{t.subtitle}</p>
      </div>

      <div className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <button
            onClick={() => setMethod('phone')}
            className={`p-4 border-2 rounded-lg transition-all ${
              method === 'phone'
                ? 'border-blue-500 bg-blue-50 text-blue-700'
                : 'border-gray-200 hover:border-gray-300'
            }`}
          >
            <Phone className="h-6 w-6 mx-auto mb-2" />
            <div className="font-medium">{t.methodPhone}</div>
          </button>

          <button
            onClick={() => setMethod('email')}
            className={`p-4 border-2 rounded-lg transition-all ${
              method === 'email'
                ? 'border-blue-500 bg-blue-50 text-blue-700'
                : 'border-gray-200 hover:border-gray-300'
            }`}
          >
            <Mail className="h-6 w-6 mx-auto mb-2" />
            <div className="font-medium">{t.methodEmail}</div>
          </button>
        </div>

        <div className="space-y-2">
          <Label htmlFor="contact">
            {method === 'phone' ? t.phoneLabel : t.emailLabel}
          </Label>
          <Input
            id="contact"
            type={method === 'phone' ? 'tel' : 'email'}
            value={contact}
            onChange={(e) => {
              const value = method === 'phone' ? formatPhone(e.target.value) : e.target.value;
              setContact(value);
            }}
            placeholder={method === 'phone' ? '+998XXXXXXXXX' : 'example@domain.com'}
            disabled={loading}
          />
          <p className="text-sm text-gray-500">
            {method === 'phone' ? t.phoneFormat : t.emailFormat}
          </p>
        </div>

        <div className="flex gap-3">
          <Button
            onClick={onBack}
            variant="outline"
            className="flex-1"
            disabled={loading}
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            {t.back}
          </Button>
          
          <Button
            onClick={handleMethodSelect}
            className="flex-1"
            disabled={loading || !contact.trim()}
          >
            {loading ? (
              <>
                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                {t.sending}
              </>
            ) : (
              <>
                <Send className="h-4 w-4 mr-2" />
                {t.continue}
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );

  const renderPhoneVerification = () => (
    <div className="space-y-6">
      <div className="text-center">
        <div className="flex justify-center mb-4">
          <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center">
            <Phone className="h-8 w-8 text-blue-500" />
          </div>
        </div>
        <h3 className="text-lg font-semibold mb-2">Введите код подтверждения</h3>
        <p className="text-gray-600">
          Код отправлен на номер:
        </p>
        <p className="font-medium text-blue-600 mt-1">{contact}</p>
      </div>

      <div className="space-y-4">
        <div>
          <Label htmlFor="verificationCode">Код подтверждения</Label>
          <Input
            id="verificationCode"
            type="text"
            value={verificationCode}
            onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
            placeholder="000000"
            maxLength={6}
            className="text-center text-lg tracking-widest"
            disabled={loading}
          />
        </div>

        <div className="flex gap-3">
          <Button
            onClick={() => setStep('method')}
            variant="outline"
            className="flex-1"
            disabled={loading}
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            {t.back}
          </Button>
          
          <Button
            onClick={handleVerifyPhoneCode}
            className="flex-1"
            disabled={loading || !verificationCode || verificationCode.length !== 6}
          >
            {loading ? (
              <>
                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                Проверка...
              </>
            ) : (
              <>
                <Shield className="h-4 w-4 mr-2" />
                Подтвердить
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );

  const renderEmailVerification = () => (
    <div className="space-y-6 text-center">
      <div className="flex justify-center">
        <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center">
          <Mail className="h-8 w-8 text-blue-500" />
        </div>
      </div>
      
      <div>
        <h3 className="text-lg font-semibold mb-2">Проверьте ваш email</h3>
        <p className="text-gray-600">
          Мы отправили ссылку для сброса пароля на адрес:
        </p>
        <p className="font-medium text-blue-600 mt-1">{contact}</p>
      </div>

      <div className="text-sm text-gray-500">
        <p>Перейдите по ссылке в письме для сброса пароля.</p>
        <p>Если письмо не пришло, проверьте папку "Спам".</p>
      </div>

      <Button
        onClick={() => setStep('method')}
        variant="outline"
        className="w-full"
      >
        <ArrowLeft className="h-4 w-4 mr-2" />
        {t.back}
      </Button>
    </div>
  );

  const renderPasswordReset = () => (
    <div className="space-y-6">
      <div className="text-center">
        <div className="flex justify-center mb-4">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center">
            <Key className="h-8 w-8 text-green-500" />
          </div>
        </div>
        <h3 className="text-lg font-semibold mb-2">Создайте новый пароль</h3>
        <p className="text-gray-600">Введите новый пароль для вашего аккаунта</p>
      </div>

      <div className="space-y-4">
        <div>
          <Label htmlFor="newPassword">{t.newPassword}</Label>
          <Input
            id="newPassword"
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder="••••••••"
            disabled={loading}
          />
        </div>

        <div>
          <Label htmlFor="confirmPassword">{t.confirmPassword}</Label>
          <Input
            id="confirmPassword"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            placeholder="••••••••"
            disabled={loading}
          />
        </div>

        <Button
          onClick={handlePasswordReset}
          className="w-full"
          disabled={loading || !newPassword || !confirmPassword}
        >
          {loading ? (
            <>
              <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
              {t.resetting}
            </>
          ) : (
            <>
              <Shield className="h-4 w-4 mr-2" />
              {t.resetPassword}
            </>
          )}
        </Button>
      </div>
    </div>
  );

  const renderSuccess = () => (
    <div className="space-y-6 text-center">
      <div className="flex justify-center">
        <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center">
          <CheckCircle className="h-8 w-8 text-green-500" />
        </div>
      </div>
      
      <div>
        <h3 className="text-lg font-semibold mb-2">{t.success}</h3>
        <p className="text-gray-600">
          Теперь вы можете войти в систему с новым паролем
        </p>
      </div>

      <Button
        onClick={onSuccess || onBack}
        className="w-full"
      >
        {t.backToLogin}
      </Button>
    </div>
  );

  return (
    <Card className="w-full max-w-md mx-auto">
      <CardContent className="p-6">
        {step === 'method' && renderMethodSelection()}
        {step === 'phone-verify' && renderPhoneVerification()}
        {step === 'email-verify' && renderEmailVerification()}
        {step === 'reset-password' && renderPasswordReset()}
        {step === 'success' && renderSuccess()}
      </CardContent>
    </Card>
  );
};

export default ForgotPassword;
