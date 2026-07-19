
import { useState, useEffect, useCallback } from 'react';
import { Card, CardHeader, CardTitle, CardContent, Button, Input, Label } from '../ui/macos';
import {
  Phone,
  Shield,
  Clock,
  CheckCircle,
  AlertTriangle,
  RefreshCw,
  Send
} from 'lucide-react';
import { api } from '../../api/client';
import { toast } from 'react-toastify';

import logger from '../../utils/logger';
import PropTypes from 'prop-types';
import { useSafeInput } from '../../hooks/useSafeInput';  // PR-39 / P0-5: sanitizer wired to form
import { useTranslation } from '../../i18n/useTranslation';
const PhoneVerification = ({
  phone,
  purpose = 'verification',
  onVerified,
  onCancel,
  customMessage,
  showPhoneInput = false,
  title  // PR-44 / P0-19: default now comes from useTranslation
}: any) => {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  // PR-44 / P0-19: title defaults to translated string instead of hardcoded RU
  const displayTitle = title || t('verificationTitle');
  const [currentPhone, setCurrentPhone] = useState(phone || '');
  // PR-39 / P0-5: verification code now sanitized via useSafeInput.
  // Previously: raw useState('') with no input sanitization — a malicious
  // user could paste script tags or control characters into the code field.
  // Now: useSafeInput strips HTML tags, control chars, and enforces max length.
  const [verificationCode, setVerificationCode] = useSafeInput('', {
    maxLength: 10,
    type: 'text',
    allowNewlines: false,
    allowSpecialChars: false,
  });
  const [loading, setLoading] = useState(false);
  const [codeSent, setCodeSent] = useState(false);
  const [timeLeft, setTimeLeft] = useState(0);
  const [attemptsLeft, setAttemptsLeft] = useState(3);
  const [verificationStatus, setVerificationStatus] = useState(null);

  useEffect(() => {
    let timer;
    if (timeLeft > 0) {
      timer = setTimeout(() => setTimeLeft(timeLeft - 1), 1000);
    }
    return () => clearTimeout(timer);
  }, [timeLeft]);

  const formatPhone = (value) => {
    // Удаляем все символы кроме цифр
    const digits = value.replace(/\D/g, '');
    
    // Добавляем +998 если номер начинается с 9
    if (digits.startsWith('9') && digits.length <= 9) {
      return `+998${digits}`;
    }
    
    // Если уже есть +998, оставляем как есть
    if (digits.startsWith('998')) {
      return `+${digits}`;
    }
    
    return value;
  };

  const validatePhone = (phone) => {
    const phoneRegex = /^\+998\d{9}$/;
    return phoneRegex.test(phone);
  };

  const checkVerificationStatus = useCallback(async () => {
    if (!currentPhone || !validatePhone(currentPhone)) return;

    try {
      const response = await api.get('/phone-verification/status', {
        params: { phone: currentPhone, purpose }
      });

      setVerificationStatus(response.data);
      
      if (response.data.exists && !response.data.verified) {
        setCodeSent(true);
        setTimeLeft(response.data.time_left_minutes * 60);
        setAttemptsLeft(response.data.max_attempts - response.data.attempts);
      }
    } catch (error) {
      logger.error('Error checking verification status:', error);
    }
  }, [currentPhone, purpose]);

  useEffect(() => {
    if (phone && !showPhoneInput) {
      checkVerificationStatus();
    }
  }, [phone, showPhoneInput, checkVerificationStatus]);

  const sendVerificationCode = async () => {
    if (!currentPhone || !validatePhone(currentPhone)) {
      toast.error(t('misc.pv_vvedite_korrektnyy_nomer_tel'));
      return;
    }

    setLoading(true);
    try {
      const payload: Record<string, unknown> = {
        phone: currentPhone,
        purpose: purpose
      };

      if (customMessage) {
        payload.custom_message = customMessage;
      }

      const response = await api.post('/phone-verification/send-code', payload);

      if (response.data.success) {
        setCodeSent(true);
        setTimeLeft(response.data.expires_in_minutes * 60);
        setAttemptsLeft(3);
        toast.success(t('misc.pv_kod_verifikatsii_otpravlen_n'));
      }
    } catch (error) {
      logger.error('Error sending verification code:', error);
      
      if (error.response?.status === 429) {
        toast.error(t('misc.pv_slishkom_chastye_zaprosy_pop'));
      } else if (error.response?.status === 502) {
        toast.error(t('misc.pv_oshibka_otpravki_sms_provert'));
      } else {
        toast.error(t('misc.pv_oshibka_otpravki_koda_verifi'));
      }
    } finally {
      setLoading(false);
    }
  };

  const verifyCode = async () => {
    if (!verificationCode || verificationCode.length !== 6) {
      toast.error(t('misc.pv_vvedite_6_znachnyy_kod'));
      return;
    }

    setLoading(true);
    try {
      const response = await api.post('/phone-verification/verify-code', {
        phone: currentPhone,
        code: verificationCode,
        purpose: purpose
      });

      if (response.data.success) {
        toast.success(t('misc.pv_nomer_telefona_uspeshno_podt'));
        if (onVerified) {
          onVerified({
            phone: currentPhone,
            verified_at: response.data.verified_at
          });
        }
      }
    } catch (error) {
      logger.error('Error verifying code:', error);
      
      const errorData = error.response?.data?.detail;
      
      if (error.response?.status === 404) {
        toast.error(t('misc.pv_kod_ne_nayden_ili_istek'));
        setCodeSent(false);
      } else if (error.response?.status === 410) {
        toast.error(t('misc.pv_kod_istek_zaprosite_novyy_ko'));
        setCodeSent(false);
      } else if (error.response?.status === 429) {
        toast.error(t('misc.pv_prevysheno_kolichestvo_popyt'));
        setCodeSent(false);
      } else if (errorData?.attempts_left !== undefined) {
        setAttemptsLeft(errorData.attempts_left);
        toast.error(t('misc.pv_nevernyy_kod_ostalos_popytok', { attempts_left: errorData.attempts_left }));
      } else {
        toast.error(t('misc.pv_oshibka_proverki_koda'));
      }
    } finally {
      setLoading(false);
    }
  };

  const cancelVerification = async () => {
    try {
      await api.delete('/phone-verification/cancel', {
        params: { phone: currentPhone, purpose }
      });
      
      setCodeSent(false);
      setVerificationCode('');
      setTimeLeft(0);
      setVerificationStatus(null);
      
      if (onCancel) {
        onCancel();
      }
    } catch (error) {
      logger.error('Error cancelling verification:', error);
    }
  };

  const formatTime = (seconds) => {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
  };

  const handlePhoneChange = (e) => {
    const formatted = formatPhone(e.target.value);
    setCurrentPhone(formatted);
  };

  const handleCodeChange = (e) => {
    const value = e.target.value.replace(/\D/g, '').slice(0, 6);
    setVerificationCode(value);
  };

  return (
    <Card className="w-full max-w-md mx-auto">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Shield className="h-5 w-5 text-blue-500" />
          {displayTitle}  {/* PR-44 / P0-19: i18n-aware title */}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Ввод номера телефона */}
        {(showPhoneInput || !phone) && (
          <div className="space-y-2">
            <Label htmlFor="phone">{t('misc.pv_nomer_telefona')}</Label>
            <div className="relative">
              <Phone className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input
                id="phone"
                type="tel"
                value={currentPhone}
                onChange={handlePhoneChange}
                placeholder="+998XXXXXXXXX"
                className="pl-10"
                disabled={codeSent}
              />
            </div>
            {currentPhone && !validatePhone(currentPhone) && (
              <p className="text-sm text-red-500">
                Номер должен быть в формате +998XXXXXXXXX
              </p>
            )}
          </div>
        )}

        {/* Статус верификации */}
        {verificationStatus && verificationStatus.verified && (
          <div className="flex items-center gap-2 p-3 bg-green-50 border border-green-200 rounded-lg">
            <CheckCircle className="h-4 w-4 text-green-500" />
            <span className="text-sm text-green-700">
              Номер телефона уже подтвержден
            </span>
          </div>
        )}

        {/* Отправка кода */}
        {!codeSent && (!verificationStatus || !verificationStatus.verified) && (
          <Button
            onClick={sendVerificationCode}
            disabled={loading || !currentPhone || !validatePhone(currentPhone)}
            type="button"
            title={loading ? t('misc.pv_otpravlyaetsya_kod_podtverzh') : t('misc.pv_otpravit_kod_podtverzhdeniya')}
            aria-label={loading ? t('misc.pv_otpravlyaetsya_kod_podtverzh') : t('misc.pv_otpravit_kod_podtverzhdeniya')}
            className="w-full"
          >
            {loading ? (
              <>
                <RefreshCw aria-hidden="true" className="h-4 w-4 mr-2 animate-spin" />
                Отправка...
              </>
            ) : (
              <>
                <Send aria-hidden="true" className="h-4 w-4 mr-2" />
                Отправить код
              </>
            )}
          </Button>
        )}

        {/* Ввод кода верификации */}
        {codeSent && (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="code">{t('misc.pv_kod_verifikatsii')}</Label>
              <Input
                id="code"
                type="text"
                value={verificationCode}
                onChange={handleCodeChange}
                placeholder="000000"
                maxLength={6}
                className="text-center text-lg tracking-widest"
              />
              <p className="text-sm text-gray-600">
                Код отправлен на номер {currentPhone}
              </p>
            </div>

            {/* Таймер и попытки */}
            <div className="flex items-center justify-between text-sm text-gray-600">
              <div className="flex items-center gap-1">
                <Clock className="h-4 w-4" />
                <span>
                  {timeLeft > 0 ? t('misc.pv_kod_deystvitelen_formattime_', { timeLeft: formatTime(timeLeft) }) : t('misc.pv_kod_istek')}
                </span>
              </div>
              <div className="flex items-center gap-1">
                <AlertTriangle className="h-4 w-4" />
                <span>Попыток: {attemptsLeft}</span>
              </div>
            </div>

            {/* Кнопки */}
            <div className="flex gap-2">
              <Button
                onClick={verifyCode}
                disabled={loading || !verificationCode || verificationCode.length !== 6 || timeLeft === 0}
                className="flex-1"
              >
                {loading ? t('misc.pv_proverka') : t('misc.pv_podtverdit')}
              </Button>
              
              <Button
                onClick={timeLeft > 0 ? cancelVerification : sendVerificationCode}
                variant="outline"
                disabled={loading}
                className="flex-1"
              >
                {timeLeft > 0 ? t('misc.pv_otmenit') : t('misc.pv_povtorit')}
              </Button>
            </div>
          </div>
        )}

        {/* Информация о целях верификации */}
        <div className="text-xs text-gray-500 space-y-1">
          {purpose === 'verification' && (
            <p>• Подтверждение номера телефона для безопасности аккаунта</p>
          )}
          {purpose === 'password_reset' && (
            <p>• Сброс пароля через SMS код</p>
          )}
          {purpose === 'phone_change' && (
            <p>• Смена номера телефона в профиле</p>
          )}
          {purpose === 'registration' && (
            <p>• Подтверждение номера при регистрации</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
};


PhoneVerification.propTypes = {
  ...(PhoneVerification.propTypes || {}),
  customMessage: PropTypes.any,
  onCancel: PropTypes.any,
  onVerified: PropTypes.any,
  phone: PropTypes.any,
  purpose: PropTypes.any,
  showPhoneInput: PropTypes.any,
  title: PropTypes.any,
};

export default PhoneVerification;


